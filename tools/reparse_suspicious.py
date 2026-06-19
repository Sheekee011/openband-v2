"""Reparse suspicious remuneration filings and keep only clear improvements."""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import run_scraper
from tools import parser_quality


def is_remuneration(filing):
    return "remuneration" in str(filing.get("docType", "")).lower()


def role(person):
    value = f"{person.get('role', '')} {person.get('name', '')}".lower()
    if re.search(r"\bchief\b", value):
        return "Chief"
    if re.search(r"\bcouncill?or\b|\bcouncil\b", value):
        return "Councillor"
    return "Unknown"


def amount(person, key):
    return parser_quality.number(person.get(key)) or 0


def row_total(person):
    return amount(person, "total")


def component_total(person):
    return sum(amount(person, key) for key in parser_quality.PAYMENT_KEYS)


def same_amount(left, right):
    if not left or not right:
        return False
    return abs(left - right) <= max(2, abs(right) * 0.001)


def filing_problems(people):
    problems = []
    if not people:
        return ["no rows"]

    if not any(role(person) == "Chief" for person in people):
        problems.append("no Chief row")
    if len(people) == 1:
        problems.append("only one row")

    seen = set()
    for person in people:
        name = re.sub(r"\W", "", str(person.get("name", "")).lower())
        key = (name, role(person))
        if key in seen:
            problems.append("duplicate official row")
        seen.add(key)

        total = row_total(person)
        components = component_total(person)
        if total and components and not parser_quality.nearly_equal(total, components):
            problems.append("row total mismatch")

        remuneration = amount(person, "remuneration")
        travel = amount(person, "travel")
        expenses = amount(person, "expenses")
        if remuneration and travel and same_amount(remuneration, travel):
            problems.append("remuneration duplicated into travel")
        if expenses and remuneration and same_amount(expenses, remuneration + travel):
            problems.append("subtotal duplicated into expenses")

        if total > 30000 and remuneration and remuneration <= 24:
            problems.append("month value in remuneration")

    return list(dict.fromkeys(problems))


def quality_key(people):
    problems = filing_problems(people)
    chiefs = sum(1 for person in people if role(person) == "Chief")
    mismatches = sum(
        1
        for person in people
        if row_total(person)
        and component_total(person)
        and not parser_quality.nearly_equal(row_total(person), component_total(person))
    )
    return (len(problems), mismatches, 0 if chiefs else 1, -len(people))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", default="data.json")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--band", action="append", default=[])
    parser.add_argument("--year", action="append", default=[])
    parser.add_argument("--problem", action="append", default=[])
    args = parser.parse_args()

    path = Path(args.path)
    data = json.loads(path.read_text(encoding="utf-8"))
    candidates = []
    for band in data.get("bands", []):
        if args.band and band.get("name") not in args.band:
            continue
        for filing in band.get("filings", []):
            if args.year and filing.get("year") not in args.year:
                continue
            people = filing.get("people") or []
            problems = filing_problems(people)
            if (
                filing.get("posted")
                and is_remuneration(filing)
                and people
                and not filing.get("manual_override")
                and problems
                and (not args.problem or any(problem in problems for problem in args.problem))
            ):
                candidates.append((band, filing))

    if args.limit:
        candidates = candidates[: args.limit]

    replaced = 0
    repaired_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    for index, (band, filing) in enumerate(candidates, start=1):
        old_people = filing.get("people") or []
        old_problems = filing_problems(old_people)
        print(
            f"[{index}/{len(candidates)}] {band.get('name')} {filing.get('year')}: "
            + "; ".join(old_problems)
        )
        result = run_scraper._extract_remuneration_rows_enhanced(filing.get("href"))
        new_people = result.get("people") or []
        if not new_people:
            print(f"  kept old rows: {result.get('parse_status')}")
            continue

        validation = parser_quality.validate_people(new_people)
        if validation.get("manual_review_required"):
            print("  kept old rows: new parse requires manual review")
            continue
        new_people = validation["people"]
        new_problems = filing_problems(new_people)
        if args.problem and any(problem in new_problems for problem in args.problem):
            print("  kept old rows: targeted problem remains")
            continue
        if not args.problem and new_problems:
            print("  kept old rows: new parse still has detected problems")
            continue
        if quality_key(new_people) >= quality_key(old_people):
            print("  kept old rows: new parse was not a clear improvement")
            continue

        filing["people"] = new_people
        filing["parse_status"] = result.get("parse_status", "ok_reparsed")
        filing["parse_confidence"] = validation.get("confidence")
        filing["manual_review_required"] = False
        filing["warnings"] = list(
            dict.fromkeys(
                (result.get("warnings") or [])
                + validation.get("warnings", [])
                + ["Reparsed after automated anomaly detection"]
            )
        )
        filing["reparsed"] = repaired_at
        band["scraped"] = repaired_at
        replaced += 1
        print(
            f"  replaced {len(old_people)} rows with {len(new_people)} rows; "
            f"remaining: {new_problems or 'none'}"
        )

    print(f"suspicious filings inspected: {len(candidates)}")
    print(f"filings replaced: {replaced}")
    if args.write and replaced:
        data["generated"] = repaired_at
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"saved: {path}")
    elif replaced:
        print("dry run only; pass --write to save")


if __name__ == "__main__":
    main()
