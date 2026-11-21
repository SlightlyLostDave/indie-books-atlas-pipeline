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
    return NAME_TO_CODE.get(stripped) or NAME_TO_CODE.get(_ALIASES.get(stripped.lower(), ""))


_ALIASES: dict[str, str] = {
    "québec": "Quebec",
    "quebec": "Quebec",
    "ontario": "Ontario",
    "british columbia": "British Columbia",
    "colombie-britannique": "British Columbia",
    "alberta": "Alberta",
    "manitoba": "Manitoba",
    "saskatchewan": "Saskatchewan",
    "nova scotia": "Nova Scotia",
    "nouvelle-écosse": "Nova Scotia",
    "new brunswick": "New Brunswick",
    "nouveau-brunswick": "New Brunswick",
    "prince edward island": "Prince Edward Island",
    "île-du-prince-édouard": "Prince Edward Island",
    "newfoundland and labrador": "Newfoundland and Labrador",
    "terre-neuve-et-labrador": "Newfoundland and Labrador",
    "yukon": "Yukon",
    "northwest territories": "Northwest Territories",
    "territoires du nord-ouest": "Northwest Territories",
    "nunavut": "Nunavut",
}

# First letter of a Canadian postal code (FSA) → province.
_POSTAL_PREFIX: dict[str, str] = {
    "A": "NL",
    "B": "NS",
    "C": "PE",
    "E": "NB",
    "G": "QC",
    "H": "QC",
    "J": "QC",
    "K": "ON",
    "L": "ON",
    "M": "ON",
    "N": "ON",
    "P": "ON",
    "R": "MB",
    "S": "SK",
    "T": "AB",
    "V": "BC",
    "Y": "YT",
}
_NUNAVUT_FSAS = {"X0A", "X0B", "X0C"}


def province_from_postal_code(postal_code: str | None) -> str | None:
    """Derive province code from a Canadian postal code's first letter(s). Never raises."""
    if not postal_code or not isinstance(postal_code, str):
        return None
    code = postal_code.strip().upper()
    if not code:
        return None
    if code[0] == "X":
        return "NU" if code[:3] in _NUNAVUT_FSAS else "NT"
    return _POSTAL_PREFIX.get(code[0])
