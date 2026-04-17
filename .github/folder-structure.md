## Folder Structure

```
indie-books-atlas-pipeline/
│
├── .github/
│ └── workflows/
│ ├── sync_osm.yml # weekly cron — OSM diff sync
│ ├── enrich_google.yml # monthly cron — Google Places enrichment
│ └── seed.yml # manual trigger only — initial seed
│
├── pipeline/
│ ├── **init**.py
│ │
│ ├── sources/ # one module per data source
│ │ ├── **init**.py
│ │ ├── osm.py # Overpass API queries + response parsing
│ │ ├── google_places.py # Places API fetch + normalization
│ │ ├── ciba.py # CIBA directory scrape/parse
│ │ └── wikidata.py # Wikidata SPARQL queries
│ │
│ ├── transforms/ # source data → stores schema shape
│ │ ├── **init**.py
│ │ ├── normalize.py # shared field normalization (phone, postal, etc.)
│ │ ├── hours_parser.py # OSM opening_hours string → hours_parsed JSONB
│ │ ├── slug.py # name + city → unique slug generation
│ │ └── quality_score.py # computes data_quality_score per record
│ │
│ ├── db/ # all Supabase interaction lives here
│ │ ├── **init**.py
│ │ ├── client.py # Supabase client singleton
│ │ ├── stores.py # read/write ops on the stores table
│ │ ├── store_sources.py # read/write ops on store_sources
│ │ └── change_log.py # change_log write helpers
│ │
│ ├── jobs/ # orchestration — one file per runnable job
│ │ ├── **init**.py
│ │ ├── seed.py # full initial ingest from all sources
│ │ ├── sync_osm.py # weekly diff: new / changed / flagged
│ │ └── enrich_google.py # monthly Google Places enrichment pass
│ │
│ └── utils/
│ ├── **init**.py
│ ├── logging.py # structured log config (used by all jobs)
│ └── provinces.py # province name ↔ code mapping helpers
│
├── scripts/ # thin CLI entry points, one per job
│ ├── run_seed.py
│ ├── run_sync_osm.py
│ └── run_enrich_google.py
│
├── tests/
│ ├── **init**.py
│ ├── test_hours_parser.py # hours_parser deserves thorough tests — OSM strings are wild
│ ├── test_normalize.py
│ ├── test_slug.py
│ ├── test_quality_score.py
│ └── fixtures/
│ ├── osm_response.json # sample Overpass API response for offline testing
│ └── google_response.json # sample Places API response
│
├── .env.example # documents required env vars, no real values
├── .env.local # gitignored — your actual local credentials
├── .gitignore
├── pyproject.toml # deps + tool config (use this over setup.py)
├── README.md
└── AGENT.md # pipeline behaviour contract (you have a template for this)
```
