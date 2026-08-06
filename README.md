# Indie Books Atlas - Pipeline

Data pipeline for [Indie Books Atlas](https://indie-books-atlas.vercel.app/), a map of independent bookstores across Canada. This repo handles ingestion and syncing store data into Supabase; the Next.js frontend lives in a separate repo.

## Jobs

| Job             | Script                         | Purpose                                      |
| --------------- | ------------------------------ | -------------------------------------------- |
| `seed`          | `scripts/run_seed.py`          | One-time full ingest from all sources        |
| `sync_osm`      | `scripts/run_sync_osm.py`      | Weekly diff against OpenStreetMap            |
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

## Maintaining the excluded stores list

Chain stores (Chapters/Indigo/Coles), university bookstores, and religious
bookstores are kept out of the map by `pipeline/utils/excluded_stores.py`.
Both `seed` and `sync_osm` check every incoming OSM store against it before
adding anything new, so entries added here take effect on the next run of
either job.

There are three ways to exclude a store, all in that one file:

- **`EXCLUDED_OSM_IDS`** - a set of specific OSM node/way IDs, for one-off
  exclusions that don't fit a general rule. Find a store's OSM ID by locating
  it on [openstreetmap.org](https://www.openstreetmap.org) and opening its
  element page (the ID is in the URL, e.g. `.../node/123456789`).
- **`EXCLUDED_NAME_KEYWORDS`** - lowercase substrings matched against the
  store's name, OSM `brand` tag, and OSM `operator` tag (e.g. `"chapters"`,
  `"university of"`).
- **`EXCLUDED_TAG_VALUES`** - exact OSM tag/value pairs to exclude on (e.g.
  `brand=Indigo`), plus a blanket rule that any store with an OSM `religion`
  tag is excluded regardless of its value.

To add a new exclusion, edit the relevant set/dict in
`pipeline/utils/excluded_stores.py` and add a short comment noting which
store(s) it targets.

**This only prevents future inserts.** It does not retroactively remove or
close stores that are already in the database - per pipeline convention,
`is_permanently_closed` is never set by pipeline code, so removing an
already-seeded store that now matches an exclusion rule is a manual step
(the `sync_osm` job logs a warning when it detects this case, to flag it for
review).

## Architecture

```
pipeline/sources/     # fetch + light parse only - no normalization
pipeline/transforms/  # pure functions: dict in, dict out - no I/O
pipeline/jobs/        # orchestration only - wire sources + transforms + db
pipeline/db/          # all Supabase calls - never import client elsewhere
pipeline/utils/       # config (pydantic-settings), logging (structlog), provinces
scripts/              # thin click wrappers around jobs - no logic here
tests/fixtures/       # static JSON for offline testing
```

See [AGENT.md](AGENT.md) for full architectural detail and data rules (quality scoring, hours parsing, OSM diff logic, etc.) and [CLAUDE.md](CLAUDE.md) for the conventions this codebase enforces.
