"""
Repository factory.

Uygulama kodu (ileride bağlandığında) repoyu buradan alacak, örn:
    from app.database_layer import repos
    repos.users.get(user_id)

ŞU AN: her şey SQLite implementasyonuna işaret ediyor (mevcut app/database.py).
YARIN: burada bir ortam değişkenine (örn. DB_BACKEND=supabase) bakıp
SupabaseUserRepository gibi sınıfları döndürebiliriz. Uygulamanın geri kalanı
tek satır bile değişmeden yeni backend'e geçmiş olur.
"""

from app.database_layer.sqlite_repository import (
    SQLiteUserRepository, SQLiteSessionRepository, SQLiteCaseRepository,
    SQLiteDocumentRepository, SQLiteGeneratedDocumentRepository, SQLiteTemplateRepository,
    SQLiteMessageRepository, SQLiteTariffRepository, SQLiteAuditRepository,
)


class Repositories:
    def __init__(self):
        self.users = SQLiteUserRepository()
        self.sessions = SQLiteSessionRepository()
        self.cases = SQLiteCaseRepository()
        self.documents = SQLiteDocumentRepository()
        self.generated_documents = SQLiteGeneratedDocumentRepository()
        self.templates = SQLiteTemplateRepository()
        self.messages = SQLiteMessageRepository()
        self.tariffs = SQLiteTariffRepository()
        self.audit = SQLiteAuditRepository()


# Tek, paylaşılan örnek (singleton). İleride Supabase'e geçerken burada bir
# if/else (ortam değişkenine göre) eklenecek - başka hiçbir dosya değişmeyecek.
repos = Repositories()
