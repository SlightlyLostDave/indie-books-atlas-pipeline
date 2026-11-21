from pipeline.transforms.normalize import (
    build_address_lines,
    normalize_instagram,
    normalize_phone,
    normalize_postal_code,
    normalize_website,
)


class TestNormalizePhone:
    def test_none_returns_none(self):
        assert normalize_phone(None) is None

    def test_empty_returns_none(self):
        assert normalize_phone("") is None

    def test_e164_passthrough(self):
        assert normalize_phone("+15198213031") == "+15198213031"

    def test_local_format(self):
        assert normalize_phone("(519) 821-3031") == "+15198213031"

    def test_with_dashes(self):
        assert normalize_phone("519-821-3031") == "+15198213031"

    def test_with_dots(self):
        assert normalize_phone("519.821.3031") == "+15198213031"

    def test_country_code_prefix(self):
        assert normalize_phone("1 519 821 3031") == "+15198213031"

    def test_invalid_returns_none(self):
        assert normalize_phone("not-a-phone") is None

    def test_too_short_returns_none(self):
        assert normalize_phone("123") is None

    def test_never_raises(self):
        # Should not raise for any input
        normalize_phone("!!!###$$$")
        normalize_phone("0" * 50)


class TestNormalizePostalCode:
    def test_none_returns_none(self):
        assert normalize_postal_code(None) is None

    def test_empty_returns_none(self):
        assert normalize_postal_code("") is None

    def test_valid_with_space(self):
        assert normalize_postal_code("N1H 2T3") == "N1H 2T3"

    def test_valid_without_space(self):
        assert normalize_postal_code("N1H2T3") == "N1H 2T3"

    def test_lowercase_normalized(self):
        assert normalize_postal_code("n1h2t3") == "N1H 2T3"

    def test_invalid_format_returns_none(self):
        assert normalize_postal_code("12345") is None

    def test_partial_returns_none(self):
        assert normalize_postal_code("N1H") is None


class TestNormalizeWebsite:
    def test_none_returns_none(self):
        assert normalize_website(None) is None

    def test_empty_returns_none(self):
        assert normalize_website("") is None

    def test_already_has_https(self):
        assert normalize_website("https://example.com") == "https://example.com"

    def test_already_has_http(self):
        assert normalize_website("http://example.com") == "http://example.com"

    def test_bare_domain_gets_https(self):
        assert normalize_website("example.com") == "https://example.com"

    def test_trailing_slash_stripped(self):
        assert normalize_website("https://example.com/") == "https://example.com"

    def test_path_preserved(self):
        assert normalize_website("https://example.com/books") == "https://example.com/books"


class TestNormalizeInstagram:
    def test_none_returns_none(self):
        assert normalize_instagram(None) is None

    def test_empty_returns_none(self):
        assert normalize_instagram("") is None

    def test_at_prefix_stripped(self):
        assert normalize_instagram("@thebookstore") == "thebookstore"

    def test_bare_handle(self):
        assert normalize_instagram("thebookstore") == "thebookstore"

    def test_full_url(self):
        assert normalize_instagram("https://instagram.com/thebookstore") == "thebookstore"

    def test_url_with_www(self):
        assert normalize_instagram("https://www.instagram.com/thebookstore/") == "thebookstore"

    def test_url_with_http(self):
        assert normalize_instagram("http://instagram.com/thebookstore") == "thebookstore"


class TestBuildAddressLines:
    def test_full_address_with_unit(self):
        tags = {"addr:housenumber": "41", "addr:street": "Quebec Street", "addr:unit": "2"}
        assert build_address_lines(tags) == ("41 Quebec Street", "Unit 2")

    def test_street_only(self):
        assert build_address_lines({"addr:street": "Quebec Street"}) == ("Quebec Street", None)

    def test_housenumber_without_street_is_none(self):
        assert build_address_lines({"addr:housenumber": "41"}) == (None, None)

    def test_addr_full_fallback(self):
        tags = {"addr:full": "41 Quebec St, Guelph"}
        assert build_address_lines(tags) == ("41 Quebec St, Guelph", None)

    def test_street_preferred_over_addr_full(self):
        tags = {"addr:street": "Quebec Street", "addr:full": "something else"}
        assert build_address_lines(tags)[0] == "Quebec Street"

    def test_prefixed_unit_kept_as_is(self):
        tags = {"addr:street": "King St W", "addr:unit": "Suite 200"}
        assert build_address_lines(tags) == ("King St W", "Suite 200")

    def test_single_letter_unit_gets_prefix(self):
        assert build_address_lines({"addr:street": "Main St", "addr:unit": "B"})[1] == "Unit B"

    def test_french_designator_kept(self):
        assert build_address_lines({"addr:street": "Rue St-Denis", "addr:unit": "Bureau 3"})[1] == "Bureau 3"

    def test_whitespace_collapsed(self):
        tags = {"addr:housenumber": " 41 ", "addr:street": "  Quebec   Street "}
        assert build_address_lines(tags) == ("41 Quebec Street", None)

    def test_whitespace_only_values_are_none(self):
        tags = {"addr:housenumber": "  ", "addr:street": "   ", "addr:unit": " "}
        assert build_address_lines(tags) == (None, None)

    def test_empty_and_none_tags(self):
        assert build_address_lines({}) == (None, None)
        assert build_address_lines(None) == (None, None)

    def test_non_string_values_ignored(self):
        assert build_address_lines({"addr:street": 123}) == (None, None)
