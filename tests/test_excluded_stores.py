from pipeline.utils.excluded_stores import is_excluded


class TestIsExcluded:
    def test_ordinary_indie_store_not_excluded(self):
        assert is_excluded(osm_id=1, name="The Reading Nook", tags={"shop": "books"}) is False

    def test_excluded_by_osm_id(self):
        from pipeline.utils import excluded_stores

        excluded_stores.EXCLUDED_OSM_IDS.add(999)
        try:
            assert is_excluded(osm_id=999, name="The Reading Nook", tags={}) is True
        finally:
            excluded_stores.EXCLUDED_OSM_IDS.discard(999)

    def test_excluded_by_name_keyword(self):
        assert is_excluded(osm_id=2, name="Chapters Indigo", tags={}) is True

    def test_excluded_by_name_keyword_case_insensitive(self):
        assert is_excluded(osm_id=3, name="CHRISTIAN BOOK Shop", tags={}) is True

    def test_excluded_by_brand_tag(self):
        assert is_excluded(osm_id=4, name="Some Bookstore", tags={"brand": "Indigo"}) is True

    def test_excluded_by_operator_tag_keyword(self):
        assert is_excluded(osm_id=5, name="Campus Books", tags={"operator": "University of Toronto"}) is True

    def test_excluded_by_operator_type_tag(self):
        assert is_excluded(osm_id=6, name="Some Bookstore", tags={"operator:type": "religious"}) is True

    def test_excluded_by_religion_tag_presence(self):
        assert is_excluded(osm_id=7, name="Some Bookstore", tags={"religion": "christian"}) is True

    def test_no_tags_defaults_to_not_excluded(self):
        assert is_excluded(osm_id=8, name="Some Bookstore", tags=None) is False

    def test_no_osm_id(self):
        assert is_excluded(osm_id=None, name="Some Bookstore", tags={}) is False
