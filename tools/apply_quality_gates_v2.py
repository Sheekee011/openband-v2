"""Temporarily patch sanitizer with stricter parser quality gates.

This script is run once by .github/workflows/apply-quality-gates-v2.yml and
then deleted by that workflow after the cleaned data is committed.
"""

from pathlib import Path

path = Path("tools/sanitize_data.py")
text = path.read_text(encoding="utf-8")

replacements = [
    (
        'r"asset|liability|payable|receivable"',
        'r"asset|liability|payable|receivable|"\n'
        '    r"director|manager|finance|post\\\\s+secondary|lands\\\\s+manager|"\n'
        '    r"education|coordinator|administrator|employee"',
    ),
    (
        'ROLE_RE = re.compile(r"\\\\b(chief|councillor|councilor|council)\\\\b", re.IGNORECASE)',
        'ROLE_RE = re.compile(r"\\\\b(chief|councillor|councilor|council)\\\\b", re.IGNORECASE)\n'
        'ROLE_WORD_IN_NAME_RE = re.compile(r"(^|\\\\b)(council\\\\s+member|council|chief|councillor|councilor)\\\\b", re.IGNORECASE)',
    ),
    (
        '    if ROLE_RE.fullmatch(text):\n        return True\n',
        '    if ROLE_RE.fullmatch(text):\n        return True\n'
        '    if ROLE_WORD_IN_NAME_RE.search(text):\n        return True\n',
    ),
    (
        'def has_total_echo(person):\n',
        'def has_small_component_shift(person):\n'
        '    total = person.get("total") or total_from_components(person)\n'
        '    if total <= 30000:\n'
        '        return False\n'
        '    for key in ("travel", "expenses", "creditCard", "otherPayments"):\n'
        '        amount = person.get(key)\n'
        '        if amount is not None and 0 < abs(amount) <= 24:\n'
        '            return True\n'
        '    return False\n\n\n'
        'def nearly_equal(left, right):\n'
        '    if not left or not right:\n'
        '        return False\n'
        '    return abs(left - right) <= max(2, abs(right) * 0.02)\n\n\n'
        'def has_component_echo(person):\n'
        '    remuneration = person.get("remuneration") or 0\n'
        '    travel = person.get("travel") or 0\n'
        '    expenses = person.get("expenses") or 0\n'
        '    total = person.get("total") or total_from_components(person)\n'
        '    if total <= 30000:\n'
        '        return False\n'
        '    if nearly_equal(travel, remuneration) and total > remuneration + 10000:\n'
        '        return True\n'
        '    if nearly_equal(expenses, remuneration + travel) and total > expenses + 10000:\n'
        '        return True\n'
        '    return False\n\n\n'
        'def has_total_echo(person):\n',
    ),
    (
        'return 0 < remuneration <= 24 and total > 50000',
        'return 0 < remuneration <= 24 and total > 1000',
    ),
    (
        '    if any(has_months_shift(person) for person in people):\n'
        '        reasons.append("month values appear in money columns")\n\n'
        '    total_echo_count = sum(1 for person in people if has_total_echo(person))\n'
        '    if total_echo_count >= max(1, len(people) // 3):\n'
        '        reasons.append("total column appears duplicated into payment columns")\n',
        '    month_shift_count = sum(1 for person in people if has_months_shift(person))\n'
        '    if month_shift_count:\n'
        '        reasons.append("month values appear in money columns")\n\n'
        '    small_component_count = sum(1 for person in people if has_small_component_shift(person))\n'
        '    if small_component_count:\n'
        '        reasons.append("small month-like values appear in payment columns")\n\n'
        '    component_echo_count = sum(1 for person in people if has_component_echo(person))\n'
        '    if component_echo_count:\n'
        '        reasons.append("payment columns appear duplicated or shifted")\n\n'
        '    total_echo_count = sum(1 for person in people if has_total_echo(person))\n'
        '    if total_echo_count:\n'
        '        reasons.append("total column appears duplicated into payment columns")\n',
    ),
]

for old, new in replacements:
    if new in text:
        continue
    if old not in text:
        raise SystemExit(f"Patch marker not found: {old[:80]!r}")
    text = text.replace(old, new, 1)

path.write_text(text, encoding="utf-8")
print("Applied quality gates v2 to tools/sanitize_data.py")
