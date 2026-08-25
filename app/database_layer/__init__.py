"""
Repository factory.

Uygulama kodu repoyu buradan alır, örn:
    from app.database_layer import repos
    repos.users.get(user_id)

Hangi backend'in (SQLite/Supabase) kullanılacağı DB_BACKEND ortam değişkeniyle
kontrol edilir:
    DB_BACKEND=sqlite    (veya hiç ayarlanmamışsa) -> SQLite kullanılır (varsayılan, güvenli)
    DB_BACKEND=supabase  -> Supabase (PostgreSQL) kullanılır

Böylece geçiş TEK bir ortam değişkeniyle, geri dönülebilir şekilde yapılır.
Render'da bu değişkeni eklemeden önce Supabase tablolarının (supabase_schema.sql)
oluşturulmuş olması gerekir.
"""

import os

_BACKEND = os.getenv("DB_BACKEND", "sqlite").strip().lower()


class Repositories:
    def __init__(self, backend: str):
        if backend == "supabase":
            from app.database_layer.supabase_repository import (
                SupabaseUserRepository, SupabaseSessionRepository, SupabaseCaseRepository,
                SupabaseDocumentRepository, SupabaseGeneratedDocumentRepository, SupabaseTemplateRepository,
                SupabaseMessageRepository, SupabaseTariffRepository, SupabaseAuditRepository,
                SupabasePlanRepository, SupabaseUsageRepository, SupabaseCalendarEventRepository,
                SupabaseTaskRepository, SupabaseTaskTemplateRepository, SupabaseTaskHistoryRepository,
                SupabasePermissionRepository, SupabaseCounterRepository, SupabaseFolderRepository, SupabasePendingMergeRepository,
            )
            self.users = SupabaseUserRepository()
            self.sessions = SupabaseSessionRepository()
            self.cases = SupabaseCaseRepository()
            self.documents = SupabaseDocumentRepository()
            self.generated_documents = SupabaseGeneratedDocumentRepository()
            self.templates = SupabaseTemplateRepository()
            self.messages = SupabaseMessageRepository()
            self.tariffs = SupabaseTariffRepository()
            self.audit = SupabaseAuditRepository()
            self.plans = SupabasePlanRepository()
            self.usage = SupabaseUsageRepository()
            self.calendar_events = SupabaseCalendarEventRepository()
            self.tasks = SupabaseTaskRepository()
            self.task_templates = SupabaseTaskTemplateRepository()
            self.task_history = SupabaseTaskHistoryRepository()
            self.permissions = SupabasePermissionRepository()
            self.counters = SupabaseCounterRepository()
            self.folders = SupabaseFolderRepository()
            self.pending_merges = SupabasePendingMergeRepository()
        else:
            from app.database_layer.sqlite_repository import (
                SQLiteUserRepository, SQLiteSessionRepository, SQLiteCaseRepository,
                SQLiteDocumentRepository, SQLiteGeneratedDocumentRepository, SQLiteTemplateRepository,
                SQLiteMessageRepository, SQLiteTariffRepository, SQLiteAuditRepository,
                SQLitePlanRepository, SQLiteUsageRepository, SQLiteCalendarEventRepository,
                SQLiteTaskRepository, SQLiteTaskTemplateRepository, SQLiteTaskHistoryRepository,
                SQLitePermissionRepository, SQLiteCounterRepository, SQLiteFolderRepository, SQLitePendingMergeRepository,
            )
            self.users = SQLiteUserRepository()
            self.sessions = SQLiteSessionRepository()
            self.cases = SQLiteCaseRepository()
            self.documents = SQLiteDocumentRepository()
            self.generated_documents = SQLiteGeneratedDocumentRepository()
            self.templates = SQLiteTemplateRepository()
            self.messages = SQLiteMessageRepository()
            self.tariffs = SQLiteTariffRepository()
            self.audit = SQLiteAuditRepository()
            self.plans = SQLitePlanRepository()
            self.usage = SQLiteUsageRepository()
            self.calendar_events = SQLiteCalendarEventRepository()
            self.tasks = SQLiteTaskRepository()
            self.task_templates = SQLiteTaskTemplateRepository()
            self.task_history = SQLiteTaskHistoryRepository()
            self.permissions = SQLitePermissionRepository()
            self.counters = SQLiteCounterRepository()
            self.folders = SQLiteFolderRepository()
            self.pending_merges = SQLitePendingMergeRepository()


# Tek, paylaşılan örnek (singleton).
repos = Repositories(_BACKEND)
