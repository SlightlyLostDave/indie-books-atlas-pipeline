from slugify import slugify as _slugify


def generate_slug(name: str, city: str, province_code: str) -> str:
    """
    Generate a URL-safe slug from name + city + province code.
    Example: "The Bookshelf", "Guelph", "ON" → "the-bookshelf-guelph-on"
    """
    combined = f"{name} {city} {province_code}"
    return _slugify(combined, allow_unicode=False)


def make_unique_slug(base_slug: str, existing_slugs: set[str]) -> str:
    """
    Return base_slug if available, else append -2, -3, etc. until unique.
    Pure function — does not query the DB.
    """
    if base_slug not in existing_slugs:
        return base_slug
    counter = 2
    while True:
        candidate = f"{base_slug}-{counter}"
        if candidate not in existing_slugs:
            return candidate
        counter += 1
