"""
Repository katmanının Supabase implementasyonu.

Her sınıf, app/database_layer/base.py'deki AYNI arayüzü uygular - sadece SQLite
yerine Supabase'e (PostgreSQL) konuşur. Uygulamanın geri kalanı (auth, files,
admin vb.) hangi implementasyonun aktif olduğunu bilmez, sadece `repos.users.get(...)`
gibi çağrılar yapar.

supabase_schema.sql dosyasındaki tabloların Supabase projenizde ÖNCEDEN
oluşturulmuş olması gerekir (Supabase SQL Editor'de çalıştırarak).
"""

from typing import Optional
from app.supabase_client import get_supabase
from app.database_layer.base import (
    UserRepository, SessionRepository, CaseRepository, DocumentRepository,
    GeneratedDocumentRepository, TemplateRepository, MessageRepository,
    TariffRepository, AuditRepository, PlanRepository, UsageRepository,
)


def _first(rows):
    return rows[0] if rows else None


class SupabaseUserRepository(UserRepository):
    def create(self, user: dict) -> dict:
        c = get_supabase()
        c.table("users").insert(user).execute()
        return self.get(user["id"])

    def get(self, user_id: str) -> Optional[dict]:
        c = get_supabase()
        r = c.table("users").select("*").eq("id", user_id).execute()
        return _first(r.data)

    def get_by_email(self, email: str) -> Optional[dict]:
        c = get_supabase()
        r = c.table("users").select("*").eq("email", email).execute()
        return _first(r.data)

    def update(self, user_id: str, values: dict) -> Optional[dict]:
        if not values: return self.get(user_id)
        c = get_supabase()
        c.table("users").update(values).eq("id", user_id).execute()
        return self.get(user_id)

    def list_all(self) -> list[dict]:
        c = get_supabase()
        r = c.table("users").select("*").order("created_at", desc=True).execute()
        return r.data or []


class SupabaseSessionRepository(SessionRepository):
    def create(self, session: dict) -> dict:
        c = get_supabase()
        c.table("sessions").insert(session).execute()
        return session

    def get(self, token: str) -> Optional[dict]:
        c = get_supabase()
        r = c.table("sessions").select("*").eq("token", token).execute()
        return _first(r.data)

    def delete(self, token: str) -> None:
        c = get_supabase()
        c.table("sessions").delete().eq("token", token).execute()


class SupabaseCaseRepository(CaseRepository):
    def create(self, case: dict) -> dict:
        from uuid import uuid4
        case = dict(case)
        case.setdefault("id", str(uuid4()))
        c = get_supabase()
        c.table("cases").insert(case).execute()
        return self.get(case["id"])

    def get(self, case_id: str) -> Optional[dict]:
        c = get_supabase()
        r = c.table("cases").select("*").eq("id", case_id).execute()
        return _first(r.data)

    def update(self, case_id: str, values: dict) -> Optional[dict]:
        if not values: return self.get(case_id)
        c = get_supabase()
        c.table("cases").update(values).eq("id", case_id).execute()
        return self.get(case_id)

    def list_by_owner(self, owner_id: str) -> list[dict]:
        c = get_supabase()
        r = c.table("cases").select("*").eq("owner_id", owner_id).order("updated_at", desc=True).execute()
        return r.data or []


class SupabaseDocumentRepository(DocumentRepository):
    def create(self, document: dict) -> dict:
        from uuid import uuid4
        document = dict(document)
        document.setdefault("id", str(uuid4()))
        c = get_supabase()
        c.table("documents").insert(document).execute()
        return self.get(document["id"])

    def get(self, document_id: str) -> Optional[dict]:
        c = get_supabase()
        r = c.table("documents").select("*").eq("id", document_id).execute()
        return _first(r.data)

    def list_by_owner(self, owner_id: str) -> list[dict]:
        c = get_supabase()
        r = c.table("documents").select("*").eq("owner_id", owner_id).order("created_at", desc=True).execute()
        return r.data or []

    def list_all_with_owner_email(self) -> list[dict]:
        # Supabase PostgREST tek sorguda foreign-table join'i "select" içinde ilişkiyle yapar.
        c = get_supabase()
        r = c.table("documents").select("*, users(email)").order("created_at", desc=True).execute()
        rows = []
        for row in (r.data or []):
            row = dict(row)
            users_rel = row.pop("users", None) or {}
            row["email"] = users_rel.get("email")
            rows.append(row)
        return rows


class SupabaseGeneratedDocumentRepository(GeneratedDocumentRepository):
    def create(self, document: dict) -> dict:
        from uuid import uuid4
        document = dict(document)
        document.setdefault("id", str(uuid4()))
        c = get_supabase()
        c.table("generated_documents").insert(document).execute()
        r = c.table("generated_documents").select("*").eq("id", document["id"]).execute()
        return _first(r.data)

    def list_by_owner(self, owner_id: str) -> list[dict]:
        c = get_supabase()
        r = c.table("generated_documents").select("*").eq("owner_id", owner_id).order("created_at", desc=True).execute()
        return r.data or []


class SupabaseTemplateRepository(TemplateRepository):
    def create(self, template: dict) -> dict:
        from uuid import uuid4
        template = dict(template)
        template.setdefault("id", str(uuid4()))
        c = get_supabase()
        c.table("custom_templates").insert(template).execute()
        return self.get(template["id"])

    def get(self, template_id: str) -> Optional[dict]:
        c = get_supabase()
        r = c.table("custom_templates").select("*").eq("id", template_id).execute()
        return _first(r.data)

    def list_visible(self, owner_id: str) -> list[dict]:
        c = get_supabase()
        r = (c.table("custom_templates").select("*")
             .or_(f"owner_id.eq.{owner_id},is_shared.eq.1")
             .order("created_at", desc=True).execute())
        return r.data or []

    def list_all(self) -> list[dict]:
        c = get_supabase()
        r = c.table("custom_templates").select("*, users(display_name, email)").order("created_at", desc=True).execute()
        rows = []
        for row in (r.data or []):
            row = dict(row)
            users_rel = row.pop("users", None) or {}
            row["owner_name"] = users_rel.get("display_name")
            row["owner_email"] = users_rel.get("email")
            rows.append(row)
        return rows

    def delete(self, template_id: str) -> None:
        c = get_supabase()
        c.table("custom_templates").delete().eq("id", template_id).execute()


class SupabaseMessageRepository(MessageRepository):
    def create(self, message: dict) -> dict:
        from uuid import uuid4
        message = dict(message)
        message.setdefault("id", str(uuid4()))
        c = get_supabase()
        c.table("messages").insert(message).execute()
        r = c.table("messages").select("*").eq("id", message["id"]).execute()
        return _first(r.data)

    def list_for_user(self, user_id: str) -> list[dict]:
        c = get_supabase()
        r = (c.table("messages").select("*")
             .or_(f"sender_id.eq.{user_id},recipient_id.eq.{user_id}")
             .order("created_at", desc=True).execute())
        return r.data or []

    def list_inbox_with_sender_name(self, recipient_id: str) -> list[dict]:
        c = get_supabase()
        r = (c.table("messages").select("*, users!messages_sender_id_fkey(display_name)")
             .eq("recipient_id", recipient_id).order("created_at", desc=True).execute())
        rows = []
        for row in (r.data or []):
            row = dict(row)
            users_rel = row.pop("users", None) or {}
            row["display_name"] = users_rel.get("display_name")
            rows.append(row)
        return rows


class SupabaseTariffRepository(TariffRepository):
    def create(self, tariff: dict) -> dict:
        from uuid import uuid4
        tariff = dict(tariff)
        tariff.setdefault("id", str(uuid4()))
        c = get_supabase()
        c.table("fee_tariffs").insert(tariff).execute()
        r = c.table("fee_tariffs").select("*").eq("id", tariff["id"]).execute()
        return _first(r.data)

    def list_all(self) -> list[dict]:
        c = get_supabase()
        r = c.table("fee_tariffs").select("*").order("year", desc=True).order("category").order("min_parties").execute()
        return r.data or []

    def find_matching(self, category: str, party_count: int, year: Optional[int] = None) -> Optional[dict]:
        c = get_supabase()
        q = c.table("fee_tariffs").select("*").eq("category", category)
        if year:
            q = q.eq("year", year)
        rows = q.execute().data or []
        if not year and rows:
            max_year = max(r["year"] for r in rows)
            rows = [r for r in rows if r["year"] == max_year]
        for r in rows:
            if r["min_parties"] <= party_count and (r["max_parties"] is None or party_count <= r["max_parties"]):
                return r
        return None

    def delete(self, tariff_id: str) -> None:
        c = get_supabase()
        c.table("fee_tariffs").delete().eq("id", tariff_id).execute()


class SupabaseAuditRepository(AuditRepository):
    def create(self, record: dict) -> dict:
        c = get_supabase()
        r = c.table("audit_logs").insert(record).execute()
        return _first(r.data) or record

    def list_all(self) -> list[dict]:
        c = get_supabase()
        r = c.table("audit_logs").select("*").order("created_at", desc=True).execute()
        return r.data or []


class SupabasePlanRepository(PlanRepository):
    def seed_defaults(self, plans: list[dict]) -> None:
        c = get_supabase()
        for p in plans:
            existing = c.table("plans").select("id").eq("id", p["id"]).execute()
            if not existing.data:
                c.table("plans").insert(p).execute()

    def get(self, plan_id: str) -> Optional[dict]:
        c = get_supabase()
        r = c.table("plans").select("*").eq("id", plan_id).execute()
        return _first(r.data)

    def list_all(self) -> list[dict]:
        c = get_supabase()
        r = c.table("plans").select("*").order("price_monthly").order("id").execute()
        return r.data or []


class SupabaseUsageRepository(UsageRepository):
    def sum_amount(self, user_id: str, metric: str, period: str) -> int:
        c = get_supabase()
        r = (c.table("usage").select("amount").eq("user_id", user_id)
             .eq("metric", metric).eq("period", period).execute())
        return sum(row["amount"] for row in (r.data or []))

    def record(self, usage: dict) -> dict:
        c = get_supabase()
        r = c.table("usage").insert(usage).execute()
        return _first(r.data) or usage
