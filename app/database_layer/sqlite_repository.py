"""
Repository katmanının SQLite implementasyonu.

Bu sınıflar, app/database.py içindeki MEVCUT şemayı birebir kullanır - hiçbir tablo
değişmedi, hiçbir sorgu davranışı değişmedi. Amaç sadece "ham SQL her yerde dağınık"
durumundan "tek bir yerden, isimlendirilmiş fonksiyonlarla erişim" durumuna geçmek.

Henüz uygulamanın geri kalanı bunu KULLANMIYOR (main.py, auth/service.py, files/service.py
vb. hâlâ eski hâliyle çalışıyor). Bu, sonraki adımda dikkatlice bağlanacak.
"""

from uuid import uuid4
from typing import Optional
from app.database import connect
from app.database_layer.base import (
    UserRepository, SessionRepository, CaseRepository, DocumentRepository,
    GeneratedDocumentRepository, TemplateRepository, MessageRepository,
    TariffRepository, AuditRepository, PlanRepository, UsageRepository,
    CalendarEventRepository, TaskRepository, TaskTemplateRepository,
    TaskHistoryRepository, PermissionRepository, CounterRepository, FolderRepository,
)


def _row_to_dict(row) -> Optional[dict]:
    return dict(row) if row is not None else None


class SQLiteUserRepository(UserRepository):
    def create(self, user: dict) -> dict:
        user = dict(user)
        user.setdefault("id", str(uuid4()))
        cols = ",".join(user.keys())
        placeholders = ",".join("?" for _ in user)
        with connect() as c:
            c.execute(f"INSERT INTO users ({cols}) VALUES ({placeholders})", tuple(user.values()))
        return self.get(user["id"])

    def get(self, user_id: str) -> Optional[dict]:
        with connect() as c:
            row = c.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        return _row_to_dict(row)

    def get_by_email(self, email: str) -> Optional[dict]:
        with connect() as c:
            row = c.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        return _row_to_dict(row)

    def update(self, user_id: str, values: dict) -> Optional[dict]:
        if not values: return self.get(user_id)
        cols = ",".join(f"{k}=?" for k in values)
        with connect() as c:
            c.execute(f"UPDATE users SET {cols} WHERE id=?", (*values.values(), user_id))
        return self.get(user_id)

    def delete(self, user_id: str) -> None:
        with connect() as c:
            c.execute("DELETE FROM users WHERE id=?", (user_id,))

    def list_all(self) -> list[dict]:
        with connect() as c:
            rows = c.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]


class SQLiteSessionRepository(SessionRepository):
    def create(self, session: dict) -> dict:
        with connect() as c:
            c.execute("""INSERT INTO sessions (token,user_id,created_at,expires_at,ip)
                VALUES(?,?,?,?,?)""",
                (session["token"], session["user_id"], session["created_at"],
                 session["expires_at"], session.get("ip")))
        return session

    def get(self, token: str) -> Optional[dict]:
        with connect() as c:
            row = c.execute("SELECT * FROM sessions WHERE token=?", (token,)).fetchone()
        return _row_to_dict(row)

    def delete(self, token: str) -> None:
        with connect() as c:
            c.execute("DELETE FROM sessions WHERE token=?", (token,))


class SQLiteCaseRepository(CaseRepository):
    def create(self, case: dict) -> dict:
        cid = case.get("id") or str(uuid4())
        with connect() as c:
            c.execute("""INSERT INTO cases
                (id,owner_id,file_no,application_no,title,file_type,start_date,status,case_data_json,registry_no,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                (cid, case["owner_id"], case.get("file_no"), case.get("application_no"),
                 case.get("title"), case.get("file_type"), case.get("start_date"),
                 case.get("status", "open"), case.get("case_data_json"), case.get("registry_no"),
                 case["created_at"], case["updated_at"]))
        return self.get(cid)

    def get(self, case_id: str) -> Optional[dict]:
        with connect() as c:
            row = c.execute("SELECT * FROM cases WHERE id=?", (case_id,)).fetchone()
        return _row_to_dict(row)

    def update(self, case_id: str, values: dict) -> Optional[dict]:
        if not values: return self.get(case_id)
        cols = ",".join(f"{k}=?" for k in values)
        with connect() as c:
            c.execute(f"UPDATE cases SET {cols} WHERE id=?", (*values.values(), case_id))
        return self.get(case_id)

    def list_by_owner(self, owner_id: str) -> list[dict]:
        with connect() as c:
            rows = c.execute("SELECT * FROM cases WHERE owner_id=? ORDER BY updated_at DESC", (owner_id,)).fetchall()
        return [dict(r) for r in rows]

    def get_by_registry_no(self, registry_no: str) -> Optional[dict]:
        with connect() as c:
            row = c.execute("SELECT * FROM cases WHERE registry_no=?", (registry_no,)).fetchone()
        return _row_to_dict(row)

    def list_all_with_owner(self) -> list[dict]:
        with connect() as c:
            rows = c.execute("""SELECT cases.*, users.display_name AS owner_name, users.email AS owner_email
                FROM cases JOIN users ON users.id=cases.owner_id ORDER BY cases.created_at ASC""").fetchall()
        return [dict(r) for r in rows]

    def delete(self, case_id: str) -> None:
        with connect() as c:
            c.execute("DELETE FROM cases WHERE id=?", (case_id,))


class SQLiteDocumentRepository(DocumentRepository):
    def create(self, document: dict) -> dict:
        did = document.get("id") or str(uuid4())
        with connect() as c:
            c.execute("""INSERT INTO documents
                (id,case_id,folder_id,owner_id,original_name,stored_path,kind,size_bytes,created_at)
                VALUES(?,?,?,?,?,?,?,?,?)""",
                (did, document.get("case_id"), document.get("folder_id"), document["owner_id"], document["original_name"],
                 document["stored_path"], document["kind"], document["size_bytes"], document["created_at"]))
        return self.get(did)

    def get(self, document_id: str) -> Optional[dict]:
        with connect() as c:
            row = c.execute("SELECT * FROM documents WHERE id=?", (document_id,)).fetchone()
        return _row_to_dict(row)

    def list_by_owner(self, owner_id: str) -> list[dict]:
        with connect() as c:
            rows = c.execute("SELECT * FROM documents WHERE owner_id=? ORDER BY created_at DESC", (owner_id,)).fetchall()
        return [dict(r) for r in rows]

    def list_by_case(self, case_id: str) -> list[dict]:
        with connect() as c:
            rows = c.execute("SELECT * FROM documents WHERE case_id=?", (case_id,)).fetchall()
        return [dict(r) for r in rows]

    def delete(self, document_id: str) -> None:
        with connect() as c:
            c.execute("DELETE FROM documents WHERE id=?", (document_id,))

    def list_all_with_owner_email(self) -> list[dict]:
        with connect() as c:
            rows = c.execute("""SELECT d.*,u.email FROM documents d JOIN users u ON u.id=d.owner_id
                ORDER BY d.created_at DESC""").fetchall()
        return [dict(r) for r in rows]


class SQLiteGeneratedDocumentRepository(GeneratedDocumentRepository):
    def create(self, document: dict) -> dict:
        did = document.get("id") or str(uuid4())
        with connect() as c:
            c.execute("""INSERT INTO generated_documents
                (id,case_id,folder_id,owner_id,original_template,stored_path,doc_kind,created_at)
                VALUES(?,?,?,?,?,?,?,?)""",
                (did, document.get("case_id"), document["owner_id"], document["original_template"],
                 document["stored_path"], document.get("doc_kind"), document["created_at"]))
        with connect() as c:
            row = c.execute("SELECT * FROM generated_documents WHERE id=?", (did,)).fetchone()
        return _row_to_dict(row)

    def list_by_owner(self, owner_id: str) -> list[dict]:
        with connect() as c:
            rows = c.execute("SELECT * FROM generated_documents WHERE owner_id=? ORDER BY created_at DESC", (owner_id,)).fetchall()
        return [dict(r) for r in rows]

    def list_by_case(self, case_id: str) -> list[dict]:
        with connect() as c:
            rows = c.execute("SELECT * FROM generated_documents WHERE case_id=?", (case_id,)).fetchall()
        return [dict(r) for r in rows]

    def delete(self, document_id: str) -> None:
        with connect() as c:
            c.execute("DELETE FROM generated_documents WHERE id=?", (document_id,))

    def get(self, document_id: str) -> Optional[dict]:
        with connect() as c:
            row = c.execute("SELECT * FROM generated_documents WHERE id=?", (document_id,)).fetchone()
        return _row_to_dict(row)


class SQLiteTemplateRepository(TemplateRepository):
    def create(self, template: dict) -> dict:
        tid = template.get("id") or str(uuid4())
        with connect() as c:
            c.execute("""INSERT INTO custom_templates
                (id,owner_id,name,is_shared,stored_path,recognized_json,unrecognized_json,created_at)
                VALUES(?,?,?,?,?,?,?,?)""",
                (tid, template["owner_id"], template["name"], int(template.get("is_shared", 0)),
                 template["stored_path"], template["recognized_json"], template["unrecognized_json"],
                 template["created_at"]))
        return self.get(tid)

    def get(self, template_id: str) -> Optional[dict]:
        with connect() as c:
            row = c.execute("SELECT * FROM custom_templates WHERE id=?", (template_id,)).fetchone()
        return _row_to_dict(row)

    def list_visible(self, owner_id: str) -> list[dict]:
        with connect() as c:
            rows = c.execute("""SELECT * FROM custom_templates
                WHERE owner_id=? OR is_shared=1 ORDER BY created_at DESC""", (owner_id,)).fetchall()
        return [dict(r) for r in rows]

    def list_all(self) -> list[dict]:
        with connect() as c:
            rows = c.execute("""SELECT ct.*, u.display_name AS owner_name, u.email AS owner_email
                FROM custom_templates ct JOIN users u ON u.id=ct.owner_id
                ORDER BY ct.created_at DESC""").fetchall()
        return [dict(r) for r in rows]

    def delete(self, template_id: str) -> None:
        with connect() as c:
            c.execute("DELETE FROM custom_templates WHERE id=?", (template_id,))


class SQLiteMessageRepository(MessageRepository):
    def create(self, message: dict) -> dict:
        mid = message.get("id") or str(uuid4())
        with connect() as c:
            c.execute("""INSERT INTO messages (id,sender_id,recipient_id,case_id,body,created_at)
                VALUES(?,?,?,?,?,?)""",
                (mid, message["sender_id"], message["recipient_id"], message.get("case_id"),
                 message["body"], message["created_at"]))
        with connect() as c:
            row = c.execute("SELECT * FROM messages WHERE id=?", (mid,)).fetchone()
        return _row_to_dict(row)

    def list_for_user(self, user_id: str) -> list[dict]:
        with connect() as c:
            rows = c.execute("""SELECT * FROM messages WHERE sender_id=? OR recipient_id=?
                ORDER BY created_at DESC""", (user_id, user_id)).fetchall()
        return [dict(r) for r in rows]

    def list_inbox_with_sender_name(self, recipient_id: str) -> list[dict]:
        with connect() as c:
            rows = c.execute("""SELECT m.*,u.display_name FROM messages m JOIN users u ON u.id=m.sender_id
                WHERE m.recipient_id=? ORDER BY m.created_at DESC""", (recipient_id,)).fetchall()
        return [dict(r) for r in rows]

    def list_thread(self, user_a: str, user_b: str) -> list[dict]:
        with connect() as c:
            rows = c.execute("""SELECT * FROM messages
                WHERE (sender_id=? AND recipient_id=?) OR (sender_id=? AND recipient_id=?)
                ORDER BY created_at ASC""", (user_a, user_b, user_b, user_a)).fetchall()
        return [dict(r) for r in rows]

    def count_unread(self, recipient_id: str) -> int:
        with connect() as c:
            row = c.execute("""SELECT COUNT(*) n FROM messages
                WHERE recipient_id=? AND read_at IS NULL""", (recipient_id,)).fetchone()
        return int(row["n"])

    def mark_thread_read(self, recipient_id: str, sender_id: str) -> None:
        from app.auth.service import now
        with connect() as c:
            c.execute("""UPDATE messages SET read_at=? WHERE recipient_id=? AND sender_id=? AND read_at IS NULL""",
                (now().isoformat(), recipient_id, sender_id))

    def list_for_case(self, case_id: str) -> list[dict]:
        with connect() as c:
            rows = c.execute("""SELECT m.*,u.display_name FROM messages m JOIN users u ON u.id=m.sender_id
                WHERE m.case_id=? ORDER BY m.created_at ASC""", (case_id,)).fetchall()
        return [dict(r) for r in rows]

    def delete_for_case(self, case_id: str) -> None:
        with connect() as c:
            c.execute("DELETE FROM messages WHERE case_id=?", (case_id,))


class SQLitePlanRepository(PlanRepository):
    def seed_defaults(self, plans: list[dict]) -> None:
        with connect() as c:
            for p in plans:
                c.execute("""INSERT OR IGNORE INTO plans
                    (id,name,price_monthly,features_json,limits_json) VALUES(?,?,?,?,?)""",
                    (p["id"], p["name"], p["price_monthly"], p["features_json"], p["limits_json"]))

    def get(self, plan_id: str) -> Optional[dict]:
        with connect() as c:
            row = c.execute("SELECT * FROM plans WHERE id=?", (plan_id,)).fetchone()
        return _row_to_dict(row)

    def list_all(self) -> list[dict]:
        with connect() as c:
            rows = c.execute("SELECT * FROM plans ORDER BY price_monthly,id").fetchall()
        return [dict(r) for r in rows]


class SQLiteUsageRepository(UsageRepository):
    def sum_amount(self, user_id: str, metric: str, period: str) -> int:
        with connect() as c:
            row = c.execute("""SELECT COALESCE(SUM(amount),0) n FROM usage
                WHERE user_id=? AND metric=? AND period=?""", (user_id, metric, period)).fetchone()
        return int(row["n"])

    def record(self, usage: dict) -> dict:
        with connect() as c:
            cur = c.execute("""INSERT INTO usage(user_id,metric,amount,period,created_at)
                VALUES(?,?,?,?,?)""",
                (usage["user_id"], usage["metric"], usage["amount"], usage["period"], usage["created_at"]))
            rid = cur.lastrowid
        with connect() as c:
            row = c.execute("SELECT * FROM usage WHERE id=?", (rid,)).fetchone()
        return _row_to_dict(row)


class SQLiteTariffRepository(TariffRepository):
    def create(self, tariff: dict) -> dict:
        tid = tariff.get("id") or str(uuid4())
        with connect() as c:
            c.execute("""INSERT INTO fee_tariffs
                (id,category,category_label,min_parties,max_parties,unit_price,year,updated_at)
                VALUES(?,?,?,?,?,?,?,?)""",
                (tid, tariff["category"], tariff["category_label"], tariff["min_parties"],
                 tariff.get("max_parties"), tariff["unit_price"], tariff["year"], tariff["updated_at"]))
        with connect() as c:
            row = c.execute("SELECT * FROM fee_tariffs WHERE id=?", (tid,)).fetchone()
        return _row_to_dict(row)

    def list_all(self) -> list[dict]:
        with connect() as c:
            rows = c.execute("SELECT * FROM fee_tariffs ORDER BY year DESC, category, min_parties").fetchall()
        return [dict(r) for r in rows]

    def find_matching(self, category: str, party_count: int, year: Optional[int] = None) -> Optional[dict]:
        with connect() as c:
            if year:
                rows = c.execute("SELECT * FROM fee_tariffs WHERE category=? AND year=?", (category, year)).fetchall()
            else:
                rows = c.execute("""SELECT * FROM fee_tariffs WHERE category=?
                    AND year=(SELECT MAX(year) FROM fee_tariffs WHERE category=?)""", (category, category)).fetchall()
        for r in rows:
            if r["min_parties"] <= party_count and (r["max_parties"] is None or party_count <= r["max_parties"]):
                return dict(r)
        return None

    def delete(self, tariff_id: str) -> None:
        with connect() as c:
            c.execute("DELETE FROM fee_tariffs WHERE id=?", (tariff_id,))


class SQLiteAuditRepository(AuditRepository):
    def create(self, record: dict) -> dict:
        with connect() as c:
            cur = c.execute("""INSERT INTO audit_logs (actor_id,action,target_id,details,created_at)
                VALUES(?,?,?,?,?)""",
                (record.get("actor_id"), record["action"], record.get("target_id"),
                 record.get("details"), record["created_at"]))
            rid = cur.lastrowid
        with connect() as c:
            row = c.execute("SELECT * FROM audit_logs WHERE id=?", (rid,)).fetchone()
        return _row_to_dict(row)

    def list_all(self) -> list[dict]:
        with connect() as c:
            rows = c.execute("SELECT * FROM audit_logs ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]


class SQLiteCalendarEventRepository(CalendarEventRepository):
    def create(self, event: dict) -> dict:
        eid = event.get("id") or str(uuid4())
        with connect() as c:
            c.execute("""INSERT INTO calendar_events
                (id,case_id,owner_id,event_type,event_date,title,description,created_at)
                VALUES(?,?,?,?,?,?,?,?)""",
                (eid, event["case_id"], event["owner_id"], event["event_type"], event["event_date"],
                 event["title"], event.get("description"), event["created_at"]))
            row = c.execute("SELECT * FROM calendar_events WHERE id=?", (eid,)).fetchone()
        return _row_to_dict(row)

    def list_for_case(self, case_id: str) -> list[dict]:
        with connect() as c:
            rows = c.execute("SELECT * FROM calendar_events WHERE case_id=? ORDER BY event_date ASC", (case_id,)).fetchall()
        return [dict(r) for r in rows]

    def list_for_owner(self, owner_id: str) -> list[dict]:
        with connect() as c:
            rows = c.execute("SELECT * FROM calendar_events WHERE owner_id=? ORDER BY event_date ASC", (owner_id,)).fetchall()
        return [dict(r) for r in rows]

    def delete_for_case(self, case_id: str) -> None:
        with connect() as c:
            c.execute("DELETE FROM calendar_events WHERE case_id=?", (case_id,))


class SQLiteTaskRepository(TaskRepository):
    def create(self, task: dict) -> dict:
        tid = task.get("id") or str(uuid4())
        with connect() as c:
            c.execute("""INSERT INTO tasks
                (id,owner_id,case_id,task_key,title,description,due_date,status,priority,
                 is_standard,is_custom,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (tid, task["owner_id"], task["case_id"], task.get("task_key"), task["title"],
                 task.get("description"), task["due_date"], task.get("status", "pending"),
                 task.get("priority", "normal"), int(task.get("is_standard", 1)), int(task.get("is_custom", 0)),
                 task["created_at"], task["updated_at"]))
        return self.get(tid)

    def get(self, task_id: str) -> Optional[dict]:
        with connect() as c:
            row = c.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        return _row_to_dict(row)

    def update(self, task_id: str, values: dict) -> Optional[dict]:
        if not values: return self.get(task_id)
        cols = ",".join(f"{k}=?" for k in values)
        with connect() as c:
            c.execute(f"UPDATE tasks SET {cols} WHERE id=?", (*values.values(), task_id))
        return self.get(task_id)

    def list_for_case(self, case_id: str) -> list[dict]:
        with connect() as c:
            rows = c.execute("SELECT * FROM tasks WHERE case_id=? ORDER BY due_date ASC", (case_id,)).fetchall()
        return [dict(r) for r in rows]

    def list_for_owner(self, owner_id: str) -> list[dict]:
        with connect() as c:
            rows = c.execute("SELECT * FROM tasks WHERE owner_id=? ORDER BY due_date ASC", (owner_id,)).fetchall()
        return [dict(r) for r in rows]


class SQLiteTaskTemplateRepository(TaskTemplateRepository):
    def upsert(self, template: dict) -> dict:
        tid = template.get("id") or str(uuid4())
        with connect() as c:
            existing = c.execute("SELECT id FROM task_templates WHERE owner_id=? AND task_key=?",
                (template["owner_id"], template["task_key"])).fetchone()
            if existing:
                c.execute("""UPDATE task_templates SET title=?,offset_days=?,priority=?,sort_order=?,
                    is_active=?,updated_at=? WHERE id=?""",
                    (template["title"], template["offset_days"], template.get("priority", "normal"),
                     template.get("sort_order", 0), int(template.get("is_active", 1)),
                     template["updated_at"], existing["id"]))
                tid = existing["id"]
            else:
                c.execute("""INSERT INTO task_templates
                    (id,owner_id,task_key,title,offset_days,priority,sort_order,is_active,created_at,updated_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?)""",
                    (tid, template["owner_id"], template["task_key"], template["title"],
                     template["offset_days"], template.get("priority", "normal"), template.get("sort_order", 0),
                     int(template.get("is_active", 1)), template["created_at"], template["updated_at"]))
            row = c.execute("SELECT * FROM task_templates WHERE id=?", (tid,)).fetchone()
        return _row_to_dict(row)

    def list_for_owner(self, owner_id: str) -> list[dict]:
        with connect() as c:
            rows = c.execute("""SELECT * FROM task_templates WHERE owner_id=? AND is_active=1
                ORDER BY sort_order ASC""", (owner_id,)).fetchall()
        return [dict(r) for r in rows]


class SQLiteTaskHistoryRepository(TaskHistoryRepository):
    def create(self, record: dict) -> dict:
        rid = record.get("id") or str(uuid4())
        with connect() as c:
            c.execute("""INSERT INTO task_history (id,task_id,actor_id,action,old_value,new_value,created_at)
                VALUES(?,?,?,?,?,?,?)""",
                (rid, record["task_id"], record.get("actor_id"), record["action"],
                 record.get("old_value"), record.get("new_value"), record["created_at"]))
            row = c.execute("SELECT * FROM task_history WHERE id=?", (rid,)).fetchone()
        return _row_to_dict(row)

    def list_for_task(self, task_id: str) -> list[dict]:
        with connect() as c:
            rows = c.execute("SELECT * FROM task_history WHERE task_id=? ORDER BY created_at ASC", (task_id,)).fetchall()
        return [dict(r) for r in rows]



class SQLiteFolderRepository(FolderRepository):
    def create(self, folder: dict) -> dict:
        folder = dict(folder)
        folder.setdefault("id", str(uuid4()))
        cols = ",".join(folder.keys())
        placeholders = ",".join("?" for _ in folder)
        with connect() as c:
            c.execute(f"INSERT INTO folders ({cols}) VALUES ({placeholders})", tuple(folder.values()))
        return self.get(folder["id"])

    def get(self, folder_id: str):
        with connect() as c: row=c.execute("SELECT * FROM folders WHERE id=?",(folder_id,)).fetchone()
        return _row_to_dict(row)

    def update(self, folder_id: str, values: dict):
        if not values: return self.get(folder_id)
        cols=",".join(f"{k}=?" for k in values)
        with connect() as c: c.execute(f"UPDATE folders SET {cols} WHERE id=?",(*values.values(),folder_id))
        return self.get(folder_id)

    def list_for_case(self, case_id: str):
        with connect() as c: rows=c.execute("SELECT * FROM folders WHERE case_id=? ORDER BY sort_order,name",(case_id,)).fetchall()
        return [dict(r) for r in rows]

    def list_by_case(self, owner_id: str, case_id: str):
        with connect() as c: rows=c.execute("SELECT * FROM folders WHERE owner_id=? AND case_id=? ORDER BY sort_order,name",(owner_id,case_id)).fetchall()
        return [dict(r) for r in rows]

    def get_case_root(self, case_id: str):
        with connect() as c: row=c.execute("SELECT * FROM folders WHERE case_id=? AND folder_type='root' AND status='active' ORDER BY created_at LIMIT 1",(case_id,)).fetchone()
        return _row_to_dict(row)

    def get_by_code(self, case_id: str, code: str, active_only=True):
        extra=" AND status='active'" if active_only else ""
        with connect() as c: row=c.execute(f"SELECT * FROM folders WHERE case_id=? AND code=?{extra} ORDER BY created_at LIMIT 1",(case_id,code)).fetchone()
        return _row_to_dict(row)

    def list_visible_to_user(self, user_id: str, case_id=None):
        q=("SELECT DISTINCT f.* FROM folders f LEFT JOIN folder_permissions fp "
           "ON fp.folder_id=f.id AND fp.user_id=? "
           "WHERE f.status IN ('active','restored') AND (f.owner_id=? OR f.is_global=1 OR fp.user_id IS NOT NULL)")
        params=[user_id,user_id]
        if case_id: q += " AND f.case_id=?"; params.append(case_id)
        q += " ORDER BY f.sort_order,f.name"
        with connect() as c: rows=c.execute(q,params).fetchall()
        return [dict(r) for r in rows]

    def list_general(self):
        with connect() as c: rows=c.execute("SELECT * FROM folders WHERE is_global=1 ORDER BY sort_order,name").fetchall()
        return [dict(r) for r in rows]

    def list_all_active_or_deleted(self):
        with connect() as c: rows=c.execute("SELECT * FROM folders ORDER BY status,sort_order,name").fetchall()
        return [dict(r) for r in rows]

    def list_deleted_before(self, cutoff: str):
        with connect() as c: rows=c.execute("SELECT * FROM folders WHERE status='deleted' AND deleted_at IS NOT NULL AND deleted_at < ?",(cutoff,)).fetchall()
        return [dict(r) for r in rows]

    def soft_delete(self, folder_id: str, user_id: str):
        from app.auth.service import now
        stamp=now().isoformat()
        with connect() as c:
            c.execute("UPDATE folders SET status='deleted',deleted_at=?,deleted_by=?,updated_at=? WHERE id=?",(stamp,user_id,stamp,folder_id))
            c.execute("UPDATE folders SET status='deleted',deleted_at=?,deleted_by=?,updated_at=? WHERE parent_id=? AND status<>'deleted'",(stamp,user_id,stamp,folder_id))
        return self.get(folder_id)

    def restore(self, folder_id: str, admin_id: str, restored_parent_id: str):
        from app.auth.service import now
        stamp=now().isoformat()
        with connect() as c: c.execute("UPDATE folders SET status='restored',restored_at=?,restored_by=?,restored_parent_id=?,parent_id=?,updated_at=? WHERE id=?",(stamp,admin_id,restored_parent_id,restored_parent_id,stamp,folder_id))
        return self.get(folder_id)

    def purge(self, folder_id: str):
        with connect() as c:
            ids=[folder_id]; i=0
            while i<len(ids):
                ids += [r['id'] for r in c.execute("SELECT id FROM folders WHERE parent_id=?",(ids[i],)).fetchall()]; i+=1
            for fid in reversed(ids):
                c.execute("UPDATE documents SET folder_id=NULL WHERE folder_id=?",(fid,))
                c.execute("UPDATE generated_documents SET folder_id=NULL WHERE folder_id=?",(fid,))
                c.execute("DELETE FROM folder_permissions WHERE folder_id=?",(fid,))
                c.execute("DELETE FROM folders WHERE id=?",(fid,))

    def grant(self, folder_id: str, user_id: str, granted_by: str):
        from app.auth.service import now
        with connect() as c: c.execute("INSERT OR IGNORE INTO folder_permissions(id,folder_id,user_id,granted_by,granted_at) VALUES(?,?,?,?,?)",(str(uuid4()),folder_id,user_id,granted_by,now().isoformat()))

    def revoke(self, folder_id: str, user_id: str):
        with connect() as c: c.execute("DELETE FROM folder_permissions WHERE folder_id=? AND user_id=?",(folder_id,user_id))

    def has_permission(self, folder_id: str, user_id: str):
        with connect() as c: row=c.execute("SELECT 1 FROM folder_permissions WHERE folder_id=? AND user_id=? LIMIT 1",(folder_id,user_id)).fetchone()
        return row is not None

class SQLitePermissionRepository(PermissionRepository):
    def grant(self, user_id: str, permission: str, granted_by: Optional[str]) -> dict:
        from app.auth.service import now
        with connect() as c:
            c.execute("""INSERT OR IGNORE INTO user_permissions (id,user_id,permission,granted_at,granted_by)
                VALUES(?,?,?,?,?)""",
                (str(uuid4()), user_id, permission, now().isoformat(), granted_by))
        return {"user_id": user_id, "permission": permission}

    def revoke(self, user_id: str, permission: str) -> None:
        with connect() as c:
            c.execute("DELETE FROM user_permissions WHERE user_id=? AND permission=?", (user_id, permission))

    def list_for_user(self, user_id: str) -> list[str]:
        with connect() as c:
            rows = c.execute("SELECT permission FROM user_permissions WHERE user_id=?", (user_id,)).fetchall()
        return [r["permission"] for r in rows]


class SQLiteCounterRepository(CounterRepository):
    def next_value(self, counter_id: str) -> int:
        with connect() as c:
            row = c.execute(
                "INSERT INTO counters(id,value) VALUES(?,1) "
                "ON CONFLICT(id) DO UPDATE SET value=value+1 RETURNING value",
                (counter_id,),
            ).fetchone()
        return int(row["value"])
