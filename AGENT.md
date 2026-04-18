# AGENT.md — Indie Books Atlas Pipeline

This file provides context for AI coding assistants working in this repository.
Read it fully before writing any code.

---

## Project overview

Indie Books Atlas (indiebooksatlas.ca) is a community resource mapping every
independent bookstore in Canada. It is a Next.js web app backed by a Supabase
(PostgreSQL + PostGIS) database. This repository contains only the data pipeline
— the scripts that ingest, sync, and enrich bookstore data from external sources
into that database. The Next.js app lives in a separate repository.

The pipeline has three jobs:

- **Seed** — one-time full ingest from all sources to populate the database
- **Sync OSM** — weekly diff sync against OpenStreetMap to catch new stores,
  changes, and potential closures
- **Enrich Google** — monthly pass that fetches current hours and phone numbers
  from the Google Places API for stores that have a `google_place_id`

---

## Tech stack

- **Python 3.11**
- **supabase-py** — database client (service role key, bypasses RLS)
- **httpx** — all HTTP requests (Overpass API, Google Places API, etc.)
- **pydantic + pydantic-settings** — data validation and settings/env management
- **structlog** — structured logging across all jobs
- **click** — CLI entry points in `scripts/`
- **tenacity** — retry logic with exponential backoff on all external API calls
- **osm-opening-hours** — parsing OSM `opening_hours` strings
- **python-slugify** — slug generation
- **phonenumbers** — phone normalization to E.164
- **python-dotenv** — local `.env.local` loading

See `pyproject.toml` for pinned versions. Install with:

```bash
pip install -e ".[dev]"
```

---

## Repository structure

```
indie-books-atlas-pipeline/
├── .github/workflows/        # GitHub Actions — sync_osm.yml, enrich_google.yml, seed.yml
├── pipeline/
│   ├── sources/              # fetch + lightly parse raw API responses
│   │   ├── osm.py            # Overpass API queries and response parsing
│   │   ├── google_places.py  # Places API fetch and normalization
│   │   ├── ciba.py           # CIBA directory scrape/parse
│   │   └── wikidata.py       # Wikidata SPARQL queries
│   ├── transforms/           # shape source dicts into the stores schema
│   │   ├── normalize.py      # shared field normalization (phone, postal, etc.)
│   │   ├── hours_parser.py   # OSM opening_hours string → hours_parsed JSONB
│   │   ├── slug.py           # name + city → unique slug
│   │   └── quality_score.py  # computes data_quality_score (0–100)
│   ├── db/                   # all Supabase interaction
│   │   ├── client.py         # Supabase client singleton
│   │   ├── stores.py         # read/write ops on stores table
│   │   ├── store_sources.py  # read/write ops on store_sources table
│   │   └── change_log.py     # change_log write helpers
│   ├── jobs/                 # orchestration — wires sources + transforms + db
│   │   ├── seed.py
│   │   ├── sync_osm.py
│   │   └── enrich_google.py
│   └── utils/
│       ├── logging.py        # structlog configuration
│       └── provinces.py      # province name ↔ code mapping
├── scripts/                  # thin click CLI wrappers around jobs
│   ├── run_seed.py
│   ├── run_sync_osm.py
│   └── run_enrich_google.py
├── tests/
│   ├── fixtures/             # osm_response.json, google_response.json
│   ├── test_hours_parser.py
│   ├── test_normalize.py
│   ├── test_slug.py
│   └── test_quality_score.py
├── .env.example
├── .env.local                # gitignored
├── pyproject.toml
└── AGENT.md
```

---

## Architecture rules

These are non-negotiable conventions. Follow them in all new code.

**1. sources/ only fetches and lightly parses.**
A source module returns a list of raw dicts that closely mirror the API
response structure. It does not apply schema normalization, slugs, or quality
scores. It handles pagination, retries, and API errors.

**2. transforms/ only shapes data — no I/O.**
Transform functions are pure: they take a dict, return a dict. They never
call the database or any external API. This makes them trivially testable.

**3. jobs/ orchestrates — it does not contain business logic.**
A job imports from sources/, transforms/, and db/ and wires them together.
If you find yourself writing a conditional or a data transformation inside a
job file, it belongs in transforms/ instead.

**4. All database calls go through db/.**
Job files and transform files never import the Supabase client directly.
They call functions like `stores.upsert_from_osm(record)` or
`change_log.write_update(store_id, diff, source)`. Raw Supabase queries
belong only inside the db/ layer.

**5. All external API calls use tenacity retry.**
Every httpx call to Overpass, Google Places, Wikidata, or any other external
service must be wrapped in a tenacity `@retry` decorator with exponential
backoff. Overpass in particular times out under load. Treat all external
calls as unreliable.

**6. All jobs write to change_log.**
Every insert, update, soft-delete flag, and review flag applied to the
stores table must produce a corresponding change*log row. Use
`change_log.write*\*` helpers. Never skip the change_log for convenience.

**7. Never auto-close a store.**
If the OSM sync finds a store that was previously in the database but is
no longer in the Overpass results, set `needs_review = true` and write a
change_log entry with `operation = 'flag_review'`. A human reviews before
any store is marked `is_permanently_closed = true`. Never set
`is_permanently_closed` from pipeline code.

**8. Scripts are thin wrappers.**
Files in scripts/ contain only a click command that calls a job function.
No logic, no direct DB calls, no transforms. If the job function needs a
parameter, pass it through click options.

---

## Database schema summary

The database lives in Supabase. PostGIS and pg_trgm extensions are enabled.
The service role key is used by all pipeline scripts — it bypasses RLS.

### Key tables

**`stores`** — canonical record per bookstore location. Primary spatial column
is `location geography(Point, 4326)`. Denormalized `lat`/`lng` numeric columns
exist for convenience. Soft deletes via `is_deleted` + `deleted_at`.

**`store_sources`** — one row per external source per store. Stores the raw
API payload in `raw_data jsonb` and the external ID (`osm_id`, `google_place_id`,
etc.) for deduplication and re-fetch targeting.

**`change_log`** — immutable audit trail. Never updated, never deleted. Every
pipeline write produces a row here. `diff jsonb` structure:

- inserts: full record snapshot
- updates: `{"field": {"from": old_value, "to": new_value}, ...}`
- flags: `{"reason": "..."}`

**`submissions`** — community corrections queue. Public INSERT allowed via RLS,
no public SELECT. Pipeline never writes here. Human review required before any
submission changes a store record.

**`events`** — book fairs and literary events. `is_published = false` until
manually reviewed. `linked_store_id` is nullable (book fairs are not store-linked).

**`spotlights`** — bookseller spotlight content for social media posts.
`is_published = false` until manually approved.

**`specialty_tags`** — controlled vocabulary reference table. The allowed values
for `stores.specialties[]` are:

```
used, antiquarian, childrens, francophone, indigenous, lgbtq,
genre_fiction, academic, art_design, multilingual, comics_graphic,
mystery_crime, sci_fi_fantasy, travel, religion_spirit,
nature_outdoors, history, feminist, zines
```

Do not add free-text values to `stores.specialties`. Only values from this
list are valid.

### Opening hours storage

Two columns on `stores`:

- `hours_raw text` — the raw OSM `opening_hours` string, stored verbatim.
  This is the source of truth. Never overwrite it with a re-serialized value.
- `hours_parsed jsonb` — structured representation for query and display.

`hours_parsed` shape:

```json
{
  "mo": { "open": "10:00", "close": "18:00", "closed": false },
  "tu": { "open": "10:00", "close": "18:00", "closed": false },
  "we": { "open": "10:00", "close": "18:00", "closed": false },
  "th": { "open": "10:00", "close": "18:00", "closed": false },
  "fr": { "open": "10:00", "close": "18:00", "closed": false },
  "sa": { "open": "10:00", "close": "16:00", "closed": false },
  "su": { "closed": true }
}
```

Valid day keys: `mo tu we th fr sa su ph` (ph = public holiday).
If a day is absent from the object, treat it as unknown (not closed).
`"closed": true` means explicitly closed that day.
`24/7` stores: all days with `"open": "00:00", "close": "23:59"`.
Stores with `"by appointment"` or unparseable strings: set `hours_parsed = null`,
preserve `hours_raw`.

### data_quality_score computation

Computed by `transforms/quality_score.py` on every upsert. Max 100.

| Condition                       | Points |
| ------------------------------- | ------ |
| `phone` is not null             | +20    |
| `website` is not null           | +20    |
| `hours_raw` is not null         | +20    |
| `is_verified = true`            | +20    |
| `short_description` is not null | +10    |
| `instagram` is not null         | +10    |

---

## Data sources

Priority order for conflict resolution when sources disagree:

1. `manual` — human-entered data always wins
2. `ciba` — CIBA member directory (high trust, manually curated)
3. `alq` — Association des libraires du Québec (high trust, Quebec stores)
4. `google_places` — best for current hours and phone
5. `osm` — best for coordinates and existence
6. `wikidata` — supplementary only
7. `community_submission` — requires human review before application

### OSM Overpass query

```
[out:json];
area["ISO3166-1"="CA"]->.canada;
(
  node["shop"="books"](area.canada);
  way["shop"="books"](area.canada);
);
out body center;
```

The `center` output gives a lat/lng for way-type features. OSM node IDs are
stored in `stores.osm_id` (bigint) and `store_sources.external_id`.

### Sync diff logic

On each weekly OSM sync run, compare the full Overpass result against the
current database by `osm_id`. Categorize each result:

- **New** (`osm_id` not in DB): insert as new store, `needs_review = false`
  if data_quality_score >= 40, else `needs_review = true`.
- **Changed** (fields differ from stored values): update changed fields,
  write change_log entry, do not touch `is_verified` or `manual`-sourced fields.
- **Missing** (`osm_id` in DB but absent from Overpass results): set
  `needs_review = true`, write change_log entry with `operation = 'flag_review'`.
  Do not set `is_permanently_closed`. Never auto-close.

---

## Environment variables

Defined in `.env.example`. Load via pydantic-settings in `pipeline/utils/config.py`
(to be created). All pipeline code accesses config through this settings object,
never via `os.environ` directly.

```
SUPABASE_URL=
SUPABASE_SERVICE_KEY=           # service role key — bypasses RLS
GOOGLE_PLACES_API_KEY=
OVERPASS_API_URL=https://overpass-api.de/api/interpreter
LOG_LEVEL=INFO                  # DEBUG | INFO | WARNING | ERROR
```

---

## Testing conventions

- Tests live in `tests/`. One test file per transform module at minimum.
- `tests/fixtures/` holds static JSON files for offline testing — do not make
  real API calls in tests. Use `pytest-httpx` to mock httpx requests.
- `hours_parser.py` requires thorough test coverage. OSM hours strings
  encountered in the wild include: `24/7`, `Mo-Fr 09:00-17:30`,
  `Mo-Sa 10:00-18:00; Su 12:00-17:00`, `Mo-Fr 09:00-17:00; PH off`,
  `"by appointment"`, and malformed/empty strings. All must be handled
  without raising exceptions.
- Coverage threshold is 70% (enforced by pytest-cov). Transform modules
  should be at 90%+. DB modules are excluded from the threshold — mock
  the Supabase client rather than testing it.

---

## What this pipeline does NOT do

- It does not serve any HTTP endpoints. It is not a web server.
- It does not send emails or notifications. Notification logic lives in
  the Next.js app or a separate service.
- It does not modify the `submissions` table. Submissions are written by
  the Next.js app and reviewed by a human. The pipeline only reads from
  `submissions` to check for approved corrections (future feature).
- It does not manage the `events`, `spotlights`, or `specialty_tags` tables.
  Those are managed manually through the Supabase dashboard or a future
  admin UI.
- It does not generate slugs for existing stores. Slug generation runs only
  on insert. Never update a slug after a store is live — it will break URLs.
