"""Compatibility launcher for the OpenBand scraper.

Keeps the nightly run bounded and adds a text-parser fallback for FNFTA PDFs.
Some ISC PDFs do not expose clean table grids to pdfplumber, but their visible
text still contains the Chief and Council rows. This launcher parses those rows
before falling back to OpenAI.
"""

import base64
import io
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request

_real_urlopen = urllib.request.urlopen


def _patched_urlopen(request, *args, **kwargs):
    return _real_urlopen(request, *args, **kwargs)


urllib.request.urlopen = _patched_urlopen

import scraper  # noqa: E402

scraper.urllib.request.urlopen = _patched_urlopen


def _json_from_model_text(text):
    text = (text or "").strip()
    if not text:
        return None
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I).strip()
        text = re.sub(r"\s*```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.S)
        if not match:
            return None
        return json.loads(match.group(0))


def _openai_file_part(pdf_bytes, pdf_url=None):
    if pdf_url:
        return {"type": "input_file", "file_url": scraper.normalize_pdf_url(pdf_url)}
    return {
        "type": "input_file",
        "filename": "filing.pdf",
        "file_data": "data:application/pdf;base64," + base64.b64encode(pdf_bytes).decode("ascii"),
    }


def _extract_with_openai_vision_fixed(pdf_bytes, pdf_url=None):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {
            "parse_status": "skipped_openai_no_key",
            "warnings": ["OPENAI_API_KEY not set"],
            "people": [],
        }

    prompt = (
        "Extract only the Chief and Council remuneration schedule from this PDF. "
        "Ignore audited financial statement project tables, notes, signatures, and totals-only rows. "
        "Return only JSON with this exact shape: "
        '{"people":[{"name":str,"role":str,"months":number|null,'
        '"remuneration":number|null,"travel":number|null,"expenses":number|null,'
        '"creditCard":number|null,"otherPayments":number|null,"total":number|null}]}. '
        'If no Chief and Council remuneration table is present, return {"people":[]}.'
    )
    payload = {
        "model": os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        "max_output_tokens": 1600,
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    _openai_file_part(pdf_bytes, pdf_url),
                ],
            }
        ],
    }

    req = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = json.loads(resp.read().decode("utf-8"))

        text = scraper.response_output_text(raw)
        data = _json_from_model_text(text)
        if not data:
            return {
                "parse_status": "error_openai_empty",
                "warnings": ["OpenAI returned no parseable JSON"],
                "people": [],
            }

        rows = data.get("people", []) if isinstance(data, dict) else []
        people = []
        for row in rows:
            people.append(
                {
                    "name": str(row.get("name", "")).strip(),
                    "role": str(row.get("role", "")).strip() or "Council",
                    "months": scraper.parse_money(row.get("months")),
                    "remuneration": scraper.parse_money(row.get("remuneration")),
                    "travel": scraper.parse_money(row.get("travel")),
                    "expenses": scraper.parse_money(row.get("expenses")),
                    "creditCard": scraper.parse_money(row.get("creditCard")),
                    "otherPayments": scraper.parse_money(row.get("otherPayments")),
                    "total": scraper.parse_money(row.get("total")),
                }
            )
        return {
            "parse_status": "ok_openai",
            "warnings": [],
            "people": [p for p in people if p["name"]],
        }
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:1200]
        return {
            "parse_status": "error_openai_http",
            "warnings": [f"OpenAI HTTP {exc.code}: {body}"],
            "people": [],
        }
    except Exception as exc:
        return {
            "parse_status": "error_openai_exception",
            "warnings": [f"OpenAI parse failed: {type(exc).__name__}: {exc}"],
            "people": [],
        }


scraper.extract_with_openai_vision = _extract_with_openai_vision_fixed

# Extra Saskatchewan First Nations flagged during OpenBand coverage review.
# IDs are ISC First Nation Profile band numbers used by the FNFTA filing pages.
_EXTRA_BANDS = [
    {"id": 404, "name": "Big River First Nation", "province": "SK", "treaty": "Treaty 6"},
    {"id": 403, "name": "Birch Narrows Dene Nation", "province": "SK", "treaty": "Treaty 10"},
    {"id": 359, "name": "Black Lake Denesuline First Nation", "province": "SK", "treaty": "Treaty 8"},
    {"id": 351, "name": "Fond du Lac Denesuline First Nation", "province": "SK", "treaty": "Treaty 8"},
    {"id": 370, "name": "James Smith Cree Nation", "province": "SK", "treaty": "Treaty 6"},
    {"id": 393, "name": "Kawacatoose First Nation", "province": "SK", "treaty": "Treaty 4"},
]
_existing_ids = {band.get("id") for band in scraper.BANDS}
scraper.BANDS.extend(band for band in _EXTRA_BANDS if band["id"] not in _existing_ids)


def _build_direct_pdf_urls_with_current_year(band_id):
    fiscal_years = [
        "2024-2025",
        "2023-2024",
        "2022-2023",
        "2021-2022",
        "2020-2021",
        "2019-2020",
        "2018-2019",
        "2017-2018",
        "2016-2017",
        "2015-2016",
        "2014-2015",
        "2013-2014",
    ]
    doc_types = [
        "Audited consolidated financial statements",
        "Schedule of Remuneration and Expenses",
    ]
    filings = []
    for fy in fiscal_years:
        for doc in doc_types:
            params = urllib.parse.urlencode(
                {"BAND_NUMBER_FF": band_id, "FY": fy, "DOC": doc, "lang": "eng"},
                quote_via=urllib.parse.quote,
            )
            filings.append({
                "year": fy,
                "docType": doc,
                "date": "See ISC",
                "href": f"{scraper.ISC_BASE}/DisplayBinaryData.aspx?{params}",
                "posted": True,
                "fallback": True,
            })
    return filings


scraper.build_direct_pdf_urls = _build_direct_pdf_urls_with_current_year

_ALLOWED_YEARS = {
    y.strip()
    for y in os.getenv("OPENBAND_PARSE_YEARS", "2024-2025,2023-2024,2022-2023").split(",")
    if y.strip()
}
_MAX_PDF_ATTEMPTS = int(os.getenv("OPENBAND_MAX_PDF_ATTEMPTS", "180") or "180")
_attempts = {"count": 0}
_original_should_parse_people = scraper.should_parse_people

_MONEY_RE = re.compile(r"\(?\$?\s*-?\d{1,3}(?:,\d{3})*(?:\.\d+)?\)?|\(?\$?\s*-?\d+(?:\.\d+)?\)?")
_SKIP_LINE_RE = re.compile(
    r"\b(total|signature|schedule|unaudited|audited|note|acknowledged|approved|remuneration|expenses|payments|months|position|name)\b",
    re.I,
)
_PROJECT_LINE_RE = re.compile(
    r"\b(project|program|contract|consulting|construction|maintenance|repair|renovation|insurance|administration|audit|legal|professional|revenue|income|asset|liability|payable|receivable)\b",
    re.I,
)
_NAME_RE = re.compile(r"^[A-Z][A-Za-z'’.-]+(?:\s+[A-Z][A-Za-z'’.-]+){1,5}\*?$")


def _parse_amount(value):
    return scraper.parse_money(value)


def _looks_like_person_name(value):
    text = scraper.clean_person_name(value)
    if not text or _PROJECT_LINE_RE.search(text):
        return False
    if re.search(r"\b(chief|councillor|councilor|total|travel|expense|payment|salary|wage)\b", text, re.I):
        return False
    return bool(_NAME_RE.match(text))


def _parse_text_line(line, allow_inferred_councillor=False):
    line = " ".join(str(line or "").replace("$", " $ ").split())
    if not line:
        return None

    has_role = re.search(r"\b(chief|councillor|councilor)\b", line, re.I)
    if _SKIP_LINE_RE.search(line) and not has_role:
        return None
    if _PROJECT_LINE_RE.search(line) and not has_role:
        return None
    if not has_role and not allow_inferred_councillor:
        return None

    matches = list(_MONEY_RE.finditer(line))
    values = []
    for match in matches:
        raw = match.group(0).replace("$", "").strip()
        amount = _parse_amount(raw)
        if amount is not None:
            values.append({"raw": raw, "amount": amount, "start": match.start(), "end": match.end()})
    if len(values) < 2:
        return None

    first_value = values[0]
    months = None
    money_values = values
    if first_value["amount"] <= 24 and "," not in first_value["raw"] and "." not in first_value["raw"]:
        months = first_value["amount"]
        money_values = values[1:]
    if len(money_values) < 2:
        return None

    name_part = line[: first_value["start"]].strip(" -:\t")
    role_match = re.search(r"\b(chief|councillor|councilor)\b", name_part, re.I)
    if role_match:
        role_word = role_match.group(1).lower()
        role = "Chief" if role_word == "chief" else "Councillor"
        if role_match.start() == 0:
            name = name_part[role_match.end() :].strip(" -:\t")
        else:
            name = name_part[: role_match.start()].strip(" -:\t")
    else:
        role = "Councillor"
        name = name_part

    name = scraper.clean_person_name(name)
    if not _looks_like_person_name(name):
        return None

    amounts = [item["amount"] for item in money_values]
    remuneration = amounts[0] if len(amounts) > 0 else None
    travel = amounts[1] if len(amounts) > 1 else None
    expenses = None
    credit_card = None
    other_payments = None
    total = None

    if len(amounts) >= 5:
        expenses = amounts[2]
        credit_card = amounts[3]
        total = amounts[4]
    elif len(amounts) == 4:
        expenses = amounts[2]
        total = amounts[3]
    elif len(amounts) == 3:
        other_payments = amounts[2]
        total = sum(value or 0 for value in [remuneration, travel, other_payments])
    elif len(amounts) == 2:
        total = sum(value or 0 for value in [remuneration, travel])

    if total is None:
        total = sum(value or 0 for value in [remuneration, travel, expenses, credit_card, other_payments])

    return {
        "name": name,
        "role": role,
        "months": months,
        "remuneration": remuneration,
        "travel": travel,
        "expenses": expenses,
        "creditCard": credit_card,
        "otherPayments": other_payments,
        "total": total,
    }


def _dedupe_people(people):
    seen = set()
    clean = []
    for person in people:
        key = (person.get("name", "").lower(), person.get("role", "").lower())
        if not person.get("name") or key in seen:
            continue
        seen.add(key)
        clean.append(person)
    return clean


def _extract_people_from_text(pdf_bytes):
    if scraper.pdfplumber is None:
        return []
    people = []
    with scraper.pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text(x_tolerance=1, y_tolerance=3) or ""
            page_is_schedule = bool(
                re.search(r"chief\s+and\s+council|chief\s+and\s+councillors|remuneration\s+and\s+expenses", text, re.I)
            )
            for line in text.splitlines():
                person = _parse_text_line(line, allow_inferred_councillor=page_is_schedule)
                if person:
                    people.append(person)
    return _dedupe_people(people)


def _extract_remuneration_rows_enhanced(pdf_url):
    if not pdf_url:
        return {"parse_status": "no_pdf_url", "warnings": ["No PDF URL available"], "people": []}

    warnings = []
    try:
        pdf_bytes = scraper.fetch_url(scraper.normalize_pdf_url(pdf_url), timeout=30)
    except Exception as exc:
        return {
            "parse_status": "error_pdf_download",
            "warnings": [f"PDF download failed: {exc}"],
            "people": [],
        }

    if scraper.pdfplumber is not None:
        try:
            people = []
            with scraper.pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                for page in pdf.pages:
                    for table in page.extract_tables() or []:
                        people.extend(scraper.extract_people_from_table(table))
            people = _dedupe_people(people)
            if people and not _looks_project_heavy(people):
                return {"parse_status": "ok_pdfplumber", "warnings": warnings, "people": people}
            if people:
                warnings.append("Discarded table extraction because rows looked project-heavy")
        except Exception as exc:
            warnings.append(f"PDF table extraction failed: {exc}")

        try:
            text_people = _extract_people_from_text(pdf_bytes)
            if text_people:
                return {
                    "parse_status": "ok_pdf_text",
                    "warnings": warnings + ["Parsed from PDF text fallback"],
                    "people": text_people,
                }
        except Exception as exc:
            warnings.append(f"PDF text extraction failed: {exc}")
    else:
        warnings.append("pdfplumber unavailable")

    ai_result = scraper.extract_with_openai_vision(pdf_bytes, pdf_url)
    if not ai_result.get("people") and ai_result.get("parse_status") == "error_openai_http":
        inline_result = scraper.extract_with_openai_vision(pdf_bytes)
        if inline_result.get("people"):
            inline_result["warnings"] = [
                "OpenAI file_url retry failed; parsed from inline PDF fallback"
            ] + inline_result.get("warnings", [])
            ai_result = inline_result
        else:
            inline_result["warnings"] = (
                ai_result.get("warnings", [])
                + ["OpenAI file_url retry failed; inline PDF retry also failed"]
                + inline_result.get("warnings", [])
            )
            ai_result = inline_result
    if ai_result.get("people"):
        ai_result["warnings"] = warnings + ["Parsed via OpenAI fallback"] + ai_result.get("warnings", [])
        return ai_result

    warnings.append("No remuneration rows detected from PDF table or text extraction")
    warnings.extend(ai_result.get("warnings", []))
    return {
        "parse_status": ai_result.get("parse_status", "no_rows"),
        "warnings": warnings,
        "people": [],
    }


def _looks_project_heavy(people):
    if not people:
        return False
    bad = sum(1 for person in people if _PROJECT_LINE_RE.search(person.get("name", "")))
    return bad >= max(1, len(people) // 2)


def _bounded_should_parse_people(filing):
    if filing.get("year") not in _ALLOWED_YEARS:
        return False
    return _original_should_parse_people(filing)


def _bounded_extract_remuneration_rows(pdf_url):
    if _attempts["count"] >= _MAX_PDF_ATTEMPTS:
        return {
            "parse_status": "skipped_run_limit",
            "warnings": [f"Skipped after {_MAX_PDF_ATTEMPTS} PDF parse attempts in this run"],
            "people": [],
        }
    _attempts["count"] += 1
    print(f"  parsing PDF {_attempts['count']}/{_MAX_PDF_ATTEMPTS}")
    return _extract_remuneration_rows_enhanced(pdf_url)


scraper.should_parse_people = _bounded_should_parse_people
scraper.extract_remuneration_rows = _bounded_extract_remuneration_rows

if __name__ == "__main__":
    print("OpenBand bounded run")
    print("  bands:", len(scraper.BANDS))
    print("  parse years:", ", ".join(sorted(_ALLOWED_YEARS)))
    print("  max PDF attempts:", _MAX_PDF_ATTEMPTS)
    scraper.main()