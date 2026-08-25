"""
StorageService'in Supabase Storage implementasyonu.

'path' parametresi, LocalStorage ile AYNI sözleşmeyi kullanır: bucket içinde
göreceli bir nesne anahtarı (örn. "uploads/abc123.pdf"). Böylece
files/service.py, customtemplates/service.py gibi çağıran kodlar hangi
backend'in aktif olduğunu hiç bilmez.

Bucket ÖNCEDEN Supabase panelinden (Storage sekmesi) elle oluşturulmuş
olmalı - bucket oluşturma SQL ile yapılamaz. Varsayılan bucket adı
"documents"; STORAGE_BUCKET ortam değişkeniyle değiştirilebilir.
Bucket PRIVATE (public olmayan) olmalı - bu uygulamadaki belgeler
kişisel/hukuki içerik taşıdığı için herkese açık olmamalı.
"""

import os
from app.storage.base import StorageService
from app.supabase_client import get_supabase

BUCKET_NAME = os.getenv("STORAGE_BUCKET", "documents")


class SupabaseStorage(StorageService):
    def __init__(self, bucket: str = BUCKET_NAME):
        self.bucket = bucket

    def _bucket(self):
        return get_supabase().storage.from_(self.bucket)

    def save(self, path: str, data: bytes, content_type: str | None = None) -> str:
        options = {"upsert": "true"}
        if content_type:
            options["content-type"] = content_type
        self._bucket().upload(path, data, options)
        return path

    def read(self, path: str) -> bytes:
        return self._bucket().download(path)

    def delete(self, path: str) -> None:
        self._bucket().remove([path])

    def exists(self, path: str) -> bool:
        folder = path.rsplit("/", 1)[0] if "/" in path else ""
        name = path.rsplit("/", 1)[-1]
        try:
            entries = self._bucket().list(folder)
        except Exception:
            return False
        return any(e.get("name") == name for e in (entries or []))

    def list(self, prefix: str) -> list[str]:
        try:
            entries = self._bucket().list(prefix)
        except Exception:
            return []
        out = []
        for e in entries or []:
            name = e.get("name")
            if name:
                out.append(f"{prefix.rstrip('/')}/{name}" if prefix else name)
        return out
