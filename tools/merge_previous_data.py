"""Merge previously parsed rows back into a fresh scraper output.

The scraper rebuilds data.json from ISC each run. When a run only targets a few
fiscal years, older parsed rows can disappear unless we merge them back from the
snapshot taken before the run. This keeps scraper runs incremental.
"""

import json
import sys
from pathlib import Path


def band_key(band):
    band_id = band.get("id")
    if band_id is not None:
        return ("id", str(band_id))
    return ("name", " ".join(band.get("name", "").lower().split()))


def filing_key(filing):
    return (
        str(filing.get("year", "")),
        " ".join(filing.get("docType", "").lower().split()),
    )


def has_people(filing):
    return bool(filing.get("people"))


def merge_band(previous_band, current_band):
    previous_filings = {filing_key(filing): filing for filing in previous_band.get("filings", [])}
    restored = 0

    for filing in current_band.get("filings", []):
        previous_filing = previous_filings.get(filing_key(filing))
        if not previous_filing:
            continue
        if has_people(filing) or not has_people(previous_filing):
            continue

        filing["people"] = previous_filing.get("people", [])
        filing["parse_status"] = previous_filing.get("parse_status", "preserved_previous_parse")
        filing["warnings"] = previous_filing.get("warnings", []) + ["Preserved from previous data.json snapshot"]
        restored += 1

    return restored


def main():
    before_path = Path(sys.argv[1] if len(sys.argv) > 1 else "data.before.json")
    after_path = Path(sys.argv[2] if len(sys.argv) > 2 else "data.json")

    if not before_path.exists():
        print(f"No previous data snapshot found at {before_path}; skipping merge")
        return

    previous = json.loads(before_path.read_text(encoding="utf-8"))
    current = json.loads(after_path.read_text(encoding="utf-8"))

    previous_bands = {band_key(band): band for band in previous.get("bands", [])}
    current_keys = {band_key(band) for band in current.get("bands", [])}
    restored = 0
    appended = 0

    for band in current.get("bands", []):
        previous_band = previous_bands.get(band_key(band))
        if previous_band:
            restored += merge_band(previous_band, band)

    for key, previous_band in previous_bands.items():
        if key not in current_keys:
            current.setdefault("bands", []).append(previous_band)
            appended += 1

    current["band_count"] = len(current.get("bands", []))
    after_path.write_text(json.dumps(current, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"restored parsed filings: {restored}")
    print(f"appended missing previous bands: {appended}")


if __name__ == "__main__":
    main()
