# OpenBand

Static FNFTA remuneration tracker for Saskatchewan First Nations.

## What is in this repo

- `index.html` - the public website
- `data.json` - generated filing and remuneration data used by the website
- `scraper.py` - restored core scraper
- `run_scraper.py` - compatibility launcher with parser fallbacks
- `run_scraper_v2.py` - v2 launcher with extra Saskatchewan coverage
- `tools/audit_data.py` - checks coverage and pending parser work

## Workflows

- **Scrape FNFTA data**: manual scraper run. It now validates the new `data.json` before committing so a bad scrape cannot easily overwrite the working site data.
- **Audit OpenBand data**: manual/PR health check for missing expected Saskatchewan First Nations and pending posted filings.
- **Restore working site from openband**: emergency restore from the original working repo.

## GitHub Pages

Use Settings -> Pages -> Deploy from branch -> `main` / `/root`.

## Secrets

Add `OPENAI_API_KEY` under Settings -> Secrets and variables -> Actions before running the scraper.
