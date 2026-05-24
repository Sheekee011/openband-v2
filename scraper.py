"""OpenBand FNFTA scraper.

Fetches Saskatchewan First Nation filing listings from Indigenous Services Canada,
parses Schedule of Remuneration and Expenses PDFs, and writes data.json.
"""

import base64
import io
import json
import os
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime
from html.parser import HTMLParser

try:
    import pdfplumber
except ImportError:  # GitHub Actions installs it from requirements.txt
    pdfplumber = None

ISC_HOST = "https://fnp-ppn.aadnc-aandc.gc.ca"
ISC_BASE = f"{ISC_HOST}/fnp/Main/Search"
USER_AGENT = "OpenBand/2.0 (public transparency research)"

BANDS = [
    {"id": 406, "name": "Ahtahkakoop Cree Nation", "province": "SK", "treaty": "Treaty 6"},
    {"id": 369, "name": "Beardy's and Okemasis' Cree Nation", "province": "SK", "treaty": "Treaty 6"},
    {"id": 404, "name": "Big River First Nation", "province": "SK", "treaty": "Treaty 6"},
    {"id": 403, "name": "Birch Narrows Dene Nation", "province": "SK", "treaty": "Treaty 10"},
    {"id": 351, "name": "Black Lake Denesuline First Nation", "province": "SK", "treaty": "Treaty 8"},
    {"id": 398, "name": "Buffalo River Dene Nation", "province": "SK", "treaty": "Treaty 10"},
    {"id": 394, "name": "Canoe Lake Cree First Nation", "province": "SK", "treaty": "Treaty 10"},
    {"id": 378, "name": "Carry the Kettle Nakoda Nation", "province": "SK", "treaty": "Treaty 4"},
    {"id": 401, "name": "Clearwater River Dene Nation", "province": "SK", "treaty": "Treaty 10"},
    {"id": 361, "name": "Cowessess First Nation", "province": "SK", "treaty": "Treaty 4"},
    {"id": 407, "name": "Cree Nation of Chitek Lake", "province": "SK", "treaty": "Treaty 6"},
    {"id": 350, "name": "Cumberland House Cree Nation", "province": "SK", "treaty": "Treaty 5"},
    {"id": 389, "name": "Day Star First Nation", "province": "SK", "treaty": "Treaty 4"},
    {"id": 400, "name": "English River First Nation", "province": "SK", "treaty": "Treaty 10"},
    {"id": 390, "name": "Fishing Lake First Nation", "province": "SK", "treaty": "Treaty 4"},
    {"id": 395, "name": "Flying Dust First Nation", "province": "SK", "treaty": "Treaty 6"},
    {"id": 351, "name": "Fond du Lac Denesuline First Nation", "province": "SK", "treaty": "Treaty 8"},
    {"id": 391, "name": "George Gordon First Nation", "province": "SK", "treaty": "Treaty 4"},
    {"id": 352, "name": "Hatchet Lake Denesuline Nation", "province": "SK", "treaty": "Treaty 10"},
    {"id": 370, "name": "James Smith Cree Nation", "province": "SK", "treaty": "Treaty 6"},
    {"id": 362, "name": "Kahkewistahaw First Nation", "province": "SK", "treaty": "Treaty 4"},
    {"id": 393, "name": "Kawacatoose First Nation", "province": "SK", "treaty": "Treaty 4"},
    {"id": 367, "name": "Keeseekoose First Nation", "province": "SK", "treaty": "Treaty 4"},
    {"id": 368, "name": "Key First Nation", "province": "SK", "treaty": "Treaty 4"},
    {"id": 377, "name": "Kinistin Saulteaux Nation", "province": "SK", "treaty": "Treaty 4"},
    {"id": 353, "name": "Lac La Ronge Indian Band", "province": "SK", "treaty": "Treaty 6"},
    {"id": 379, "name": "Little Black Bear First Nation", "province": "SK", "treaty": "Treaty 4"},
    {"id": 340, "name": "Little Pine First Nation", "province": "SK", "treaty": "Treaty 6"},
    {"id": 341, "name": "Lucky Man Cree Nation", "province": "SK", "treaty": "Treaty 6"},
    {"id": 396, "name": "Makwa Sahgaiehcan First Nation", "province": "SK", "treaty": "Treaty 6"},
    {"id": 374, "name": "Mistawasis Nehiyawak", "province": "SK", "treaty": "Treaty 6"},
    {"id": 354, "name": "Montreal Lake Cree Nation", "province": "SK", "treaty": "Treaty 6"},
    {"id": 343, "name": "Mosquito, Grizzly Bear's Head, Lean Man First Nation", "province": "SK", "treaty": "Treaty 6"},
    {"id": 381, "name": "Muscowpetung Saulteaux Nation", "province": "SK", "treaty": "Treaty 4"},
    {"id": 375, "name": "Muskeg Lake Cree Nation", "province": "SK", "treaty": "Treaty 6"},
    {"id": 371, "name": "Muskoday First Nation", "province": "SK", "treaty": "Treaty 6"},
    {"id": 392, "name": "Muskowekwan First Nation", "province": "SK", "treaty": "Treaty 4"},
    {"id": 380, "name": "Nekaneet First Nation", "province": "SK", "treaty": "Treaty 4"},
    {"id": 408, "name": "Ocean Man First Nation", "province": "SK", "treaty": "Treaty 4"},
    {"id": 363, "name": "Ochapowace Nation", "province": "SK", "treaty": "Treaty 4"},
    {"id": 382, "name": "Okanese First Nation", "province": "SK", "treaty": "Treaty 4"},
    {"id": 373, "name": "One Arrow First Nation", "province": "SK", "treaty": "Treaty 6"},
    {"id": 344, "name": "Onion Lake Cree Nation", "province": "SK", "treaty": "Treaty 6"},
    {"id": 383, "name": "Pasqua First Nation", "province": "SK", "treaty": "Treaty 4"},
    {"id": 384, "name": "Peepeekisis Cree Nation", "province": "SK", "treaty": "Treaty 4"},
    {"id": 405, "name": "Pelican Lake First Nation", "province": "SK", "treaty": "Treaty 6"},
    {"id": 355, "name": "Peter Ballantyne Cree Nation", "province": "SK", "treaty": "Treaty 6"},
    {"id": 409, "name": "Pheasant Rump Nakota Nation", "province": "SK", "treaty": "Treaty 4"},
    {"id": 385, "name": "Piapot First Nation", "province": "SK", "treaty": "Treaty 4"},
    {"id": 345, "name": "Poundmaker Cree Nation", "province": "SK", "treaty": "Treaty 6"},
    {"id": 356, "name": "Red Earth Cree Nation", "province": "SK", "treaty": "Treaty 6"},
    {"id": 346, "name": "Red Pheasant Cree Nation", "province": "SK", "treaty": "Treaty 6"},
    {"id": 364, "name": "Sakimay First Nation", "province": "SK", "treaty": "Treaty 4"},
    {"id": 347, "name": "Saulteaux First Nation", "province": "SK", "treaty": "Treaty 6"},
    {"id": 357, "name": "Shoal Lake Cree Nation", "province": "SK", "treaty": "Treaty 6"},
    {"id": 386, "name": "Standing Buffalo Dakota Nation", "province": "SK", "treaty": "Treaty 4"},
    {"id": 387, "name": "Star Blanket Cree Nation", "province": "SK", "treaty": "Treaty 4"},
    {"id": 360, "name": "Sturgeon Lake First Nation", "province": "SK", "treaty": "Treaty 6"},
    {"id": 348, "name": "Sweetgrass First Nation", "province": "SK", "treaty": "Treaty 6"},
    {"id": 368, "name": "The Key First Nation", "province": "SK", "treaty": "Treaty 4"},
    {"id": 349, "name": "Thunderchild First Nation", "province": "SK", "treaty": "Treaty 6"},
    {"id": 358, "name": "Wahpeton Dakota Nation", "province": "SK", "treaty": "Treaty 4"},
]


def now():
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


class FilingParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_table = False
        self.in_td = False
        self.row = []
        self.cell = ""
        self.href = None
        self.rows = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "table":
            self.in_table = True
        elif self.in_table and tag == "tr":
            self.row = []
        elif self.in_table and tag == "td":
            self.in_td = True
            self.cell = ""
            self.href = None
        elif self.in_td and tag == "a":
            self.href = attrs.get("href")

    def handle_endtag(self, tag):
        if tag == "td" and self.in_td:
            self.row.append({"text": " ".join(self.cell.split()), "href": self.href})
            self.in_td = False
        elif tag == "tr" and self.in_table and len(self.row) >= 3:
            self.rows.append(self.row)
        elif tag == "table":
            self.in_table = False

    def handle_data(self, data):
        if self.in_td:
            self.cell += data


def fetch(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def absolute_href(href):
    if not href:
        return None
    if href.startswith("http"):
        return href
    if href.startswith("/"):
        return ISC_HOST + href
    return ISC_BASE + "/" + href


def normalize_pdf_url(url):
    parts = urllib.parse.urlsplit(url)
    query = urllib.parse.urlencode(
        urllib.parse.parse_qsl(parts.query, keep_blank_values=True),
        quote_via=urllib.parse.quote,
    )
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path, query, parts.fragment))


def fetch_filings(band_id):
    url = f"{ISC_BASE}/FederalFundingMain.aspx?BAND_NUMBER={band_id}&lang=eng"
    html = fetch(url, timeout=20).decode("utf-8", errors="replace")
    parser = FilingParser()
    parser.feed(html)
    filings = []
    for row in parser.rows:
        year = row[0]["text"]
        doc_type = row[1]["text"]
        date = row[2]["text"]
        if not re.match(r"\d{4}-\d{4}", year):
            continue
        posted = date not in {"", "Not yet posted", "-", "—", "N/A"}
        filings.append({
            "year": year,
            "docType": doc_type,
            "date": date,
            "href": absolute_href(row[1]["href"]) if posted else None,
            "posted": posted,
        })
    return filings


def parse_money(value):
    if value is None:
        return None
    text = str(value).strip()
    if not text or text in {"-", "—", "N/A"}:
        return None
    negative = text.startswith("(") and text.endswith(")")
    cleaned = re.sub(r"[^0-9.\-]", "", text)
    if not cleaned or cleaned in {"-", "."}:
        return None
    try:
        amount = float(cleaned)
        return -amount if negative and amount > 0 else amount
    except ValueError:
        return None


def clean_name(value):
    value = re.sub(r"\*+$", "", str(value or "").strip())
    return " ".join(value.split())


def header_key(value):
    text = " ".join(str(value or "").lower().split())
    if text.startswith("name"):
        return "name"
    if "position" in text or text == "chief and council":
        return "role"
    if "month" in text:
        return "months"
    if "remuneration" in text or "salary" in text or "honoraria" in text:
        return "remuneration"
    if "travel" in text or "per diem" in text:
        return "travel"
    if "credit" in text and "card" in text:
        return "creditCard"
    if "other" in text and "payment" in text:
        return "otherPayments"
    if "expense" in text:
        return "expenses"
    if text == "total":
        return "total"
    return None


def role_from(values):
    text = " ".join(values).lower()
    if re.search(r"\bchief\b", text):
        return "Chief"
    if re.search(r"\bcouncillor\b|\bcouncil\b", text):
        return "Councillor"
    return "Council"


def total_for(person):
    if person.get("total") is not None:
        return person["total"]
    fields = ["remuneration", "travel", "expenses", "creditCard", "otherPayments"]
    values = [person.get(field) or 0 for field in fields]
    return sum(values) if any(values) else None


def extract_table_people(table):
    people = []
    keys = []
    for row in table or []:
        cells = [" ".join(str(cell or "").split()) for cell in row]
        if not " ".join(cells).strip():
            continue
        possible_keys = [header_key(cell) for cell in cells]
        if "remuneration" in possible_keys and ("months" in possible_keys or "travel" in possible_keys or "expenses" in possible_keys or "total" in possible_keys):
            keys = possible_keys
            continue
        if re.match(r"^total\b", cells[0], re.I):
            continue
        amounts = [parse_money(cell) for cell in cells]
        if not any(amount is not None for amount in amounts):
            continue

        def value(key):
            if key in keys:
                index = keys.index(key)
                if index < len(cells):
                    return cells[index]
            return None

        name = clean_name(value("name"))
        role = value("role") or ""
        if not name and cells and re.search(r"chief|councillor|council", cells[0], re.I):
            role = role or cells[0]
            name = clean_name(cells[1] if len(cells) > 1 else "")
        if not name:
            for cell in cells:
                if parse_money(cell) is None and not re.search(r"chief|councillor|council|month|position", cell, re.I) and len(cell) > 1:
                    name = clean_name(cell)
                    break
        if not name:
            continue

        person = {
            "name": name,
            "role": role_from([role] + cells),
            "months": parse_money(value("months")),
            "remuneration": parse_money(value("remuneration")),
            "travel": parse_money(value("travel")),
            "expenses": parse_money(value("expenses")),
            "creditCard": parse_money(value("creditCard")),
            "otherPayments": parse_money(value("otherPayments")),
            "total": parse_money(value("total")),
        }
        if person["remuneration"] is None:
            person["remuneration"] = next((amount for amount in amounts if amount is not None), None)
        person["total"] = total_for(person)
        people.append(person)
    return people


def response_text(raw):
    if raw.get("output_text"):
        return raw["output_text"].strip()
    chunks = []
    for item in raw.get("output", []):
        for content in item.get("content", []):
            if content.get("text"):
                chunks.append(content["text"])
    return "\n".join(chunks).strip()


def parse_with_openai(pdf_bytes):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {"parse_status": "skipped_openai_no_key", "warnings": ["OPENAI_API_KEY not set"], "people": []}
    prompt = (
        "Extract the Chief and Council remuneration table from this PDF. Return only JSON like "
        "{\"people\":[{\"name\":str,\"role\":str,\"months\":number|null,\"remuneration\":number|null,"
        "\"travel\":number|null,\"expenses\":number|null,\"creditCard\":number|null,\"otherPayments\":number|null,\"total\":number|null}]}."
    )
    payload = {
        "model": os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        "input": [{"role": "user", "content": [
            {"type": "input_text", "text": prompt},
            {"type": "input_file", "filename": "filing.pdf", "file_data": "data:application/pdf;base64," + base64.b64encode(pdf_bytes).decode("ascii")},
        ]}],
    }
    req = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        parsed = json.loads(response_text(data))
        people = []
        for row in parsed.get("people", []):
            person = {
                "name": clean_name(row.get("name")),
                "role": str(row.get("role") or "Council"),
                "months": parse_money(row.get("months")),
                "remuneration": parse_money(row.get("remuneration")),
                "travel": parse_money(row.get("travel")),
                "expenses": parse_money(row.get("expenses")),
                "creditCard": parse_money(row.get("creditCard")),
                "otherPayments": parse_money(row.get("otherPayments")),
                "total": parse_money(row.get("total")),
            }
            person["total"] = total_for(person)
            if person["name"]:
                people.append(person)
        return {"parse_status": "ok_openai", "warnings": [], "people": people}
    except Exception as exc:
        return {"parse_status": "error_openai", "warnings": [f"OpenAI parse failed: {exc}"], "people": []}


def extract_people(pdf_url):
    if not pdf_url:
        return {"parse_status": "no_pdf_url", "warnings": ["No PDF URL"], "people": []}
    try:
        pdf_bytes = fetch(normalize_pdf_url(pdf_url), timeout=40)
    except Exception as exc:
        return {"parse_status": "error_pdf_download", "warnings": [f"PDF download failed: {exc}"], "people": []}
    warnings = []
    if pdfplumber is not None:
        try:
            people = []
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                for page in pdf.pages:
                    for table in page.extract_tables() or []:
                        people.extend(extract_table_people(table))
            if people:
                return {"parse_status": "ok_pdfplumber", "warnings": warnings, "people": people}
            warnings.append("No remuneration rows detected by pdfplumber")
        except Exception as exc:
            warnings.append(f"pdfplumber failed: {exc}")
    ai = parse_with_openai(pdf_bytes)
    ai["warnings"] = warnings + ai.get("warnings", [])
    return ai


def should_parse(filing, parse_years):
    if not filing.get("posted") or not filing.get("href"):
        return False
    if "remuneration" not in filing.get("docType", "").lower():
        return False
    return not parse_years or filing.get("year") in parse_years


def main():
    parse_years = {item.strip() for item in os.getenv("OPENBAND_PARSE_YEARS", "2024-2025,2023-2024,2022-2023").split(",") if item.strip()}
    max_attempts = int(os.getenv("OPENBAND_MAX_PDF_ATTEMPTS", "80"))
    delay = float(os.getenv("OPENBAND_REQUEST_DELAY", "1"))
    pdf_attempts = 0
    errors = 0
    results = []
    print(f"OpenBand scraper starting - {now()}")
    for index, band in enumerate(BANDS, start=1):
        print(f"[{index}/{len(BANDS)}] {band['name']} ({band['id']})")
        try:
            filings = fetch_filings(band["id"])
            status = "ok"
        except Exception as exc:
            print(f"  listing failed: {exc}")
            filings = []
            status = "listing_error"
            errors += 1
        enriched = []
        for filing in filings:
            item = dict(filing)
            item["people"] = []
            item["parse_status"] = "not_applicable"
            item["warnings"] = []
            if should_parse(item, parse_years):
                if pdf_attempts < max_attempts:
                    parsed = extract_people(item["href"])
                    item.update(parsed)
                    pdf_attempts += 1
                else:
                    item["parse_status"] = "skipped_attempt_limit"
                    item["warnings"] = ["OPENBAND_MAX_PDF_ATTEMPTS reached"]
            enriched.append(item)
        results.append({
            "id": band["id"],
            "name": band["name"],
            "province": band["province"],
            "treaty": band["treaty"],
            "filings": enriched,
            "status": status,
            "scraped": now(),
        })
        time.sleep(delay)
    output = {"generated": now(), "band_count": len(results), "error_count": errors, "bands": results}
    with open("data.json", "w", encoding="utf-8") as handle:
        json.dump(output, handle, ensure_ascii=False, indent=2)
    print(f"Done. {len(results)} bands scraped, {errors} listing errors, {pdf_attempts} PDFs attempted.")


if __name__ == "__main__":
    main()
