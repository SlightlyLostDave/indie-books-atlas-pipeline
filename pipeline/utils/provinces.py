NAME_TO_CODE: dict[str, str] = {
    "Alberta": "AB",
    "British Columbia": "BC",
    "Manitoba": "MB",
    "New Brunswick": "NB",
    "Newfoundland and Labrador": "NL",
    "Northwest Territories": "NT",
    "Nova Scotia": "NS",
    "Nunavut": "NU",
    "Ontario": "ON",
    "Prince Edward Island": "PE",
    "Quebec": "QC",
    "Saskatchewan": "SK",
    "Yukon": "YT",
}

CODE_TO_NAME: dict[str, str] = {v: k for k, v in NAME_TO_CODE.items()}

_ALL_CODES = set(NAME_TO_CODE.values())


def normalize_province(raw: str | None) -> str | None:
    """Return two-letter province code from either a full name or existing code."""
    if not raw:
        return None
    stripped = raw.strip()
    upper = stripped.upper()
    if upper in _ALL_CODES:
        return upper
    return NAME_TO_CODE.get(stripped)
