from pipeline.transforms.specialties import (
    VOCABULARY,
    resolve_specialties,
    specialties_from_osm_tags,
)


class TestSpecialtiesFromOsmTags:
    def test_none_and_empty(self):
        assert specialties_from_osm_tags(None) is None
        assert specialties_from_osm_tags({}) is None

    def test_second_hand(self):
        assert specialties_from_osm_tags({"second_hand": "only"}) == ["used"]
        assert specialties_from_osm_tags({"second_hand": "yes"}) == ["used"]
        assert specialties_from_osm_tags({"second_hand": "no"}) is None

    def test_books_tag_multi_value_sorted_and_deduped(self):
        tags = {"books": "comic; Manga;antiquarian;children", "second_hand": "yes"}
        assert specialties_from_osm_tags(tags) == [
            "antiquarian",
            "childrens",
            "comics_graphic",
            "used",
        ]

    def test_unknown_values_dropped(self):
        assert specialties_from_osm_tags({"books": "general;cookbooks"}) is None

    def test_francophone(self):
        assert specialties_from_osm_tags({"language:fr": "main"}) == ["francophone"]

    def test_non_string_books_tag(self):
        assert specialties_from_osm_tags({"books": 5}) is None

    def test_output_always_in_vocabulary(self):
        values = ["comic", "religion", "travel", "art", "history", "zine", "lgbt"]
        assert set(specialties_from_osm_tags({"books": ";".join(values)})) <= VOCABULARY


class TestResolveSpecialties:
    def test_existing_curated_list_is_never_changed(self):
        assert resolve_specialties(["history"], ["used"]) is None

    def test_empty_existing_takes_osm(self):
        assert resolve_specialties([], ["used"]) == ["used"]
        assert resolve_specialties(None, ["used"]) == ["used"]

    def test_nothing_from_osm(self):
        assert resolve_specialties(None, None) is None
