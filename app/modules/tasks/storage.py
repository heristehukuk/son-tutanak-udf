import json
import sqlite3
import uuid
from datetime import datetime, date, timedelta
from app.database import connect
from .models import STANDARD_TASKS, STATUSES, PRIORITIES


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def ensure_schema():
    with connect() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS task_templates (
            id TEXT PRIMARY KEY,
            owner_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            task_key TEXT NOT NULL,
            title TEXT NOT NULL,
            offset_days INTEGER NOT NULL DEFAULT 0,
            priority TEXT NOT NULL DEFAULT 'normal',
            sort_order INTEGER NOT NULL DEFAULT 0,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(owner_id, task_key)
        );
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            owner_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
            task_key TEXT,
            title TEXT NOT NULL,
            description TEXT,
            due_date TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            priority TEXT NOT NULL DEFAULT 'normal',
            is_standard INTEGER NOT NULL DEFAULT 1,
            is_custom INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            completed_at TEXT,
            cancelled_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_tasks_owner_case ON tasks(owner_id, case_id);
        CREATE INDEX IF NOT EXISTS idx_tasks_due ON tasks(owner_id, due_date, status);
        CREATE TABLE IF NOT EXISTS task_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
            actor_id TEXT REFERENCES users(id) ON DELETE SET NULL,
            action TEXT NOT NULL,
            old_value TEXT,
            new_value TEXT,
            created_at TEXT NOT NULL
        );
        """)
        # Backward-compatible case columns.
        cols = {r["name"] for r in c.execute("PRAGMA table_info(cases)").fetchall()}
        if "file_type" not in cols:
            c.execute("ALTER TABLE cases ADD COLUMN file_type TEXT")
        if "start_date" not in cols:
            c.execute("ALTER TABLE cases ADD COLUMN start_date TEXT")


def seed_user_templates(owner_id):
    ensure_schema()
    with connect() as c:
        existing = {r["task_key"] for r in c.execute("SELECT task_key FROM task_templates WHERE owner_id=?", (owner_id,)).fetchall()}
        stamp = now_iso()
        for item in STANDARD_TASKS:
            if item["key"] in existing:
                continue
            c.execute("""INSERT INTO task_templates
                (id,owner_id,task_key,title,offset_days,priority,sort_order,is_active,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (str(uuid.uuid4()), owner_id, item["key"], item["title"], item["offset_days"], item["priority"], item["sort_order"], 1, stamp, stamp))


def get_case(owner_id, case_id):
    ensure_schema()
    with connect() as c:
        return c.execute("SELECT * FROM cases WHERE id=? AND owner_id=?", (case_id, owner_id)).fetchone()


def update_case_info(owner_id, case_id, file_no=None, applicant_name=None, file_type=None, start_date=None, status=None):
    ensure_schema()
    with connect() as c:
        row = c.execute("SELECT * FROM cases WHERE id=? AND owner_id=?", (case_id, owner_id)).fetchone()
        if not row:
            return None
        c.execute("""UPDATE cases SET file_no=?, title=?, file_type=?, start_date=?, status=?, updated_at=?
                     WHERE id=? AND owner_id=?""",
                  (file_no if file_no is not None else row["file_no"],
                   applicant_name if applicant_name is not None else row["title"],
                   file_type if file_type is not None else row["file_type"],
                   start_date if start_date is not None else row["start_date"],
                   status if status is not None else row["status"],
                   now_iso(), case_id, owner_id))
        return c.execute("SELECT * FROM cases WHERE id=? AND owner_id=?", (case_id, owner_id)).fetchone()


def set_case_status(owner_id, case_id, status):
    ensure_schema()
    if status not in {"open", "completed"}:
        raise ValueError("Geçersiz dosya durumu.")
    with connect() as c:
        row=c.execute("SELECT id FROM cases WHERE id=? AND owner_id=?",(case_id,owner_id)).fetchone()
        if not row: raise ValueError("Dosya bulunamadı.")
        c.execute("UPDATE cases SET status=?, updated_at=? WHERE id=? AND owner_id=?",(status,now_iso(),case_id,owner_id))
    return get_case(owner_id,case_id)


def _parse_start(value):
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d.%m.%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            pass
    return None


def create_standard_tasks(owner_id, case_id):
    """Create the six standard tasks once. Existing tasks are never duplicated."""
    ensure_schema()
    seed_user_templates(owner_id)
    case = get_case(owner_id, case_id)
    if not case:
        return {"created": 0, "reason": "case_not_found"}
    start = _parse_start(case["start_date"])
    if not start:
        return {"created": 0, "reason": "start_date_missing"}
    with connect() as c:
        existing = {r["task_key"] for r in c.execute("SELECT task_key FROM tasks WHERE owner_id=? AND case_id=? AND is_standard=1", (owner_id, case_id)).fetchall()}
        templates = c.execute("""SELECT * FROM task_templates WHERE owner_id=? AND is_active=1 ORDER BY sort_order,id""", (owner_id,)).fetchall()
        created = 0
        stamp = now_iso()
        for t in templates:
            if t["task_key"] in existing:
                continue
            due = start + timedelta(days=int(t["offset_days"]))
            tid = str(uuid.uuid4())
            c.execute("""INSERT INTO tasks
                (id,owner_id,case_id,task_key,title,description,due_date,status,priority,is_standard,is_custom,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (tid, owner_id, case_id, t["task_key"], t["title"], None, due.isoformat(), "pending", t["priority"], 1, 0, stamp, stamp))
            c.execute("""INSERT INTO task_history(task_id,actor_id,action,old_value,new_value,created_at)
                         VALUES(?,?,?,?,?,?)""", (tid, owner_id, "created", None, json.dumps({"title": t["title"], "due_date": due.isoformat()}, ensure_ascii=False), stamp))
            created += 1
        return {"created": created, "reason": "ok"}


def list_tasks(owner_id, case_id=None):
    ensure_schema()
    with connect() as c:
        if case_id:
            return c.execute("""SELECT t.*, c.file_no, c.title AS applicant_name, c.file_type, c.start_date
                              FROM tasks t JOIN cases c ON c.id=t.case_id
                              WHERE t.owner_id=? AND t.case_id=?
                              ORDER BY CASE t.status WHEN 'completed' THEN 3 WHEN 'cancelled' THEN 4 ELSE 1 END,
                                       t.due_date, t.created_at""", (owner_id, case_id)).fetchall()
        return c.execute("""SELECT t.*, c.file_no, c.title AS applicant_name, c.file_type, c.start_date
                          FROM tasks t JOIN cases c ON c.id=t.case_id
                          WHERE t.owner_id=? ORDER BY t.due_date,t.created_at""", (owner_id,)).fetchall()


def get_task(owner_id, task_id):
    ensure_schema()
    with connect() as c:
        return c.execute("SELECT * FROM tasks WHERE id=? AND owner_id=?", (task_id, owner_id)).fetchone()


def _history(c, task_id, actor_id, action, old, new):
    c.execute("INSERT INTO task_history(task_id,actor_id,action,old_value,new_value,created_at) VALUES(?,?,?,?,?,?)",
              (task_id, actor_id, action, json.dumps(old, ensure_ascii=False) if old is not None else None,
               json.dumps(new, ensure_ascii=False) if new is not None else None, now_iso()))


def create_custom_task(owner_id, case_id, title, due_date, priority="normal", description=""):
    ensure_schema()
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
    tid = str(uuid.uuid4()); stamp = now_iso()
    with connect() as c:
        c.execute("""INSERT INTO tasks
            (id,owner_id,case_id,task_key,title,description,due_date,status,priority,is_standard,is_custom,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (tid, owner_id, case_id, None, title.strip(), description.strip(), due_date, "pending", priority, 0, 1, stamp, stamp))
        _history(c, tid, owner_id, "created", None, {"title": title.strip(), "due_date": due_date, "priority": priority})
    return get_task(owner_id, tid)


def update_task(owner_id, task_id, **changes):
    ensure_schema()
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
    with connect() as c:
        sets=[]; vals=[]
        for k,v in changes.items():
            sets.append(f"{k}=?"); vals.append(v.strip() if isinstance(v,str) else v)
        if "status" in changes:
            if changes["status"] == "completed":
                sets += ["completed_at=?", "cancelled_at=NULL"]; vals.append(stamp)
            elif changes["status"] == "cancelled":
                sets += ["cancelled_at=?"]; vals.append(stamp)
            else:
                sets += ["completed_at=NULL", "cancelled_at=NULL"]
        sets.append("updated_at=?"); vals.append(stamp)
        vals += [task_id, owner_id]
        c.execute(f"UPDATE tasks SET {', '.join(sets)} WHERE id=? AND owner_id=?", vals)
        for k,v in changes.items():
            old=task[k]
            if str(old or "") != str(v or ""):
                _history(c, task_id, owner_id, f"changed_{k}", {k: old}, {k: v})
    return get_task(owner_id, task_id)


def update_template(owner_id, template_id, title, offset_days, priority):
    ensure_schema()
    if priority not in PRIORITIES:
        priority="normal"
    try:
        offset_days=int(offset_days)
    except Exception:
        raise ValueError("Gün değeri sayı olmalı.")
    if offset_days < 0 or offset_days > 21:
        raise ValueError("Standart görev günü 0 ile 21 arasında olmalı.")
    with connect() as c:
        row=c.execute("SELECT * FROM task_templates WHERE id=? AND owner_id=?",(template_id,owner_id)).fetchone()
        if not row: raise ValueError("Görev şablonu bulunamadı.")
        c.execute("UPDATE task_templates SET title=?,offset_days=?,priority=?,updated_at=? WHERE id=? AND owner_id=?",
                  (title.strip(),offset_days,priority,now_iso(),template_id,owner_id))
    return True


def templates(owner_id):
    seed_user_templates(owner_id)
    with connect() as c:
        return c.execute("SELECT * FROM task_templates WHERE owner_id=? ORDER BY sort_order,id",(owner_id,)).fetchall()


def history(owner_id, task_id):
    ensure_schema()
    with connect() as c:
        ok=c.execute("SELECT id FROM tasks WHERE id=? AND owner_id=?",(task_id,owner_id)).fetchone()
        if not ok:return []
        return c.execute("SELECT * FROM task_history WHERE task_id=? ORDER BY created_at DESC,id DESC",(task_id,)).fetchall()


def global_stats(owner_id):
    ensure_schema()
    today=date.today().isoformat()
    with connect() as c:
        total=c.execute("SELECT COUNT(*) n FROM tasks WHERE owner_id=?",(owner_id,)).fetchone()["n"]
        completed=c.execute("SELECT COUNT(*) n FROM tasks WHERE owner_id=? AND status='completed'",(owner_id,)).fetchone()["n"]
        overdue=c.execute("SELECT COUNT(*) n FROM tasks WHERE owner_id=? AND status NOT IN ('completed','cancelled') AND due_date<?",(owner_id,today)).fetchone()["n"]
        today_n=c.execute("SELECT COUNT(*) n FROM tasks WHERE owner_id=? AND status NOT IN ('completed','cancelled') AND due_date=?",(owner_id,today)).fetchone()["n"]
        upcoming=c.execute("SELECT COUNT(*) n FROM tasks WHERE owner_id=? AND status NOT IN ('completed','cancelled') AND due_date>? AND due_date<=date(?, '+7 day')",(owner_id,today,today)).fetchone()["n"]
    return {"total":total,"completed":completed,"overdue":overdue,"today":today_n,"upcoming":upcoming}
