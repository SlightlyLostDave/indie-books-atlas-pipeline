# Indie Books Atlas — Pipeline

Data pipeline for [Indie Books Atlas](https://indiebooksatlas.ca), a map of independent bookstores across Canada. This repo handles ingestion and syncing store data into Supabase; the Next.js frontend lives in a separate repo.

## Jobs

| Job | Script | Purpose |
|---|---|---|
| `seed` | `scripts/run_seed.py` | One-time full ingest from all sources |
| `sync_osm` | `scripts/run_sync_osm.py` | Weekly diff against OpenStreetMap |
| `enrich_google` | `scripts/run_enrich_google.py` | Monthly hours/phone update via Google Places |

Data is merged from multiple sources with a fixed priority order (highest wins on conflict):
`manual` > `ciba` > `alq` > `google_places` > `osm` > `wikidata` > `community_submission`

## Setup

Requires Python >=3.11.

```bash
pip install -e ".[dev]"
cp .env.example .env.local   # fill in credentials
```

Required environment variables (`.env.local`):

```
SUPABASE_URL=
SUPABASE_SERVICE_KEY=
GOOGLE_PLACES_API_KEY=
OVERPASS_API_URL=https://overpass-api.de/api/interpreter
LOG_LEVEL=INFO
```

## Running jobs

```bash
python scripts/run_seed.py
python scripts/run_sync_osm.py
python scripts/run_enrich_google.py
```

Pass `--help` to any script to see available flags.

## Development

```bash
pytest                    # run tests (70% coverage threshold enforced)
pytest --cov=pipeline     # with coverage report

black pipeline tests      # format
isort pipeline tests      # sort imports
ruff check pipeline tests # lint
```

## Architecture

```
pipeline/sources/     # fetch + light parse only — no normalization
pipeline/transforms/  # pure functions: dict in, dict out — no I/O
pipeline/jobs/        # orchestration only — wire sources + transforms + db
pipeline/db/          # all Supabase calls — never import client elsewhere
pipeline/utils/       # config (pydantic-settings), logging (structlog), provinces
scripts/              # thin click wrappers around jobs — no logic here
tests/fixtures/       # static JSON for offline testing
```

See [AGENT.md](AGENT.md) for full architectural detail and data rules (quality scoring, hours parsing, OSM diff logic, etc.), and [CLAUDE.md](CLAUDE.md) for the conventions this codebase enforces.
