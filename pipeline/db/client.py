from supabase import Client, create_client

from pipeline.utils.config import get_settings

_client: Client | None = None


def get_client() -> Client:
    global _client
    if _client is None:
        s = get_settings()
        _client = create_client(s.supabase_url, s.supabase_service_key)
    return _client
