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
                SupabasePlanRepository, SupabaseUsageRepository,
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
        else:
            from app.database_layer.sqlite_repository import (
                SQLiteUserRepository, SQLiteSessionRepository, SQLiteCaseRepository,
                SQLiteDocumentRepository, SQLiteGeneratedDocumentRepository, SQLiteTemplateRepository,
                SQLiteMessageRepository, SQLiteTariffRepository, SQLiteAuditRepository,
                SQLitePlanRepository, SQLiteUsageRepository,
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


# Tek, paylaşılan örnek (singleton).
repos = Repositories(_BACKEND)# Tek, paylaşılan örnek (singleton). İleride Supabase'e geçerken burada bir
# if/else (ortam değişkenine göre) eklenecek - başka hiçbir dosya değişmeyecek.
repos = Repositories()
