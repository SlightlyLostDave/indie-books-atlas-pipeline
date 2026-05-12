import re

import phonenumbers

_POSTAL_RE = re.compile(r"^([A-Za-z]\d[A-Za-z])\s*(\d[A-Za-z]\d)$")
_INSTAGRAM_URL_RE = re.compile(
    r"(?:https?://)?(?:www\.)?instagram\.com/([A-Za-z0-9_.]+)/?", re.IGNORECASE
)


def normalize_phone(raw: str | None, default_region: str = "CA") -> str | None:
    """Return E.164 phone string or None if unparseable. Never raises."""
    if not raw:
        return None
    try:
        number = phonenumbers.parse(raw, default_region)
        if phonenumbers.is_valid_number(number):
            return phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164)
        return None
    except phonenumbers.NumberParseException:
        return None


def normalize_postal_code(raw: str | None) -> str | None:
    """Return 'A1A 1A1' formatted Canadian postal code or None if invalid."""
    if not raw:
        return None
    match = _POSTAL_RE.match(raw.strip())
    if not match:
        return None
    return f"{match.group(1).upper()} {match.group(2).upper()}"


def normalize_website(raw: str | None) -> str | None:
    """Ensure URL has https scheme. Return None if empty."""
    if not raw:
        return None
    url = raw.strip().rstrip("/")
    if not url:
        return None
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"
    return url


def normalize_instagram(raw: str | None) -> str | None:
    """Return bare Instagram handle without @ or URL prefix. None if empty."""
    if not raw:
        return None
    url_match = _INSTAGRAM_URL_RE.search(raw)
    if url_match:
        return url_match.group(1)
    handle = raw.strip().lstrip("@")
    return handle if handle else None
