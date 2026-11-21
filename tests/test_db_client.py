import pytest

from pipeline.db import client
from pipeline.utils.config import Settings


def test_get_client_raises_clear_error_when_supabase_config_missing(monkeypatch):
    monkeypatch.setattr(client, "_client", None)
    monkeypatch.setattr(
        client,
        "get_settings",
        lambda: Settings(_env_file=None, supabase_url="", supabase_service_key=""),
    )
    with pytest.raises(RuntimeError, match="SUPABASE_URL, SUPABASE_SERVICE_KEY not set"):
        client.get_client()
