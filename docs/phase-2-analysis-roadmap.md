# OpenBand Phase 2 Analysis Roadmap

Phase 2 begins after Phase 1 has a reliable Saskatchewan dataset.

Phase 1 makes OpenBand trustworthy. Phase 2 makes OpenBand analytical.

The Phase 2 standard is:

> Turn verified public filings into comparison, trend, alert, and research tools without weakening source trust.

## Product Positioning

Phase 2 should position OpenBand as the analysis layer on top of public FNFTA records.

It should help people answer questions like:

- How has Chief and Council compensation changed over time?
- How does compensation compare across similarly sized First Nations?
- Which filings changed sharply from one fiscal year to the next?
- Which categories drive the largest changes?
- Which records need a closer look from journalists, researchers, or community members?

## Phase 2 Entry Requirements

Do not start heavy analytics until Phase 1 is strong enough.

Phase 2 should wait until:

- expected Saskatchewan names missing is `0`
- most recent Saskatchewan remuneration filings are visible
- pending posted remuneration filings are reduced as far as practical
- source links are stable
- parsed rows pass sanitizer checks
- audit status is public and easy to understand

Analysis is only valuable if the underlying data is trustworthy.

## Core Features

### 1. Compare Bands By Population

Goal: let users compare remuneration against community size.

Needed data:

- First Nation population
- registered population if available
- on-reserve population if available
- province
- treaty or region
- source URL for population data
- population year or snapshot date

User-facing views:

- compensation per registered member
- compensation per on-reserve member
- total Chief and Council compensation by population group
- comparable First Nations by size range

Trust rule:

Population numbers must show their source and date. If population data is missing or stale, label it clearly.

### 2. Compensation Trends

Goal: show how remuneration changes over time.

Views:

- total Chief and Council compensation by fiscal year
- Chief remuneration over time
- Councillor average over time
- expenses and travel over time
- year-over-year percentage change
- highest increase and highest decrease tables

Trust rule:

Trend lines should only use parsed years. Pending years should appear as gaps, not zeros.

### 3. Historical Changes

Goal: make changes easy to inspect.

Views:

- fiscal year timeline for each First Nation
- member-level history when names match across years
- role changes over time
- council size changes over time
- filing availability timeline

Trust rule:

Name matching should be conservative. If a person name changes spelling or cannot be matched safely, avoid pretending it is the same person.

### 4. Automated Summaries

Goal: give readers a plain-language summary of each filing.

Examples:

- total paid to Chief and Council
- highest-paid role or member
- biggest change from prior parsed year
- whether expenses increased or decreased
- whether the newest year is parsed or pending

Trust rule:

Summaries should cite the fiscal year and source filing. Avoid loaded language. Use neutral public-records wording.

### 5. Searchable Categories

Goal: make data searchable beyond First Nation name.

Categories:

- fiscal year
- treaty area
- province
- population range
- compensation range
- expense range
- parsed status
- source status
- extraction method
- review-needed status

Future categories after spending-data work:

- contractor/vendor
- program area
- project type
- travel
- legal
- consulting
- construction
- administration

Trust rule:

Categories should come from structured fields, not guesses, unless labelled as inferred.

### 6. Spending Heatmaps

Goal: help people see patterns quickly.

Possible heatmaps:

- total remuneration by First Nation and year
- year-over-year change by First Nation
- pending filing density by year
- expense share of total compensation
- travel and other payments by year
- future spending categories by community and year

Trust rule:

Heatmaps must avoid implying wrongdoing. They are navigation and pattern-finding tools, not conclusions.

### 7. Export Tools

Goal: make OpenBand useful for journalists and researchers.

Exports:

- current table CSV
- all parsed rows CSV
- selected fiscal years CSV
- First Nation history CSV
- audit summary CSV
- source-link inventory
- future JSON API snapshot

Trust rule:

Every export row should include source URL, fiscal year, parse status, extraction method, and generated date.

### 8. Alerts

Goal: notify users when public records change.

Alert types:

- new filing posted
- pending filing parsed
- large year-over-year change detected
- missing source recovered
- parser status changed
- audit health changed

Potential delivery:

- email alerts
- RSS feed
- static changelog page
- GitHub release notes
- webhook/API later

Trust rule:

Alerts should say exactly what changed and link to the source record.

## Data Model Additions

Phase 2 will likely need new generated files instead of cramming everything into `data.json`.

Possible files:

- `data.json` - current filing and row data
- `population.json` - population snapshots and sources
- `trends.json` - generated yearly trend metrics
- `summaries.json` - filing-level summaries
- `alerts.json` - recent changes detected by workflows
- `exports/openband-remuneration.csv` - full public export
- `exports/openband-sources.csv` - source URL inventory

## Workflow Additions

Possible future workflows:

- **Build trend metrics**: generates trend tables after `data.json` changes.
- **Build population comparisons**: joins population data to remuneration data.
- **Detect changes**: compares the newest scrape against the previous committed data.
- **Build public exports**: publishes CSV and JSON snapshots.
- **Generate summaries**: creates neutral filing summaries from structured rows.

## UI Additions

Phase 2 should add analysis without making the homepage confusing.

Recommended navigation:

- Search
- Compare
- Trends
- Exports
- Methodology
- Data status

Recommended first analysis screens:

1. First Nation profile with historical timeline
2. Compare First Nations by population group
3. Saskatchewan trend dashboard
4. Download/export page
5. Recent changes page

## Build Order

Recommended Phase 2 order:

1. Full CSV export with source URLs and parse statuses
2. First Nation historical trend view
3. Population data file and source labels
4. Compare by population range
5. Trend dashboard
6. Automated neutral summaries
7. Recent changes page
8. Alerts/RSS/email
9. Spending-category heatmaps after spending data exists

## What Not To Do Yet

Do not rush into conclusions or rankings before the data is ready.

Avoid:

- implying misconduct from high numbers alone
- ranking communities without context
- hiding uncertainty
- comparing population-adjusted numbers without population source dates
- AI-generated commentary that sounds accusatory
- paywalling core public-interest access too early

## Phase 2 Success Metric

Phase 2 succeeds when OpenBand becomes useful not only for looking up a filing, but for understanding patterns across years and communities.

People should be able to say:

> I found the source on OpenBand, checked the PDF, exported the data, and used the trend tools to understand what changed.
