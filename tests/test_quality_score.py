from pipeline.transforms.quality_score import compute_quality_score


class TestComputeQualityScore:
    def test_empty_record_is_zero(self):
        assert compute_quality_score({}) == 0

    def test_none_values_score_zero(self):
        record = {
            "phone": None,
            "website": None,
            "hours_raw": None,
            "is_verified": None,
            "short_description": None,
            "instagram": None,
        }
        assert compute_quality_score(record) == 0

    def test_full_record_is_100(self):
        record = {
            "phone": "+15198213031",
            "website": "https://bookshelf.ca",
            "hours_raw": "Mo-Fr 10:00-18:00",
            "is_verified": True,
            "short_description": "A great indie bookstore.",
            "instagram": "thebookshelf",
        }
        assert compute_quality_score(record) == 100

    def test_phone_only(self):
        assert compute_quality_score({"phone": "+15198213031"}) == 20

    def test_website_only(self):
        assert compute_quality_score({"website": "https://example.com"}) == 20

    def test_hours_only(self):
        assert compute_quality_score({"hours_raw": "Mo-Fr 09:00-17:00"}) == 20

    def test_verified_true(self):
        assert compute_quality_score({"is_verified": True}) == 20

    def test_verified_false_scores_zero(self):
        assert compute_quality_score({"is_verified": False}) == 0

    def test_verified_truthy_non_bool_scores_zero(self):
        # Only bool True counts — not 1 or non-empty string
        assert compute_quality_score({"is_verified": 1}) == 0
        assert compute_quality_score({"is_verified": "yes"}) == 0

    def test_short_description(self):
        assert compute_quality_score({"short_description": "Great store."}) == 10

    def test_instagram(self):
        assert compute_quality_score({"instagram": "mybookstore"}) == 10

    def test_partial_score(self):
        record = {"phone": "+15198213031", "website": "https://example.com", "instagram": "handle"}
        assert compute_quality_score(record) == 50

    def test_empty_string_scores_zero(self):
        record = {"phone": "", "website": "", "hours_raw": "", "short_description": "", "instagram": ""}
        assert compute_quality_score(record) == 0

    def test_score_never_exceeds_100(self):
        record = {
            "phone": "+15198213031",
            "website": "https://example.com",
            "hours_raw": "Mo-Fr 10:00-18:00",
            "is_verified": True,
            "short_description": "A great store.",
            "instagram": "handle",
            "extra_field": "whatever",
        }
        assert compute_quality_score(record) == 100
