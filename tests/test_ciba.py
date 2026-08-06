from pathlib import Path

import httpx
import pytest

from pipeline.sources import ciba

_FIXTURES = Path(__file__).parent / "fixtures"
_DIRECTORY_URL = "https://cibabooks.ca/member-directory/"
_LOAD_MEMBERS_URL = "https://cibabooks.ca/Sys/MemberDirectory/LoadMembers"


def _page_html() -> str:
    return (_FIXTURES / "ciba_directory_page.html").read_text(encoding="utf-8")


def _load_members_body() -> str:
    return (_FIXTURES / "ciba_load_members_response.txt").read_text(encoding="utf-8")


class TestFetchMemberList:
    def test_happy_path(self, httpx_mock):
        httpx_mock.add_response(url=_DIRECTORY_URL, text=_page_html())
        httpx_mock.add_response(url=_LOAD_MEMBERS_URL, text=_load_members_body())

        stores = ciba.fetch_member_list()

        assert stores == [
            {
                "name": "A Different Booklist",
                "city": "Toronto",
                "province": "ON",
                "external_id": "57351770",
            },
            {
                "name": "AUDREYS BOOKS LTD.",
                "city": "EDMONTON",
                "province": "AB",
                "external_id": "57351628",
            },
            {
                "name": "Aslan's Den",
                "city": "Innisfail",
                "province": "AB",
                "external_id": "57351632",
            },
        ]

    def test_strips_multi_digit_count_suffix(self, httpx_mock):
        httpx_mock.add_response(url=_DIRECTORY_URL, text=_page_html())
        httpx_mock.add_response(url=_LOAD_MEMBERS_URL, text=_load_members_body())

        stores = ciba.fetch_member_list()

        assert stores[1]["name"] == "AUDREYS BOOKS LTD."

    def test_unescapes_html_entities(self, httpx_mock):
        httpx_mock.add_response(url=_DIRECTORY_URL, text=_page_html())
        httpx_mock.add_response(url=_LOAD_MEMBERS_URL, text=_load_members_body())

        stores = ciba.fetch_member_list()

        assert stores[2]["name"] == "Aslan's Den"

    def test_page_fetch_failure_returns_empty(self, httpx_mock):
        httpx_mock.add_exception(httpx.ConnectError("boom"), url=_DIRECTORY_URL)

        assert ciba.fetch_member_list() == []

    def test_missing_form_id_returns_empty(self, httpx_mock):
        httpx_mock.add_response(
            url=_DIRECTORY_URL, text="<html><body>no form id here</body></html>"
        )

        assert ciba.fetch_member_list() == []

    def test_load_members_failure_returns_empty(self, httpx_mock):
        httpx_mock.add_response(url=_DIRECTORY_URL, text=_page_html())
        httpx_mock.add_exception(httpx.ConnectError("boom"), url=_LOAD_MEMBERS_URL)

        assert ciba.fetch_member_list() == []

    def test_malformed_json_structure_returns_empty(self, httpx_mock):
        httpx_mock.add_response(url=_DIRECTORY_URL, text=_page_html())
        httpx_mock.add_response(
            url=_LOAD_MEMBERS_URL,
            text='while(1); {"TotalCount": 0, "JsonStructure": "not json at all {{{"}',
        )

        assert ciba.fetch_member_list() == []


class TestParseJsObjectLiteral:
    def test_converts_bare_keys_and_single_quotes(self):
        raw = "{members:[[{c1:[{fft:2, v:'Store Name'}]}],[123]]}"

        result = ciba._parse_js_object_literal(raw)

        assert result == {"members": [[{"c1": [{"fft": 2, "v": "Store Name"}]}], [123]]}

    def test_handles_escaped_single_quote_in_value(self):
        raw = r"{c1:[{fft:2, v:'Aslan\'s Den'}]}"

        result = ciba._parse_js_object_literal(raw)

        assert result == {"c1": [{"fft": 2, "v": "Aslan's Den"}]}


@pytest.fixture(autouse=True)
def _no_retry_delay(monkeypatch):
    # tenacity's exponential backoff would otherwise slow down the failure-path tests
    monkeypatch.setattr(ciba._fetch_html.retry, "wait", lambda *_args, **_kwargs: 0)
    monkeypatch.setattr(ciba._fetch_members_json.retry, "wait", lambda *_args, **_kwargs: 0)
