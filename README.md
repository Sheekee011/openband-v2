# OpenBand

OpenBand makes First Nations Financial Transparency Act filings easier to search, inspect, export, and verify.

The public website focuses on Saskatchewan FNFTA Chief and Council remuneration filings. Every displayed result should stay connected to the original Indigenous Services Canada source filing so readers can verify the figures themselves.

## Website Features

- Search Saskatchewan First Nations by name.
- View Chief and Council remuneration rows by fiscal year.
- Open the original Indigenous Services Canada FNFTA filing from each result.
- Export the currently displayed table as CSV.
- Copy a ready-to-use citation for a filing.
- See current data status from `audit-results.txt` directly on the homepage.
- See whether a filing is parsed, pending, not posted, or needs extraction review.

## What Is In This Repo

- `index.html` - the public website
- `data.json` - generated filing and remuneration data used by the website
- `audit-results.txt` - latest coverage and parser-health report
- `scraper.py` - restored core scraper
- `run_scraper.py` - compatibility launcher with parser fallbacks
- `run_scraper_v2.py` - v2 launcher with extra Saskatchewan coverage
- `tools/merge_previous_data.py` - preserves already parsed rows and pending statuses during incremental runs
- `tools/sanitize_data.py` - removes obvious non-person rows and repairs broken totals
- `tools/audit_data.py` - checks coverage and pending parser work
- `tools/capital_parser.py` - extracts validated audited-statement summaries into `capital-data.json`

## Community Capital data

Community Capital summaries are stored separately from remuneration data in
`capital-data.json`. The parser targets the statement of operations, statement
of financial position, and change in net assets/debt to extract:

- revenue and expense totals with category breakdowns
- annual surplus or deficit
- cash and investments
- tangible capital assets and annual capital purchases
- reported debt

Run a bounded local batch with:

```bash
python tools/capital_parser.py --year 2024-2025 --limit 10
```

The `Backfill Community Capital data` GitHub Actions workflow supports larger
batches and an optional OpenAI fallback. Summaries that fail reconciliation
remain marked for manual review and are not displayed as parsed data.

Each run also writes `capital-extraction-report.json`, including before/after
coverage, successful and partial records, failed records, non-applicable source
documents, unresolved filings, parser method, and extraction warnings.

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

## Verification Standard

OpenBand should be used as a transparent index and research lead. Automated extractions are labelled and linked back to source PDFs. For publication, verify exact figures against the original ISC filing linked from the result page.

The standard is not "trust the scraper." The standard is "make public records easier to find, compare, and verify."
