"""
OSM opening_hours → hours_parsed JSONB converter.

Strategy:
1. Handle None / empty → None.
2. Handle "24/7" as a special case.
3. Detect prose strings ("by appointment", etc.) → None.
4. Attempt structured parsing via _parse_osm_string (regex-based fast path).
5. Any failure returns None; hours_raw is always preserved by the caller.

parse_google_hours handles Google Places API regularOpeningHours.periods.
"""

import re

_ALL_DAYS = ["mo", "tu", "we", "th", "fr", "sa", "su"]

_DAY_ABBR = {
    "Mo": "mo", "Tu": "tu", "We": "we", "Th": "th",
    "Fr": "fr", "Sa": "sa", "Su": "su", "PH": "ph",
}

# Google Places day index: 0=Sunday, 1=Monday, ..., 6=Saturday
_GOOGLE_DAY_MAP = {0: "su", 1: "mo", 2: "tu", 3: "we", 4: "th", 5: "fr", 6: "sa"}

_PROSE_PATTERNS = re.compile(
    r"by appointment|call ahead|phone|on request|seasonal|varies|see website|closed",
    re.IGNORECASE,
)

_TIME_RE = r"(\d{1,2}:\d{2})"
_RANGE_RE = re.compile(rf"{_TIME_RE}-{_TIME_RE}")
_DAY_ABBRS = "|".join(_DAY_ABBR.keys())
_DAY_RANGE_RE = re.compile(rf"({_DAY_ABBRS})-({_DAY_ABBRS})")
_DAY_LIST_RE = re.compile(rf"((?:(?:{_DAY_ABBRS}),?)+)")


def _expand_day_range(start: str, end: str) -> list[str]:
    """Expand e.g. Mo-Fr into [mo, tu, we, th, fr]."""
    keys = _ALL_DAYS
    s_idx = keys.index(_DAY_ABBR[start])
    e_idx = keys.index(_DAY_ABBR[end])
    if s_idx <= e_idx:
        return keys[s_idx : e_idx + 1]
    # Wrap-around (e.g. Fr-Mo) — uncommon but handle gracefully
    return keys[s_idx:] + keys[: e_idx + 1]


def _parse_rule(rule: str) -> dict[str, dict]:
    """
    Parse a single OSM rule segment like 'Mo-Fr 09:00-17:30' or 'Sa 10:00-14:00'.
    Returns a dict of {day_key: {open, close, closed}} entries.
    """
    rule = rule.strip()
    result: dict[str, dict] = {}

    # Check for explicit "off" / "closed"
    if re.search(r"\boff\b|\bclosed\b", rule, re.IGNORECASE):
        # Determine which days
        days = _extract_days(rule)
        for day in days:
            result[day] = {"closed": True}
        return result

    time_match = _RANGE_RE.search(rule)
    if not time_match:
        return result

    open_time = time_match.group(1)
    close_time = time_match.group(2)
    days = _extract_days(rule)
    for day in days:
        result[day] = {"open": open_time, "close": close_time, "closed": False}
    return result


def _extract_days(rule: str) -> list[str]:
    """Return day keys covered by a rule string."""
    days: list[str] = []
    range_match = _DAY_RANGE_RE.search(rule)
    if range_match:
        days = _expand_day_range(range_match.group(1), range_match.group(2))
    else:
        for abbr, key in _DAY_ABBR.items():
            if re.search(rf"\b{abbr}\b", rule):
                days.append(key)
    return days


def _is_prose(raw: str) -> bool:
    return bool(_PROSE_PATTERNS.search(raw))


def parse_osm_hours(raw: str | None) -> dict | None:
    """
    Convert an OSM opening_hours string to hours_parsed shape.
    Returns None for None, empty, prose, or unparseable strings.
    Never raises.
    """
    if not raw:
        return None
    raw = raw.strip()
    if not raw:
        return None

    # 24/7 shortcut
    if raw == "24/7":
        return {day: {"open": "00:00", "close": "23:59", "closed": False} for day in _ALL_DAYS}

    if _is_prose(raw):
        return None

    try:
        result: dict[str, dict] = {}
        # Split on semicolons into individual rules
        rules = [r.strip() for r in raw.split(";") if r.strip()]
        for rule in rules:
            # Skip PH-only rules that don't represent a weekday
            parsed = _parse_rule(rule)
            result.update(parsed)
        # An empty result for a non-trivial string → treat as unparseable
        if not result and raw:
            return None
        return result if result else None
    except Exception:
        return None


def parse_google_hours(periods: list[dict] | None) -> dict | None:
    """
    Convert Google Places regularOpeningHours.periods to hours_parsed shape.
    periods entry: {"open": {"day": int, "hour": int, "minute": int},
                    "close": {"day": int, "hour": int, "minute": int}}
    Google day: 0=Sunday, 1=Monday, ..., 6=Saturday.
    Returns None if periods is None or empty.
    """
    if not periods:
        return None
    try:
        result: dict[str, dict] = {}
        for period in periods:
            open_info = period.get("open", {})
            close_info = period.get("close", {})
            day_key = _GOOGLE_DAY_MAP.get(open_info.get("day"))
            if day_key is None:
                continue
            open_time = f"{open_info.get('hour', 0):02d}:{open_info.get('minute', 0):02d}"
            close_time = f"{close_info.get('hour', 0):02d}:{close_info.get('minute', 0):02d}"
            result[day_key] = {"open": open_time, "close": close_time, "closed": False}
        return result if result else None
    except Exception:
        return None
