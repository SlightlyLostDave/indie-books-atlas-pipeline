# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Data pipeline for [Indie Books Atlas](https://indiebooksatlas.ca) — a map of independent bookstores across Canada. This repo only handles ingestion and sync; the Next.js frontend lives elsewhere. Three jobs: **seed** (one-time full ingest), **sync_osm** (weekly diff), **enrich_google** (monthly hours/phone update).

## Commands

```bash
pip install -e ".[dev]"          # install with dev dependencies

pytest                           # run all tests (70% coverage threshold enforced)
pytest tests/test_hours_parser.py  # run a single test file
pytest --cov=pipeline            # with coverage report

black pipeline tests             # format
ruff check pipeline tests        # lint
isort pipeline tests             # sort imports

python scripts/run_seed.py
python scripts/run_sync_osm.py
python scripts/run_enrich_google.py
```

Copy `.env.example` to `.env.local` and fill in credentials before running jobs.

## Architecture

Read `AGENT.md` for full detail. The short version:

```
pipeline/sources/     # fetch + light parse only — no normalization
pipeline/transforms/  # pure functions: dict in, dict out — no I/O
pipeline/jobs/        # orchestration only — wire sources + transforms + db
pipeline/db/          # all Supabase calls — never import client elsewhere
pipeline/utils/       # config (pydantic-settings), logging (structlog), provinces
scripts/              # thin click wrappers around jobs — no logic here
tests/fixtures/       # static JSON for offline testing
```

**Non-negotiable rules:**

- `sources/` returns raw dicts mirroring the API structure — no slug, no quality score, no schema normalization
- `transforms/` functions are pure — no DB calls, no httpx
- `jobs/` contains no business logic — any conditional or transformation belongs in `transforms/`
- All DB access goes through `db/` functions — never `from supabase import create_client` in a job or transform
- All external HTTP calls must use a `tenacity @retry` with exponential backoff
- Every store write (insert/update/flag) must produce a `change_log` row via `change_log.write_*` helpers
- **Never set `is_permanently_closed` from pipeline code** — flag `needs_review = true` and let a human decide
- **Never update a slug after insert** — it breaks live URLs

## Key data rules

**Source priority** (highest wins on conflict): `manual` > `ciba` > `alq` > `google_places` > `osm` > `wikidata` > `community_submission`

**OSM sync diff logic:**
- New `osm_id`: insert; set `needs_review = true` if `data_quality_score < 40`
- Changed fields: update, write change_log, never touch `is_verified` or `manual`-sourced fields
- Missing from Overpass: set `needs_review = true`, write `flag_review` change_log entry — do not close

**`data_quality_score`** (0–100): +20 each for phone, website, hours_raw, is_verified; +10 each for short_description, instagram

**`hours_parsed`** shape: `{ "mo": { "open": "10:00", "close": "18:00", "closed": false }, "su": { "closed": true }, ... }`. Keys: `mo tu we th fr sa su ph`. Absent key = unknown (not closed). Unparseable strings → `hours_parsed = null`, preserve `hours_raw`.

**`stores.specialties[]`** only accepts values from the `specialty_tags` table controlled vocabulary — no free text.

## Testing conventions

- Use `pytest-httpx` to mock all httpx calls — no real API calls in tests
- `hours_parser.py` must handle without exceptions: `24/7`, `Mo-Fr 09:00-17:30`, `Mo-Sa 10:00-18:00; Su 12:00-17:00`, `PH off`, `"by appointment"`, malformed/empty strings
- Transform modules target 90%+ coverage; DB modules are excluded (mock the Supabase client)
- Fixtures live in `tests/fixtures/` as static JSON files
