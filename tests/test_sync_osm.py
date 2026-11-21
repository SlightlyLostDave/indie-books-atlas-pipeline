import json
from pathlib import Path

from pipeline.jobs import sync_osm
from pipeline.sources import osm

FIXTURE = Path(__file__).parent / "fixtures" / "osm_response.json"


def _fixture_elements() -> list[dict]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))["elements"]


class _StoresStub:
    def __init__(self, existing_by_osm_id=None):
        self.existing_by_osm_id = existing_by_osm_id or {}
        self.inserted = []
        self.updated = []
        self.flagged = []

    def get_all_osm_ids(self):
        return set(self.existing_by_osm_id)

    def get_all_slugs(self):
        return set()

    def get_store_by_osm_id(self, osm_id):
        return self.existing_by_osm_id.get(osm_id)

    def insert_store(self, record):
        row = {**record, "id": f"id-{len(self.inserted)}"}
        self.inserted.append(row)
        return row

    def update_store(self, store_id, fields):
        self.updated.append((store_id, fields))
        return {"id": store_id, **fields}

    def flag_needs_review(self, store_id):
        self.flagged.append(store_id)


def _patch(monkeypatch, stores_stub, elements):
    change_log_calls = {"insert": [], "update": [], "flag": []}
    monkeypatch.setattr(sync_osm, "get_settings", lambda: type("S", (), {"overpass_api_url": ""})())
    monkeypatch.setattr(sync_osm.osm, "fetch_canadian_bookstores", lambda url: elements)
    for name in (
        "get_all_osm_ids",
        "get_all_slugs",
        "get_store_by_osm_id",
        "insert_store",
        "update_store",
        "flag_needs_review",
    ):
        monkeypatch.setattr(sync_osm.stores, name, getattr(stores_stub, name))
    monkeypatch.setattr(
        sync_osm.change_log, "write_insert", lambda *a, **k: change_log_calls["insert"].append(a)
    )
    monkeypatch.setattr(
        sync_osm.change_log, "write_update", lambda *a, **k: change_log_calls["update"].append(a)
    )
    monkeypatch.setattr(
        sync_osm.change_log,
        "write_flag_review",
        lambda *a, **k: change_log_calls["flag"].append(a),
    )
    monkeypatch.setattr(sync_osm.store_sources, "upsert_source", lambda *a, **k: None)
    return change_log_calls


class TestOsmElementToFields:
    def test_address_lines_from_fixture(self):
        parsed = osm.parse_element(_fixture_elements()[0])
        fields = sync_osm._osm_element_to_fields(parsed)
        assert fields["address_line1"] == "41 Quebec Street"
        assert fields["address_line2"] is None
        assert fields["city"] == "Guelph"
        assert fields["postal_code"] == "N1H 2T3"

    def test_no_address_tags_yields_none(self):
        parsed = osm.parse_element(_fixture_elements()[1])
        fields = sync_osm._osm_element_to_fields(parsed)
        assert fields["address_line1"] is None
        assert fields["address_line2"] is None

    def test_unit_maps_to_address_line2(self):
        element = {
            "type": "node",
            "id": 1,
            "lat": 43.6,
            "lon": -79.4,
            "tags": {
                "name": "Unit Books",
                "addr:housenumber": "100",
                "addr:street": "King Street West",
                "addr:unit": "Suite 200",
            },
        }
        fields = sync_osm._osm_element_to_fields(osm.parse_element(element))
        assert fields["address_line1"] == "100 King Street West"
        assert fields["address_line2"] == "Suite 200"


class TestRunSyncOsmAddress:
    def test_new_store_inserted_with_address(self, monkeypatch):
        stores_stub = _StoresStub()
        calls = _patch(monkeypatch, stores_stub, [_fixture_elements()[0]])

        sync_osm.run_sync_osm()

        assert len(stores_stub.inserted) == 1
        row = stores_stub.inserted[0]
        assert row["address_line1"] == "41 Quebec Street"
        assert "address_line2" in row
        assert len(calls["insert"]) == 1

    def test_existing_store_backfilled_with_address(self, monkeypatch):
        element = _fixture_elements()[0]
        existing = {
            "id": "store-1",
            "osm_id": element["id"],
            "source": "osm",
            "name": "The Bookshelf",
            "address_line1": None,
            "address_line2": None,
            "data_quality_score": 60,
        }
        stores_stub = _StoresStub({element["id"]: existing})
        calls = _patch(monkeypatch, stores_stub, [element])

        sync_osm.run_sync_osm()

        assert len(stores_stub.updated) == 1
        store_id, payload = stores_stub.updated[0]
        assert store_id == "store-1"
        assert payload["address_line1"] == "41 Quebec Street"
        assert "address_line2" not in payload  # None values never overwrite
        assert len(calls["update"]) == 1
        diff = calls["update"][0][1]
        assert diff["address_line1"] == {"from": None, "to": "41 Quebec Street"}

    def test_missing_osm_tags_do_not_erase_existing_address(self, monkeypatch):
        element = _fixture_elements()[1]  # no street tags
        existing = {
            "id": "store-2",
            "osm_id": element["id"],
            "source": "osm",
            "address_line1": "123 Manual Entry Rd",
        }
        stores_stub = _StoresStub({element["id"]: existing})
        _patch(monkeypatch, stores_stub, [element])

        sync_osm.run_sync_osm()

        for _, payload in stores_stub.updated:
            assert "address_line1" not in payload

    def test_higher_priority_source_not_backfilled(self, monkeypatch):
        element = _fixture_elements()[0]
        existing = {
            "id": "store-3",
            "osm_id": element["id"],
            "source": "ciba",
            "address_line1": None,
        }
        stores_stub = _StoresStub({element["id"]: existing})
        _patch(monkeypatch, stores_stub, [element])

        sync_osm.run_sync_osm()

        assert stores_stub.updated == []


def _qc_element(**tags):
    return {
        "type": "node",
        "id": 555,
        "lat": 45.5,
        "lon": -73.6,
        "tags": {"name": "Le Port de tête", "addr:postcode": "H2T 1X6", **tags},
    }


class TestRunSyncOsmNewFields:
    def test_new_store_gets_new_fields_and_score(self, monkeypatch):
        stores_stub = _StoresStub()
        element = _qc_element(
            **{
                "contact:instagram": "leportdetete",
                "description": "Librairie",
                "second_hand": "yes",
            }
        )
        _patch(monkeypatch, stores_stub, [element])

        sync_osm.run_sync_osm()

        row = stores_stub.inserted[0]
        assert row["instagram"] == "leportdetete"
        assert row["short_description"] == "Librairie"
        assert row["specialties"] == ["used"]
        assert row["province"] == "QC"
        assert row["data_quality_score"] == 20

    def test_curated_specialties_never_overwritten(self, monkeypatch):
        existing = {"id": "s1", "osm_id": 555, "source": "osm", "specialties": ["francophone"]}
        stores_stub = _StoresStub({555: existing})
        _patch(monkeypatch, stores_stub, [_qc_element(second_hand="yes")])

        sync_osm.run_sync_osm()

        for _, payload in stores_stub.updated:
            assert "specialties" not in payload

    def test_empty_specialties_backfilled(self, monkeypatch):
        existing = {"id": "s1", "osm_id": 555, "source": "osm", "specialties": []}
        stores_stub = _StoresStub({555: existing})
        _patch(monkeypatch, stores_stub, [_qc_element(second_hand="yes")])

        sync_osm.run_sync_osm()

        _, payload = stores_stub.updated[0]
        assert payload["specialties"] == ["used"]
