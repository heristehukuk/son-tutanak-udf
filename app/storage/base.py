"""
Storage katmanı - soyut arayüz.

Şu an dosyalar (yüklenen belgeler, üretilen UDF'ler, özel şablonlar, harcama pusulaları)
doğrudan yerel diske (Path.write_bytes vb.) yazılıyor. Bu arayüz sayesinde ileride
Supabase Storage'a, sonra kendi sunucunuza (yerel disk/S3/MinIO) geçerken uygulamanın
geri kalanına dokunmayacağız.

ÖNEMLİ: Bu dosya şu an hiçbir yerde KULLANILMIYOR. files/service.py, customtemplates/service.py,
feepusula/service.py hâlâ doğrudan Path ile çalışıyor. Bağlama işi ayrı bir adımda yapılacak.
"""

from abc import ABC, abstractmethod


class StorageService(ABC):
    @abstractmethod
    def save(self, path: str, data: bytes, content_type: str | None = None) -> str:
        """Veriyi kaydeder, kalıcı bir referans (path/url) döner."""
        ...

    @abstractmethod
    def read(self, path: str) -> bytes:
        ...

    @abstractmethod
    def delete(self, path: str) -> None:
        ...

    @abstractmethod
    def exists(self, path: str) -> bool:
        ...

    @abstractmethod
    def list(self, prefix: str) -> list[str]:
        ...
