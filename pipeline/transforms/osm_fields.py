"""
Map a parsed OSM element (osm.parse_element output) onto `stores` columns.
Shared by seed and sync_osm so both jobs map OSM tags identically. Pure — no I/O.
"""

from pipeline.transforms import normalize
from pipeline.transforms.hours_parser import parse_osm_hours
from pipeline.transforms.specialties import specialties_from_osm_tags
from pipeline.utils.provinces import normalize_province, province_from_postal_code

SHORT_DESCRIPTION_MAX = 300


def _first(tags: dict, *keys: str) -> str | None:
    for key in keys:
        value = tags.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _short_description(tags: dict) -> str | None:
    raw = _first(tags, "description", "description:en", "description:fr")
    if not raw:
        return None
    text = " ".join(raw.split())
    if len(text) <= SHORT_DESCRIPTION_MAX:
        return text
    cut = text[: SHORT_DESCRIPTION_MAX - 1].rsplit(" ", 1)[0]
    return f"{cut}…"


def _province(tags: dict, postal_code: str | None) -> str | None:
    for key in ("addr:province", "addr:state", "is_in:province", "is_in:state_code", "is_in:state"):
        code = normalize_province(tags.get(key))
        if code:
            return code
    return province_from_postal_code(postal_code)


def osm_element_to_fields(parsed: dict) -> dict:
    """Return the `stores` fields derivable from one parsed OSM element."""
    tags = parsed.get("tags") or {}
    lat, lng = parsed.get("lat"), parsed.get("lng")
    hours_raw = tags.get("opening_hours")
    postal_code = normalize.normalize_postal_code(tags.get("addr:postcode"))
    address_line1, address_line2 = normalize.build_address_lines(tags)

    return {
        "name": (tags.get("name") or "").strip() or None,
        "lat": lat,
        "lng": lng,
        "location": f"POINT({lng} {lat})" if lat is not None and lng is not None else None,
        "phone": normalize.normalize_phone(
            _first(tags, "phone", "contact:phone", "contact:mobile", "mobile")
        ),
        "website": normalize.normalize_website(_first(tags, "website", "contact:website", "url")),
        "instagram": normalize.normalize_instagram(_first(tags, "contact:instagram", "instagram")),
        "short_description": _short_description(tags),
        "specialties": specialties_from_osm_tags(tags),
        "hours_raw": hours_raw,
        "hours_parsed": parse_osm_hours(hours_raw),
        "address_line1": address_line1,
        "address_line2": address_line2,
        "city": _first(tags, "addr:city", "is_in:city", "addr:place"),
        "province": _province(tags, postal_code),
        "postal_code": postal_code,
    }
