from uuid import uuid4
from app.database_layer import repos
from app.auth.service import now

DEFAULT_FOLDERS = [
    ("01 - Başvuru ve Kaynak Belgeler", "source"),
    ("02 - Davetler", "invitation"),
    ("03 - Görüşme Belgeleri", "meeting"),
    ("04 - Son Tutanaklar", "final_report"),
    ("05 - Ücret Pusulaları", "fee"),
    ("06 - Üst Yazılar", "cover_letter"),
    ("07 - Diğer Belgeler", "other"),
]

def ensure_case_folders(owner_id: str, case_id: str):
    """Dosya için kök + standart klasörleri idempotent biçimde oluşturur."""
    rows = repos.folders.list_by_case(owner_id, case_id)
    root = next((r for r in rows if r.get("folder_type") == "root" and not r.get("parent_id")), None)
    if not root:
        root = repos.folders.create({
            "id": str(uuid4()), "owner_id": owner_id, "case_id": case_id,
            "parent_id": None, "name": "Dosya", "folder_type": "root",
            "created_at": now().isoformat(), "updated_at": now().isoformat(),
        })
        rows.append(root)

    existing_types = {r.get("folder_type") for r in rows}
    for name, ftype in DEFAULT_FOLDERS:
        if ftype in existing_types:
            continue
        rows.append(repos.folders.create({
            "id": str(uuid4()), "owner_id": owner_id, "case_id": case_id,
            "parent_id": root["id"], "name": name, "folder_type": ftype,
            "created_at": now().isoformat(), "updated_at": now().isoformat(),
        }))
    return rows

def get_case_root(owner_id, case_id):
    rows = ensure_case_folders(owner_id, case_id)
    return next((r for r in rows if r.get("folder_type") == "root" and not r.get("parent_id")), None)

def get_folder(owner_id, folder_id):
    row = repos.folders.get(folder_id)
    if not row or row.get("owner_id") != owner_id:
        return None
    return row

def folder_for_type(owner_id, case_id, folder_type):
    rows = ensure_case_folders(owner_id, case_id)
    return next((r for r in rows if r.get("folder_type") == folder_type), get_case_root(owner_id, case_id))
