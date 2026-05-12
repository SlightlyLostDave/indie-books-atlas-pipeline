"""
Monthly Google Places enrichment job.
Fetches current phone/hours/website for stores with a google_place_id.
"""

import time

from pipeline.db import change_log, store_sources, stores
from pipeline.sources import google_places
from pipeline.transforms import normalize, quality_score
from pipeline.transforms.hours_parser import parse_google_hours
from pipeline.utils.config import get_settings
from pipeline.utils.logging import get_logger

log = get_logger(__name__)

_RATE_LIMIT_DELAY = 0.1  # 10 requests/second


def _extract_enrichment(place_data: dict) -> dict:
    """Pull phone, website, and hours out of a Places API v1 response."""
    phone = normalize.normalize_phone(place_data.get("internationalPhoneNumber"))
    website = normalize.normalize_website(place_data.get("websiteUri"))
    periods = (place_data.get("regularOpeningHours") or {}).get("periods")
    hours_parsed = parse_google_hours(periods)
    return {
        "phone": phone,
        "website": website,
        "hours_parsed": hours_parsed,
    }


def _compute_diff(existing: dict, enrichment: dict) -> dict:
    diff = {}
    for key, new_val in enrichment.items():
        if new_val is None:
            continue
        old_val = existing.get(key)
        if old_val != new_val:
            diff[key] = {"from": old_val, "to": new_val}
    return diff


def run_enrich_google(dry_run: bool = False) -> None:
    settings = get_settings()
    if not settings.google_places_api_key:
        log.error("google_places_api_key_missing")
        return

    log.info("enrich_google_start", dry_run=dry_run)

    target_stores = stores.get_stores_with_google_place_id()
    log.info("stores_to_enrich", count=len(target_stores))

    updated = unchanged = errors = 0

    for store in target_stores:
        place_id = store["google_place_id"]
        store_id = store["id"]
        try:
            place_data = google_places.fetch_place_details(
                place_id, settings.google_places_api_key
            )
            enrichment = _extract_enrichment(place_data)
            diff = _compute_diff(store, enrichment)

            if not diff:
                unchanged += 1
            elif dry_run:
                log.info("dry_run_would_update", store_id=store_id, fields=list(diff.keys()))
                updated += 1
            else:
                update_payload = {k: v["to"] for k, v in diff.items()}
                new_score = quality_score.compute_quality_score({**store, **update_payload})
                if new_score != store.get("data_quality_score"):
                    update_payload["data_quality_score"] = new_score
                    diff["data_quality_score"] = {
                        "from": store.get("data_quality_score"),
                        "to": new_score,
                    }
                stores.update_store(store_id, update_payload)
                change_log.write_update(store_id, diff, "google_places")
                store_sources.upsert_source(store_id, "google_places", place_id, place_data)
                updated += 1

        except Exception as exc:
            log.warning("enrich_google_error", store_id=store_id, place_id=place_id, error=str(exc))
            errors += 1

        time.sleep(_RATE_LIMIT_DELAY)

    log.info("enrich_google_complete", updated=updated, unchanged=unchanged, errors=errors)
