# Uses Google Places API v1 (places.googleapis.com/v1/places/{place_id}).
# Field selection via X-Goog-FieldMask header to control billing.

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

_BASE_URL = "https://places.googleapis.com/v1/places"
_DEFAULT_FIELDS = "name,internationalPhoneNumber,regularOpeningHours,websiteUri"


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=30))
def fetch_place_details(
    place_id: str,
    api_key: str,
    fields: str = _DEFAULT_FIELDS,
) -> dict:
    """
    Fetch a single place from Google Places API v1.
    Returns raw API response dict.
    """
    url = f"{_BASE_URL}/{place_id}"
    with httpx.Client(timeout=30.0) as client:
        response = client.get(
            url,
            headers={
                "X-Goog-Api-Key": api_key,
                "X-Goog-FieldMask": fields,
            },
        )
        response.raise_for_status()
        return response.json()
