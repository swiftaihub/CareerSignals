# CareerSignal

CareerSignal is a configurable local job-search intelligence pipeline. It collects job postings, normalizes messy source records, extracts structured fields from job descriptions, ranks jobs against a target candidate profile, and exports a polished Excel workbook for search planning.

The MVP runs locally with mock/sample job data by default and can ingest real data from Adzuna, SerpApi Google Jobs, Greenhouse, Lever, and USAJOBS when credentials or public board identifiers are configured.

## Why This Exists

Targeted job searching produces a lot of noisy, repetitive information. CareerSignal turns postings into a structured tracker with match scores, skill signals, company priorities, and category summaries so a candidate can focus effort on the roles most aligned with their background and goals.

The sample candidate profile emphasizes Python, SQL, Spark/PySpark, dbt, Databricks, cloud data platforms, BI tools, healthcare analytics, fintech/risk analytics, product analytics, and applied LLM analytics.

## Features

- YAML-driven job categories, filters, candidate profile, ranking weights, and skill aliases.
- Mock connector that runs without paid API keys.
- Real-source connectors for Adzuna, SerpApi Google Jobs, Greenhouse, Lever, and USAJOBS.
- Configurable posted-date freshness filter; default keeps only jobs posted within the last 24 hours.
- Local debug JSON snapshots when `CAREERSIGNAL_WRITE_DEBUG_JSON=true`.
- MotherDuck raw/staging/app schemas for production-style ELT mode.
- dbt staging, intermediate, and mart models for dashboard-ready tables.
- FastAPI repository layer with local and MotherDuck-backed implementations.
- Minimal Next.js dashboard scaffold that talks only to FastAPI.
- Normalized job schema with stable job IDs.
- Deduplication by job ID, post link, and fuzzy company/title/location matching.
- Salary parsing for annual and hourly pay ranges.
- Rule-based skill extraction with alias mapping.
- Industry, seniority, work-arrangement, and visa-sponsorship classification.
- Weighted match scoring with deterministic reasoning summaries.
- Excel workbook export with five tabs, filters, frozen headers, clickable links, salary formatting, and score conditional formatting.
- Pytest coverage for core processing and export behavior.

## Architecture

```text
config/                 YAML configuration
data/sample/            Demo job postings
data/raw/               Local debug raw API/source snapshots
data/processed/         Local debug processed snapshots and discovery audits
dbt/                    dbt project for staging, intermediate, and mart models
packages/               Shared storage, dbt, and repository services
apps/api/               FastAPI backend
apps/web/               Next.js dashboard scaffold
src/config/             Config schemas and loader
src/connectors/         Job source connectors
src/ingestion/          Raw and processed data persistence
src/processing/         Normalization, parsing, extraction, classification, scoring
src/exporters/          Excel workbook export
src/utils/              Logging, hashing, text helpers
tests/                  Unit tests
outputs/                Generated workbook output
```

Local processing flow:

1. Load and validate YAML configs.
2. Fetch jobs from one or more configured connectors.
3. Normalize raw postings into the shared schema.
4. Keep only postings inside the configured freshness window.
5. Optionally save timestamped raw JSON for retained postings.
6. Deduplicate jobs.
7. Parse salary and extract skills.
8. Classify industry, seniority, work arrangement, and visa signal.
9. Score jobs against the candidate profile.
10. Optionally save timestamped processed JSON.
11. Export the Excel workbook.

MotherDuck processing flow:

```text
Connector APIs
  -> raw.job_posts_raw
  -> staging.python_jobs_processed
  -> dbt staging models
  -> dbt intermediate models
  -> dbt mart models
  -> FastAPI
  -> Next.js Dashboard
  -> Excel Export
```

## Setup

Python 3.11+ is recommended.

For dbt, Python 3.11 or 3.12 is currently the safest choice. Python 3.14 may expose upstream dbt dependency compatibility issues.

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
```

On Windows machines where `python` is not on PATH, use the Python launcher:

```bash
py -m pip install -r requirements.txt
```

Optional environment setup:

```bash
copy .env.example .env
```

The default `JOB_SOURCES=mock` runs entirely from `data/sample/sample_jobs.json`.

Core data-mode settings:

```text
CAREERSIGNAL_DATA_MODE=local
MOTHERDUCK_TOKEN=
MOTHERDUCK_DATABASE=CareerSignal
CAREERSIGNAL_LOCAL_DATA_DIR=data
CAREERSIGNAL_OUTPUT_DIR=outputs
CAREERSIGNAL_EXCEL_PATH=outputs/job_search_tracker.xlsx
CAREERSIGNAL_WRITE_DEBUG_JSON=false
DBT_PROJECT_DIR=dbt
DBT_PROFILES_DIR=dbt
DBT_TARGET=local
CAREERSIGNAL_RUN_DBT=true
CAREERSIGNAL_RUN_DBT_TESTS=true
```

## Run The Pipeline

```bash
python src/main.py
```

or:

```bash
python -m src.main
```

Expected terminal summary:

```text
CareerSignal pipeline completed.
Fetched jobs: 125
Freshness filtered out: 32
Total jobs processed: 15
Deduplicated jobs: 15
Top matches: ...
Excel exported to: outputs/job_search_tracker_20260708_143012.xlsx
```

If `CAREERSIGNAL_WRITE_DEBUG_JSON=true`, the summary also includes timestamped raw and processed debug snapshot paths.

## Run Tests

```bash
pytest
```

## Configuration

Job categories live in `config/jobs_config.yml`. Add, remove, or tune categories without changing processing code:

```yaml
job_categories:
  - category_name: "Analytics Engineer"
    search_titles:
      - "Analytics Engineer"
      - "Senior Analytics Engineer"
    industries:
      - "technology"
      - "SaaS"
```

Candidate preferences and skill groups live in `config/candidate_profile.yml`. Skill aliases live in `config/skill_taxonomy.yml`, which allows terms like `PowerBI`, `Microsoft Power BI`, and `Power BI` to resolve to the same canonical skill.

Ranking weights are configurable:

```yaml
ranking_weights:
  title_match: 0.25
  required_skill_match: 0.25
  industry_match: 0.20
  salary_match: 0.10
  work_arrangement_match: 0.10
  visa_signal_match: 0.10
```

Freshness filtering is also configurable in `config/jobs_config.yml`:

```yaml
freshness_filter:
  enabled: true
  max_post_age_hours: 24
  include_unknown_dates: false
```

With the default settings, each refresh keeps only jobs posted within the last 24 hours. Jobs with unknown or unparseable posted dates are excluded unless `include_unknown_dates` is set to `true`. For sources that expose only a date without a timestamp, CareerSignal treats postings on the cutoff date as eligible.

## Real Data Ingestion

Source selection is controlled with `JOB_SOURCES` in `.env`.

```text
JOB_SOURCES=mock
```

Use a comma-separated list to combine sources:

```text
JOB_SOURCES=adzuna,greenhouse,lever
```

Use `all` to try every real connector:

```text
JOB_SOURCES=all
```

If configured real sources return no records, CareerSignal falls back to mock data so local runs still complete.

Supported source settings:

- Adzuna: set `ADZUNA_APP_ID`, `ADZUNA_APP_KEY`, and optional `ADZUNA_COUNTRY`, `ADZUNA_MAX_PAGES`, `ADZUNA_MAX_QUERIES_PER_CATEGORY`.
- SerpApi Google Jobs: set `SERPAPI_API_KEY`; the default query cap is intentionally low because SerpApi searches may count against paid usage.
- Greenhouse: set `GREENHOUSE_COMPANY_TOKENS` to board tokens from URLs like `boards.greenhouse.io/{token}`.
- Lever: set `LEVER_COMPANY_SITES` to site names from URLs like `jobs.lever.co/{site}`.
- USAJOBS: set `USAJOBS_USER_AGENT` and `USAJOBS_API_KEY` from developer.usajobs.gov.

When `CAREERSIGNAL_WRITE_DEBUG_JSON=true`, local debug snapshots are written to:

- `data/raw/raw_jobs_<timestamp>.json`
- `data/processed/processed_jobs_<timestamp>.json`

### Discover Greenhouse And Lever Slugs

Greenhouse board tokens and Lever site names are public identifiers, not secret keys. If you know a company's careers URL, the helper below can inspect it, validate any public Greenhouse or Lever endpoints it finds, and generate `.env` lines.

```bash
py scripts/discover_ats_boards.py --url "Example=https://boards.greenhouse.io/vaulttec"
```

You can pass several URLs:

```bash
py scripts/discover_ats_boards.py \
  --url "Lever Demo=https://jobs.lever.co/leverdemo" \
  --url "Greenhouse Demo=https://boards.greenhouse.io/vaulttec"
```

Or use a CSV file with `company,url` columns:

```bash
py scripts/discover_ats_boards.py --input config/company_targets.csv
```

The command writes a timestamped JSON audit file to `data/processed/discovery/ats_board_discovery_<timestamp>.json` and prints:

```text
GREENHOUSE_COMPANY_TOKENS=...
LEVER_COMPANY_SITES=...
```

## Excel Workbook

CareerSignal exports a timestamped workbook using `CAREERSIGNAL_EXCEL_PATH` as a base name, for example `outputs/job_search_tracker_20260708_143012.xlsx`. This keeps each run from replacing a previous workbook.

The workbook includes these tabs:

- `All Jobs`: normalized job records and match reasoning.
- `Top Matches`: jobs at or above `output.top_match_threshold`, sorted by score, salary, and posting date.
- `By Category Summary`: volume, match quality, salary, work arrangement, and visa signal by category.
- `Skill Gap Analysis`: skill frequency across jobs, candidate coverage, gap priority, and example titles.
- `Company Priority List`: company-level match quality, salary, visa summary, and priority.

In local mode, Excel is exported from Python processed data. In MotherDuck mode, Excel is exported from dbt mart tables so the dashboard and workbook share the same source of truth.

## MotherDuck + dbt Analytics Layer

MotherDuck mode makes Excel an export target instead of the primary source of truth. Raw JSON files are useful for debugging and offline development, but production-mode data should live in MotherDuck tables with dbt providing lineage, repeatable transformations, and dashboard-ready marts.

Set:

```text
CAREERSIGNAL_DATA_MODE=motherduck
MOTHERDUCK_DATABASE=CareerSignal
MOTHERDUCK_TOKEN=<stored only in .env>
DBT_TARGET=dev
```

Do not expose `MOTHERDUCK_TOKEN` in frontend code, README files, logs, tests, or committed examples.

Initialize schemas:

```bash
python -m packages.careersignal_core.storage.init_motherduck
```

Run the pipeline in MotherDuck mode:

```bash
CAREERSIGNAL_DATA_MODE=motherduck python src/main.py
```

Run dbt manually:

```bash
cd dbt
dbt debug --profiles-dir .
dbt run --profiles-dir .
dbt test --profiles-dir .
```

The dbt project is named `careersignal_dbt` and includes:

- `raw` sources: `job_posts_raw`, `ingestion_runs`, `connector_errors`
- `staging` sources: `python_jobs_processed`, `python_candidate_skills`
- `app` source: `job_application_status`
- staging models that standardize Python bridge output
- intermediate models for dedupe, skill explosion, and latest application status
- mart models for jobs, top matches, category summary, skill gap analysis, and company priorities

The FastAPI backend queries mart tables through `MotherDuckJobRepository` when `CAREERSIGNAL_DATA_MODE=motherduck`. In local mode it uses `LocalJobRepository` and reads local workbook output as a fallback.

FastAPI:

```bash
uvicorn apps.api.main:app --reload
```

Next.js dashboard:

```bash
cd apps/web
npm install
npm run dev
```

The Next.js frontend never receives MotherDuck credentials. It calls FastAPI endpoints such as `/api/jobs`, `/api/top-matches`, `/api/data/status`, `/api/dbt/run`, and `/api/dbt/test`.

## Connector Design

Each connector implements `BaseJobConnector.fetch_jobs(category_config)` and returns raw job dictionaries that can be normalized by `src/processing/normalize.py`. API connectors are intentionally environment-driven so credentials are not hardcoded. Source adapters catch recoverable HTTP and JSON failures, log them, and allow the rest of the pipeline to continue.

## Future Roadmap

- Add Workday career-page parser where legally and technically appropriate.
- Add Power BI dashboard export.
- Add LLM-based JD extraction.
- Add resume-to-JD matching.
- Add tailored resume recommendation.
- Add cover-letter or outreach-message draft generation.
- Add application-status tracking.
- Add GitHub Actions scheduled refresh.
- Add cloud deployment later.

## Notes

This MVP intentionally avoids fragile web scraping as the default path and does not require paid APIs. It is suitable for local experimentation, portfolio demonstration, and iterative extension into a richer job-search operating system.
