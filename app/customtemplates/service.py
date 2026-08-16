
import json
from pathlib import Path
from uuid import uuid4
from app.database import CUSTOM_TEMPLATE_DIR
from app.database_layer import repos
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
    repos.templates.create({
        "id":tid,"owner_id":owner_id,"name":clean_name,"is_shared":1 if is_shared else 0,
        "stored_path":str(path),"recognized_json":json.dumps(recognized,ensure_ascii=False),
        "unrecognized_json":json.dumps(unrecognized,ensure_ascii=False),"created_at":now().isoformat(),
    })
    return tid, recognized, unrecognized

def list_visible_templates(user_id):
    """Kullanıcının kendi şablonları + paylaşılan (is_shared) tüm şablonlar."""
    return repos.templates.list_visible(user_id)

def list_all_templates():
    """Admin için: sistemdeki TÜM özel şablonlar (sahibiyle birlikte)."""
    return repos.templates.list_all()

def get_template(template_id):
    return repos.templates.get(template_id)

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
    repos.templates.delete(template_id)
    return True
