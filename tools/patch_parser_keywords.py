from pathlib import Path
import re

path = Path("run_scraper.py")
text = path.read_text(encoding="utf-8")


def replace_once(old, new, label):
    global text
    if old in text:
        text = text.replace(old, new, 1)
        return
    if new in text:
        return
    raise SystemExit(f"Could not find {label}")


# Broaden person-name matching, then normalize curly apostrophes before matching.
new_name_line = r'''_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z'., -]{1,90}\*?$")'''
if new_name_line not in text:
    text, count = re.subn(
        r'_NAME_RE = re\.compile\(r"[^"]+"\)',
        lambda match: new_name_line,
        text,
        count=1,
    )
    if count != 1:
        raise SystemExit("Could not replace _NAME_RE")

old_looks_like = r'''def _looks_like_person_name(value):
    text = scraper.clean_person_name(value)
    if not text or _PROJECT_LINE_RE.search(text):
        return False
    if re.search(r"\b(chief|councillor|councilor|total|travel|expense|payment|salary|wage)\b", text, re.I):
        return False
    return bool(_NAME_RE.match(text))
'''
new_looks_like = r'''def _looks_like_person_name(value):
    text = scraper.clean_person_name(value).replace("\u2019", "'")
    if not text or _PROJECT_LINE_RE.search(text):
        return False
    if re.search(r"\b(chief|councillor|councilor|total|travel|expense|payment|salary|wage)\b", text, re.I):
        return False
    if len(re.findall(r"[A-Za-z]+", text)) < 2:
        return False
    return bool(_NAME_RE.match(text))
'''
replace_once(old_looks_like, new_looks_like, "_looks_like_person_name")

marker = "# --- Keyword-aware FNFTA table parsing ---"
if marker not in text:
    name_line = re.search(r'_NAME_RE = re\.compile\(r"[^"]+"\)\n', text)
    if not name_line:
        raise SystemExit("Could not find _NAME_RE insert point")
    block = r'''
# --- Keyword-aware FNFTA table parsing ---
_ROLE_WORD_RE = re.compile(r"\b(chief|councillor|councilor)\b", re.I)
_ROLE_ONLY_RE = re.compile(r"^\s*(chief|councillor|councilor)\s*$", re.I)
_COLUMN_HEADER_RE = re.compile(
    r"\b(name|position|title|role|months?|remuneration|salary|honou?raria|travel|per\s*diems?|expenses?|reimbursements?|credit\s*card|visa|mastercard|other|payments?|benefits?|incentives?|total)\b",
    re.I,
)
_TOTAL_ROW_RE = re.compile(r"^\s*(total|subtotal|grand\s+total)\b", re.I)


def _clean_cell(value):
    return " ".join(str(value or "").replace("\u00a0", " ").split()).strip()


def _row_text(row):
    return " ".join(_clean_cell(cell) for cell in row if _clean_cell(cell))


def _is_column_header_line(line):
    line = _clean_cell(line)
    if not line:
        return False
    low = line.lower()
    if not _COLUMN_HEADER_RE.search(low):
        return False
    if re.search(r"\b(schedule|for the year ended|unaudited|audited)\b", low) and not re.search(
        r"\b(name|position|role|months?|travel|credit|other|total)\b", low
    ):
        return False
    money_count = len(_MONEY_RE.findall(line))
    return money_count <= 1 and not re.search(r"\b(chief|councillor|councilor)\b.+\d{2,}", low)


def _is_header_row(row):
    cells = [_clean_cell(cell) for cell in row]
    nonempty = [cell for cell in cells if cell]
    if not nonempty:
        return False
    keys = [key for key in (_column_key(cell) for cell in cells) if key]
    if len(set(keys)) >= 2:
        return True
    if len(nonempty) <= 1:
        return False
    return _is_column_header_line(_row_text(cells))


def _column_key(text):
    t = _clean_cell(text).lower()
    if not t:
        return None
    if re.search(r"\b(schedule|for the year ended|unaudited|audited)\b", t) and len(t.split()) > 4:
        return None
    if re.search(r"\b(number\s+of\s+)?months?\b", t):
        return "months"
    if re.search(r"\b(chief\s+and\s+council|chief\s+and\s+councillors|council\s+member|position|title|role)\b", t):
        return "role"
    if re.search(r"\bname\b", t):
        return "name"
    if "credit" in t or "visa" in t or "mastercard" in t:
        return "creditCard"
    if re.search(r"\b(total\s+paid|total)$|^total\b", t) and "remuneration" not in t:
        return "total"
    if re.search(r"\b(remuneration|salary|honou?raria|wages?)\b", t):
        return "remuneration"
    if re.search(r"\b(other|benefits?|incentives?)\b", t):
        return "otherPayments"
    if re.search(r"\b(travel|per\s*diems?|mileage|accommodation)\b", t):
        return "travel"
    if re.search(r"\b(expenses?|reimbursements?|allowances?)\b", t):
        return "expenses"
    if re.search(r"\bpayments?\b", t):
        return "otherPayments"
    return None


def _build_column_map(table):
    header_rows = []
    for row in table[:8]:
        cells = [_clean_cell(cell) for cell in row]
        if _is_header_row(cells):
            header_rows.append(cells)
    if not header_rows:
        return {}, ""

    width = max(len(row) for row in header_rows)
    combined = []
    for idx in range(width):
        parts = []
        for row in header_rows:
            if idx < len(row) and row[idx]:
                parts.append(row[idx])
        combined.append(" ".join(parts))

    column_map = {}
    for idx, heading in enumerate(combined):
        key = _column_key(heading)
        if key:
            column_map[idx] = key
    return column_map, " ".join(combined)


def _first_amount_in_cell(cell):
    cell = _clean_cell(cell)
    if not cell or cell in {"-", "--", "---"}:
        return None
    match = _MONEY_RE.search(cell.replace("$", " $ "))
    if not match:
        return None
    return _parse_amount(match.group(0).replace("$", "").strip())


def _looks_like_total(candidate, parts):
    if candidate is None or not parts:
        return False
    visible_sum = sum(value or 0 for value in parts)
    if visible_sum <= 0:
        return False
    return abs(candidate - visible_sum) <= max(5, visible_sum * 0.05)


def _assign_money_values(amounts, header_hint=""):
    amounts = [amount for amount in amounts if amount is not None]
    result = {
        "remuneration": None,
        "travel": None,
        "expenses": None,
        "creditCard": None,
        "otherPayments": None,
        "total": None,
    }
    if not amounts:
        return result

    hint = _clean_cell(header_hint).lower()
    has_total = bool(re.search(r"\btotal\b", hint))
    has_credit = bool(re.search(r"\b(credit|visa|mastercard)\b", hint))
    has_other = bool(re.search(r"\b(other|benefits?|incentives?)\b", hint))
    has_expense = bool(re.search(r"\b(expenses?|reimbursements?|allowances?)\b", hint))

    result["remuneration"] = amounts[0]
    if len(amounts) > 1:
        result["travel"] = amounts[1]

    if len(amounts) >= 6:
        result.update({
            "expenses": amounts[2],
            "creditCard": amounts[3],
            "otherPayments": amounts[4],
            "total": amounts[5],
        })
    elif len(amounts) == 5:
        result["expenses"] = amounts[2]
        if has_other and not has_credit:
            result["otherPayments"] = amounts[3]
        else:
            result["creditCard"] = amounts[3]
        result["total"] = amounts[4]
    elif len(amounts) == 4:
        if has_total or _looks_like_total(amounts[3], amounts[:3]):
            if has_other and not has_expense:
                result["otherPayments"] = amounts[2]
            else:
                result["expenses"] = amounts[2]
            result["total"] = amounts[3]
        else:
            result["expenses"] = amounts[2]
            result["otherPayments"] = amounts[3]
    elif len(amounts) == 3:
        if has_total or _looks_like_total(amounts[2], amounts[:2]):
            result["total"] = amounts[2]
        elif has_other and not has_expense:
            result["otherPayments"] = amounts[2]
        else:
            result["expenses"] = amounts[2]
    elif len(amounts) == 2 and has_total:
        result["travel"] = None
        result["total"] = amounts[1]

    if result["total"] is None:
        result["total"] = sum(result.get(key) or 0 for key in ["remuneration", "travel", "expenses", "creditCard", "otherPayments"])
    return result


def _strip_role_words(value):
    return scraper.clean_person_name(_ROLE_WORD_RE.sub(" ", _clean_cell(value)).strip(" -:\t")).replace("\u2019", "'")


def _extract_role_from_cells(cells):
    for cell in cells:
        match = _ROLE_WORD_RE.search(cell)
        if match:
            word = match.group(1).lower()
            return "Chief" if word == "chief" else "Councillor"
    return None


def _parse_keyword_table_row(row, column_map, header_hint):
    cells = [_clean_cell(cell) for cell in row]
    joined = _row_text(cells)
    if not joined or _is_header_row(cells) or _TOTAL_ROW_RE.search(joined):
        return None
    if _PROJECT_LINE_RE.search(joined) and not _ROLE_WORD_RE.search(joined):
        return None

    amounts_by_col = {idx: _first_amount_in_cell(cell) for idx, cell in enumerate(cells)}
    numeric_cols = [idx for idx, value in amounts_by_col.items() if value is not None]
    if len(numeric_cols) < 2:
        return None

    role = None
    for idx, key in column_map.items():
        if key == "role" and idx < len(cells):
            role = _extract_role_from_cells([cells[idx]]) or role
    role = role or _extract_role_from_cells(cells[: max(numeric_cols[0], 1)])

    name = None
    for idx, key in column_map.items():
        if key == "name" and idx < len(cells):
            candidate = _strip_role_words(cells[idx])
            if _looks_like_person_name(candidate):
                name = candidate
                break

    if not name:
        before_numbers = cells[: numeric_cols[0]]
        candidates = []
        for cell in before_numbers:
            if _ROLE_ONLY_RE.match(cell):
                continue
            candidate = _strip_role_words(cell)
            if _looks_like_person_name(candidate):
                candidates.append(candidate)
        if candidates:
            name = max(candidates, key=len)

    if not name:
        return None
    if not role:
        role = "Chief" if re.search(r"\bchief\b", joined, re.I) else "Councillor"

    months = None
    months_cols = [idx for idx, key in column_map.items() if key == "months"]
    for idx in months_cols:
        if idx < len(cells):
            amount = amounts_by_col.get(idx)
            if amount is not None and 0 < amount <= 24:
                months = amount
                break
    if months is None:
        for idx in numeric_cols:
            amount = amounts_by_col[idx]
            if amount is not None and 0 < amount <= 24 and idx <= numeric_cols[0] + 1:
                months = amount
                break

    mapped_money = {"remuneration": None, "travel": None, "expenses": None, "creditCard": None, "otherPayments": None, "total": None}
    for idx, key in column_map.items():
        if key in mapped_money and idx < len(cells):
            value = amounts_by_col.get(idx)
            if value is not None:
                mapped_money[key] = value

    if mapped_money["remuneration"] is not None or sum(1 for value in mapped_money.values() if value is not None) >= 2:
        if mapped_money["total"] is None:
            mapped_money["total"] = sum(mapped_money.get(key) or 0 for key in ["remuneration", "travel", "expenses", "creditCard", "otherPayments"])
        money = mapped_money
    else:
        money_amounts = []
        for idx in numeric_cols:
            value = amounts_by_col[idx]
            if value is None:
                continue
            if months is not None and idx in months_cols:
                continue
            if value <= 24 and idx <= numeric_cols[0] + 1:
                continue
            money_amounts.append(value)
        money = _assign_money_values(money_amounts, header_hint)

    if not any(money.get(key) for key in ["remuneration", "travel", "expenses", "creditCard", "otherPayments", "total"]):
        return None

    return {
        "name": name,
        "role": role,
        "months": months,
        **money,
    }


def _extract_people_from_keyword_table(table):
    if not table:
        return []
    column_map, header_hint = _build_column_map(table)
    people = []
    for row in table:
        person = _parse_keyword_table_row(row, column_map, header_hint)
        if person:
            people.append(person)
    return _dedupe_people(people)
'''
    text = text[: name_line.end()] + block + text[name_line.end():]

old_amount_block = r'''    amounts = [item["amount"] for item in money_values]
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
'''
new_amount_block = r'''    amounts = [item["amount"] for item in money_values]
    money = _assign_money_values(amounts, header_context)

    return {
        "name": name,
        "role": role,
        "months": months,
        **money,
    }
'''
replace_once(old_amount_block, new_amount_block, "text amount assignment block")

if 'def _parse_text_line(line, allow_inferred_councillor=False):' in text:
    text = text.replace(
        'def _parse_text_line(line, allow_inferred_councillor=False):',
        'def _parse_text_line(line, allow_inferred_councillor=False, header_context=""):',
        1,
    )
elif 'def _parse_text_line(line, allow_inferred_councillor=False, header_context=""):' not in text:
    raise SystemExit("Could not find _parse_text_line signature")

old_text_loop = r'''            for line in text.splitlines():
                person = _parse_text_line(line, allow_inferred_councillor=page_is_schedule)
                if person:
                    people.append(person)
'''
new_text_loop = r'''            header_context = ""
            for line in text.splitlines():
                if _is_column_header_line(line):
                    header_context = (header_context + " " + _clean_cell(line)).strip()
                    continue
                person = _parse_text_line(
                    line,
                    allow_inferred_councillor=page_is_schedule,
                    header_context=header_context,
                )
                if person:
                    people.append(person)
'''
replace_once(old_text_loop, new_text_loop, "text extraction loop")

old_table_block = r'''            people = []
            with scraper.pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                for page in pdf.pages:
                    for table in page.extract_tables() or []:
                        people.extend(scraper.extract_people_from_table(table))
            people = _dedupe_people(people)
            if people and not _looks_project_heavy(people):
                return {"parse_status": "ok_pdfplumber", "warnings": warnings, "people": people}
            if people:
                warnings.append("Discarded table extraction because rows looked project-heavy")
'''
new_table_block = r'''            keyword_people = []
            fallback_people = []
            with scraper.pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                for page in pdf.pages:
                    for table in page.extract_tables() or []:
                        parsed = _extract_people_from_keyword_table(table)
                        if parsed:
                            keyword_people.extend(parsed)
                        else:
                            fallback_people.extend(scraper.extract_people_from_table(table))
            people = _dedupe_people(keyword_people or fallback_people)
            if people and not _looks_project_heavy(people):
                method = "ok_pdf_keyword_table" if keyword_people else "ok_pdfplumber"
                note = "Parsed from keyword-aware PDF table extraction" if keyword_people else None
                if note:
                    warnings.append(note)
                return {"parse_status": method, "warnings": warnings, "people": people}
            if people:
                warnings.append("Discarded table extraction because rows looked project-heavy")
'''
replace_once(old_table_block, new_table_block, "table extraction block")

path.write_text(text, encoding="utf-8")
print("parser keyword patch applied")
