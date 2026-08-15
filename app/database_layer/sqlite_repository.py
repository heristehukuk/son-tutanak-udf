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
    TariffRepository, AuditRepository,
)


def _row_to_dict(row) -> Optional[dict]:
    return dict(row) if row is not None else None


class SQLiteUserRepository(UserRepository):
    def create(self, user: dict) -> dict:
        with connect() as c:
            c.execute("""INSERT INTO users
                (id,email,display_name,password_hash,status,plan_id,is_super_admin,created_at,iban)
                VALUES(?,?,?,?,?,?,?,?,?)""",
                (user["id"], user["email"], user["display_name"], user["password_hash"],
                 user.get("status", "pending"), user.get("plan_id", "free"),
                 int(user.get("is_super_admin", 0)), user["created_at"], user.get("iban")))
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
            c.execute("""INSERT INTO cases (id,owner_id,file_no,application_no,title,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?)""",
                (cid, case["owner_id"], case.get("file_no"), case.get("application_no"),
                 case.get("title"), case["created_at"], case["updated_at"]))
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


class SQLiteDocumentRepository(DocumentRepository):
    def create(self, document: dict) -> dict:
        did = document.get("id") or str(uuid4())
        with connect() as c:
            c.execute("""INSERT INTO documents
                (id,case_id,owner_id,original_name,stored_path,kind,size_bytes,created_at)
                VALUES(?,?,?,?,?,?,?,?)""",
                (did, document.get("case_id"), document["owner_id"], document["original_name"],
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


class SQLiteGeneratedDocumentRepository(GeneratedDocumentRepository):
    def create(self, document: dict) -> dict:
        did = document.get("id") or str(uuid4())
        with connect() as c:
            c.execute("""INSERT INTO generated_documents
                (id,case_id,owner_id,original_template,stored_path,created_at)
                VALUES(?,?,?,?,?,?)""",
                (did, document.get("case_id"), document["owner_id"], document["original_template"],
                 document["stored_path"], document["created_at"]))
        with connect() as c:
            row = c.execute("SELECT * FROM generated_documents WHERE id=?", (did,)).fetchone()
        return _row_to_dict(row)

    def list_by_owner(self, owner_id: str) -> list[dict]:
        with connect() as c:
            rows = c.execute("SELECT * FROM generated_documents WHERE owner_id=? ORDER BY created_at DESC", (owner_id,)).fetchall()
        return [dict(r) for r in rows]


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
            c.execute("""INSERT INTO messages (id,sender_id,recipient_id,body,created_at)
                VALUES(?,?,?,?,?)""",
                (mid, message["sender_id"], message["recipient_id"], message["body"], message["created_at"]))
        with connect() as c:
            row = c.execute("SELECT * FROM messages WHERE id=?", (mid,)).fetchone()
        return _row_to_dict(row)

    def list_for_user(self, user_id: str) -> list[dict]:
        with connect() as c:
            rows = c.execute("""SELECT * FROM messages WHERE sender_id=? OR recipient_id=?
                ORDER BY created_at DESC""", (user_id, user_id)).fetchall()
        return [dict(r) for r in rows]


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
