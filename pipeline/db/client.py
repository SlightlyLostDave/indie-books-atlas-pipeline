from supabase import Client, create_client

from pipeline.utils.config import get_settings

_client: Client | None = None


def get_client() -> Client:
    global _client
    if _client is None:
        s = get_settings()
        missing = [
            name
            for name, value in (
                ("SUPABASE_URL", s.supabase_url),
                ("SUPABASE_SERVICE_KEY", s.supabase_service_key),
            )
            if not value
        ]
        if missing:
            raise RuntimeError(
                f"{', '.join(missing)} not set: check GitHub environment "
                "'production' secrets or .env.local"
            )
        _client = create_client(s.supabase_url, s.supabase_service_key)
    return _client
