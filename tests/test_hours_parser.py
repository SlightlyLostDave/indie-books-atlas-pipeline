from pipeline.transforms.hours_parser import parse_google_hours, parse_osm_hours


class TestParseOsmHours:
    def test_none_returns_none(self):
        assert parse_osm_hours(None) is None

    def test_empty_string_returns_none(self):
        assert parse_osm_hours("") is None

    def test_whitespace_only_returns_none(self):
        assert parse_osm_hours("   ") is None

    def test_24_7(self):
        result = parse_osm_hours("24/7")
        assert result is not None
        for day in ["mo", "tu", "we", "th", "fr", "sa", "su"]:
            assert result[day]["open"] == "00:00"
            assert result[day]["close"] == "23:59"
            assert result[day]["closed"] is False

    def test_mo_fr_range(self):
        result = parse_osm_hours("Mo-Fr 09:00-17:30")
        assert result is not None
        for day in ["mo", "tu", "we", "th", "fr"]:
            assert result[day]["open"] == "09:00"
            assert result[day]["close"] == "17:30"
            assert result[day]["closed"] is False
        assert "sa" not in result
        assert "su" not in result

    def test_mo_sa_plus_su_semicolon(self):
        result = parse_osm_hours("Mo-Sa 10:00-18:00; Su 12:00-17:00")
        assert result is not None
        for day in ["mo", "tu", "we", "th", "fr", "sa"]:
            assert result[day]["open"] == "10:00"
            assert result[day]["close"] == "18:00"
        assert result["su"]["open"] == "12:00"
        assert result["su"]["close"] == "17:00"

    def test_ph_off(self):
        result = parse_osm_hours("Mo-Fr 09:00-17:00; PH off")
        assert result is not None
        # Weekdays should be present
        for day in ["mo", "tu", "we", "th", "fr"]:
            assert result[day]["open"] == "09:00"
        # PH off should appear as closed
        assert result.get("ph") == {"closed": True}

    def test_by_appointment_returns_none(self):
        assert parse_osm_hours("by appointment") is None
        assert parse_osm_hours("By Appointment Only") is None

    def test_malformed_string_returns_none(self):
        # Should not raise, just return None
        assert parse_osm_hours("open whenever we feel like it") is None

    def test_single_day(self):
        result = parse_osm_hours("Sa 10:00-15:00")
        assert result is not None
        assert result["sa"]["open"] == "10:00"
        assert result["sa"]["close"] == "15:00"
        assert "mo" not in result

    def test_closed_day(self):
        result = parse_osm_hours("Mo-Sa 10:00-18:00; Su off")
        assert result is not None
        assert result["su"] == {"closed": True}


class TestParseGoogleHours:
    def test_none_returns_none(self):
        assert parse_google_hours(None) is None

    def test_empty_list_returns_none(self):
        assert parse_google_hours([]) is None

    def test_full_week_fixture(self):
        periods = [
            {"open": {"day": 1, "hour": 10, "minute": 0}, "close": {"day": 1, "hour": 18, "minute": 0}},
            {"open": {"day": 2, "hour": 10, "minute": 0}, "close": {"day": 2, "hour": 18, "minute": 0}},
            {"open": {"day": 3, "hour": 10, "minute": 0}, "close": {"day": 3, "hour": 18, "minute": 0}},
            {"open": {"day": 4, "hour": 10, "minute": 0}, "close": {"day": 4, "hour": 18, "minute": 0}},
            {"open": {"day": 5, "hour": 10, "minute": 0}, "close": {"day": 5, "hour": 17, "minute": 0}},
            {"open": {"day": 0, "hour": 12, "minute": 0}, "close": {"day": 0, "hour": 17, "minute": 0}},
        ]
        result = parse_google_hours(periods)
        assert result is not None
        assert result["mo"] == {"open": "10:00", "close": "18:00", "closed": False}
        assert result["fr"] == {"open": "10:00", "close": "17:00", "closed": False}
        assert result["su"] == {"open": "12:00", "close": "17:00", "closed": False}
        assert "sa" not in result  # Saturday not in periods

    def test_sunday_maps_correctly(self):
        # Google day 0 = Sunday
        periods = [{"open": {"day": 0, "hour": 9, "minute": 30}, "close": {"day": 0, "hour": 16, "minute": 0}}]
        result = parse_google_hours(periods)
        assert result["su"]["open"] == "09:30"

    def test_saturday_maps_correctly(self):
        # Google day 6 = Saturday
        periods = [{"open": {"day": 6, "hour": 11, "minute": 0}, "close": {"day": 6, "hour": 15, "minute": 0}}]
        result = parse_google_hours(periods)
        assert result["sa"]["open"] == "11:00"

    def test_zero_padded_hours(self):
        periods = [{"open": {"day": 1, "hour": 9, "minute": 5}, "close": {"day": 1, "hour": 17, "minute": 0}}]
        result = parse_google_hours(periods)
        assert result["mo"]["open"] == "09:05"
