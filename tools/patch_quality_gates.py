from pathlib import Path

path = Path('tools/sanitize_data.py')
text = path.read_text(encoding='utf-8')

old_bad = r'''BAD_NAME_RE = re.compile(
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
'''
new_bad = r'''BAD_NAME_RE = re.compile(
    r"\b("
    r"year\s+ended|schedule|remuneration|expenses?|unaudited|audited|"
    r"signature|signatures?|total|subtotal|page|note|notes?|"
    r"docusign|envelope|indigenous\s+services\s+canada|services\s+canada|"
    r"isc|aadnc|aandc|sac|government\s+of\s+canada|"
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
REVERSED_HEADER_RE = re.compile(r"(latoT|rehtO|yralaS|shtnoM|emaN|noitisoP|levarT)")
'''
if old_bad in text:
    text = text.replace(old_bad, new_bad, 1)
elif 'REVERSED_HEADER_RE' not in text:
    raise SystemExit('Could not patch bad-name regex')

old_name = r'''def is_bad_name(name):
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
'''
new_name = r'''def is_bad_name(name):
    text = clean_name(name)
    if not text or not re.search(r"[A-Za-z]", text):
        return True
    if REVERSED_HEADER_RE.search(text):
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
'''
if old_name in text:
    text = text.replace(old_name, new_name, 1)
elif 'REVERSED_HEADER_RE.search(text)' not in text:
    raise SystemExit('Could not patch is_bad_name')

insert_after = r'''def total_from_components(person):
    return sum(person.get(key) or 0 for key in PAYMENT_KEYS)
'''
quality_block = r'''def total_from_components(person):
    return sum(person.get(key) or 0 for key in PAYMENT_KEYS)


def has_months_shift(person):
    remuneration = person.get("remuneration")
    total = person.get("total") or total_from_components(person)
    if remuneration is None:
        return False
    return 0 < remuneration <= 24 and total > 50000


def has_total_echo(person):
    """Detect rows where a total column was also treated as another payment."""
    remuneration = person.get("remuneration") or 0
    travel = person.get("travel") or 0
    expenses = person.get("expenses") or 0
    credit_card = person.get("creditCard") or 0
    other = person.get("otherPayments") or 0
    total = person.get("total") or 0
    base = remuneration + travel + expenses + credit_card
    if base <= 0 or other <= 0 or total <= 0:
        return False
    return abs(other - base) <= max(2, base * 0.02) and abs(total - (base + other)) <= max(2, total * 0.02)


def suspicious_filing_reasons(people):
    if not people:
        return []

    reasons = []
    if len(people) == 1:
        reasons.append("only one parsed row")

    if any(has_months_shift(person) for person in people):
        reasons.append("month values appear in money columns")

    total_echo_count = sum(1 for person in people if has_total_echo(person))
    if total_echo_count >= max(1, len(people) // 3):
        reasons.append("total column appears duplicated into payment columns")

    chief_count = sum(1 for person in people if normalize_role(person.get("role")) == "Chief")
    if chief_count == 0 and len(people) <= 3:
        reasons.append("no Chief row in a small parsed filing")

    return reasons
'''
if 'def has_months_shift(person):' not in text:
    if insert_after not in text:
        raise SystemExit('Could not find total_from_components insert point')
    text = text.replace(insert_after, quality_block, 1)

old_quarantine_spot = r'''    cleaned_people, duplicates = dedupe_people(cleaned_people)
    removed += duplicates

    if removed or fixed or len(cleaned_people) != len(people):
        filing["people"] = cleaned_people
        add_warning(filing, f"Sanitized parsed rows: removed {removed}, fixed totals {fixed}")
'''
new_quarantine_spot = r'''    cleaned_people, duplicates = dedupe_people(cleaned_people)
    removed += duplicates

    reasons = suspicious_filing_reasons(cleaned_people)
    if reasons:
        removed += len(cleaned_people)
        cleaned_people = []
        add_warning(filing, "Quarantined parsed rows: " + "; ".join(reasons))

    if removed or fixed or len(cleaned_people) != len(people):
        filing["people"] = cleaned_people
        add_warning(filing, f"Sanitized parsed rows: removed {removed}, fixed totals {fixed}")
'''
if old_quarantine_spot in text:
    text = text.replace(old_quarantine_spot, new_quarantine_spot, 1)
elif 'suspicious_filing_reasons(cleaned_people)' not in text:
    raise SystemExit('Could not patch sanitize_filing quarantine logic')

path.write_text(text, encoding='utf-8')
print('quality gates patched')
