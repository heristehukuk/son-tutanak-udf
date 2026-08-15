import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CALENDAR_DB = BASE_DIR / "calendar.sqlite"


def get_connection():
    connection = sqlite3.connect(str(CALENDAR_DB), check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    return connection


def init_calendar_database():
    with get_connection() as connection:
        connection.execute("""CREATE TABLE IF NOT EXISTS calendar_cases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id TEXT,
            main_case_id TEXT,
            case_no TEXT NOT NULL,
            applicant_name TEXT NOT NULL,
            file_type TEXT NOT NULL,
            start_date TEXT NOT NULL,
            normal_due_date TEXT NOT NULL,
            extended_due_date TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(case_no, start_date)
        )""")
        connection.execute("""CREATE TABLE IF NOT EXISTS calendar_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            event_date TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            FOREIGN KEY(case_id) REFERENCES calendar_cases(id) ON DELETE CASCADE
        )""")
        cols={r["name"] for r in connection.execute("PRAGMA table_info(calendar_cases)").fetchall()}
        if "owner_id" not in cols: connection.execute("ALTER TABLE calendar_cases ADD COLUMN owner_id TEXT")
        if "main_case_id" not in cols: connection.execute("ALTER TABLE calendar_cases ADD COLUMN main_case_id TEXT")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_calendar_cases_owner ON calendar_cases(owner_id)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_calendar_cases_main ON calendar_cases(main_case_id)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_calendar_events_date ON calendar_events(event_date)")
        connection.commit()


def get_case_by_main_id(main_case_id, owner_id):
    with get_connection() as c:
        row=c.execute("SELECT * FROM calendar_cases WHERE main_case_id=? AND owner_id=?",(main_case_id,owner_id)).fetchone()
    return dict(row) if row else None


def get_case_by_key(case_no, start_date, owner_id):
    with get_connection() as c:
        row=c.execute("SELECT * FROM calendar_cases WHERE case_no=? AND start_date=? AND owner_id=?",(case_no,start_date,owner_id)).fetchone()
    return dict(row) if row else None


def insert_case(data):
    with get_connection() as c:
        cur=c.execute("""INSERT INTO calendar_cases
            (owner_id,main_case_id,case_no,applicant_name,file_type,start_date,normal_due_date,extended_due_date,created_at)
            VALUES(?,?,?,?,?,?,?,?,?)""",(
                data.get("owner_id"),data.get("main_case_id"),data["case_no"],data["applicant_name"],data["file_type"],
                data["start_date"],data["normal_due_date"],data["extended_due_date"],data["created_at"]))
        c.commit(); return int(cur.lastrowid)


def update_case(case_id,data):
    with get_connection() as c:
        c.execute("""UPDATE calendar_cases SET main_case_id=?,case_no=?,applicant_name=?,file_type=?,start_date=?,normal_due_date=?,extended_due_date=? WHERE id=?""",
                  (data.get("main_case_id"),data["case_no"],data["applicant_name"],data["file_type"],data["start_date"],data["normal_due_date"],data["extended_due_date"],case_id))
        c.execute("DELETE FROM calendar_events WHERE case_id=?",(case_id,))
        c.commit()


def insert_event(data):
    with get_connection() as c:
        cur=c.execute("""INSERT INTO calendar_events(case_id,event_type,event_date,title,description) VALUES(?,?,?,?,?)""",
                      (data["case_id"],data["event_type"],data["event_date"],data["title"],data.get("description")))
        c.commit(); return int(cur.lastrowid)


def get_case(case_id, owner_id=None):
    with get_connection() as c:
        q="SELECT * FROM calendar_cases WHERE id=?"; p=[case_id]
        if owner_id is not None: q+=" AND owner_id=?"; p.append(owner_id)
        row=c.execute(q,p).fetchone()
    return dict(row) if row else None


def list_cases(owner_id=None):
    with get_connection() as c:
        if owner_id is None: rows=c.execute("SELECT * FROM calendar_cases ORDER BY start_date DESC").fetchall()
        else: rows=c.execute("SELECT * FROM calendar_cases WHERE owner_id=? ORDER BY start_date DESC",(owner_id,)).fetchall()
    return [dict(r) for r in rows]


def list_events(start_date=None,end_date=None,owner_id=None):
    query="""SELECT e.*,c.case_no,c.applicant_name,c.file_type,c.start_date,c.main_case_id,c.owner_id
               FROM calendar_events e JOIN calendar_cases c ON c.id=e.case_id"""
    conditions=[]; params=[]
    if owner_id is not None: conditions.append("c.owner_id=?"); params.append(owner_id)
    if start_date: conditions.append("e.event_date>=?"); params.append(start_date)
    if end_date: conditions.append("e.event_date<=?"); params.append(end_date)
    if conditions: query+=" WHERE "+" AND ".join(conditions)
    query+=" ORDER BY e.event_date ASC"
    with get_connection() as c: rows=c.execute(query,params).fetchall()
    return [dict(r) for r in rows]


def delete_case(case_id,owner_id=None):
    with get_connection() as c:
        q="DELETE FROM calendar_events WHERE case_id IN (SELECT id FROM calendar_cases WHERE id=?"; p=[case_id]
        if owner_id is not None: q+=" AND owner_id=?"; p.append(owner_id)
        q+=")"; c.execute(q,p)
        q2="DELETE FROM calendar_cases WHERE id=?"; p2=[case_id]
        if owner_id is not None: q2+=" AND owner_id=?"; p2.append(owner_id)
        c.execute(q2,p2); c.commit()

init_calendar_database()
