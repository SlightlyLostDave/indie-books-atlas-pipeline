"""
Weekly OSM diff sync.
Categorizes stores as new / changed / missing and handles each accordingly.
"""

from pipeline.db import change_log, store_sources, stores
from pipeline.sources import osm
from pipeline.transforms import normalize, quality_score, slug
from pipeline.transforms.hours_parser import parse_osm_hours
from pipeline.utils.config import get_settings
from pipeline.utils.logging import get_logger
from pipeline.utils.provinces import normalize_province

log = get_logger(__name__)

_PROTECTED_FIELDS = {"slug", "is_permanently_closed", "is_verified", "needs_review", "source"}
_MANUAL_SOURCES = {"manual", "ciba", "alq"}


def _osm_element_to_fields(parsed: dict) -> dict:
    """Convert a parsed OSM element to a flat fields dict for diffing."""
    tags = parsed.get("tags", {})
    hours_raw = tags.get("opening_hours")
    return {
        "name": tags.get("name", "").strip() or None,
        "lat": parsed.get("lat"),
        "lng": parsed.get("lng"),
        "location": f"POINT({parsed.get('lng')} {parsed.get('lat')})" if parsed.get("lat") else None,
        "phone": normalize.normalize_phone(tags.get("phone") or tags.get("contact:phone")),
        "website": normalize.normalize_website(tags.get("website") or tags.get("contact:website")),
        "hours_raw": hours_raw,
        "hours_parsed": parse_osm_hours(hours_raw),
        "city": tags.get("addr:city"),
        "province": normalize_province(tags.get("addr:province") or tags.get("addr:state")),
        "postal_code": normalize.normalize_postal_code(tags.get("addr:postcode")),
    }


def _compute_diff(existing: dict, new_fields: dict) -> dict:
    """Return {field: {from, to}} for changed fields only."""
    diff = {}
    for key, new_val in new_fields.items():
        if key in _PROTECTED_FIELDS or new_val is None:
            continue
        old_val = existing.get(key)
        if old_val != new_val:
            diff[key] = {"from": old_val, "to": new_val}
    return diff


def run_sync_osm(dry_run: bool = False) -> None:
    settings = get_settings()
    log.info("sync_osm_start", dry_run=dry_run)

    # --- Fetch Overpass ---
    log.info("fetching_overpass")
    raw_elements = osm.fetch_canadian_bookstores(settings.overpass_api_url)
    parsed_elements = [osm.parse_element(e) for e in raw_elements]
    overpass_map: dict[int, dict] = {e["osm_id"]: e for e in parsed_elements}
    overpass_ids = set(overpass_map.keys())
    log.info("overpass_fetched", count=len(overpass_ids))

    # --- Fetch current DB state ---
    db_ids = stores.get_all_osm_ids()
    log.info("db_osm_ids_fetched", count=len(db_ids))

    new_ids = overpass_ids - db_ids
    present_ids = overpass_ids & db_ids
    missing_ids = db_ids - overpass_ids

    log.info("diff_categorized", new=len(new_ids), changed_candidates=len(present_ids), missing=len(missing_ids))

    inserted = updated = flagged = skipped = 0
    existing_slugs: set[str] = set() if dry_run else stores.get_all_slugs()

    # --- Insert new stores ---
    for osm_id in new_ids:
        parsed = overpass_map[osm_id]
        fields = _osm_element_to_fields(parsed)

        if not fields.get("name") or not fields.get("lat") or not fields.get("lng"):
            skipped += 1
            continue

        city = fields.get("city") or ""
        province = fields.get("province") or ""
        base = slug.generate_slug(fields["name"], city, province)
        unique = slug.make_unique_slug(base, existing_slugs)
        existing_slugs.add(unique)

        record = {
            **fields,
            "osm_id": osm_id,
            "slug": unique,
            "source": "osm",
            "is_verified": False,
            "is_deleted": False,
        }
        record["data_quality_score"] = quality_score.compute_quality_score(record)
        record["needs_review"] = record["data_quality_score"] < 40

        if dry_run:
            log.info("dry_run_would_insert", osm_id=osm_id, name=fields.get("name"))
            inserted += 1
            continue

        inserted_row = stores.insert_store(record)
        store_id = inserted_row["id"]
        change_log.write_insert(store_id, record, "osm")
        store_sources.upsert_source(store_id, "osm", parsed["external_id"], parsed)
        if record["needs_review"]:
            log.info("new_store_needs_review", osm_id=osm_id, score=record["data_quality_score"])
        inserted += 1

    # --- Update changed stores ---
    for osm_id in present_ids:
        parsed = overpass_map[osm_id]
        existing = stores.get_store_by_osm_id(osm_id)
        if not existing:
            skipped += 1
            continue

        # Never overwrite fields from higher-priority sources
        if existing.get("source") in _MANUAL_SOURCES:
            skipped += 1
            continue

        new_fields = _osm_element_to_fields(parsed)
        diff = _compute_diff(existing, new_fields)

        if not diff:
            skipped += 1
            continue

        new_score = quality_score.compute_quality_score({**existing, **new_fields})
        diff["data_quality_score"] = {"from": existing.get("data_quality_score"), "to": new_score}

        if dry_run:
            log.info("dry_run_would_update", osm_id=osm_id, fields=list(diff.keys()))
            updated += 1
            continue

        update_payload = {k: v["to"] for k, v in diff.items()}
        stores.update_store(existing["id"], update_payload)
        change_log.write_update(existing["id"], diff, "osm")
        store_sources.upsert_source(existing["id"], "osm", parsed["external_id"], parsed)
        updated += 1

    # --- Flag missing stores ---
    for osm_id in missing_ids:
        existing = stores.get_store_by_osm_id(osm_id)
        if not existing:
            continue

        if dry_run:
            log.info("dry_run_would_flag", osm_id=osm_id)
            flagged += 1
            continue

        stores.flag_needs_review(existing["id"])
        change_log.write_flag_review(
            existing["id"],
            f"osm_id {osm_id} missing from Overpass results",
            "osm",
        )
        flagged += 1

    log.info(
        "sync_osm_complete",
        inserted=inserted,
        updated=updated,
        flagged=flagged,
        skipped=skipped,
    )
