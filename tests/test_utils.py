from pipeline.utils.provinces import CODE_TO_NAME, NAME_TO_CODE, normalize_province


class TestProvinces:
    def test_name_to_code_completeness(self):
        assert len(NAME_TO_CODE) == 13

    def test_known_province_by_name(self):
        assert NAME_TO_CODE["Ontario"] == "ON"
        assert NAME_TO_CODE["British Columbia"] == "BC"
        assert NAME_TO_CODE["Quebec"] == "QC"

    def test_code_to_name_roundtrip(self):
        for name, code in NAME_TO_CODE.items():
            assert CODE_TO_NAME[code] == name

    def test_normalize_from_full_name(self):
        assert normalize_province("Ontario") == "ON"
        assert normalize_province("British Columbia") == "BC"
        assert normalize_province("Newfoundland and Labrador") == "NL"

    def test_normalize_from_code(self):
        assert normalize_province("ON") == "ON"
        assert normalize_province("BC") == "BC"
        assert normalize_province("QC") == "QC"

    def test_normalize_lowercase_code(self):
        assert normalize_province("on") == "ON"
        assert normalize_province("bc") == "BC"

    def test_normalize_with_whitespace(self):
        assert normalize_province("  ON  ") == "ON"
        assert normalize_province("  Ontario  ") == "ON"

    def test_normalize_none_returns_none(self):
        assert normalize_province(None) is None

    def test_normalize_empty_returns_none(self):
        assert normalize_province("") is None

    def test_normalize_unknown_returns_none(self):
        assert normalize_province("California") is None
        assert normalize_province("XX") is None

    def test_all_territories_present(self):
        for territory in ["NT", "NU", "YT"]:
            assert territory in CODE_TO_NAME
