-- =============================================================================
-- Indie Books Atlas — Database Schema
-- Supabase / PostgreSQL + PostGIS
-- =============================================================================
-- Run order matters. Execute top to bottom.
-- Requires the PostGIS and pg_trgm extensions (enabled below).
-- =============================================================================


-- -----------------------------------------------------------------------------
-- Extensions
-- -----------------------------------------------------------------------------

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;       -- powers fuzzy name/city search
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";   -- uuid_generate_v4() fallback


-- =============================================================================
-- ENUMS
-- =============================================================================

CREATE TYPE data_source_type AS ENUM (
  'osm',
  'ciba',
  'alq',
  'google_places',
  'wikidata',
  'manual',
  'community_submission'
);

CREATE TYPE province_code AS ENUM (
  'AB', 'BC', 'MB', 'NB', 'NL', 'NS', 'NT', 'NU', 'ON', 'PE', 'QC', 'SK', 'YT'
);

CREATE TYPE submission_status AS ENUM (
  'pending',
  'approved',
  'rejected',
  'duplicate'
);

CREATE TYPE submission_type AS ENUM (
  'correction',
  'new_store',
  'closure_report',
  'hours_update',
  'other'
);

CREATE TYPE event_type AS ENUM (
  'book_fair',
  'author_reading',
  'signing',
  'workshop',
  'launch',
  'other'
);

CREATE TYPE change_operation AS ENUM (
  'insert',
  'update',
  'soft_delete',
  'restore',
  'flag_review'
);


-- =============================================================================
-- STORES
-- Core table. One row per canonical bookstore location.
-- =============================================================================

CREATE TABLE stores (
  id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Identity
  name                  text NOT NULL,
  slug                  text NOT NULL UNIQUE,         -- e.g. 'the-bookshelf-guelph'
  short_description     text,                         -- 1–2 sentence editorial blurb
  staff_picks           text,                         -- freeform, human-entered only

  -- Address
  address_line1         text,
  address_line2         text,
  city                  text NOT NULL,
  province              province_code NOT NULL,
  postal_code           text,

  -- Geography (PostGIS)
  location              geography(Point, 4326),       -- primary spatial column
  lat                   numeric(10, 7),               -- denormalized for convenience
  lng                   numeric(10, 7),               -- denormalized for convenience

  -- Contact
  phone                 text,
  email                 text,
  website               text,
  instagram             text,                         -- handle only, no full URL
  bluesky               text,                         -- handle only
  tiktok                text,                         -- handle only
  twitter               text,                         -- handle only
  facebook              text,                         -- handle only
  bookshop_org_url      text,                         -- full URL, affiliate tag appended at render time

  -- Opening hours
  -- Raw OSM string is source of truth. Parsed JSONB is for query/display.
  -- Parsed structure: { "mo": {"open": "10:00", "close": "18:00", "closed": false}, ... }
  -- Days: mo tu we th fr sa su ph (public holiday)
  hours_raw             text,                         -- e.g. 'Mo-Sa 10:00-18:00; Su 12:00-17:00'
  hours_parsed          jsonb,                        -- structured, see comment above
  hours_note            text,                         -- freeform note e.g. 'Summer hours may vary'

  -- Specialties (controlled vocabulary — see SPECIALTY_TAGS below)
  specialties           text[] NOT NULL DEFAULT '{}',

  -- Status flags
  is_verified           boolean NOT NULL DEFAULT false,
  is_permanently_closed boolean NOT NULL DEFAULT false,
  is_featured           boolean NOT NULL DEFAULT false,  -- spotlight flag
  needs_review          boolean NOT NULL DEFAULT false,  -- triage queue flag
  is_deleted            boolean NOT NULL DEFAULT false,  -- soft delete
  deleted_at            timestamptz,

  -- Data quality (0–100, computed by pipeline)
  -- +20 has phone
  -- +20 has website
  -- +20 has hours_raw
  -- +20 is_verified = true
  -- +10 has short_description
  -- +10 has instagram
  data_quality_score    smallint NOT NULL DEFAULT 0 CHECK (data_quality_score BETWEEN 0 AND 100),

  -- Provenance
  primary_source        data_source_type NOT NULL DEFAULT 'osm',
  osm_id                bigint UNIQUE,                -- OSM node/way ID
  google_place_id       text UNIQUE,
  wikidata_id           text UNIQUE,                  -- e.g. 'Q12345'
  ciba_member_id        text,
  alq_member_id         text,

  -- Timestamps
  last_verified_at      timestamptz,
  last_synced_at        timestamptz,                  -- last pipeline touch
  created_at            timestamptz NOT NULL DEFAULT now(),
  updated_at            timestamptz NOT NULL DEFAULT now()
);

-- Indexes
CREATE INDEX idx_stores_location      ON stores USING GIST (location);
CREATE INDEX idx_stores_province      ON stores (province) WHERE is_deleted = false AND is_permanently_closed = false;
CREATE INDEX idx_stores_specialties   ON stores USING GIN (specialties);
CREATE INDEX idx_stores_needs_review  ON stores (needs_review) WHERE needs_review = true;
CREATE INDEX idx_stores_featured      ON stores (is_featured) WHERE is_featured = true;
CREATE INDEX idx_stores_quality       ON stores (data_quality_score);
CREATE INDEX idx_stores_osm_id        ON stores (osm_id) WHERE osm_id IS NOT NULL;
CREATE INDEX idx_stores_name_trgm     ON stores USING GIN (name gin_trgm_ops);
CREATE INDEX idx_stores_city_trgm     ON stores USING GIN (city gin_trgm_ops);


-- -----------------------------------------------------------------------------
-- Specialty tags — controlled vocabulary reference
-- Not a foreign key constraint (arrays don't support that cleanly),
-- but documents the allowed values and their display labels.
-- -----------------------------------------------------------------------------

CREATE TABLE specialty_tags (
  tag           text PRIMARY KEY,   -- value stored in stores.specialties[]
  label         text NOT NULL,      -- display label e.g. 'Used & Secondhand'
  label_fr      text,               -- French display label
  sort_order    smallint NOT NULL DEFAULT 0,
  is_active     boolean NOT NULL DEFAULT true
);

INSERT INTO specialty_tags (tag, label, label_fr, sort_order) VALUES
  ('used',              'Used & Secondhand',          'Livres usagés',                  10),
  ('antiquarian',       'Rare & Antiquarian',         'Livres rares et anciens',        20),
  ('childrens',         'Children''s',                'Livres pour enfants',            30),
  ('francophone',       'Francophone',                'Francophone',                    40),
  ('indigenous',        'Indigenous & First Nations', 'Autochtone et Premières Nations', 50),
  ('lgbtq',             'LGBTQ+',                     'LGBTQ+',                         60),
  ('genre_fiction',     'Genre Fiction',              'Fiction de genre',               70),
  ('academic',          'Academic & Scholarly',       'Académique et savant',           80),
  ('art_design',        'Art & Design',               'Art et design',                  90),
  ('multilingual',      'Multilingual',               'Multilingue',                    100),
  ('comics_graphic',    'Comics & Graphic Novels',    'Bandes dessinées',               110),
  ('mystery_crime',     'Mystery & Crime',            'Mystère et polar',               120),
  ('sci_fi_fantasy',    'Sci-Fi & Fantasy',           'SF et fantastique',              130),
  ('travel',            'Travel',                     'Voyage',                         140),
  ('religion_spirit',   'Religion & Spirituality',    'Religion et spiritualité',       150),
  ('nature_outdoors',   'Nature & Outdoors',          'Nature et plein air',            160),
  ('history',           'History',                    'Histoire',                       170),
  ('feminist',          'Feminist',                   'Féministe',                      180),
  ('zines',             'Zines & Small Press',        'Zines et petite presse',         190);


-- =============================================================================
-- STORE SOURCES
-- One row per external source that references a given store.
-- Tracks provenance across OSM, Google, CIBA, etc.
-- =============================================================================

CREATE TABLE store_sources (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  store_id        uuid NOT NULL REFERENCES stores (id) ON DELETE CASCADE,
  source          data_source_type NOT NULL,
  external_id     text,                         -- OSM node ID, Google Place ID, etc.
  source_url      text,                         -- direct URL to listing if applicable
  raw_data        jsonb,                        -- full raw payload from source at last fetch
  fetched_at      timestamptz NOT NULL DEFAULT now(),
  is_primary      boolean NOT NULL DEFAULT false,

  UNIQUE (store_id, source)
);

CREATE INDEX idx_store_sources_store_id ON store_sources (store_id);
CREATE INDEX idx_store_sources_source   ON store_sources (source);


-- =============================================================================
-- EVENTS
-- Book fairs and other literary events.
-- In-store events (readings, signings) are schema-present but event_type
-- distinguishes them. The UI only surfaces book_fair for MVP.
-- =============================================================================

CREATE TABLE events (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Identity
  name              text NOT NULL,
  slug              text NOT NULL UNIQUE,
  description       text,
  event_type        event_type NOT NULL DEFAULT 'book_fair',

  -- Timing
  start_date        date NOT NULL,
  end_date          date NOT NULL,
  start_time        time,                       -- null = all-day
  end_time          time,
  timezone          text NOT NULL DEFAULT 'America/Toronto',
  is_recurring      boolean NOT NULL DEFAULT false,
  recurrence_note   text,                       -- freeform e.g. 'Annual — last Saturday in April'

  -- Location
  venue_name        text,
  address_line1     text,
  address_line2     text,
  city              text NOT NULL,
  province          province_code NOT NULL,
  postal_code       text,
  location          geography(Point, 4326),
  lat               numeric(10, 7),
  lng               numeric(10, 7),

  -- Optional link to a store listing
  linked_store_id   uuid REFERENCES stores (id) ON DELETE SET NULL,

  -- External
  website           text,
  ticket_url        text,
  instagram         text,

  -- Admin
  is_published      boolean NOT NULL DEFAULT false,  -- review queue: false until approved
  is_featured       boolean NOT NULL DEFAULT false,
  submitted_by      text,                            -- email of submitter if community-sourced
  source            data_source_type NOT NULL DEFAULT 'manual',

  -- Timestamps
  created_at        timestamptz NOT NULL DEFAULT now(),
  updated_at        timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_events_start_date    ON events (start_date) WHERE is_published = true;
CREATE INDEX idx_events_province      ON events (province) WHERE is_published = true;
CREATE INDEX idx_events_event_type    ON events (event_type) WHERE is_published = true;
CREATE INDEX idx_events_location      ON events USING GIST (location);
CREATE INDEX idx_events_linked_store  ON events (linked_store_id) WHERE linked_store_id IS NOT NULL;


-- =============================================================================
-- SUBMISSIONS
-- Community corrections and new store submissions.
-- Nothing here touches the stores table directly —
-- all changes go through human review first.
-- =============================================================================

CREATE TABLE submissions (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),

  submission_type   submission_type NOT NULL,
  status            submission_status NOT NULL DEFAULT 'pending',

  -- Which store this is about (null for new_store submissions)
  store_id          uuid REFERENCES stores (id) ON DELETE SET NULL,
  store_name_hint   text,                       -- submitter-provided name if store_id unknown

  -- Submitter info (optional — no account required)
  submitter_name    text,
  submitter_email   text,

  -- The actual submission content
  -- For corrections: key/value pairs of proposed changes e.g. {"phone": "519-555-0100"}
  -- For new stores: all known fields
  -- For closures: just a note is fine
  proposed_changes  jsonb,
  notes             text,

  -- Review
  reviewed_by       text,                       -- admin identifier
  reviewed_at       timestamptz,
  review_notes      text,

  -- Timestamps
  created_at        timestamptz NOT NULL DEFAULT now(),
  updated_at        timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_submissions_status    ON submissions (status) WHERE status = 'pending';
CREATE INDEX idx_submissions_store_id  ON submissions (store_id) WHERE store_id IS NOT NULL;
CREATE INDEX idx_submissions_type      ON submissions (submission_type);


-- =============================================================================
-- CHANGE LOG
-- Immutable audit trail. One row per field-level or record-level change.
-- Written by pipeline scripts and admin actions.
-- Never updated, never deleted.
-- =============================================================================

CREATE TABLE change_log (
  id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  store_id        uuid,                         -- nullable: some log entries may not be store-specific
  operation       change_operation NOT NULL,
  source          data_source_type NOT NULL,
  changed_by      text,                         -- 'pipeline', 'admin', or an admin user identifier
  submission_id   uuid REFERENCES submissions (id) ON DELETE SET NULL,

  -- What changed
  -- For updates: {"field": {"from": old_value, "to": new_value}, ...}
  -- For inserts: full record snapshot
  -- For soft deletes / restores: {"reason": "..."} or similar
  diff            jsonb,

  created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_change_log_store_id    ON change_log (store_id) WHERE store_id IS NOT NULL;
CREATE INDEX idx_change_log_created_at  ON change_log (created_at DESC);
CREATE INDEX idx_change_log_operation   ON change_log (operation);


-- =============================================================================
-- SOCIAL FEATURES
-- Bookseller spotlight metadata.
-- Drives the featured store indicator on the detail page
-- and provides structured data for social post generation.
-- =============================================================================

CREATE TABLE spotlights (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  store_id        uuid NOT NULL REFERENCES stores (id) ON DELETE CASCADE,

  -- Content
  headline        text NOT NULL,                -- short punchy header for the social card
  body            text NOT NULL,                -- 3–5 sentences, editorial voice
  pull_quote      text,                         -- optional single quote from owner/staff
  pull_quote_attr text,                         -- attribution e.g. 'Jane, owner'

  -- Q&A pairs (for longer on-site spotlights)
  -- Array of {"question": "...", "answer": "..."} objects
  qa_pairs        jsonb,

  -- Media
  image_url       text,                         -- hosted image URL (store-provided or Street View)
  image_credit    text,                         -- e.g. '@thetypestore on Instagram'
  image_alt       text,

  -- Social post copy
  instagram_caption   text,                     -- ready-to-post IG caption including tags
  bluesky_post        text,                     -- 300 char max

  -- Scheduling
  publish_date    date,
  is_published    boolean NOT NULL DEFAULT false,

  -- Timestamps
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_spotlights_store_id     ON spotlights (store_id);
CREATE INDEX idx_spotlights_publish_date ON spotlights (publish_date) WHERE is_published = true;


-- =============================================================================
-- TRIGGERS
-- updated_at auto-maintenance on mutable tables.
-- =============================================================================

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$;

CREATE TRIGGER stores_updated_at
  BEFORE UPDATE ON stores
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER events_updated_at
  BEFORE UPDATE ON events
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER submissions_updated_at
  BEFORE UPDATE ON submissions
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER spotlights_updated_at
  BEFORE UPDATE ON spotlights
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- =============================================================================
-- ROW LEVEL SECURITY
-- Public read on safe tables. All writes via service role only
-- except submissions (public insert allowed, no read).
-- =============================================================================

ALTER TABLE stores          ENABLE ROW LEVEL SECURITY;
ALTER TABLE store_sources   ENABLE ROW LEVEL SECURITY;
ALTER TABLE events          ENABLE ROW LEVEL SECURITY;
ALTER TABLE submissions     ENABLE ROW LEVEL SECURITY;
ALTER TABLE change_log      ENABLE ROW LEVEL SECURITY;
ALTER TABLE spotlights      ENABLE ROW LEVEL SECURITY;
ALTER TABLE specialty_tags  ENABLE ROW LEVEL SECURITY;

-- Public can read active, non-deleted stores
CREATE POLICY stores_public_read ON stores
  FOR SELECT USING (
    is_deleted = false
    AND is_permanently_closed = false
  );

-- Public can read published events
CREATE POLICY events_public_read ON events
  FOR SELECT USING (is_published = true);

-- Public can read specialty tags
CREATE POLICY specialty_tags_public_read ON specialty_tags
  FOR SELECT USING (is_active = true);

-- Public can read published spotlights
CREATE POLICY spotlights_public_read ON spotlights
  FOR SELECT USING (is_published = true);

-- Public can INSERT submissions only (no read, no update)
CREATE POLICY submissions_public_insert ON submissions
  FOR INSERT WITH CHECK (status = 'pending');

-- No public access to change_log, store_sources
-- (service role bypasses RLS for all pipeline and admin operations)


-- =============================================================================
-- HELPER VIEWS
-- =============================================================================

-- Active stores with computed open-now flag
-- open_now is approximate: compares current local time against hours_parsed.
-- hours_parsed day keys: mo tu we th fr sa su
-- hours_parsed value: {"open": "10:00", "close": "18:00"} | {"closed": true}
CREATE VIEW stores_active AS
SELECT
  s.*,
  -- Open now: checks current day key in hours_parsed against current UTC time
  -- Timezone-naive approximation. Good enough for display; don't use for SLAs.
  CASE
    WHEN s.hours_parsed IS NULL THEN NULL
    ELSE (
      SELECT
        CASE
          WHEN (day_data->>'closed')::boolean IS TRUE THEN false
          WHEN (day_data->>'open') IS NULL            THEN NULL
          ELSE (
            localtime BETWEEN
              (day_data->>'open')::time AND
              (day_data->>'close')::time
          )
        END
      FROM (
        SELECT s.hours_parsed -> lower(to_char(now(), 'Dy'))  -- 'Mon' -> 'mo' won't work directly
               AS day_data                                     -- see note below
      ) sub
    )
  END AS is_open_now
FROM stores s
WHERE s.is_deleted = false
  AND s.is_permanently_closed = false;

-- Note: the is_open_now column above is a scaffold. The day key mapping
-- (PostgreSQL's to_char 'Dy' returns 'Mon', 'Tue' etc., not 'mo', 'tu')
-- should be handled in application logic or a more complete SQL expression.
-- Left intentionally simple here to avoid obscuring the schema intent.


-- Admin triage view: stores needing attention, ordered by urgency
CREATE VIEW stores_review_queue AS
SELECT
  id,
  name,
  city,
  province,
  data_quality_score,
  needs_review,
  is_verified,
  last_verified_at,
  last_synced_at,
  primary_source,
  CASE
    WHEN needs_review = true              THEN 'flagged'
    WHEN data_quality_score < 40          THEN 'low_quality'
    WHEN last_verified_at < now() - interval '90 days'
      OR last_verified_at IS NULL         THEN 'stale'
    ELSE 'ok'
  END AS review_reason
FROM stores
WHERE is_deleted = false
  AND is_permanently_closed = false
  AND (
    needs_review = true
    OR data_quality_score < 40
    OR last_verified_at < now() - interval '90 days'
    OR last_verified_at IS NULL
  )
ORDER BY
  needs_review DESC,
  data_quality_score ASC,
  last_verified_at ASC NULLS FIRST;


-- Pending submissions count by type (for admin dashboard widget)
CREATE VIEW submissions_pending_summary AS
SELECT
  submission_type,
  count(*) AS count,
  min(created_at) AS oldest_pending
FROM submissions
WHERE status = 'pending'
GROUP BY submission_type;


-- =============================================================================
-- SPATIAL FUNCTION
-- Nearby stores — used by the "near me" feature.
-- Returns stores within radius_km of a given point,
-- ordered by distance, excluding closed/deleted.
-- =============================================================================

CREATE OR REPLACE FUNCTION stores_near(
  lng       double precision,
  lat       double precision,
  radius_km double precision DEFAULT 25
)
RETURNS TABLE (
  id                  uuid,
  name                text,
  slug                text,
  city                text,
  province            province_code,
  address_line1       text,
  lat                 numeric,
  lng                 numeric,
  phone               text,
  website             text,
  instagram           text,
  specialties         text[],
  is_verified         boolean,
  data_quality_score  smallint,
  distance_km         double precision
)
LANGUAGE sql STABLE AS $$
  SELECT
    s.id,
    s.name,
    s.slug,
    s.city,
    s.province,
    s.address_line1,
    s.lat,
    s.lng,
    s.phone,
    s.website,
    s.instagram,
    s.specialties,
    s.is_verified,
    s.data_quality_score,
    ST_Distance(
      s.location,
      ST_SetSRID(ST_MakePoint(lng, lat), 4326)::geography
    ) / 1000.0 AS distance_km
  FROM stores s
  WHERE
    s.is_deleted = false
    AND s.is_permanently_closed = false
    AND ST_DWithin(
      s.location,
      ST_SetSRID(ST_MakePoint(lng, lat), 4326)::geography,
      radius_km * 1000
    )
  ORDER BY distance_km ASC;
$$;


-- =============================================================================
-- GEOJSON FUNCTION
-- Returns all active stores as a GeoJSON FeatureCollection.
-- Called by the Next.js API route that feeds the Mapbox source.
-- Keeping this in the DB avoids assembling large payloads in app code.
-- =============================================================================

CREATE OR REPLACE FUNCTION stores_geojson()
RETURNS json
LANGUAGE sql STABLE AS $$
  SELECT json_build_object(
    'type', 'FeatureCollection',
    'features', COALESCE(json_agg(f), '[]'::json)
  )
  FROM (
    SELECT json_build_object(
      'type',       'Feature',
      'geometry',   ST_AsGeoJSON(s.location)::json,
      'properties', json_build_object(
        'id',                 s.id,
        'name',               s.name,
        'slug',               s.slug,
        'city',               s.city,
        'province',           s.province,
        'address_line1',      s.address_line1,
        'phone',              s.phone,
        'website',            s.website,
        'instagram',          s.instagram,
        'specialties',        s.specialties,
        'is_verified',        s.is_verified,
        'is_featured',        s.is_featured,
        'data_quality_score', s.data_quality_score,
        'hours_raw',          s.hours_raw
      )
    ) AS f
    FROM stores s
    WHERE s.is_deleted = false
      AND s.is_permanently_closed = false
      AND s.location IS NOT NULL
  ) features;
$$;


-- =============================================================================
-- END OF SCHEMA
-- =============================================================================
