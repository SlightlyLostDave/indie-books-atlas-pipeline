from pipeline.transforms.osm_fields import SHORT_DESCRIPTION_MAX, osm_element_to_fields


def _parsed(**tags):
    return {"osm_id": 1, "lat": 45.5, "lng": -73.6, "tags": tags}


class TestOsmElementToFields:
    def test_instagram_url_normalized(self):
        tags = {"contact:instagram": "https://instagram.com/drawnandquarterly/"}
        assert osm_element_to_fields(_parsed(**tags))["instagram"] == "drawnandquarterly"

    def test_instagram_bare_tag(self):
        assert osm_element_to_fields(_parsed(instagram="@shop"))["instagram"] == "shop"

    def test_short_description(self):
        f = osm_element_to_fields(_parsed(description="  Used   and rare books. "))
        assert f["short_description"] == "Used and rare books."

    def test_description_fr_fallback(self):
        f = osm_element_to_fields(_parsed(**{"description:fr": "Librairie indépendante"}))
        assert f["short_description"] == "Librairie indépendante"

    def test_long_description_truncated_on_word_boundary(self):
        f = osm_element_to_fields(_parsed(description="word " * 200))
        assert len(f["short_description"]) <= SHORT_DESCRIPTION_MAX
        assert f["short_description"].endswith("word…")

    def test_specialties(self):
        assert osm_element_to_fields(_parsed(second_hand="only"))["specialties"] == ["used"]

    def test_phone_mobile_fallback(self):
        f = osm_element_to_fields(_parsed(**{"contact:mobile": "514-555-0199"}))
        assert f["phone"] == "+15145550199"

    def test_website_url_fallback(self):
        assert osm_element_to_fields(_parsed(url="example.ca"))["website"] == "https://example.ca"

    def test_city_is_in_fallback(self):
        assert osm_element_to_fields(_parsed(**{"is_in:city": "Halifax"}))["city"] == "Halifax"

    def test_province_french_name(self):
        assert osm_element_to_fields(_parsed(**{"addr:province": "Québec"}))["province"] == "QC"

    def test_province_from_postal_code(self):
        f = osm_element_to_fields(_parsed(**{"addr:postcode": "h2t 1x6"}))
        assert f["postal_code"] == "H2T 1X6"
        assert f["province"] == "QC"

    def test_explicit_province_beats_postal_code(self):
        tags = {"addr:province": "ON", "addr:postcode": "H2T 1X6"}
        assert osm_element_to_fields(_parsed(**tags))["province"] == "ON"

    def test_empty_tags(self):
        f = osm_element_to_fields({"lat": None, "lng": None, "tags": None})
        assert f["name"] is None
        assert f["location"] is None
        for key in ("instagram", "short_description", "specialties", "province"):
            assert f[key] is None
