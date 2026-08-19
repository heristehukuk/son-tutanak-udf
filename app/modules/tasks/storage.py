"""
Görevler modülünün depolama katmanı.

ÖNEMLİ: Bu dosya artık app.database_layer.repos üzerinden çalışır - yani
DB_BACKEND=sqlite VEYA DB_BACKEND=supabase, ikisinde de aynı şekilde çalışır.
Önceki sürüm doğrudan app.database.connect() (ham SQLite) kullanıyordu; bu,
Supabase'e geçildiğinde görev verilerinin tamamen kopmasına yol açıyordu.
"""
import json
from datetime import datetime, date, timedelta
from uuid import uuid4
from app.database_layer import repos
from .models import STANDARD_TASKS, STATUSES, PRIORITIES


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def ensure_schema():
    """Geriye dönük uyumluluk için no-op: şema artık app.database.init_db()
    (SQLite) ve supabase_schema.sql (Supabase) tarafından yönetiliyor."""
    return None


def seed_user_templates(owner_id):
    existing = {t["task_key"] for t in repos.task_templates.list_for_owner(owner_id)}
    stamp = now_iso()
    for item in STANDARD_TASKS:
        if item["key"] in existing:
            continue
        repos.task_templates.upsert({
            "owner_id": owner_id, "task_key": item["key"], "title": item["title"],
            "offset_days": item["offset_days"], "priority": item["priority"],
            "sort_order": item["sort_order"], "is_active": 1,
            "created_at": stamp, "updated_at": stamp,
        })


def get_case(owner_id, case_id):
    case = repos.cases.get(case_id)
    if not case or case.get("owner_id") != owner_id:
        return None
    return case


def update_case_info(owner_id, case_id, file_no=None, applicant_name=None, file_type=None, start_date=None, status=None, case_data=None):
    case = get_case(owner_id, case_id)
    if not case:
        return None
    merged_json = case.get("case_data_json")
    if case_data is not None:
        try:
            merged = json.loads(merged_json) if merged_json else {}
        except Exception:
            merged = {}
        if isinstance(case_data, dict):
            merged.update(case_data)
        merged_json = json.dumps(merged, ensure_ascii=False)
    values = {
        "file_no": file_no if file_no is not None else case.get("file_no"),
        "title": applicant_name if applicant_name is not None else case.get("title"),
        "file_type": file_type if file_type is not None else case.get("file_type"),
        "start_date": start_date if start_date is not None else case.get("start_date"),
        "status": status if status is not None else case.get("status"),
        "case_data_json": merged_json,
        "updated_at": now_iso(),
    }
    return repos.cases.update(case_id, values)


def set_case_status(owner_id, case_id, status):
    if status not in {"open", "completed"}:
        raise ValueError("Geçersiz dosya durumu.")
    case = get_case(owner_id, case_id)
    if not case:
        raise ValueError("Dosya bulunamadı.")
    return repos.cases.update(case_id, {"status": status, "updated_at": now_iso()})


def _parse_start(value):
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d.%m.%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            pass
    return None


def _resolve_case_start_date(case_id: str, case: dict):
    """Dosyanın süreç başlangıç tarihini güvenli biçimde bulur.

    Öncelik:
      1) cases.start_date
      2) case_data_json içindeki baslangicTarihi/start_date
      3) eski kayıtlarda normal_deadline takvim olayından geriye doğru hesaplama
    Bulunan tarih cases.start_date alanına da yazılır ki sonraki görev işlemleri
    doğrudan aynı alanı kullanabilsin.
    """
    start = _parse_start(case.get("start_date"))
    if start:
        return start

    raw_json = case.get("case_data_json")
    if raw_json:
        try:
            data = json.loads(raw_json) if isinstance(raw_json, str) else dict(raw_json)
        except Exception:
            data = {}
        for key in ("baslangicTarihi", "start_date", "process_start_date"):
            start = _parse_start(str(data.get(key) or ""))
            if start:
                repos.cases.update(case_id, {"start_date": start.isoformat(), "updated_at": now_iso()})
                return start

    # Eski kayıtlarda takvim normal süre tarihi mevcut olabilir.
    try:
        events = repos.calendar_events.list_for_case(case_id)
        normal = next((e for e in events if e.get("event_type") == "normal_deadline"), None)
        if normal and normal.get("event_date"):
            due = date.fromisoformat(str(normal["event_date"])[:10])
            file_type = str(case.get("file_type") or "").lower()
            weeks = 6 if "ticari" in file_type else 3
            start = due - timedelta(days=weeks * 7)
            repos.cases.update(case_id, {"start_date": start.isoformat(), "updated_at": now_iso()})
            return start
    except Exception:
        pass
    return None


def create_standard_tasks(owner_id, case_id):
    """6 standart görevi bir kez oluşturur. Mevcut görevler asla tekrarlanmaz."""
    seed_user_templates(owner_id)
    case = get_case(owner_id, case_id)
    if not case:
        return {"created": 0, "reason": "case_not_found"}
    if case.get("status") == "deleted":
        return {"created": 0, "reason": "case_deleted"}
    start = _resolve_case_start_date(case_id, case)
    if not start:
        return {"created": 0, "reason": "start_date_missing"}
    existing = {t["task_key"] for t in repos.tasks.list_for_case(case_id) if t.get("is_standard")}
    templates_list = sorted(repos.task_templates.list_for_owner(owner_id), key=lambda t: (t.get("sort_order", 0), t.get("id", "")))
    created = 0
    stamp = now_iso()
    for t in templates_list:
        if t["task_key"] in existing:
            continue
        due = start + timedelta(days=int(t["offset_days"]))
        task = repos.tasks.create({
            "owner_id": owner_id, "case_id": case_id, "task_key": t["task_key"], "title": t["title"],
            "description": None, "due_date": due.isoformat(), "status": "pending", "priority": t["priority"],
            "is_standard": 1, "is_custom": 0, "created_at": stamp, "updated_at": stamp,
        })
        repos.task_history.create({
            "task_id": task["id"], "actor_id": owner_id, "action": "created",
            "old_value": None, "new_value": json.dumps({"title": t["title"], "due_date": due.isoformat()}, ensure_ascii=False),
            "created_at": stamp,
        })
        created += 1
    return {"created": created, "reason": "ok"}


def _attach_case_fields(tasks_list, case):
    out = []
    for t in tasks_list:
        t = dict(t)
        t["file_no"] = case.get("file_no") if case else None
        t["applicant_name"] = case.get("title") if case else None
        t["file_type"] = case.get("file_type") if case else None
        t["start_date"] = case.get("start_date") if case else None
        out.append(t)
    return out


def list_tasks(owner_id, case_id=None):
    if case_id:
        case = get_case(owner_id, case_id)
        tasks_list = repos.tasks.list_for_case(case_id)
        tasks_list = [t for t in tasks_list if t.get("owner_id") == owner_id]
        tasks_list = _attach_case_fields(tasks_list, case)
    else:
        tasks_list = repos.tasks.list_for_owner(owner_id)
        cases_by_id = {c["id"]: c for c in repos.cases.list_by_owner(owner_id)}
        out = []
        for t in tasks_list:
            out.extend(_attach_case_fields([t], cases_by_id.get(t.get("case_id"))))
        tasks_list = out
    order = {"pending": 1, "in_progress": 1, "completed": 3, "cancelled": 4}
    tasks_list.sort(key=lambda t: (order.get(t.get("status"), 1), t.get("due_date") or "", t.get("created_at") or ""))
    return tasks_list


def get_task(owner_id, task_id):
    task = repos.tasks.get(task_id)
    if not task or task.get("owner_id") != owner_id:
        return None
    return task


def create_custom_task(owner_id, case_id, title, due_date, priority="normal", description=""):
    case = get_case(owner_id, case_id)
    if not case:
        raise ValueError("Dosya bulunamadı veya erişim yetkiniz yok.")
    if not title.strip():
        raise ValueError("Görev adı boş olamaz.")
    if priority not in PRIORITIES:
        priority = "normal"
    try:
        date.fromisoformat(due_date)
    except Exception:
        raise ValueError("Geçerli bir görev tarihi seçin.")
    stamp = now_iso()
    task = repos.tasks.create({
        "owner_id": owner_id, "case_id": case_id, "task_key": None, "title": title.strip(),
        "description": description.strip(), "due_date": due_date, "status": "pending",
        "priority": priority, "is_standard": 0, "is_custom": 1, "created_at": stamp, "updated_at": stamp,
    })
    repos.task_history.create({
        "task_id": task["id"], "actor_id": owner_id, "action": "created", "old_value": None,
        "new_value": json.dumps({"title": title.strip(), "due_date": due_date, "priority": priority}, ensure_ascii=False),
        "created_at": stamp,
    })
    return get_task(owner_id, task["id"])


def update_task(owner_id, task_id, **changes):
    allowed = {"title", "description", "due_date", "status", "priority"}
    changes = {k: v for k, v in changes.items() if k in allowed and v is not None}
    task = get_task(owner_id, task_id)
    if not task:
        raise ValueError("Görev bulunamadı.")
    if "status" in changes and changes["status"] not in STATUSES:
        raise ValueError("Geçersiz görev durumu.")
    if "priority" in changes and changes["priority"] not in PRIORITIES:
        raise ValueError("Geçersiz öncelik.")
    if "due_date" in changes:
        date.fromisoformat(changes["due_date"])
    if "title" in changes and not str(changes["title"]).strip():
        raise ValueError("Görev adı boş olamaz.")
    stamp = now_iso()
    values = {k: (v.strip() if isinstance(v, str) else v) for k, v in changes.items()}
    if "status" in changes:
        if changes["status"] == "completed":
            values["completed_at"] = stamp
            values["cancelled_at"] = None
        elif changes["status"] == "cancelled":
            values["cancelled_at"] = stamp
        else:
            values["completed_at"] = None
            values["cancelled_at"] = None
    values["updated_at"] = stamp
    repos.tasks.update(task_id, values)
    for k, v in changes.items():
        old = task.get(k)
        if str(old or "") != str(v or ""):
            repos.task_history.create({
                "task_id": task_id, "actor_id": owner_id, "action": f"changed_{k}",
                "old_value": json.dumps({k: old}, ensure_ascii=False),
                "new_value": json.dumps({k: v}, ensure_ascii=False), "created_at": stamp,
            })
    return get_task(owner_id, task_id)


def update_template(owner_id, template_id, title, offset_days, priority):
    if priority not in PRIORITIES:
        priority = "normal"
    try:
        offset_days = int(offset_days)
    except Exception:
        raise ValueError("Gün değeri sayı olmalı.")
    if offset_days < 0 or offset_days > 21:
        raise ValueError("Standart görev günü 0 ile 21 arasında olmalı.")
    existing = {t["id"]: t for t in repos.task_templates.list_for_owner(owner_id)}
    row = existing.get(template_id)
    if not row:
        raise ValueError("Görev şablonu bulunamadı.")
    repos.task_templates.upsert({
        "id": row["id"], "owner_id": owner_id, "task_key": row["task_key"], "title": title.strip(),
        "offset_days": offset_days, "priority": priority, "sort_order": row.get("sort_order", 0),
        "is_active": 1, "created_at": row.get("created_at") or now_iso(), "updated_at": now_iso(),
    })
    return True


def templates(owner_id):
    seed_user_templates(owner_id)
    return sorted(repos.task_templates.list_for_owner(owner_id), key=lambda t: (t.get("sort_order", 0), t.get("id", "")))


def history(owner_id, task_id):
    task = get_task(owner_id, task_id)
    if not task:
        return []
    records = repos.task_history.list_for_task(task_id)
    return sorted(records, key=lambda r: r.get("created_at") or "", reverse=True)


DOC_KIND_TITLES = {
    "son_tutanak": "Son Tutanak",
    "davet_mektubu": "Davet Mektubu",
    "ucret_pusulasi": "Ücret Pusulası",
    "ust_yazi": "Üst Yazı",
}


def document_checklist(owner_id, case_id):
    """Bir dosyaya bağlı üretilmiş belgeleri, belgenin gerçek türüne (doc_kind)
    göre tespit eder. Önceki sürüm bunu şablon ADI içinde metin arayarak (string
    matching) tahmin ediyordu; artık belge üretilirken kaydedilen doc_kind alanına
    dayanıyor - şablon adı değişse bile checklist doğru çalışır."""
    all_docs = repos.generated_documents.list_by_owner(owner_id)
    rows = [d for d in all_docs if d.get("case_id") == case_id]
    rows.sort(key=lambda d: d.get("created_at") or "", reverse=True)
    out = []
    for key, title in DOC_KIND_TITLES.items():
        match = next((r for r in rows if r.get("doc_kind") == key), None)
        out.append({"key": key, "title": title, "created": bool(match), "document": match})
    return out


def global_stats(owner_id):
    today = date.today().isoformat()
    tasks_list = repos.tasks.list_for_owner(owner_id)
    total = len(tasks_list)
    completed = sum(1 for t in tasks_list if t.get("status") == "completed")
    overdue = sum(1 for t in tasks_list if t.get("status") not in ("completed", "cancelled") and (t.get("due_date") or "") < today)
    today_n = sum(1 for t in tasks_list if t.get("status") not in ("completed", "cancelled") and (t.get("due_date") or "") == today)
    week_end = (date.today() + timedelta(days=7)).isoformat()
    upcoming = sum(1 for t in tasks_list if t.get("status") not in ("completed", "cancelled") and today < (t.get("due_date") or "") <= week_end)
    return {"total": total, "completed": completed, "overdue": overdue, "today": today_n, "upcoming": upcoming}
