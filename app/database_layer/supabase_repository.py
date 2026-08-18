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
    CalendarEventRepository, TaskRepository, TaskTemplateRepository,
    TaskHistoryRepository, PermissionRepository, CounterRepository, FolderRepository,
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

    def delete(self, user_id: str) -> None:
        c = get_supabase()
        c.table("users").delete().eq("id", user_id).execute()


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

    def get_by_registry_no(self, registry_no: str) -> Optional[dict]:
        c = get_supabase()
        r = c.table("cases").select("*").eq("registry_no", registry_no).execute()
        return _first(r.data)

    def list_all_with_owner(self) -> list[dict]:
        c = get_supabase()
        r = (c.table("cases").select("*, users!cases_owner_id_fkey(display_name,email)")
             .order("created_at", desc=False).execute())
        rows = []
        for row in (r.data or []):
            row = dict(row)
            owner = row.pop("users", None) or {}
            row["owner_name"] = owner.get("display_name")
            row["owner_email"] = owner.get("email")
            rows.append(row)
        return rows

    def delete(self, case_id: str) -> None:
        c = get_supabase()
        c.table("cases").delete().eq("id", case_id).execute()


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

    def list_by_case(self, case_id: str) -> list[dict]:
        c = get_supabase()
        r = c.table("documents").select("*").eq("case_id", case_id).execute()
        return r.data or []

    def delete(self, document_id: str) -> None:
        c = get_supabase()
        c.table("documents").delete().eq("id", document_id).execute()

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

    def get(self, document_id: str) -> Optional[dict]:
        c = get_supabase()
        r = c.table("generated_documents").select("*").eq("id", document_id).execute()
        return _first(r.data)

    def list_by_case(self, case_id: str) -> list[dict]:
        c = get_supabase()
        r = c.table("generated_documents").select("*").eq("case_id", case_id).execute()
        return r.data or []

    def delete(self, document_id: str) -> None:
        c = get_supabase()
        c.table("generated_documents").delete().eq("id", document_id).execute()


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

    def list_thread(self, user_a: str, user_b: str) -> list[dict]:
        c = get_supabase()
        r = (c.table("messages").select("*")
             .or_(f"and(sender_id.eq.{user_a},recipient_id.eq.{user_b}),"
                  f"and(sender_id.eq.{user_b},recipient_id.eq.{user_a})")
             .order("created_at", desc=False).execute())
        return r.data or []

    def count_unread(self, recipient_id: str) -> int:
        c = get_supabase()
        r = (c.table("messages").select("id").eq("recipient_id", recipient_id)
             .is_("read_at", "null").execute())
        return len(r.data or [])

    def mark_thread_read(self, recipient_id: str, sender_id: str) -> None:
        from app.auth.service import now
        c = get_supabase()
        (c.table("messages").update({"read_at": now().isoformat()})
         .eq("recipient_id", recipient_id).eq("sender_id", sender_id).is_("read_at", "null").execute())

    def list_for_case(self, case_id: str) -> list[dict]:
        c = get_supabase()
        r = (c.table("messages").select("*, users!messages_sender_id_fkey(display_name)")
             .eq("case_id", case_id).order("created_at", desc=False).execute())
        rows = []
        for row in (r.data or []):
            row = dict(row)
            users_rel = row.pop("users", None) or {}
            row["display_name"] = users_rel.get("display_name")
            rows.append(row)
        return rows

    def delete_for_case(self, case_id: str) -> None:
        c = get_supabase()
        c.table("messages").delete().eq("case_id", case_id).execute()


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


class SupabaseCalendarEventRepository(CalendarEventRepository):
    def create(self, event: dict) -> dict:
        from uuid import uuid4
        event = dict(event)
        event.setdefault("id", str(uuid4()))
        c = get_supabase()
        c.table("calendar_events").insert(event).execute()
        r = c.table("calendar_events").select("*").eq("id", event["id"]).execute()
        return _first(r.data)

    def list_for_case(self, case_id: str) -> list[dict]:
        c = get_supabase()
        r = c.table("calendar_events").select("*").eq("case_id", case_id).order("event_date").execute()
        return r.data or []

    def list_for_owner(self, owner_id: str) -> list[dict]:
        c = get_supabase()
        r = c.table("calendar_events").select("*").eq("owner_id", owner_id).order("event_date").execute()
        return r.data or []

    def delete_for_case(self, case_id: str) -> None:
        c = get_supabase()
        c.table("calendar_events").delete().eq("case_id", case_id).execute()


class SupabaseTaskRepository(TaskRepository):
    def create(self, task: dict) -> dict:
        from uuid import uuid4
        task = dict(task)
        task.setdefault("id", str(uuid4()))
        c = get_supabase()
        c.table("tasks").insert(task).execute()
        return self.get(task["id"])

    def get(self, task_id: str) -> Optional[dict]:
        c = get_supabase()
        r = c.table("tasks").select("*").eq("id", task_id).execute()
        return _first(r.data)

    def update(self, task_id: str, values: dict) -> Optional[dict]:
        if not values: return self.get(task_id)
        c = get_supabase()
        c.table("tasks").update(values).eq("id", task_id).execute()
        return self.get(task_id)

    def list_for_case(self, case_id: str) -> list[dict]:
        c = get_supabase()
        r = c.table("tasks").select("*").eq("case_id", case_id).order("due_date").execute()
        return r.data or []

    def list_for_owner(self, owner_id: str) -> list[dict]:
        c = get_supabase()
        r = c.table("tasks").select("*").eq("owner_id", owner_id).order("due_date").execute()
        return r.data or []


class SupabaseTaskTemplateRepository(TaskTemplateRepository):
    def upsert(self, template: dict) -> dict:
        from uuid import uuid4
        c = get_supabase()
        existing = (c.table("task_templates").select("id")
                    .eq("owner_id", template["owner_id"]).eq("task_key", template["task_key"]).execute())
        if existing.data:
            tid = existing.data[0]["id"]
            values = {k: v for k, v in template.items() if k not in ("id", "owner_id", "task_key", "created_at")}
            c.table("task_templates").update(values).eq("id", tid).execute()
        else:
            template = dict(template)
            template.setdefault("id", str(uuid4()))
            c.table("task_templates").insert(template).execute()
            tid = template["id"]
        r = c.table("task_templates").select("*").eq("id", tid).execute()
        return _first(r.data)

    def list_for_owner(self, owner_id: str) -> list[dict]:
        c = get_supabase()
        r = (c.table("task_templates").select("*").eq("owner_id", owner_id)
             .eq("is_active", 1).order("sort_order").execute())
        return r.data or []


class SupabaseTaskHistoryRepository(TaskHistoryRepository):
    def create(self, record: dict) -> dict:
        from uuid import uuid4
        record = dict(record)
        record.setdefault("id", str(uuid4()))
        c = get_supabase()
        c.table("task_history").insert(record).execute()
        r = c.table("task_history").select("*").eq("id", record["id"]).execute()
        return _first(r.data)

    def list_for_task(self, task_id: str) -> list[dict]:
        c = get_supabase()
        r = c.table("task_history").select("*").eq("task_id", task_id).order("created_at").execute()
        return r.data or []



class SupabaseFolderRepository(FolderRepository):
    def create(self, folder: dict) -> dict:
        from uuid import uuid4
        folder=dict(folder); folder.setdefault("id",str(uuid4()))
        c=get_supabase(); c.table("folders").insert(folder).execute(); return self.get(folder["id"])
    def get(self, folder_id: str):
        return _first(get_supabase().table("folders").select("*").eq("id",folder_id).execute().data)
    def update(self, folder_id: str, values: dict):
        get_supabase().table("folders").update(values).eq("id",folder_id).execute(); return self.get(folder_id)
    def list_for_case(self, case_id: str):
        return get_supabase().table("folders").select("*").eq("case_id",case_id).order("sort_order").order("name").execute().data or []
    def list_by_case(self, owner_id: str, case_id: str):
        return get_supabase().table("folders").select("*").eq("owner_id",owner_id).eq("case_id",case_id).order("sort_order").order("name").execute().data or []
    def get_case_root(self, case_id: str):
        return _first(get_supabase().table("folders").select("*").eq("case_id",case_id).eq("folder_type","root").eq("status","active").limit(1).execute().data)
    def get_by_code(self, case_id: str, code: str, active_only=True):
        q=get_supabase().table("folders").select("*").eq("case_id",case_id).eq("code",code)
        if active_only:q=q.eq("status","active")
        return _first(q.limit(1).execute().data)
    def list_visible_to_user(self, user_id: str, case_id=None):
        c=get_supabase()
        own=c.table("folders").select("*").eq("owner_id",user_id).in_("status",["active","restored"]).execute().data or []
        gen=c.table("folders").select("*").eq("is_global",1).eq("status","active").execute().data or []
        p=c.table("folder_permissions").select("folder_id").eq("user_id",user_id).execute().data or []
        ids=[x["folder_id"] for x in p]
        permitted=c.table("folders").select("*").in_("id",ids).in_("status",["active","restored"]).execute().data if ids else []
        merged={x["id"]:x for x in own+gen+(permitted or [])}
        vals=list(merged.values())
        if case_id: vals=[x for x in vals if x.get("case_id")==case_id]
        return sorted(vals,key=lambda x:(x.get("sort_order",1000),x.get("name", "")))
    def list_general(self):
        return get_supabase().table("folders").select("*").eq("is_global",1).execute().data or []
    def list_all_active_or_deleted(self):
        return get_supabase().table("folders").select("*").order("status").order("sort_order").order("name").execute().data or []
    def list_deleted_before(self, cutoff: str):
        return get_supabase().table("folders").select("*").eq("status","deleted").lt("deleted_at",cutoff).execute().data or []
    def soft_delete(self, folder_id: str, user_id: str):
        from app.auth.service import now
        stamp=now().isoformat(); self.update(folder_id,{"status":"deleted","deleted_at":stamp,"deleted_by":user_id,"updated_at":stamp})
        folder=self.get(folder_id)
        if folder and folder.get("case_id"):
            for child in self.list_for_case(folder["case_id"]):
                if child.get("parent_id")==folder_id and child.get("status")!="deleted": self.update(child["id"],{"status":"deleted","deleted_at":stamp,"deleted_by":user_id,"updated_at":stamp})
        return self.get(folder_id)
    def restore(self, folder_id: str, admin_id: str, restored_parent_id: str):
        from app.auth.service import now
        stamp=now().isoformat(); return self.update(folder_id,{"status":"restored","restored_at":stamp,"restored_by":admin_id,"restored_parent_id":restored_parent_id,"parent_id":restored_parent_id,"updated_at":stamp})
    def purge(self, folder_id: str):
        c=get_supabase(); ids=[folder_id]; i=0
        while i<len(ids):
            ids += [r["id"] for r in (c.table("folders").select("id").eq("parent_id",ids[i]).execute().data or [])]; i+=1
        for fid in reversed(ids):
            c.table("documents").update({"folder_id":None}).eq("folder_id",fid).execute(); c.table("generated_documents").update({"folder_id":None}).eq("folder_id",fid).execute(); c.table("folder_permissions").delete().eq("folder_id",fid).execute(); c.table("folders").delete().eq("id",fid).execute()
    def grant(self, folder_id: str, user_id: str, granted_by: str):
        from uuid import uuid4
        from app.auth.service import now
        c=get_supabase(); e=c.table("folder_permissions").select("id").eq("folder_id",folder_id).eq("user_id",user_id).execute().data or []
        if not e:c.table("folder_permissions").insert({"id":str(uuid4()),"folder_id":folder_id,"user_id":user_id,"granted_by":granted_by,"granted_at":now().isoformat()}).execute()
    def revoke(self, folder_id: str, user_id: str):
        get_supabase().table("folder_permissions").delete().eq("folder_id",folder_id).eq("user_id",user_id).execute()
    def has_permission(self, folder_id: str, user_id: str):
        return bool(get_supabase().table("folder_permissions").select("id").eq("folder_id",folder_id).eq("user_id",user_id).limit(1).execute().data)

class SupabasePermissionRepository(PermissionRepository):
    def grant(self, user_id: str, permission: str, granted_by: Optional[str]) -> dict:
        from uuid import uuid4
        from app.auth.service import now
        c = get_supabase()
        existing = (c.table("user_permissions").select("id")
                    .eq("user_id", user_id).eq("permission", permission).execute())
        if not existing.data:
            c.table("user_permissions").insert({
                "id": str(uuid4()), "user_id": user_id, "permission": permission,
                "granted_at": now().isoformat(), "granted_by": granted_by,
            }).execute()
        return {"user_id": user_id, "permission": permission}

    def revoke(self, user_id: str, permission: str) -> None:
        c = get_supabase()
        c.table("user_permissions").delete().eq("user_id", user_id).eq("permission", permission).execute()

    def list_for_user(self, user_id: str) -> list[str]:
        c = get_supabase()
        r = c.table("user_permissions").select("permission").eq("user_id", user_id).execute()
        return [row["permission"] for row in (r.data or [])]


class SupabaseCounterRepository(CounterRepository):
    def next_value(self, counter_id: str) -> int:
        c = get_supabase()
        r = c.rpc("next_counter", {"counter_id": counter_id}).execute()
        return int(r.data)
