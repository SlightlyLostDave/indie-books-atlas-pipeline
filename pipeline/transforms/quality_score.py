def compute_quality_score(record: dict) -> int:
    """
    Compute data_quality_score (0-100).
    +20: phone, website, hours_raw, is_verified (bool True only)
    +10: short_description, instagram
    """
    score = 0
    if record.get("phone"):
        score += 20
    if record.get("website"):
        score += 20
    if record.get("hours_raw"):
        score += 20
    if record.get("is_verified") is True:
        score += 20
    if record.get("short_description"):
        score += 10
    if record.get("instagram"):
        score += 10
    return score
