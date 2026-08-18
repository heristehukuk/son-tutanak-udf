"""
Repository katmanı - soyut arayüzler.

Uygulamanın geri kalanı (auth, files, admin, messaging, customtemplates, feepusula vb.)
veritabanına DOĞRUDAN erişmek yerine bu arayüzler üzerinden konuşacak. Böylece SQLite'tan
Supabase'e, oradan da kendi PostgreSQL sunucunuza geçerken uygulamanın geri kalanına
dokunmamız gerekmeyecek - sadece bu arayüzlerin YENİ bir uygulaması (implementation)
yazılacak (örn. SupabaseUserRepository), mevcut kod aynı kalacak.

Uygulamanın tamamı (auth/files/admin/messaging/calendar/tasks vb.) bu arayüzler
üzerinden çalışır; hangi implementasyonun (SQLite/Supabase) aktif olduğunu
`app/database_layer/__init__.py` DB_BACKEND ortam değişkenine göre seçer.
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

    @abstractmethod
    def delete(self, user_id: str) -> None: ...


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

    @abstractmethod
    def get_by_registry_no(self, registry_no: str) -> Optional[dict]: ...

    @abstractmethod
    def list_all_with_owner(self) -> list[dict]:
        """Admin paneli için: her dosyayı sahibinin adı/e-postasıyla birlikte döner."""
        ...

    @abstractmethod
    def delete(self, case_id: str) -> None: ...


class CounterRepository(ABC):
    @abstractmethod
    def next_value(self, counter_id: str) -> int:
        """Verilen anahtar için bir sonraki sırayı ATOMİK olarak döner (yarış
        durumuna karşı güvenli - iki dosya aynı anda oluşsa bile aynı numarayı
        alamaz)."""
        ...


class DocumentRepository(ABC):
    @abstractmethod
    def create(self, document: dict) -> dict: ...

    @abstractmethod
    def get(self, document_id: str) -> Optional[dict]: ...

    @abstractmethod
    def list_by_owner(self, owner_id: str) -> list[dict]: ...

    @abstractmethod
    def list_by_case(self, case_id: str) -> list[dict]: ...

    @abstractmethod
    def list_all_with_owner_email(self) -> list[dict]:
        """Admin paneli için: her belgeyi sahibinin e-postasıyla birlikte döner."""
        ...

    @abstractmethod
    def delete(self, document_id: str) -> None: ...


class GeneratedDocumentRepository(ABC):
    @abstractmethod
    def create(self, document: dict) -> dict: ...

    @abstractmethod
    def get(self, document_id: str) -> Optional[dict]: ...

    @abstractmethod
    def list_by_owner(self, owner_id: str) -> list[dict]: ...

    @abstractmethod
    def list_by_case(self, case_id: str) -> list[dict]: ...

    @abstractmethod
    def delete(self, document_id: str) -> None: ...


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

    @abstractmethod
    def list_inbox_with_sender_name(self, recipient_id: str) -> list[dict]:
        """Gelen kutusu: her mesajı gönderenin adıyla birlikte döner."""
        ...

    @abstractmethod
    def list_thread(self, user_a: str, user_b: str) -> list[dict]:
        """İki kullanıcı arasındaki tüm mesajlar, kronolojik sırayla."""
        ...

    @abstractmethod
    def count_unread(self, recipient_id: str) -> int: ...

    @abstractmethod
    def mark_thread_read(self, recipient_id: str, sender_id: str) -> None: ...

    @abstractmethod
    def list_for_case(self, case_id: str) -> list[dict]: ...

    @abstractmethod
    def delete_for_case(self, case_id: str) -> None: ...


class CalendarEventRepository(ABC):
    @abstractmethod
    def create(self, event: dict) -> dict: ...

    @abstractmethod
    def list_for_case(self, case_id: str) -> list[dict]: ...

    @abstractmethod
    def list_for_owner(self, owner_id: str) -> list[dict]: ...

    @abstractmethod
    def delete_for_case(self, case_id: str) -> None: ...


class TaskRepository(ABC):
    @abstractmethod
    def create(self, task: dict) -> dict: ...

    @abstractmethod
    def get(self, task_id: str) -> Optional[dict]: ...

    @abstractmethod
    def update(self, task_id: str, values: dict) -> Optional[dict]: ...

    @abstractmethod
    def list_for_case(self, case_id: str) -> list[dict]: ...

    @abstractmethod
    def list_for_owner(self, owner_id: str) -> list[dict]: ...


class TaskTemplateRepository(ABC):
    @abstractmethod
    def upsert(self, template: dict) -> dict: ...

    @abstractmethod
    def list_for_owner(self, owner_id: str) -> list[dict]: ...


class TaskHistoryRepository(ABC):
    @abstractmethod
    def create(self, record: dict) -> dict: ...

    @abstractmethod
    def list_for_task(self, task_id: str) -> list[dict]: ...


class PermissionRepository(ABC):
    @abstractmethod
    def grant(self, user_id: str, permission: str, granted_by: Optional[str]) -> dict: ...

    @abstractmethod
    def revoke(self, user_id: str, permission: str) -> None: ...

    @abstractmethod
    def list_for_user(self, user_id: str) -> list[str]: ...


class FolderRepository(ABC):
    @abstractmethod
    def create(self, folder: dict) -> dict: ...
    @abstractmethod
    def get(self, folder_id: str) -> Optional[dict]: ...
    @abstractmethod
    def update(self, folder_id: str, values: dict) -> Optional[dict]: ...
    @abstractmethod
    def list_for_case(self, case_id: str) -> list[dict]: ...
    @abstractmethod
    def list_by_case(self, owner_id: str, case_id: str) -> list[dict]: ...
    @abstractmethod
    def get_case_root(self, case_id: str) -> Optional[dict]: ...
    @abstractmethod
    def get_by_code(self, case_id: str, code: str, active_only: bool = True) -> Optional[dict]: ...
    @abstractmethod
    def list_visible_to_user(self, user_id: str, case_id: Optional[str] = None) -> list[dict]: ...
    @abstractmethod
    def list_general(self) -> list[dict]: ...
    @abstractmethod
    def list_all_active_or_deleted(self) -> list[dict]: ...
    @abstractmethod
    def list_deleted_before(self, cutoff: str) -> list[dict]: ...
    @abstractmethod
    def soft_delete(self, folder_id: str, user_id: str) -> dict: ...
    @abstractmethod
    def restore(self, folder_id: str, admin_id: str, restored_parent_id: str) -> dict: ...
    @abstractmethod
    def purge(self, folder_id: str) -> None: ...
    @abstractmethod
    def grant(self, folder_id: str, user_id: str, granted_by: str) -> None: ...
    @abstractmethod
    def revoke(self, folder_id: str, user_id: str) -> None: ...
    @abstractmethod
    def has_permission(self, folder_id: str, user_id: str) -> bool: ...


class PlanRepository(ABC):
    @abstractmethod
    def seed_defaults(self, plans: list[dict]) -> None: ...

    @abstractmethod
    def get(self, plan_id: str) -> Optional[dict]: ...

    @abstractmethod
    def list_all(self) -> list[dict]: ...


class UsageRepository(ABC):
    @abstractmethod
    def sum_amount(self, user_id: str, metric: str, period: str) -> int: ...

    @abstractmethod
    def record(self, usage: dict) -> dict: ...


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
