"""Clean parsed FNFTA remuneration rows before the website reads data.json.

The scraper has to handle many PDF layouts. Some layouts expose page headings,
dates, or project/accounting rows as text that can look like a person row. This
script is a conservative cleanup pass: it removes obvious non-person rows,
normalizes fields, deduplicates rows, recalculates broken totals, and converts
internal parser statuses into public-friendly data statuses.
"""

import json
import re
import sys
from pathlib import Path

PAYMENT_KEYS = ("remuneration", "travel", "expenses", "creditCard", "otherPayments")
ALL_MONEY_KEYS = PAYMENT_KEYS + ("total",)

PUBLIC_STATUS_MAP = {
    "": "pending_review",
    None: "pending_review",
    "error": "pending_review",
    "error_openai": "pending_ai_review",
    "error_openai_empty": "pending_ai_review",
    "error_pdf_download": "source_download_failed",
    "no_pdf_url": "source_unavailable",
    "no_rows": "pending_review",
    "not_applicable": "not_required",
    "sanitized_no_valid_rows": "pending_manual_review",
    "skipped_openai_no_key": "pending_ai_setup",
    "skipped_pdfplumber": "pending_review",
    "skipped_run_limit": "pending_retry",
}

TECHNICAL_STATUS_MAP = {
    "error": "parser_failed",
    "error_openai": "openai_extraction_failed",
    "error_openai_empty": "openai_empty_response",
    "error_pdf_download": "pdf_download_failed",
    "sanitized_no_valid_rows": "rows_removed_by_sanitizer",
    "skipped_openai_no_key": "openai_key_missing",
}

BAD_NAME_RE = re.compile(
    r"\b("
    r"year\s+ended|schedule|remuneration|expenses?|unaudited|audited|"
    r"signature|signatures?|total|subtotal|page|note|notes?|"
    r"chief\s+and\s+council|chief\s+and\s+councillors?|"
    r"number\s+of\s+months|travel|payments?|per\s+diems?|credit\s+card|"
    r"acknowledged|approved|accompanying|statement|financial|"
    r"project|program|contract|construction|maintenance|repair|renovation|"
    r"insurance|administration|audit|legal|professional|revenue|income|"
    r"asset|liability|payable|receivable"
    r")\b",
    re.IGNORECASE,
)

ROLE_RE = re.compile(r"\b(chief|councillor|councilor|council)\b", re.IGNORECASE)
WHITESPACE_RE = re.compile(r"\s+")


def clean_text(value):
    return WHITESPACE_RE.sub(" ", str(value or "").replace("\u00a0", " ")).strip()


def is_remuneration(filing):
    return "remuneration" in clean_text(filing.get("docType")).lower()


def clean_name(value):
    text = clean_text(value).strip(" -*:;,.\t")
    text = re.sub(r"\*+$", "", text).strip()
    return text


def normalize_role(value):
    text = clean_text(value).lower()
    if "chief" in text:
        return "Chief"
    if "councillor" in text or "councilor" in text or "council" in text:
        return "Councillor"
    return clean_text(value) or "Councillor"


def parse_money(value):
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value) if float(value).is_integer() else float(value)

    text = clean_text(value)
    if not text or text in {"-", "--", "---", "N/A", "n/a"}:
        return None

    negative = text.startswith("(") and text.endswith(")")
    cleaned = re.sub(r"[^0-9.\-]", "", text)
    if cleaned in {"", "-", "."}:
        return None

    try:
        amount = float(cleaned)
    except ValueError:
        return None

    if negative and amount > 0:
        amount = -amount
    return int(amount) if amount.is_integer() else amount


def is_bad_name(name):
    text = clean_name(name)
    if not text or not re.search(r"[A-Za-z]", text):
        return True
    if BAD_NAME_RE.search(text):
        return True
    if ROLE_RE.fullmatch(text):
        return True
    if len(text) > 90:
        return True
    tokens = text.split()
    if len(tokens) > 7:
        return True
    return False


def sane_months(value):
    amount = parse_money(value)
    if amount is None:
        return None
    if 0 < amount <= 24:
        return amount
    return None


def total_from_components(person):
    return sum(person.get(key) or 0 for key in PAYMENT_KEYS)


def add_warning(filing, note):
    warnings = filing.setdefault("warnings", [])
    if note not in warnings:
        warnings.append(note)


def set_technical_status(filing, status):
    if status in (None, "", "not_applicable", "not_required", "not_posted"):
        return
    filing["technical_status"] = TECHNICAL_STATUS_MAP.get(status, status)


def normalize_filing_status(filing):
    status = filing.get("parse_status")

    if not is_remuneration(filing):
        if status != "not_required":
            set_technical_status(filing, status)
            filing["parse_status"] = "not_required"
        return

    if not filing.get("posted"):
        if status != "not_posted":
            set_technical_status(filing, status)
            filing["parse_status"] = "not_posted"
        return

    people = filing.get("people") or []
    if people and str(status or "").startswith("ok_"):
        return

    public_status = PUBLIC_STATUS_MAP.get(status)
    if public_status and public_status != status:
        set_technical_status(filing, status)
        filing["parse_status"] = public_status
        if status == "error_openai":
            add_warning(filing, "OpenAI-assisted extraction needs review")


def sanitize_person(person):
    if not isinstance(person, dict):
        return None, "not_object"

    cleaned = dict(person)
    cleaned["name"] = clean_name(cleaned.get("name"))
    if is_bad_name(cleaned["name"]):
        return None, "bad_name"

    cleaned["role"] = normalize_role(cleaned.get("role"))
    cleaned["months"] = sane_months(cleaned.get("months"))

    for key in ALL_MONEY_KEYS:
        cleaned[key] = parse_money(cleaned.get(key))

    component_total = total_from_components(cleaned)
    current_total = cleaned.get("total")
    max_component = max((cleaned.get(key) or 0 for key in PAYMENT_KEYS), default=0)

    changed_total = False
    if component_total > 0:
        # Keep a valid PDF total, but repair totals that are missing, date-like,
        # lower than a component, or far away from the visible component sum.
        if (
            current_total is None
            or current_total <= 31
            or current_total < max_component
            or abs(current_total - component_total) > max(5, component_total * 0.08)
        ):
            cleaned["total"] = int(component_total) if float(component_total).is_integer() else component_total
            changed_total = True
    elif not current_total or current_total <= 31:
        return None, "no_money"

    largest_money = max((abs(cleaned.get(key) or 0) for key in ALL_MONEY_KEYS), default=0)
    if largest_money <= 31:
        return None, "date_like_money"

    return cleaned, "fixed_total" if changed_total else "ok"


def dedupe_people(people):
    chosen = {}
    removed = 0
    for person in people:
        key = (person.get("name", "").lower(), person.get("role", "").lower())
        previous = chosen.get(key)
        if previous is None:
            chosen[key] = person
            continue
        removed += 1
        if (person.get("total") or 0) > (previous.get("total") or 0):
            chosen[key] = person
    return list(chosen.values()), removed


def sanitize_filing(filing):
    normalize_filing_status(filing)

    people = filing.get("people") or []
    if not people:
        return 0, 0, 0

    cleaned_people = []
    removed = 0
    fixed = 0
    for person in people:
        cleaned, status = sanitize_person(person)
        if cleaned is None:
            removed += 1
            continue
        if status == "fixed_total":
            fixed += 1
        cleaned_people.append(cleaned)

    cleaned_people, duplicates = dedupe_people(cleaned_people)
    removed += duplicates

    if removed or fixed or len(cleaned_people) != len(people):
        filing["people"] = cleaned_people
        add_warning(filing, f"Sanitized parsed rows: removed {removed}, fixed totals {fixed}")

    if people and not cleaned_people:
        set_technical_status(filing, filing.get("parse_status"))
        filing["parse_status"] = "pending_manual_review"

    normalize_filing_status(filing)
    return len(people), removed, fixed


def sanitize_data(data):
    inspected = 0
    removed = 0
    fixed = 0

    for band in data.get("bands", []):
        for filing in band.get("filings", []):
            before, filing_removed, filing_fixed = sanitize_filing(filing)
            if before:
                inspected += before
                removed += filing_removed
                fixed += filing_fixed

    data["band_count"] = len(data.get("bands", []))
    return inspected, removed, fixed


def main():
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "data.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    inspected, removed, fixed = sanitize_data(data)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"sanitized rows inspected: {inspected}")
    print(f"sanitized rows removed: {removed}")
    print(f"sanitized totals fixed: {fixed}")


if __name__ == "__main__":
    main()
