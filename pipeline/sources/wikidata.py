import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

_SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"

SPARQL_QUERY = """
SELECT ?item ?itemLabel ?lat ?lng ?osm_id ?website ?inception ?provinceLabel ?closed WHERE {
  ?item wdt:P31/wdt:P279* wd:Q200764 .
  ?item wdt:P17 wd:Q16 .
  ?item wdt:P625 ?coord .
  BIND(geof:latitude(?coord) AS ?lat)
  BIND(geof:longitude(?coord) AS ?lng)
  OPTIONAL { ?item wdt:P402 ?osm_id }
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P571 ?inception }
  OPTIONAL { ?item wdt:P131* ?province . ?province wdt:P31 wd:Q11828004 . }
  OPTIONAL { ?item wdt:P576 ?closed }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,fr". }
}
"""


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=30))
def fetch_canadian_bookstores(sparql_endpoint: str = _SPARQL_ENDPOINT) -> list[dict]:
    """
    Run SPARQL query against Wikidata and return raw binding dicts.
    Each dict has keys matching the SELECT variables.
    """
    with httpx.Client(timeout=60.0) as client:
        response = client.get(
            sparql_endpoint,
            params={"query": SPARQL_QUERY.strip(), "format": "json"},
            headers={
                "Accept": "application/sparql-results+json",
                "User-Agent": "indie-books-atlas-pipeline/0.1 (https://indiebooksatlas.ca)",
            },
        )
        response.raise_for_status()
        data = response.json()
        return data.get("results", {}).get("bindings", [])
