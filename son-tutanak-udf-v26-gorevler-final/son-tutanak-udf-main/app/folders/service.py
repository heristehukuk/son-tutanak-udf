from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4
from app.database_layer import repos

STANDARD_FOLDERS = [
    ("01", "01 - Başvuru ve Kaynak Belgeler", "source"),
    ("02", "02 - Davetler", "invitation"),
    ("03", "03 - Görüşme Belgeleri", "meeting"),
    ("04", "04 - Son Tutanaklar", "final_report"),
    ("05", "05 - Ücret Pusulaları", "fee"),
    ("06", "06 - Üst Yazılar", "cover_letter"),
    ("07", "07 - Diğer Belgeler", "other"),
]
DOC_FOLDER_TYPES = {
    "source": "01", "davet_mektubu": "02", "meeting": "03",
    "son_tutanak": "04", "ucret_pusulasi": "05", "ust_yazi": "06", "ust_yazi_son_tutanak": "06", "ust_yazi_ucret_pusulasi": "06",
}
TRASH_DAYS = 15


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _is_admin(user: dict | None) -> bool:
    return bool(user and user.get("is_super_admin"))


def case_root_name(case: dict) -> str:
    file_no = (case.get("file_no") or "").strip()
    title = (case.get("title") or "").strip()
    if file_no and title:
        return f"{file_no} - {title}"
    if file_no:
        return file_no
    if title and title != "Yeni Dosya":
        return title
    registry = (case.get("registry_no") or "").strip()
    return f"Dosya - {registry}" if registry else f"Dosya - {case.get('id', '')[:8]}"


def ensure_general_folder(admin_id: str | None = None) -> dict:
    rows = repos.folders.list_general()
    existing = next((r for r in rows if r.get("folder_type") == "global_root" and r.get("status") == "active"), None)
    if existing:
        return existing
    return repos.folders.create({
        "id": str(uuid4()), "case_id": None, "owner_id": admin_id,
        "parent_id": None, "name": "Genel Klasörler", "folder_type": "global_root",
        "sort_order": 0, "is_system": 1, "is_global": 1, "status": "active",
        "created_at": _now(), "updated_at": _now(),
    })


def ensure_restored_root(owner_id: str | None = None, case_id: str | None = None) -> dict:
    rows = repos.folders.list_all_active_or_deleted() if getattr(repos, "folders", None) else []
    for r in rows:
        if (r.get("folder_type") == "restored_root" and r.get("status") == "active"
                and r.get("owner_id") == owner_id and r.get("case_id") == case_id):
            return r
    return repos.folders.create({
        "id": str(uuid4()), "case_id": case_id, "owner_id": None,
        "parent_id": None, "name": "Geri Yüklenenler", "folder_type": "restored_root",
        "sort_order": 9998, "is_system": 1, "is_global": 0, "status": "restored",
        "created_at": _now(), "updated_at": _now(),
    })


def ensure_case_folders(owner_id: str, case_id: str) -> list[dict]:
    case = repos.cases.get(case_id)
    if not case or case.get("owner_id") != owner_id:
        return []
    rows = repos.folders.list_for_case(case_id)
    root = next((r for r in rows if r.get("folder_type") == "root" and r.get("status") == "active"), None)
    stamp = _now()
    if not root:
        root = repos.folders.create({
            "id": str(uuid4()), "case_id": case_id, "owner_id": owner_id,
            "parent_id": None, "name": case_root_name(case), "folder_type": "root",
            "sort_order": 0, "is_system": 1, "is_global": 0, "status": "active",
            "created_at": stamp, "updated_at": stamp,
        })
        rows.append(root)
    elif root.get("name") != case_root_name(case):
        root = repos.folders.update(root["id"], {"name": case_root_name(case), "updated_at": stamp})
        rows = [root if r.get("id") == root["id"] else r for r in rows]

    existing_codes = {str(r.get("code")): r for r in rows if r.get("is_system") and r.get("status") == "active"}
    for code, name, folder_type in STANDARD_FOLDERS:
        if code in existing_codes:
            continue
        rows.append(repos.folders.create({
            "id": str(uuid4()), "case_id": case_id, "owner_id": owner_id,
            "parent_id": root["id"], "name": name, "folder_type": folder_type,
            "code": code, "sort_order": int(code), "is_system": 1, "is_global": 0,
            "status": "active", "created_at": stamp, "updated_at": stamp,
        }))
    return repos.folders.list_for_case(case_id)


def update_case_folder_name(owner_id: str, case_id: str) -> None:
    case = repos.cases.get(case_id)
    if not case or case.get("owner_id") != owner_id:
        return
    root = repos.folders.get_case_root(case_id)
    if root and root.get("status") == "active":
        repos.folders.update(root["id"], {"name": case_root_name(case), "updated_at": _now()})


def get_system_folder(owner_id: str, case_id: str, code: str) -> dict | None:
    ensure_case_folders(owner_id, case_id)
    return repos.folders.get_by_code(case_id, code, active_only=True)


def folder_for_document(owner_id: str, case_id: str | None, kind: str = "source", doc_kind: str | None = None) -> dict | None:
    if not case_id:
        return None
    code = DOC_FOLDER_TYPES.get(doc_kind or kind, "07")
    return get_system_folder(owner_id, case_id, code)


def can_view_folder(user: dict, folder: dict) -> bool:
    status = folder.get("status", "active")
    if _is_admin(user):
        return True
    if status == "deleted":
        return False
    if status == "restored":
        return repos.folders.has_permission(folder["id"], user["id"])
    if folder.get("is_global"):
        return True
    if folder.get("owner_id") == user["id"]:
        return True
    return repos.folders.has_permission(folder["id"], user["id"])


def visible_folders(user: dict, case_id: str | None = None) -> list[dict]:
    if _is_admin(user):
        rows = repos.folders.list_all_active_or_deleted()
        if case_id:
            rows = [r for r in rows if r.get("case_id") == case_id]
    else:
        rows = repos.folders.list_visible_to_user(user["id"], case_id=case_id)
    return [r for r in rows if _is_admin(user) or can_view_folder(user, r)]


def delete_folder(user: dict, folder_id: str) -> dict:
    folder = repos.folders.get(folder_id)
    if not folder:
        raise ValueError("Klasör bulunamadı.")
    if not _is_admin(user):
        if folder.get("owner_id") != user["id"] or folder.get("is_system"):
            raise PermissionError("Bu klasörü silme yetkiniz yok.")
    elif not user.get("is_super_admin"):
        raise PermissionError("Bu işlem için yönetici yetkisi gerekir.")
    deleted = repos.folders.soft_delete(folder_id, user["id"])
    return deleted


def restore_folder(admin_user: dict, folder_id: str) -> dict:
    if not _is_admin(admin_user):
        raise PermissionError("Sadece admin geri yükleyebilir.")
    folder = repos.folders.get(folder_id)
    if not folder or folder.get("status") != "deleted":
        raise ValueError("Silinmiş klasör bulunamadı.")
    restored_root = ensure_restored_root(folder.get("owner_id"), folder.get("case_id"))
    restored = repos.folders.restore(folder_id, admin_user["id"], restored_root["id"])
    # Alt klasörlerin parent ilişkisini koru; yalnızca durumlarını geri al.
    if folder.get("case_id"):
        rows = repos.folders.list_for_case(folder["case_id"])
        descendants = []
        pending = [folder_id]
        seen = {folder_id}
        while pending:
            parent = pending.pop(0)
            for row in rows:
                if row.get("id") in seen:
                    continue
                if row.get("parent_id") == parent:
                    seen.add(row["id"])
                    descendants.append(row)
                    pending.append(row["id"])
        stamp = _now()
        for row in descendants:
            if row.get("status") == "deleted":
                repos.folders.update(row["id"], {
                    "status": "restored",
                    "restored_at": stamp,
                    "restored_by": admin_user["id"],
                    "restored_parent_id": restored["id"],
                    "deleted_at": None,
                    "deleted_by": None,
                    "updated_at": stamp,
                })
    return restored


def grant_folder_access(admin_user: dict, folder_id: str, user_id: str) -> None:
    if not _is_admin(admin_user):
        raise PermissionError("Sadece admin yetki verebilir.")
    folder = repos.folders.get(folder_id)
    if not folder:
        raise ValueError("Klasör bulunamadı.")
    repos.folders.grant(folder_id, user_id, admin_user["id"])


def revoke_folder_access(admin_user: dict, folder_id: str, user_id: str) -> None:
    if not _is_admin(admin_user):
        raise PermissionError("Sadece admin yetki kaldırabilir.")
    repos.folders.revoke(folder_id, user_id)


def cleanup_deleted_folders() -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=TRASH_DAYS)
    purged = 0
    for folder in repos.folders.list_deleted_before(cutoff.isoformat()):
        repos.folders.purge(folder["id"])
        purged += 1
    return purged
