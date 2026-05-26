# OpenBand

OpenBand is public records infrastructure for First Nations Financial Transparency Act filings.

The immediate goal is simple: make Saskatchewan FNFTA Chief and Council remuneration data searchable, accurate, source-linked, accessible, and reliable enough that community members, journalists, researchers, and policy analysts can use it as a trusted starting point.

OpenBand is not trying to monetize attention right now. Phase 1 is trust: become the cleanest FNFTA dataset online.

## What OpenBand Is

- **Transparency infrastructure**: a stable public index for records that already exist but are hard to search.
- **Public records modernization**: PDFs and filing pages are turned into structured, searchable data.
- **Searchable governance data**: people can search by First Nation, fiscal year, role, and remuneration fields.
- **Research tooling**: every row stays connected to the original ISC filing so figures can be verified.
- **Community accessibility**: the site is designed to make public filings easier to inspect on ordinary devices.

## Phase 1 Priorities

OpenBand's current work is focused on reliability, not monetization.

- Parse every Saskatchewan First Nation with posted FNFTA remuneration filings.
- Reduce the posted-but-pending filing count as far as possible.
- Preserve historical filings year by year.
- Keep every parsed row linked to the source ISC PDF.
- Clearly label parsed, pending, not posted, and review-needed filings.
- Keep `audit-results.txt` visible so the dataset's health is public.
- Improve mobile usability, search speed, and table readability.
- Treat uncertain extraction as pending review instead of pretending it is perfect.

See [`docs/phase-1-trust-roadmap.md`](docs/phase-1-trust-roadmap.md) for the working roadmap.

## Public Website Features

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
