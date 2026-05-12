from pipeline.db.client import get_client


def write_insert(store_id: str, record_snapshot: dict, source: str) -> None:
    """Log an insert operation with the full record as diff."""
    get_client().table("change_log").insert(
        {
            "store_id": store_id,
            "operation": "insert",
            "diff": record_snapshot,
            "source": source,
        }
    ).execute()


def write_update(store_id: str, diff: dict, source: str) -> None:
    """
    Log an update. diff shape: {"field": {"from": old_val, "to": new_val}, ...}.
    Only changed fields should be in diff.
    """
    get_client().table("change_log").insert(
        {
            "store_id": store_id,
            "operation": "update",
            "diff": diff,
            "source": source,
        }
    ).execute()


def write_flag_review(store_id: str, reason: str, source: str) -> None:
    """Log a flag_review operation."""
    get_client().table("change_log").insert(
        {
            "store_id": store_id,
            "operation": "flag_review",
            "diff": {"reason": reason},
            "source": source,
        }
    ).execute()
