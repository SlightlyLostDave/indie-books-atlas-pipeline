from difflib import SequenceMatcher

_SIMILARITY_THRESHOLD = 0.8


def name_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def find_fuzzy_match(name: str, province: str | None, candidates: list[dict]) -> dict | None:
    """
    Find the best-matching candidate by name, restricted to the same province
    when both sides have one (avoids cross-country false positives).
    candidates: [{"key": ..., "name": ..., "province": ...}, ...]
    Returns the single best match at/above the similarity threshold, or None.
    """
    best_match = None
    best_score = _SIMILARITY_THRESHOLD
    for candidate in candidates:
        candidate_province = candidate.get("province")
        if province and candidate_province and province != candidate_province:
            continue
        score = name_similarity(name, candidate["name"])
        if score >= best_score:
            best_score = score
            best_match = candidate
    return best_match
