"""
Seed job — one-time full ingest from all sources.
Safe to re-run: uses upsert logic keyed on osm_id or (name_lower, city_lower).
"""

from pipeline.db import change_log, store_sources, stores
from pipeline.sources import ciba, osm, wikidata
from pipeline.transforms import dedup, normalize, quality_score, slug
from pipeline.transforms.hours_parser import parse_osm_hours
from pipeline.utils.config import get_settings
from pipeline.utils.excluded_stores import is_excluded
from pipeline.utils.logging import get_logger
from pipeline.utils.provinces import normalize_province

log = get_logger(__name__)

SOURCE_PRIORITY = ["manual", "ciba", "alq", "google_places", "osm", "wikidata", "community_submission"]


def _priority(source: str) -> int:
    try:
        return SOURCE_PRIORITY.index(source)
    except ValueError:
        return len(SOURCE_PRIORITY)


def _build_osm_record(parsed: dict) -> dict:
    """Shape an OSM parse_element dict into a stores insert dict."""
    tags = parsed.get("tags", {})
    phone = normalize.normalize_phone(tags.get("phone") or tags.get("contact:phone"))
    website = normalize.normalize_website(tags.get("website") or tags.get("contact:website"))
    hours_raw = tags.get("opening_hours")
    hours_parsed = parse_osm_hours(hours_raw)
    province = normalize_province(
        tags.get("addr:province") or tags.get("addr:state")
    )
    return {
        "name": tags.get("name", "").strip() or None,
        "lat": parsed.get("lat"),
        "lng": parsed.get("lng"),
        "location": f"POINT({parsed.get('lng')} {parsed.get('lat')})" if parsed.get("lat") else None,
        "phone": phone,
        "website": website,
        "hours_raw": hours_raw,
        "hours_parsed": hours_parsed,
        "city": tags.get("addr:city"),
        "province": province,
        "postal_code": normalize.normalize_postal_code(tags.get("addr:postcode")),
        "osm_id": parsed.get("osm_id"),
        "source": "osm",
        "is_verified": False,
        "needs_review": False,
        "is_deleted": False,
    }


def _build_ciba_record(entry: dict) -> dict:
    province = normalize_province(entry.get("province"))
    return {
        "name": entry.get("name", "").strip() or None,
        "city": entry.get("city"),
        "province": province,
        "phone": normalize.normalize_phone(entry.get("phone")),
        "website": normalize.normalize_website(entry.get("website")),
        "source": "ciba",
        "is_verified": False,
        "needs_review": False,
        "is_deleted": False,
    }


def _build_wikidata_record(binding: dict) -> dict:
    def val(key: str) -> str | None:
        return binding.get(key, {}).get("value")

    lat = val("lat")
    lng = val("lng")
    return {
        "name": val("itemLabel"),
        "lat": float(lat) if lat else None,
        "lng": float(lng) if lng else None,
        "location": f"POINT({lng} {lat})" if lat and lng else None,
        "website": normalize.normalize_website(val("website")),
        "province": normalize_province(val("provinceLabel")),
        "source": "wikidata",
        "is_verified": False,
        "needs_review": bool(val("closed")),
        "is_deleted": False,
    }


def run_seed(dry_run: bool = False) -> None:
    settings = get_settings()
    log.info("seed_start", dry_run=dry_run)

    # --- Fetch all sources ---
    log.info("fetching_osm")
    raw_osm = osm.fetch_canadian_bookstores(settings.overpass_api_url)
    osm_parsed = [osm.parse_element(e) for e in raw_osm]
    log.info("osm_fetched", count=len(osm_parsed))

    log.info("fetching_ciba")
    ciba_data = ciba.fetch_member_list()
    log.info("ciba_fetched", count=len(ciba_data))

    log.info("fetching_wikidata")
    wikidata_data = wikidata.fetch_canadian_bookstores()
    log.info("wikidata_fetched", count=len(wikidata_data))

    # --- Build unified record map ---
    # Key: osm_id (int) when available, else (name_lower, city_lower)
    record_map: dict = {}  # key → {"record": dict, "source_data": dict, "source_name": str}

    for parsed in osm_parsed:
        record = _build_osm_record(parsed)
        if not record.get("name"):
            continue
        if is_excluded(osm_id=parsed.get("osm_id"), name=record["name"], tags=parsed.get("tags")):
            continue
        key = parsed["osm_id"]
        record_map[key] = {"record": record, "raw": parsed, "source": "osm"}

    for entry in ciba_data:
        record = _build_ciba_record(entry)
        if not record.get("name"):
            continue
        if is_excluded(osm_id=None, name=record["name"]):
            continue
        name_city = (record["name"].lower(), (record.get("city") or "").lower())
        # Check if already in map via osm_id match — merge if higher priority
        existing_key = _find_existing_key(record_map, name_city, record.get("province"))
        if existing_key is not None:
            existing = record_map[existing_key]
            if _priority("ciba") < _priority(existing["source"]):
                record_map[existing_key] = {"record": {**existing["record"], **_non_null(record)}, "raw": entry, "source": "ciba"}
        else:
            record_map[name_city] = {"record": record, "raw": entry, "source": "ciba"}

    for binding in wikidata_data:
        record = _build_wikidata_record(binding)
        if not record.get("name"):
            continue
        if is_excluded(osm_id=None, name=record["name"]):
            continue
        name_city = (record["name"].lower(), "")
        existing_key = _find_existing_key(record_map, name_city, record.get("province"))
        if existing_key is None:
            record_map[name_city] = {"record": record, "raw": binding, "source": "wikidata"}

    log.info("deduplication_complete", unique_stores=len(record_map))

    # --- Pre-fetch existing slugs ---
    existing_slugs: set[str] = set() if dry_run else stores.get_all_slugs()

    inserted = updated = skipped = 0

    for key, item in record_map.items():
        record = item["record"]
        source_name = item["source"]
        raw_data = item["raw"]

        if not record.get("name"):
            skipped += 1
            continue
        if source_name != "ciba" and (not record.get("lat") or not record.get("lng")):
            skipped += 1
            continue
        if source_name == "ciba" and (not record.get("lat") or not record.get("lng")):
            record["needs_review"] = True

        # Compute slug
        city = record.get("city") or ""
        province = record.get("province") or ""
        base = slug.generate_slug(record["name"], city, province)
        unique = slug.make_unique_slug(base, existing_slugs)
        existing_slugs.add(unique)
        record["slug"] = unique

        # Compute quality score
        record["data_quality_score"] = quality_score.compute_quality_score(record)

        if dry_run:
            log.info("dry_run_would_insert", name=record["name"], slug=unique)
            inserted += 1
            continue

        # Check for existing store by osm_id
        existing = None
        if isinstance(key, int):
            existing = stores.get_store_by_osm_id(key)

        if existing:
            diff = _compute_diff(existing, record)
            if diff:
                new_values = {field: change["to"] for field, change in diff.items()}
                stores.update_store(existing["id"], new_values)
                change_log.write_update(existing["id"], diff, source_name)
                updated += 1
            else:
                skipped += 1
        else:
            inserted_row = stores.insert_store(record)
            store_id = inserted_row["id"]
            change_log.write_insert(store_id, record, source_name)
            if source_name == "wikidata" and record.get("needs_review"):
                change_log.write_flag_review(
                    store_id, "wikidata has a dissolution date (P576)", source_name
                )
            store_sources.upsert_source(
                store_id,
                source_name,
                str(raw_data.get("external_id") or raw_data.get("osm_id") or ""),
                raw_data if isinstance(raw_data, dict) else {},
            )
            inserted += 1

    log.info("seed_complete", inserted=inserted, updated=updated, skipped=skipped)


def _non_null(record: dict) -> dict:
    """Return only non-None fields from record."""
    return {k: v for k, v in record.items() if v is not None}


def _find_existing_key(record_map: dict, name_city: tuple, province: str | None = None) -> object | None:
    """Check if a (name, city) tuple is already represented in the map, exactly or fuzzily."""
    if name_city in record_map:
        return name_city
    name, _city = name_city
    candidates = [
        {"key": key, "name": value["record"]["name"], "province": value["record"].get("province")}
        for key, value in record_map.items()
    ]
    match = dedup.find_fuzzy_match(name, province, candidates)
    return match["key"] if match else None


def _compute_diff(existing: dict, new: dict) -> dict:
    """Return {field: {from, to}} for fields that changed."""
    skip = {"id", "created_at", "updated_at", "slug", "is_permanently_closed", "is_verified", "needs_review"}
    diff = {}
    for key, new_val in new.items():
        if key in skip or new_val is None:
            continue
        old_val = existing.get(key)
        if old_val != new_val:
            diff[key] = {"from": old_val, "to": new_val}
    return diff
