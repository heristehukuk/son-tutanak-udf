"""
StorageService'in yerel disk implementasyonu.

Mevcut UPLOAD_DIR / GENERATED_DIR / CUSTOM_TEMPLATE_DIR mantığını birebir korur.
'path' parametresi, o kök klasöre göre GÖRECELİ bir yol olarak kabul edilir
(örn. "documents/abc123.pdf"), böylece ileride SupabaseStorage aynı 'path'
sözleşmesiyle (bucket içinde nesne anahtarı olarak) kolayca yerini alabilir.
"""

from pathlib import Path
from app.storage.base import StorageService


class LocalStorage(StorageService):
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, path: str) -> Path:
        full = (self.root / path).resolve()
        if self.root.resolve() not in full.parents and full != self.root.resolve():
            raise ValueError(f"Geçersiz depolama yolu (kök klasör dışına çıkıyor): {path}")
        return full

    def save(self, path: str, data: bytes, content_type: str | None = None) -> str:
        full = self._resolve(path)
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_bytes(data)
        return str(full)

    def read(self, path: str) -> bytes:
        return self._resolve(path).read_bytes()

    def delete(self, path: str) -> None:
        full = self._resolve(path)
        full.unlink(missing_ok=True)

    def exists(self, path: str) -> bool:
        return self._resolve(path).exists()

    def list(self, prefix: str) -> list[str]:
        base = self._resolve(prefix) if prefix else self.root
        if not base.exists(): return []
        if base.is_file(): return [str(base.relative_to(self.root))]
        return [str(p.relative_to(self.root)) for p in base.rglob("*") if p.is_file()]
