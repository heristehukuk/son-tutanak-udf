"""
Repository katmanı - soyut arayüzler.

Uygulamanın geri kalanı (auth, files, admin, messaging, customtemplates, feepusula vb.)
veritabanına DOĞRUDAN erişmek yerine bu arayüzler üzerinden konuşacak. Böylece SQLite'tan
Supabase'e, oradan da kendi PostgreSQL sunucunuza geçerken uygulamanın geri kalanına
dokunmamız gerekmeyecek - sadece bu arayüzlerin YENİ bir uygulaması (implementation)
yazılacak (örn. SupabaseUserRepository), mevcut kod aynı kalacak.

ÖNEMLİ: Bu dosya şu an hiçbir yerde KULLANILMIYOR. Mevcut auth/files/admin vb. modülleri
hâlâ eskisi gibi app/database.py + sqlite3 ile doğrudan çalışıyor. Bu, kasıtlı bir tercih:
riskli olan "mevcut kodu bu katmana bağlama" adımını ayrı ve dikkatli yapacağız.
"""

from abc import ABC, abstractmethod
from typing import Optional


class UserRepository(ABC):
    @abstractmethod
    def create(self, user: dict) -> dict: ...

    @abstractmethod
    def get(self, user_id: str) -> Optional[dict]: ...

    @abstractmethod
    def get_by_email(self, email: str) -> Optional[dict]: ...

    @abstractmethod
    def update(self, user_id: str, values: dict) -> Optional[dict]: ...

    @abstractmethod
    def list_all(self) -> list[dict]: ...


class SessionRepository(ABC):
    @abstractmethod
    def create(self, session: dict) -> dict: ...

    @abstractmethod
    def get(self, token: str) -> Optional[dict]: ...

    @abstractmethod
    def delete(self, token: str) -> None: ...


class CaseRepository(ABC):
    @abstractmethod
    def create(self, case: dict) -> dict: ...

    @abstractmethod
    def get(self, case_id: str) -> Optional[dict]: ...

    @abstractmethod
    def update(self, case_id: str, values: dict) -> Optional[dict]: ...

    @abstractmethod
    def list_by_owner(self, owner_id: str) -> list[dict]: ...


class DocumentRepository(ABC):
    @abstractmethod
    def create(self, document: dict) -> dict: ...

    @abstractmethod
    def get(self, document_id: str) -> Optional[dict]: ...

    @abstractmethod
    def list_by_owner(self, owner_id: str) -> list[dict]: ...


class GeneratedDocumentRepository(ABC):
    @abstractmethod
    def create(self, document: dict) -> dict: ...

    @abstractmethod
    def list_by_owner(self, owner_id: str) -> list[dict]: ...


class TemplateRepository(ABC):
    @abstractmethod
    def create(self, template: dict) -> dict: ...

    @abstractmethod
    def get(self, template_id: str) -> Optional[dict]: ...

    @abstractmethod
    def list_visible(self, owner_id: str) -> list[dict]: ...

    @abstractmethod
    def list_all(self) -> list[dict]: ...

    @abstractmethod
    def delete(self, template_id: str) -> None: ...


class MessageRepository(ABC):
    @abstractmethod
    def create(self, message: dict) -> dict: ...

    @abstractmethod
    def list_for_user(self, user_id: str) -> list[dict]: ...


class TariffRepository(ABC):
    @abstractmethod
    def create(self, tariff: dict) -> dict: ...

    @abstractmethod
    def list_all(self) -> list[dict]: ...

    @abstractmethod
    def find_matching(self, category: str, party_count: int, year: Optional[int] = None) -> Optional[dict]: ...

    @abstractmethod
    def delete(self, tariff_id: str) -> None: ...


class AuditRepository(ABC):
    @abstractmethod
    def create(self, record: dict) -> dict: ...

    @abstractmethod
    def list_all(self) -> list[dict]: ...
