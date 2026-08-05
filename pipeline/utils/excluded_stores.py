# Explicit osm_ids to always exclude, regardless of tags/name (one-off cases)
EXCLUDED_OSM_IDS: set[int] = set({497225557, 383411604, 3954151948, 2415450684, 3372125716, 11263766711, 338846655, 13196769742, 9061416372, 5622497607, 6570888196, 1278853303, 83469502, 14059959501, 9049473956, 6329863984, 1867466141, 11197791364, 3583635757, 9697055394})  # e.g. {123456789}  # Example: Chapters downtown Toronto

# Substring matches (case-insensitive) against tags.brand / tags.operator / name
EXCLUDED_NAME_KEYWORDS: set[str] = {
    "chapters",
    "indigo",
    "coles",
    "smithbooks",
    "university of",
    "campus store",
    "christian book",
    "christian science",
    "catholic book",
    "gospel",
}

# OSM tags whose value excludes a store
EXCLUDED_TAG_VALUES: dict[str, set[str]] = {
    "brand": {"chapters", "indigo", "coles"},
    "operator:type": {"religious", "university"},
}

# Presence of a "religion" tag (any value) on a shop=books node excludes it
EXCLUDE_IF_RELIGION_TAG_PRESENT = True


def is_excluded(*, osm_id: int | None, name: str | None, tags: dict | None = None) -> bool:
    """Pure predicate: True if this store should never be seeded/synced."""
    if osm_id is not None and osm_id in EXCLUDED_OSM_IDS:
        return True

    tags = tags or {}
    haystacks = [name or "", tags.get("brand") or "", tags.get("operator") or ""]
    lowered = " ".join(h.lower() for h in haystacks)
    if any(kw in lowered for kw in EXCLUDED_NAME_KEYWORDS):
        return True

    for tag_key, bad_values in EXCLUDED_TAG_VALUES.items():
        val = (tags.get(tag_key) or "").lower()
        if val in bad_values:
            return True

    if EXCLUDE_IF_RELIGION_TAG_PRESENT and tags.get("religion"):
        return True

    return False
