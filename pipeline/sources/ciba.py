# FRAGILE: depends on CIBA page structure — https://cibabooks.ca
# Returns [] on any failure so seed continues uninterrupted.

import re
from html.parser import HTMLParser

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from pipeline.utils.logging import get_logger

_BASE_URL = "https://cibabooks.ca"
log = get_logger(__name__)


class _MemberParser(HTMLParser):
    """Minimal HTML parser that extracts member store data from the CIBA directory."""

    def __init__(self) -> None:
        super().__init__()
        self.stores: list[dict] = []
        self._current: dict | None = None
        self._capture_field: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple]) -> None:
        attr_dict = dict(attrs)
        classes = attr_dict.get("class", "")
        if "member-listing" in classes or "member-card" in classes:
            self._current = {}
        elif self._current is not None:
            if "member-name" in classes or "store-name" in classes:
                self._capture_field = "name"
            elif "member-city" in classes or "store-city" in classes:
                self._capture_field = "city"
            elif "member-province" in classes or "store-province" in classes:
                self._capture_field = "province"
            elif tag == "a" and "href" in attr_dict:
                href = attr_dict["href"]
                if href.startswith("http") and "instagram" not in href and "facebook" not in href:
                    self._current["website"] = href
                elif "tel:" in href:
                    self._current["phone"] = href.replace("tel:", "").strip()

    def handle_endtag(self, tag: str) -> None:
        if tag in ("article", "div") and self._current and self._current.get("name"):
            self.stores.append(self._current)
            self._current = None
        self._capture_field = None

    def handle_data(self, data: str) -> None:
        if self._capture_field and self._current is not None:
            text = data.strip()
            if text:
                self._current[self._capture_field] = text
            self._capture_field = None


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=30))
def _fetch_html(url: str) -> str:
    with httpx.Client(timeout=30.0) as client:
        response = client.get(
            url,
            follow_redirects=True,
            headers={"User-Agent": "indie-books-atlas-pipeline/0.1 (https://indiebooksatlas.ca)"},
        )
        response.raise_for_status()
        return response.text


def fetch_member_list(base_url: str = _BASE_URL) -> list[dict]:
    """
    Fetch and parse the CIBA member directory.
    Returns [] on any failure — never raises.
    """
    try:
        html = _fetch_html(f"{base_url}/member-directory/")
        parser = _MemberParser()
        parser.feed(html)
        stores = parser.stores

        # Fallback: if the HTML parser found nothing, attempt a simple regex pass
        # on common patterns like "Store Name, City, Province"
        if not stores:
            stores = _regex_fallback(html)

        log.info("ciba_fetch_complete", count=len(stores))
        return stores
    except Exception as exc:
        log.warning("ciba_fetch_failed", error=str(exc))
        return []


def _regex_fallback(html: str) -> list[dict]:
    """Last-resort regex extraction when the HTML parser yields nothing."""
    results = []
    for match in re.finditer(
        r'<h[23][^>]*>(.*?)</h[23]>.*?<p[^>]*>(.*?),\s*([A-Z]{2})\s*</p>',
        html,
        re.DOTALL,
    ):
        name = re.sub(r"<[^>]+>", "", match.group(1)).strip()
        city = re.sub(r"<[^>]+>", "", match.group(2)).strip()
        province = match.group(3).strip()
        if name:
            results.append({"name": name, "city": city, "province": province})
    return results
