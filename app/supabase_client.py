import os
from functools import lru_cache

from supabase import Client, create_client


@lru_cache(maxsize=1)
def get_supabase() -> Client:
    url = os.getenv("SUPABASE_URL")
    secret_key = os.getenv("SUPABASE_SECRET_KEY")

    if not url:
        raise RuntimeError("SUPABASE_URL Environment Variable bulunamadı.")

    if not secret_key:
        raise RuntimeError("SUPABASE_SECRET_KEY Environment Variable bulunamadı.")

    return create_client(url, secret_key)


def supabase_health() -> dict:
    """
    Supabase bağlantısının temel olarak kurulabildiğini kontrol eder.
    Secret key hiçbir şekilde döndürülmez.
    """
    try:
        client = get_supabase()

        # Henüz hiçbir veri değiştirmiyoruz.
        # Sadece public.plans tablosuna güvenli bir SELECT yapıyoruz.
        result = client.table("plans").select("id").limit(1).execute()

        return {
            "connected": True,
            "query_ok": True,
            "rows": len(result.data or []),
        }

    except Exception as exc:
        return {
            "connected": False,
            "query_ok": False,
            "error": str(exc),
        }
