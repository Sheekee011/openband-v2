# OpenBand

Static FNFTA remuneration tracker for Saskatchewan First Nations.

OpenBand is built as a public-interest research tool: searchable, source-linked,
and careful about the difference between parsed data, pending filings, and rows
that still need manual review.

## Public website features

- Search Saskatchewan First Nations by name.
- View Chief and Council remuneration rows by fiscal year.
- Open the original Indigenous Services Canada FNFTA filing from each result.
- Export the currently displayed table as CSV.
- Copy a ready-to-use citation for a filing.
- See current data status from `audit-results.txt` directly on the homepage.
- See whether a filing is parsed, pending, not posted, or needs extraction review.

## What is in this repo

- `index.html` - the public website
- `data.json` - generated filing and remuneration data used by the website
- `audit-results.txt` - latest coverage and parser-health report
- `scraper.py` - restored core scraper
- `run_scraper.py` - compatibility launcher with parser fallbacks
- `run_scraper_v2.py` - v2 launcher with extra Saskatchewan coverage
- `tools/merge_previous_data.py` - preserves already parsed rows and pending statuses during incremental runs
- `tools/sanitize_data.py` - removes obvious non-person rows and repairs broken totals
- `tools/audit_data.py` - checks coverage and pending parser work

## Workflows

- **Scrape FNFTA data**: manual current-year scraper run. It validates the new `data.json` before committing so a bad scrape cannot easily overwrite the working site data.
- **Backfill pending remuneration data**: manual batch parser for reducing the pending posted filing count.
- **Retry pending remuneration parsing**: retries all year groups and requires `OPENAI_API_KEY` so hard PDFs can use the AI fallback.
- **Sanitize OpenBand data**: cleans parsed rows and refreshes the audit.
- **Audit OpenBand data**: manual/PR health check for missing expected Saskatchewan First Nations and pending posted filings.
- **Restore working site from openband**: emergency restore from the original working repo.

## GitHub Pages

Use Settings -> Pages -> Deploy from branch -> `main` / `/root`.

## Secrets

Add `OPENAI_API_KEY` under Settings -> Secrets and variables -> Actions before running parser workflows.

## Verification standard

OpenBand should be used as a transparent index and research lead. Automated
extractions are labelled and linked back to source PDFs. For publication, verify
exact figures against the original ISC filing linked from the result page.
