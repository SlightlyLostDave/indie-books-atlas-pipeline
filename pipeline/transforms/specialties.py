"""Map OSM tags onto the specialty_tags controlled vocabulary. Pure functions only."""

VOCABULARY = frozenset(
    {
        "used",
        "antiquarian",
        "childrens",
        "francophone",
        "indigenous",
        "lgbtq",
        "genre_fiction",
        "academic",
        "art_design",
        "multilingual",
        "comics_graphic",
        "mystery_crime",
        "sci_fi_fantasy",
        "travel",
        "religion_spirit",
        "nature_outdoors",
        "history",
        "feminist",
        "zines",
    }
)

# Values of the OSM `books=*` tag (semicolon-separated) → vocabulary value.
_BOOKS_TAG_MAP = {
    "used": "used",
    "second_hand": "used",
    "antiquarian": "antiquarian",
    "rare": "antiquarian",
    "children": "childrens",
    "childrens": "childrens",
    "comic": "comics_graphic",
    "comics": "comics_graphic",
    "manga": "comics_graphic",
    "graphic_novel": "comics_graphic",
    "religion": "religion_spirit",
    "religious": "religion_spirit",
    "travel": "travel",
    "art": "art_design",
    "academic": "academic",
    "history": "history",
    "lgbtq": "lgbtq",
    "lgbt": "lgbtq",
    "feminist": "feminist",
    "zines": "zines",
    "zine": "zines",
    "science_fiction": "sci_fi_fantasy",
    "fantasy": "sci_fi_fantasy",
    "crime": "mystery_crime",
    "mystery": "mystery_crime",
}

_YES = {"yes", "only", "main"}


def _split(value: object) -> list[str]:
    if not isinstance(value, str):
        return []
    return [v.strip().lower() for v in value.split(";") if v.strip()]


def specialties_from_osm_tags(tags: dict | None) -> list[str] | None:
    """
    Return a sorted list of vocabulary values derived from OSM tags, or None if
    nothing maps. Unknown tag values are dropped — never free text.
    """
    if not tags:
        return None

    found: set[str] = set()
    if (tags.get("second_hand") or "").strip().lower() in _YES:
        found.add("used")
    for value in _split(tags.get("books")):
        mapped = _BOOKS_TAG_MAP.get(value)
        if mapped:
            found.add(mapped)
    if (tags.get("language:fr") or "").strip().lower() in _YES:
        found.add("francophone")

    found &= VOCABULARY
    return sorted(found) or None


def resolve_specialties(existing: list[str] | None, from_osm: list[str] | None) -> list[str] | None:
    """
    OSM may only seed specialties on a store that has none. Once a store has any
    specialties (possibly curated by a human), OSM never changes them.
    Returns the value to write, or None for "leave as is".
    """
    if existing:
        return None
    return from_osm
