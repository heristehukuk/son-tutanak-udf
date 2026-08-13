
import json
from pathlib import Path
from uuid import uuid4
from app.database import connect, CUSTOM_TEMPLATE_DIR
from app.auth.service import now
from app.documents.engine import scan_custom_template

MAX_NAME_LEN = 120

def create_template(owner_id, name, is_shared, data):
    """UDF şablonunu tarar (köşeli parantezleri çözer), diske kaydeder, DB satırı oluşturur.
    Dönüş: (template_id, recognized, unrecognized)"""
    from app.documents.engine import read_udf
    _, old_text, _ = read_udf(data)
    recognized, unrecognized = scan_custom_template(old_text)
    tid = str(uuid4())
    path = CUSTOM_TEMPLATE_DIR / (tid + ".udf")
    path.write_bytes(data)
    clean_name = (name or "Adsız Şablon").strip()[:MAX_NAME_LEN] or "Adsız Şablon"
    with connect() as c:
        c.execute("""INSERT INTO custom_templates
        (id,owner_id,name,is_shared,stored_path,recognized_json,unrecognized_json,created_at)
        VALUES(?,?,?,?,?,?,?,?)""",
        (tid, owner_id, clean_name, 1 if is_shared else 0, str(path),
         json.dumps(recognized, ensure_ascii=False), json.dumps(unrecognized, ensure_ascii=False), now().isoformat()))
    return tid, recognized, unrecognized

def list_visible_templates(user_id):
    """Kullanıcının kendi şablonları + paylaşılan (is_shared) tüm şablonlar."""
    with connect() as c:
        rows = c.execute("""SELECT * FROM custom_templates
        WHERE owner_id=? OR is_shared=1 ORDER BY created_at DESC""", (user_id,)).fetchall()
    return [dict(r) for r in rows]

def list_all_templates():
    """Admin için: sistemdeki TÜM özel şablonlar (sahibiyle birlikte)."""
    with connect() as c:
        rows = c.execute("""SELECT ct.*, u.display_name AS owner_name, u.email AS owner_email
        FROM custom_templates ct JOIN users u ON u.id=ct.owner_id
        ORDER BY ct.created_at DESC""").fetchall()
    return [dict(r) for r in rows]

def get_template(template_id):
    with connect() as c:
        row = c.execute("SELECT * FROM custom_templates WHERE id=?", (template_id,)).fetchone()
    return dict(row) if row else None

def get_template_bytes(row):
    return Path(row["stored_path"]).read_bytes()

def can_use_template(row, user):
    """Kullanıcı bu şablonu şablon seçiminde kullanabilir mi? (kendisininki, paylaşılan, ya da admin)"""
    if not row: return False
    if row["owner_id"] == user["id"]: return True
    if row["is_shared"]: return True
    if user["is_super_admin"]: return True
    return False

def delete_template(template_id, user):
    row = get_template(template_id)
    if not row: return False
    if row["owner_id"] != user["id"] and not user["is_super_admin"]:
        return False
    try:
        Path(row["stored_path"]).unlink(missing_ok=True)
    except Exception:
        pass
    with connect() as c:
        c.execute("DELETE FROM custom_templates WHERE id=?", (template_id,))
    return True
