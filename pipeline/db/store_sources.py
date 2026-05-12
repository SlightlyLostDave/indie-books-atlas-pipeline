from pipeline.db.client import get_client


def upsert_source(store_id: str, source: str, external_id: str, raw_data: dict) -> None:
    """Upsert into store_sources on (store_id, source)."""
    get_client().table("store_sources").upsert(
        {
            "store_id": store_id,
            "source": source,
            "external_id": external_id,
            "raw_data": raw_data,
        },
        on_conflict="store_id,source",
    ).execute()


def get_source(store_id: str, source: str) -> dict | None:
    response = (
        get_client()
        .table("store_sources")
        .select("*")
        .eq("store_id", store_id)
        .eq("source", source)
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else None
