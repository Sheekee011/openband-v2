# OpenBand Phase 1 Trust Roadmap

OpenBand's first job is not monetization. The first job is trust.

The Phase 1 standard is:

> Make Saskatchewan FNFTA data searchable, accurate, source-linked, accessible, and reliable enough that people can say: check OpenBand.

## Positioning

OpenBand should be described as:

- transparency infrastructure
- public records modernization
- searchable governance data
- research tooling
- accessibility for communities

This positioning keeps the project grounded in public-interest value. It also makes the project easier to understand for journalists, researchers, universities, Indigenous economic organizations, policy analysts, and governance consultants.

## North Star

Become the cleanest FNFTA remuneration dataset online, starting with Saskatchewan.

A clean dataset means:

- Every expected Saskatchewan First Nation is present.
- Every posted remuneration filing is visible, even when not parsed yet.
- Parsed rows include names, roles, months, remuneration, expenses, other payment fields, totals, fiscal year, and source URL.
- Pending filings are clearly labelled.
- Uncertain parses are sent to review instead of being shown as fact.
- The audit report shows dataset health in public.

## Current Product Rules

OpenBand should always preserve user trust.

- Do not hide posted filings just because they are hard to parse.
- Do not display estimated numbers as real data.
- Do not bury source links.
- Do not let a bad scrape overwrite working data.
- Do not treat AI extraction as final unless it passes cleanup and basic reasonableness checks.
- Do not overbuild business features before the dataset is strong.

## Phase 1 Work Queue

### 1. Coverage

Goal: every Saskatchewan First Nation appears in search.

Checklist:

- Keep `tools/audit_data.py` aligned with the expected Saskatchewan list.
- Add aliases when ISC names differ from common names.
- Keep missing expected names at `0` in `audit-results.txt`.
- Keep historical filing links available even when rows are pending.

### 2. Parsing Quality

Goal: reduce posted remuneration filings still pending as far as possible.

Checklist:

- Run `Retry pending remuneration parsing` in manageable batches.
- Keep preserving previous parsed rows with `tools/merge_previous_data.py`.
- Improve table extraction for recurring PDF layouts.
- Improve text extraction for schedules where rows are visible but table structure is missing.
- Use the OpenAI fallback only for hard PDFs and label that extraction method.
- Send suspicious rows to manual review instead of publishing them.

### 3. Data Safety

Goal: make regressions difficult.

Checklist:

- Keep scraper validation on band count, error count, and parsed filing regressions.
- Keep sanitizer checks for fake names, date-like totals, project rows, duplicate rows, and broken totals.
- Keep public statuses friendly while preserving technical statuses for debugging.
- Keep `audit-results.txt` committed with `data.json` updates.

### 4. Public Verification

Goal: every displayed number can be checked.

Checklist:

- Keep `View ISC filing` visible on every result.
- Keep source notes clear about extraction method.
- Keep citation copy available.
- Keep CSV export source-linked.
- Use plain labels: parsed, pending, not posted, review needed.

### 5. Usability

Goal: the site should feel fast and obvious.

Checklist:

- Make search instant and forgiving.
- Default each reserve to the newest parsed year when the newest posted year is still pending.
- Keep fiscal year switching clear.
- Keep mobile tables readable.
- Avoid jargon in user-facing messages.
- Make pending states helpful instead of confusing.

## Trust Metrics

These numbers should improve over time:

- Saskatchewan First Nations tracked
- bands with parsed remuneration
- parsed remuneration filings
- posted remuneration filings still pending
- pending filings by fiscal year
- pending filings by parse status
- expected Saskatchewan names missing

The most important Phase 1 number is:

> posted remuneration filings still pending

That number should move down without sacrificing accuracy.

## Future Leverage

Only after the dataset is reliable should OpenBand expand into partnerships or paid work.

Possible later paths:

- journalist/researcher data exports
- university research partnerships
- grants for public records accessibility
- governance analysis tools
- spending-category tracking beyond remuneration
- historical trend reports
- API access for researchers

Those are Phase 2 or later. Phase 1 is the dataset.
