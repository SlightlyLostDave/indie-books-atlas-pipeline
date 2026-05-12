import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

OVERPASS_QUERY = """
[out:json];
area["ISO3166-1"="CA"]->.canada;
(
  node["shop"="books"](area.canada);
  way["shop"="books"](area.canada);
);
out body center;
"""


@retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=2, min=4, max=60))
def fetch_canadian_bookstores(overpass_url: str) -> list[dict]:
    """
    POST the Overpass query and return the raw elements list.
    Each element is exactly as returned — no normalization.
    """
    with httpx.Client(timeout=120.0) as client:
        response = client.post(overpass_url, data={"data": OVERPASS_QUERY})
        response.raise_for_status()
        return response.json().get("elements", [])


def parse_element(element: dict) -> dict:
    """
    Flatten a single Overpass element to a minimal dict.
    way elements carry lat/lng in element["center"]; node elements use top-level lat/lon.
    external_id uses "type/id" format to avoid collisions across element types.
    """
    osm_type = element.get("type", "node")
    osm_id = element["id"]

    if osm_type == "way":
        center = element.get("center", {})
        lat = center.get("lat")
        lng = center.get("lon")
    else:
        lat = element.get("lat")
        lng = element.get("lon")

    return {
        "osm_id": int(osm_id),
        "osm_type": osm_type,
        "external_id": f"{osm_type}/{osm_id}",
        "lat": lat,
        "lng": lng,
        "tags": element.get("tags", {}),
    }
