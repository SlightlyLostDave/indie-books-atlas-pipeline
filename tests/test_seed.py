from pipeline.jobs import seed


def _osm_element(osm_id=1, name="Audreys Books", city="Edmonton", province="AB", lat=53.5, lng=-113.5):
    return {
        "osm_id": osm_id,
        "lat": lat,
        "lng": lng,
        "tags": {
            "name": name,
            "addr:city": city,
            "addr:province": province,
        },
    }


class _StoresStub:
    def __init__(self, existing_by_osm_id=None):
        self.existing_by_osm_id = existing_by_osm_id or {}
        self.inserted = []
        self.updated = []

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


def _wikidata_binding(
    name="Wikidata Books", lat=53.5, lng=-113.5, website=None, province=None, closed=None
):
    binding = {
        "itemLabel": {"value": name},
        "lat": {"value": str(lat)},
        "lng": {"value": str(lng)},
    }
    if website:
        binding["website"] = {"value": website}
    if province:
        binding["provinceLabel"] = {"value": province}
    if closed:
        binding["closed"] = {"value": closed}
    return binding


def _patch_common(
    monkeypatch, stores_stub, osm_elements=None, ciba_entries=None, wikidata_bindings=None
):
    monkeypatch.setattr(seed, "get_settings", lambda: type("S", (), {"overpass_api_url": ""})())
    monkeypatch.setattr(seed.osm, "fetch_canadian_bookstores", lambda url: osm_elements or [])
    monkeypatch.setattr(
        seed.osm,
        "parse_element",
        lambda e: {"osm_id": e["osm_id"], "lat": e["lat"], "lng": e["lng"], "tags": e["tags"]},
    )
    monkeypatch.setattr(seed.ciba, "fetch_member_list", lambda: ciba_entries or [])
    monkeypatch.setattr(
        seed.wikidata, "fetch_canadian_bookstores", lambda: wikidata_bindings or []
    )
    monkeypatch.setattr(seed.stores, "get_all_slugs", stores_stub.get_all_slugs)
    monkeypatch.setattr(seed.stores, "get_store_by_osm_id", stores_stub.get_store_by_osm_id)
    monkeypatch.setattr(seed.stores, "insert_store", stores_stub.insert_store)
    monkeypatch.setattr(seed.stores, "update_store", stores_stub.update_store)
    monkeypatch.setattr(seed.change_log, "write_insert", lambda *a, **k: None)
    monkeypatch.setattr(seed.change_log, "write_update", lambda *a, **k: None)
    monkeypatch.setattr(seed.change_log, "write_flag_review", lambda *a, **k: None)
    monkeypatch.setattr(seed.store_sources, "upsert_source", lambda *a, **k: None)


class TestCibaWithoutCoordinates:
    def test_ciba_only_entry_is_inserted_despite_missing_coordinates(self, monkeypatch):
        stores_stub = _StoresStub()
        ciba_entries = [
            {"name": "A Different Booklist", "city": "Toronto", "province": "ON", "external_id": "1"}
        ]
        _patch_common(monkeypatch, stores_stub, osm_elements=[], ciba_entries=ciba_entries)

        seed.run_seed()

        assert len(stores_stub.inserted) == 1
        assert stores_stub.inserted[0]["name"] == "A Different Booklist"

    def test_inserted_ciba_record_needs_review(self, monkeypatch):
        stores_stub = _StoresStub()
        ciba_entries = [
            {"name": "A Different Booklist", "city": "Toronto", "province": "ON", "external_id": "1"}
        ]
        _patch_common(monkeypatch, stores_stub, osm_elements=[], ciba_entries=ciba_entries)

        seed.run_seed()

        assert stores_stub.inserted[0]["needs_review"] is True


class TestOsmStillRequiresCoordinates:
    def test_osm_entry_missing_coordinates_is_skipped(self, monkeypatch):
        stores_stub = _StoresStub()
        osm_elements = [_osm_element(lat=None, lng=None)]
        _patch_common(monkeypatch, stores_stub, osm_elements=osm_elements, ciba_entries=[])

        seed.run_seed()

        assert stores_stub.inserted == []


class TestFuzzyMerge:
    def test_ciba_entry_merges_into_fuzzy_matched_osm_record(self, monkeypatch):
        stores_stub = _StoresStub()
        osm_elements = [_osm_element(osm_id=42, name="Audreys Books", city="Edmonton", province="AB")]
        ciba_entries = [
            {
                "name": "AUDREYS BOOKS LTD.",
                "city": "EDMONTON",
                "province": "AB",
                "external_id": "99",
                "phone": "780-555-1234",
            }
        ]
        _patch_common(monkeypatch, stores_stub, osm_elements=osm_elements, ciba_entries=ciba_entries)

        seed.run_seed()

        assert len(stores_stub.inserted) == 1
        assert stores_stub.inserted[0]["phone"] == "+17805551234"
        assert stores_stub.inserted[0]["lat"] == 53.5


class TestWikidata:
    def test_wikidata_only_entry_is_inserted(self, monkeypatch):
        stores_stub = _StoresStub()
        bindings = [_wikidata_binding(name="Wikidata Books", website="https://example.com")]
        _patch_common(monkeypatch, stores_stub, wikidata_bindings=bindings)

        seed.run_seed()

        assert len(stores_stub.inserted) == 1
        assert stores_stub.inserted[0]["name"] == "Wikidata Books"
        assert stores_stub.inserted[0]["source"] == "wikidata"
        assert stores_stub.inserted[0]["website"] == "https://example.com"
        assert stores_stub.inserted[0]["needs_review"] is False

    def test_wikidata_entry_with_dissolution_date_needs_review(self, monkeypatch):
        stores_stub = _StoresStub()
        bindings = [_wikidata_binding(name="World's Biggest Bookstore", closed="2014-01-01T00:00:00Z")]
        _patch_common(monkeypatch, stores_stub, wikidata_bindings=bindings)
        flagged = []
        monkeypatch.setattr(
            seed.change_log, "write_flag_review", lambda *a, **k: flagged.append((a, k))
        )

        seed.run_seed()

        assert len(stores_stub.inserted) == 1
        assert stores_stub.inserted[0]["needs_review"] is True
        assert "is_permanently_closed" not in stores_stub.inserted[0]
        assert len(flagged) == 1

    def test_wikidata_entry_matching_existing_osm_record_is_dropped(self, monkeypatch):
        stores_stub = _StoresStub()
        osm_elements = [_osm_element(osm_id=42, name="Audreys Books", city="Edmonton", province="AB")]
        bindings = [_wikidata_binding(name="Audreys Books")]
        _patch_common(monkeypatch, stores_stub, osm_elements=osm_elements, wikidata_bindings=bindings)

        seed.run_seed()

        assert len(stores_stub.inserted) == 1
        assert stores_stub.inserted[0]["source"] == "osm"

    def test_wikidata_entry_in_different_province_from_same_named_osm_is_not_merged(self, monkeypatch):
        stores_stub = _StoresStub()
        osm_elements = [_osm_element(osm_id=42, name="Second Story Books", city="Edmonton", province="AB")]
        bindings = [_wikidata_binding(name="Second Story Books", province="Ontario")]
        _patch_common(monkeypatch, stores_stub, osm_elements=osm_elements, wikidata_bindings=bindings)

        seed.run_seed()

        assert len(stores_stub.inserted) == 2
        sources = {row["source"] for row in stores_stub.inserted}
        assert sources == {"osm", "wikidata"}

    def test_chain_name_from_wikidata_is_excluded(self, monkeypatch):
        stores_stub = _StoresStub()
        bindings = [_wikidata_binding(name="Indigo Books & Music")]
        _patch_common(monkeypatch, stores_stub, wikidata_bindings=bindings)

        seed.run_seed()

        assert stores_stub.inserted == []


class TestCibaChainExclusion:
    def test_chain_name_from_ciba_is_excluded(self, monkeypatch):
        stores_stub = _StoresStub()
        ciba_entries = [{"name": "Chapters Indigo", "city": "Toronto", "province": "ON", "external_id": "1"}]
        _patch_common(monkeypatch, stores_stub, ciba_entries=ciba_entries)

        seed.run_seed()

        assert stores_stub.inserted == []
