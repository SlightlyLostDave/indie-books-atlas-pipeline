from pipeline.db.client import get_client

# Fields that must never be overwritten by pipeline code after insert.
_IMMUTABLE_FIELDS = {"slug", "is_permanently_closed"}


def get_all_osm_ids() -> set[int]:
    """Return every osm_id in active stores."""
    response = (
        get_client()
        .table("stores")
        .select("osm_id")
        .eq("is_deleted", False)
        .not_.is_("osm_id", "null")
        .execute()
    )
    return {row["osm_id"] for row in response.data}


def get_store_by_osm_id(osm_id: int) -> dict | None:
    response = (
        get_client()
        .table("stores")
        .select("*")
        .eq("osm_id", osm_id)
        .eq("is_deleted", False)
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else None


def get_all_slugs() -> set[str]:
    response = get_client().table("stores").select("slug").execute()
    return {row["slug"] for row in response.data if row.get("slug")}


def insert_store(record: dict) -> dict:
    """
    Insert a new store row and return it.
    Caller must write change_log afterward.
    record must already have slug and data_quality_score set.
    """
    response = get_client().table("stores").insert(record).execute()
    return response.data[0]


def update_store(store_id: str, fields: dict) -> dict:
    """
    Partial update. Silently drops immutable fields and is_verified.
    Returns updated row. Caller must write change_log.
    """
    safe = {k: v for k, v in fields.items() if k not in _IMMUTABLE_FIELDS and k != "is_verified"}
    response = (
        get_client().table("stores").update(safe).eq("id", store_id).execute()
    )
    return response.data[0]


def flag_needs_review(store_id: str) -> None:
    """Set needs_review=True. Never clears it — only humans do."""
    get_client().table("stores").update({"needs_review": True}).eq("id", store_id).execute()


def get_stores_with_google_place_id() -> list[dict]:
    response = (
        get_client()
        .table("stores")
        .select("*")
        .not_.is_("google_place_id", "null")
        .eq("is_deleted", False)
        .execute()
    )
    return response.data
