# FRAGILE: the CIBA directory (https://cibabooks.ca/member-directory/) is a Wild Apricot
# "Member Directory" gadget — the page itself is a static shell, member data is loaded
# client-side via a POST to /Sys/MemberDirectory/LoadMembers keyed on a per-page `formId`
# scraped out of the page's inline <script>. The response is `while(1); {...}` (an
# anti-hijacking prefix) wrapping a JSON envelope whose "JsonStructure" field is itself a
# loose JS object literal (unquoted keys, single-quoted strings), not valid JSON.
# Returns [] on any failure so seed continues uninterrupted.

import html
import json
import re

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from pipeline.utils.logging import get_logger

_BASE_URL = "https://cibabooks.ca"
_HEADERS = {"User-Agent": "indie-books-atlas-pipeline/0.1 (https://indiebooksatlas.ca)"}
_FORM_ID_RE = re.compile(r"MemberDirectoryListRenderer\.FormId\s*=\s*'(\d+)'")
_JS_STRING_RE = re.compile(r"'((?:[^'\\]|\\.)*)'")
_JS_BARE_KEY_RE = re.compile(r"(?<=[{,])\s*([A-Za-z_][A-Za-z0-9_]*)\s*:")
_COUNT_SUFFIX_RE = re.compile(r"\s*\(\d+\)$")

log = get_logger(__name__)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=30))
def _fetch_html(url: str) -> str:
    with httpx.Client(timeout=30.0) as client:
        response = client.get(url, follow_redirects=True, headers=_HEADERS)
        response.raise_for_status()
        return response.text


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=30))
def _fetch_members_json(base_url: str, form_id: str) -> dict:
    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            f"{base_url}/Sys/MemberDirectory/LoadMembers",
            data={"formId": form_id, "searchQuery": "", "pageIndex": "0"},
            headers={**_HEADERS, "X-Requested-With": "XMLHttpRequest"},
        )
        response.raise_for_status()
        body = response.text.strip()
        if body.startswith("while(1);"):
            body = body[len("while(1);") :].strip()
        return json.loads(body)


def _unescape_js_string(match: re.Match) -> str:
    return json.dumps(match.group(1).replace("\\'", "'"))


def _parse_js_object_literal(raw: str) -> dict:
    """Convert a loose JS object literal (unquoted keys, single-quoted strings) to JSON."""
    converted = _JS_STRING_RE.sub(_unescape_js_string, raw)
    converted = _JS_BARE_KEY_RE.sub(r'"\1":', converted)
    return json.loads(converted)


def _cell_value(row: dict, column: str) -> str | None:
    cell = row.get(column)
    if not cell:
        return None
    value = cell[0].get("v")
    return html.unescape(value) if value else None


def _rows_to_stores(data: dict) -> list[dict]:
    rows, member_ids = data["members"]
    stores = []
    for row, member_id in zip(rows, member_ids, strict=True):
        name = _cell_value(row, "c1")
        if not name:
            continue
        name = _COUNT_SUFFIX_RE.sub("", name).strip()
        stores.append(
            {
                "name": name,
                "city": _cell_value(row, "c2"),
                "province": _cell_value(row, "c3"),
                "external_id": str(member_id),
            }
        )
    return stores


def fetch_member_list(base_url: str = _BASE_URL) -> list[dict]:
    """
    Fetch and parse the CIBA member directory.
    Returns [] on any failure — never raises.
    """
    try:
        page_html = _fetch_html(f"{base_url}/member-directory/")
        form_id_match = _FORM_ID_RE.search(page_html)
        if not form_id_match:
            raise ValueError("could not find MemberDirectoryListRenderer.FormId on page")
        form_id = form_id_match.group(1)

        envelope = _fetch_members_json(base_url, form_id)
        data = _parse_js_object_literal(envelope["JsonStructure"])
        stores = _rows_to_stores(data)

        log.info("ciba_fetch_complete", count=len(stores))
        return stores
    except Exception as exc:
        log.warning("ciba_fetch_failed", error=str(exc))
        return []
