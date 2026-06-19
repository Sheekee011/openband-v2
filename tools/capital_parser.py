"""Parse conservative Community Capital summaries from audited statements.

The parser targets a small set of high-value public-record fields and refuses
to publish a summary when the operations statement cannot be reconciled.
"""

import argparse
import base64
import io
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

try:
    import pdfplumber
except ImportError:  # pragma: no cover
    pdfplumber = None


MONEY_RE = re.compile(r"\(?\$?\s*-?\d[\d,]*(?:\.\d+)?\)?")
YEAR_RE = re.compile(r"\b20\d{2}\b")
OPERATIONS_RE = re.compile(r"statement of operations", re.I)
POSITION_RE = re.compile(r"statement of financial position", re.I)
NET_ASSET_RE = re.compile(
    r"statement of (?:changes? in )?net (?:financial assets|financial debt|debt)",
    re.I,
)
TOTAL_REVENUE_RE = re.compile(r"^(?:total\s+)?revenue$", re.I)
TOTAL_EXPENSE_RE = re.compile(
    r"^(?:total\s+)?(?:(?:program|operating)\s+)?"
    r"(?:expenses?|expenditures?)(?:\s+\(.*\))?$",
    re.I,
)
EXPENSE_SECTION_RE = re.compile(
    r"^(?:program\s+)?(?:expenses?|expenditures?)$",
    re.I,
)
SURPLUS_RE = re.compile(
    r"^(?:(?:annual|current|operating)\s+)?"
    r"(?:surplus|deficit)(?:\s+\(deficit\))?(?:\s+before.*)?$",
    re.I,
)
EXPENSE_SECTION_END_RE = re.compile(
    r"^(?:total\s+(?:(?:program|operating)\s+)?(?:expenses?|expenditures?)"
    r"|(?:(?:annual|current|operating)\s+)?(?:surplus|deficit))",
    re.I,
)
CAPITAL_PURCHASE_RE = re.compile(
    r"^(?:purchases?|acquisition|additions?)\s+(?:of\s+)?tangible\s+capital\s+assets?",
    re.I,
)
SKIP_LINE_RE = re.compile(
    r"^(schedules?|budget|actual|note|the accompanying|for the year|as at|page \d+)",
    re.I,
)


def now_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def clean_text(value):
    return " ".join(str(value or "").replace("\u00a0", " ").split()).strip()


def parse_money(value):
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = clean_text(value)
    if not text or text in {"-", "--", "N/A", "n/a"}:
        return None
    negative = text.startswith("(") and text.endswith(")")
    cleaned = re.sub(r"[^0-9.\-]", "", text)
    if cleaned in {"", "-", "."}:
        return None
    try:
        amount = float(cleaned)
    except ValueError:
        return None
    return -amount if negative and amount > 0 else amount


def rounded(value):
    if value is None:
        return None
    return int(value) if float(value).is_integer() else round(float(value), 2)


def line_parts(line):
    line = re.sub(r"\([^)]*[A-Za-z][^)]*\)", "", line)
    matches = list(MONEY_RE.finditer(line))
    if not matches:
        return clean_text(line), []
    while len(matches) > 1:
        raw = matches[0].group(0).strip()
        amount = parse_money(raw)
        later = [parse_money(match.group(0)) for match in matches[1:]]
        is_schedule_index = (
            amount is not None
            and 0 <= amount <= 99
            and "," not in raw
            and "." not in raw
            and "$" not in raw
            and "(" not in raw
            and any(value is not None and abs(value) >= 100 for value in later)
        )
        if not is_schedule_index:
            break
        matches.pop(0)
    label = clean_text(line[: matches[0].start()]).strip(" :-$")
    values = [parse_money(match.group(0)) for match in matches]
    return label, [value for value in values if value is not None]


def actual_value(values, page_text, line=""):
    if not values:
        return None
    header = "\n".join(page_text.splitlines()[:12]).lower()
    if "budget" in header:
        if len(values) >= 3:
            return values[1]
        if len(values) == 2 and re.search(
            r"\d[\d,]*(?:\.\d+)?\s+-\s+\(?-?\d", line
        ):
            if re.search(
                r"(?:^|\s)\d{1,2}\s+-\s+\(?-?\d[\d,]*(?:\.\d+)?"
                r"\s+\(?-?\d[\d,]*(?:\.\d+)?",
                line,
            ):
                return values[0]
            return 0
        if len(values) == 1 and re.search(
            r"\s-\s+-\s+\(?-?\d", line
        ):
            return 0
    elif len(values) == 1 and re.search(r"\s-\s+\(?-?\d", line):
        return 0
    return values[0]


def normalize_category(label):
    text = clean_text(label)
    text = re.sub(r"\s+\(note.*$", "", text, flags=re.I)
    text = re.sub(r"\s+\(schedule.*$", "", text, flags=re.I)
    text = re.sub(r"\s+\d+$", "", text)
    return text.strip(" :-")


def broad_revenue_category(label):
    low = label.lower()
    if re.search(r"indigenous services|government|cmhc|canada|province|tribal council|health.*authority|child.*family", low):
        return "Government transfers"
    if re.search(r"rent|lease|sales|fees?|royalt|investment|interest|business entit|farming|store|bingo|fundraising", low):
        return "Own-source revenue"
    if "trust" in low:
        return "Trust distributions"
    return "Other revenue"


def broad_expense_category(label):
    low = label.lower()
    if "land claims" in low:
        return "Operations"
    mappings = [
        (r"housing|\bcmhc\b", "Housing"),
        (r"education|school", "Education"),
        (r"health", "Health"),
        (r"infrastructure|public works|community development|capital", "Infrastructure / public works"),
        (r"economic|land management", "Economic development"),
        (r"social|child|family", "Social programs"),
        (
            r"government (?:support|services)|administration|band government|"
            r"registration(?: and)? membership|membership|lands and memberships",
            "Administration",
        ),
    ]
    for pattern, category in mappings:
        if re.search(pattern, low):
            return category
    return "Operations"


def statement_pages(page_texts, pattern):
    return [
        text
        for text in page_texts
        if pattern.search("\n".join(text.splitlines()[:8]))
    ]


def parse_section_rows(
    page_texts,
    start_pattern,
    end_pattern,
    category_fn,
    reject_pattern=None,
):
    rows = []
    active = False
    for page_text in page_texts:
        for raw_line in page_text.splitlines():
            line = clean_text(raw_line)
            if start_pattern.search(line):
                active = True
                continue
            if active and end_pattern.search(line):
                return rows
            if not active:
                continue
            label, values = line_parts(line)
            if not label or not values or SKIP_LINE_RE.search(label):
                continue
            if reject_pattern and reject_pattern.search(label):
                continue
            if TOTAL_REVENUE_RE.match(label) or TOTAL_EXPENSE_RE.match(label):
                continue
            if len(values) == 1 and re.search(r"\s-\s+-\s+\(", line):
                amount = 0
            else:
                amount = actual_value(values, page_text, line)
            if amount is None:
                continue
            rows.append(
                {
                    "category": category_fn(label),
                    "sourceLabel": normalize_category(label),
                    "amount": rounded(amount),
                }
            )
    return rows


def sum_rows(rows):
    return sum(parse_money(row.get("amount")) or 0 for row in rows)


def find_named_amount(page_texts, pattern):
    for page_text in page_texts:
        for raw_line in page_text.splitlines():
            label, values = line_parts(clean_text(raw_line))
            if pattern.search(label):
                value = actual_value(values, page_text, clean_text(raw_line))
                if value is not None:
                    return value
    return None


def aggregate_categories(rows):
    totals = {}
    source_rows = []
    for row in rows:
        category = row["category"]
        totals[category] = totals.get(category, 0) + (parse_money(row["amount"]) or 0)
        source_rows.append(
            {
                "label": row["sourceLabel"],
                "category": category,
                "amount": row["amount"],
            }
        )
    return (
        [
            {"category": category, "amount": rounded(amount)}
            for category, amount in sorted(totals.items(), key=lambda item: -item[1])
        ],
        source_rows,
    )


def extract_debt(position_pages):
    patterns = [
        re.compile(r"^bank indebtedness$", re.I),
        re.compile(r"^short[- ]term debt$", re.I),
        re.compile(r"^current portion of long[- ]term debt", re.I),
        re.compile(r"^current portion of term loans", re.I),
        re.compile(r"^current portion of capital lease obligations", re.I),
        re.compile(r"^long[- ]term debt", re.I),
        re.compile(r"^term loans due on demand", re.I),
        re.compile(r"^capital lease obligations", re.I),
    ]
    components = []
    for page_text in position_pages:
        for raw_line in page_text.splitlines():
            label, values = line_parts(clean_text(raw_line))
            if not values or not any(pattern.search(label) for pattern in patterns):
                continue
            value = actual_value(values, page_text, clean_text(raw_line))
            if value is not None:
                components.append({"label": normalize_category(label), "amount": rounded(value)})
    total = sum(parse_money(item["amount"]) or 0 for item in components)
    return {"total": rounded(total), "components": components} if components else None


def nearly_equal(left, right, tolerance=0.01):
    if left is None or right is None:
        return False
    return abs(left - right) <= max(10.0, abs(right) * tolerance)


def validate_summary(summary):
    warnings = []
    severe = []
    revenue = parse_money(summary.get("totalRevenue"))
    expenses = parse_money(summary.get("totalExpenses"))
    surplus = parse_money(summary.get("annualSurplusDeficit"))
    revenue_rows = summary.get("revenueBreakdown") or []
    expense_rows = summary.get("expenseBreakdown") or []

    if revenue is None or revenue <= 0:
        severe.append("Total revenue was not extracted")
    if expenses is None or expenses <= 0:
        severe.append("Total expenses were not extracted")
    if len(revenue_rows) < 2:
        severe.append("Revenue breakdown is incomplete")
    if len(expense_rows) < 2:
        severe.append("Expense breakdown is incomplete")
    if revenue_rows and revenue is not None and not nearly_equal(sum_rows(revenue_rows), revenue):
        severe.append("Revenue categories do not reconcile to total revenue")
    expense_sum = sum_rows(expense_rows)
    if expense_rows and expenses is not None and not nearly_equal(expense_sum, expenses):
        if expense_sum > expenses:
            severe.append("Expense categories exceed reported expenses")
        else:
            severe.append("Expense categories do not reconcile to total expenses")
    if revenue is not None and any(
        nearly_equal(parse_money(row.get("amount")), revenue, tolerance=0.001)
        for row in expense_rows
    ):
        severe.append("An expense category appears to contain total revenue")
    if surplus is None:
        warnings.append("Annual surplus or deficit was not extracted")
    elif revenue is not None and expenses is not None and not nearly_equal(
        surplus, revenue - expenses
    ):
        severe.append("Revenue, expenses, and annual surplus do not reconcile")
    if summary.get("capitalSpending") is None:
        warnings.append("Capital spending was not extracted")
    if summary.get("debt") is None:
        warnings.append("Debt summary was not extracted")

    if severe:
        confidence = "low"
        status = "manual_review"
    elif warnings:
        confidence = "medium"
        status = "parsed"
    else:
        confidence = "high"
        status = "parsed"
    return {
        "parseStatus": status,
        "confidence": confidence,
        "warnings": severe + warnings,
        "publishable": not severe,
    }


def parse_page_texts(page_texts, source_url=None, fiscal_year=None):
    operations = statement_pages(page_texts, OPERATIONS_RE)
    position = statement_pages(page_texts, POSITION_RE)
    net_assets = statement_pages(page_texts, NET_ASSET_RE)
    if not operations:
        return {
            "parseStatus": "manual_review",
            "confidence": "low",
            "warnings": ["No clear statement of operations found"],
        }

    revenue_rows = parse_section_rows(
        operations,
        re.compile(r"^revenue$", re.I),
        EXPENSE_SECTION_RE,
        broad_revenue_category,
    )
    expense_rows = parse_section_rows(
        operations,
        EXPENSE_SECTION_RE,
        EXPENSE_SECTION_END_RE,
        broad_expense_category,
        reject_pattern=re.compile(r"\brevenue\b", re.I),
    )
    revenue_breakdown, revenue_source_rows = aggregate_categories(revenue_rows)
    expense_breakdown, expense_source_rows = aggregate_categories(expense_rows)

    total_revenue = find_named_amount(operations, TOTAL_REVENUE_RE) or sum_rows(revenue_rows)
    total_expenses = find_named_amount(operations, TOTAL_EXPENSE_RE) or sum_rows(expense_rows)
    surplus = find_named_amount(operations, SURPLUS_RE)

    cash = find_named_amount(
        position,
        re.compile(r"^(?:cash|cash resources|cash and cash equivalents)$", re.I),
    )
    investments = find_named_amount(
        position,
        re.compile(r"^(?:marketable securities|investments)$", re.I),
    )
    capital_assets = find_named_amount(
        position,
        re.compile(r"^tangible capital assets", re.I),
    )
    capital_spending = find_named_amount(net_assets, CAPITAL_PURCHASE_RE)
    debt = extract_debt(position)

    summary = {
        "totalRevenue": rounded(total_revenue),
        "totalExpenses": rounded(total_expenses),
        "annualSurplusDeficit": rounded(surplus),
        "cashInvestments": rounded((cash or 0) + (investments or 0)) if cash is not None else None,
        "revenueBreakdown": revenue_breakdown,
        "expenseBreakdown": expense_breakdown,
        "capitalSpending": {
            "total": rounded(abs(capital_spending)),
            "categories": [],
        }
        if capital_spending is not None
        else None,
        "capitalAssets": rounded(capital_assets),
        "debt": debt,
        "sourceRevenueRows": revenue_source_rows,
        "sourceExpenseRows": expense_source_rows,
        "sourceUrl": source_url,
        "fiscalYear": fiscal_year,
        "parser": "capital_text_v1",
    }
    summary.update(validate_summary(summary))
    return summary


def parse_pdf_bytes(pdf_bytes, source_url=None, fiscal_year=None):
    if pdfplumber is None:
        return {
            "parseStatus": "error",
            "confidence": "low",
            "warnings": ["pdfplumber is unavailable"],
        }

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        page_texts = [
            page.extract_text(x_tolerance=1, y_tolerance=3) or ""
            for page in pdf.pages
        ]
    return parse_page_texts(page_texts, source_url, fiscal_year)


def response_output_text(payload):
    if payload.get("output_text"):
        return payload["output_text"]
    chunks = []
    for output in payload.get("output", []):
        for content in output.get("content", []):
            if content.get("text"):
                chunks.append(content["text"])
    return "\n".join(chunks)


def extract_with_openai(pdf_bytes, source_url, fiscal_year):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    prompt = (
        "Extract a conservative summary from this First Nation audited financial statement. "
        "Use the actual current-year column, not budget or prior-year values. Return JSON only "
        "with keys totalRevenue, totalExpenses, annualSurplusDeficit, cashInvestments, "
        "capitalAssets, capitalSpending, debt, revenueBreakdown, expenseBreakdown, warnings. "
        "Breakdown rows must have category, sourceLabel, and amount. Do not infer missing values."
    )
    payload = {
        "model": os.getenv("OPENAI_MODEL", "gpt-4.1"),
        "max_output_tokens": 4000,
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {
                        "type": "input_file",
                        "filename": "audited-statement.pdf",
                        "file_data": "data:application/pdf;base64,"
                        + base64.b64encode(pdf_bytes).decode("ascii"),
                    },
                ],
            }
        ],
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            result = json.loads(response.read().decode("utf-8"))
        text = response_output_text(result).strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.I)
        summary = json.loads(text)
        summary["sourceUrl"] = source_url
        summary["fiscalYear"] = fiscal_year
        summary["parser"] = "capital_openai_v1"
        summary.update(validate_summary(summary))
        return summary
    except Exception as exc:
        return {
            "parseStatus": "error_openai",
            "confidence": "low",
            "warnings": [f"OpenAI capital extraction failed: {type(exc).__name__}: {exc}"],
        }


def normalize_pdf_url(url):
    parts = urllib.parse.urlsplit(url)
    pairs = urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
    query = urllib.parse.urlencode(pairs, quote_via=urllib.parse.quote)
    return urllib.parse.urlunsplit(
        (parts.scheme, parts.netloc, parts.path, query, parts.fragment)
    )


def fetch_pdf(url):
    request = urllib.request.Request(
        normalize_pdf_url(url),
        headers={"User-Agent": "OpenBand/1.0 audited statement parser"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def is_audited_statement(filing):
    return bool(
        re.search(r"audited.*financial|financial.*statements", filing.get("docType", ""), re.I)
    )


def load_capital_data(path):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"schemaVersion": 1, "generated": None, "bands": {}}


def save_summary(capital_data, band, filing, summary):
    band_record = capital_data.setdefault("bands", {}).setdefault(
        str(band["id"]),
        {"name": band["name"], "years": {}},
    )
    band_record["name"] = band["name"]
    band_record.setdefault("years", {})[filing["year"]] = summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="data.json")
    parser.add_argument("--output", default="capital-data.json")
    parser.add_argument("--band", action="append", default=[])
    parser.add_argument("--year", action="append", default=[])
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--use-openai", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    data = json.loads(Path(args.data).read_text(encoding="utf-8"))
    output_path = Path(args.output)
    capital_data = load_capital_data(output_path)
    candidates = []
    for band in data.get("bands", []):
        if args.band and band.get("name") not in args.band:
            continue
        for filing in band.get("filings", []):
            if not filing.get("posted") or not filing.get("href") or not is_audited_statement(filing):
                continue
            if args.year and filing.get("year") not in args.year:
                continue
            existing = (
                capital_data.get("bands", {})
                .get(str(band.get("id")), {})
                .get("years", {})
                .get(filing.get("year"))
            )
            if existing and existing.get("parseStatus") == "parsed" and not args.force:
                continue
            candidates.append((band, filing))

    candidates.sort(
        key=lambda item: (str(item[1].get("year", "")), item[0].get("name", "")),
        reverse=True,
    )
    if args.limit:
        candidates = candidates[: args.limit]

    parsed = 0
    reviewed = 0
    for index, (band, filing) in enumerate(candidates, start=1):
        print(f"[{index}/{len(candidates)}] {band['name']} {filing['year']}")
        try:
            pdf_bytes = fetch_pdf(filing["href"])
            summary = parse_pdf_bytes(pdf_bytes, filing["href"], filing["year"])
            if not summary.get("publishable") and args.use_openai:
                ai_summary = extract_with_openai(pdf_bytes, filing["href"], filing["year"])
                if ai_summary and ai_summary.get("publishable"):
                    summary = ai_summary
            save_summary(capital_data, band, filing, summary)
            if summary.get("publishable"):
                parsed += 1
                print(
                    f"  parsed ({summary.get('confidence')}): "
                    f"revenue={summary.get('totalRevenue')} expenses={summary.get('totalExpenses')}"
                )
            else:
                reviewed += 1
                print("  manual review:", "; ".join(summary.get("warnings") or []))
        except Exception as exc:
            reviewed += 1
            save_summary(
                capital_data,
                band,
                filing,
                {
                    "fiscalYear": filing["year"],
                    "sourceUrl": filing["href"],
                    "parseStatus": "error",
                    "confidence": "low",
                    "warnings": [f"Capital parse failed: {type(exc).__name__}: {exc}"],
                    "publishable": False,
                },
            )
            print(f"  error: {exc}")

    capital_data["generated"] = now_iso()
    capital_data["schemaVersion"] = 1
    output_path.write_text(
        json.dumps(capital_data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"capital filings parsed: {parsed}")
    print(f"capital filings needing review: {reviewed}")
    print(f"saved: {output_path}")


if __name__ == "__main__":
    main()
