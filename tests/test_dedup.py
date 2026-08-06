from pipeline.transforms import dedup


class TestNameSimilarity:
    def test_identical_names(self):
        assert dedup.name_similarity("Audreys Books", "Audreys Books") == 1.0

    def test_case_and_whitespace_insensitive(self):
        score = dedup.name_similarity("AUDREYS BOOKS LTD.", "  audreys books ltd.  ")
        assert score == 1.0

    def test_dissimilar_names(self):
        score = dedup.name_similarity("Audreys Books", "A Different Booklist")
        assert score < 0.7


class TestFindFuzzyMatch:
    def test_exact_name_same_province_matches(self):
        candidates = [{"key": "a", "name": "Audreys Books", "province": "AB"}]

        match = dedup.find_fuzzy_match("Audreys Books", "AB", candidates)

        assert match == candidates[0]

    def test_case_and_suffix_different_name_same_province_matches(self):
        candidates = [{"key": "a", "name": "Audreys Books", "province": "AB"}]

        match = dedup.find_fuzzy_match("AUDREYS BOOKS LTD.", "AB", candidates)

        assert match == candidates[0]

    def test_similar_name_different_province_does_not_match(self):
        candidates = [{"key": "a", "name": "Audreys Books", "province": "ON"}]

        match = dedup.find_fuzzy_match("Audreys Books", "AB", candidates)

        assert match is None

    def test_dissimilar_names_do_not_match(self):
        candidates = [{"key": "a", "name": "A Different Booklist", "province": "ON"}]

        match = dedup.find_fuzzy_match("Aslan's Den", "ON", candidates)

        assert match is None

    def test_empty_candidate_list_returns_none(self):
        assert dedup.find_fuzzy_match("Audreys Books", "AB", []) is None

    def test_missing_province_on_one_side_still_matches(self):
        candidates = [{"key": "a", "name": "Audreys Books", "province": None}]

        match = dedup.find_fuzzy_match("Audreys Books", "AB", candidates)

        assert match == candidates[0]

    def test_best_of_multiple_candidates_is_returned(self):
        candidates = [
            {"key": "a", "name": "Audrey Books", "province": "AB"},
            {"key": "b", "name": "Audreys Books", "province": "AB"},
        ]

        match = dedup.find_fuzzy_match("Audreys Books", "AB", candidates)

        assert match["key"] == "b"
