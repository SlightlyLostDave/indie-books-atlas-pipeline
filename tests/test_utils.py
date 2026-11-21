from pipeline.utils.provinces import (
    CODE_TO_NAME,
    NAME_TO_CODE,
    normalize_province,
    province_from_postal_code,
)


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

    def test_french_province_names(self):
        assert normalize_province("Québec") == "QC"
        assert normalize_province("Colombie-Britannique") == "BC"


class TestProvinceFromPostalCode:
    def test_common_prefixes(self):
        assert province_from_postal_code("M5V 2T6") == "ON"
        assert province_from_postal_code("v6b 1a1") == "BC"
        assert province_from_postal_code("T5J 0N3") == "AB"
        assert province_from_postal_code("A1C 5M2") == "NL"

    def test_x_split_between_nunavut_and_nwt(self):
        assert province_from_postal_code("X0A 0H0") == "NU"
        assert province_from_postal_code("X1A 2N1") == "NT"

    def test_invalid(self):
        assert province_from_postal_code(None) is None
        assert province_from_postal_code("  ") is None
        assert province_from_postal_code("Z1Z 1Z1") is None
