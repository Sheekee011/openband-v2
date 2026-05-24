# OpenBand

Static FNFTA remuneration tracker for Saskatchewan First Nations.

## What is in this repo

- `index.html` - the public website
- `data.json` - generated filing and remuneration data used by the website
- `scraper.py` - restored core scraper
- `run_scraper.py` - compatibility launcher with parser fallbacks
- `run_scraper_v2.py` - v2 launcher with extra Saskatchewan coverage
- `tools/merge_previous_data.py` - preserves already parsed rows during incremental runs
- `tools/audit_data.py` - checks coverage and pending parser work

## Workflows

- **Scrape FNFTA data**: manual current-year scraper run. It validates the new `data.json` before committing so a bad scrape cannot easily overwrite the working site data.
- **Backfill pending remuneration data**: manual batch parser for reducing the pending posted filing count. Start with `2024-2025,2023-2024,2022-2023`, then run older batches like `2021-2022,2020-2021,2019-2020`.
- **Audit OpenBand data**: manual/PR health check for missing expected Saskatchewan First Nations and pending posted filings. It prints pending counts by fiscal year.
- **Restore working site from openband**: emergency restore from the original working repo.

## GitHub Pages

Use Settings -> Pages -> Deploy from branch -> `main` / `/root`.

## Secrets

Add `OPENAI_API_KEY` under Settings -> Secrets and variables -> Actions before running parser workflows.
