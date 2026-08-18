
from pathlib import Path
import sqlite3

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
GENERATED_DIR = DATA_DIR / "generated"
# NOT: database.py, app/ paket kökünde; documents/engine.py bir seviye derinde (documents/ altında).
# Bu yüzden "templates/udf" klasörüne engine.py'deki TEMPLATE_DIR ile AYNI fiziksel yola ulaşmak için
# burada parents[1] değil, doğrudan bu dosyanın bulunduğu klasör (.parent) esas alınır.
CUSTOM_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates" / "udf" / "users_sablon"
DB_PATH = DATA_DIR / "app.db"

for p in (DATA_DIR, UPLOAD_DIR, GENERATED_DIR, CUSTOM_TEMPLATE_DIR):
    p.mkdir(parents=True, exist_ok=True)

def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def init_db():
    with connect() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, display_name TEXT NOT NULL,
            password_hash TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
            plan_id TEXT NOT NULL DEFAULT 'free', is_super_admin INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL, approved_at TEXT, expires_at TEXT, last_ip TEXT, iban TEXT,
            mediator_no INTEGER UNIQUE
        );
        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            created_at TEXT NOT NULL, expires_at TEXT NOT NULL, ip TEXT
        );
        CREATE TABLE IF NOT EXISTS plans (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, price_monthly REAL NOT NULL DEFAULT 0,
            active INTEGER NOT NULL DEFAULT 1, features_json TEXT NOT NULL, limits_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS cases (
            id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            file_no TEXT, application_no TEXT, title TEXT,
            file_type TEXT, start_date TEXT, status TEXT NOT NULL DEFAULT 'open', case_data_json TEXT,
            registry_no TEXT UNIQUE,
            deleted_at TEXT, deleted_by TEXT, deleted_from_status TEXT,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS documents (
            id TEXT PRIMARY KEY, case_id TEXT REFERENCES cases(id) ON DELETE SET NULL,
            owner_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            original_name TEXT NOT NULL, stored_path TEXT NOT NULL, kind TEXT NOT NULL,
            size_bytes INTEGER NOT NULL, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS generated_documents (
            id TEXT PRIMARY KEY, case_id TEXT REFERENCES cases(id) ON DELETE SET NULL,
            owner_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            original_template TEXT NOT NULL, stored_path TEXT NOT NULL, doc_kind TEXT, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            metric TEXT NOT NULL, amount INTEGER NOT NULL DEFAULT 1, period TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY, sender_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            recipient_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            case_id TEXT REFERENCES cases(id) ON DELETE SET NULL,
            body TEXT NOT NULL, created_at TEXT NOT NULL, read_at TEXT
        );
        CREATE TABLE IF NOT EXISTS calendar_events (
            id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
            owner_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            event_type TEXT NOT NULL, event_date TEXT NOT NULL,
            title TEXT NOT NULL, description TEXT, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS task_templates (
            id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            task_key TEXT NOT NULL, title TEXT NOT NULL, offset_days INTEGER NOT NULL DEFAULT 0,
            priority TEXT NOT NULL DEFAULT 'normal', sort_order INTEGER NOT NULL DEFAULT 0,
            is_active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            UNIQUE(owner_id, task_key)
        );
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
            task_key TEXT, title TEXT NOT NULL, description TEXT, due_date TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending', priority TEXT NOT NULL DEFAULT 'normal',
            is_standard INTEGER NOT NULL DEFAULT 1, is_custom INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL, completed_at TEXT, cancelled_at TEXT
        );
        CREATE TABLE IF NOT EXISTS task_history (
            id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
            actor_id TEXT REFERENCES users(id) ON DELETE SET NULL, action TEXT NOT NULL,
            old_value TEXT, new_value TEXT, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS user_permissions (
            id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            permission TEXT NOT NULL, granted_at TEXT NOT NULL, granted_by TEXT,
            UNIQUE(user_id, permission)
        );
        CREATE TABLE IF NOT EXISTS counters (
            id TEXT PRIMARY KEY, value INTEGER NOT NULL DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_tasks_owner_case ON tasks(owner_id, case_id);
        CREATE INDEX IF NOT EXISTS idx_tasks_due ON tasks(owner_id, due_date, status);
        CREATE INDEX IF NOT EXISTS idx_calendar_events_case ON calendar_events(case_id);
        CREATE INDEX IF NOT EXISTS idx_calendar_events_owner_date ON calendar_events(owner_id, event_date);
        CREATE INDEX IF NOT EXISTS idx_messages_case ON messages(case_id);
        CREATE INDEX IF NOT EXISTS idx_user_permissions_user ON user_permissions(user_id);
        CREATE INDEX IF NOT EXISTS idx_users_mediator_no ON users(mediator_no);
        CREATE INDEX IF NOT EXISTS idx_cases_registry_no ON cases(registry_no);
        CREATE TABLE IF NOT EXISTS surveys (
            id TEXT PRIMARY KEY, title TEXT NOT NULL, description TEXT, active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS survey_questions (
            id TEXT PRIMARY KEY, survey_id TEXT NOT NULL REFERENCES surveys(id) ON DELETE CASCADE,
            question TEXT NOT NULL, kind TEXT NOT NULL DEFAULT 'text'
        );
        CREATE TABLE IF NOT EXISTS survey_answers (
            id TEXT PRIMARY KEY, survey_id TEXT NOT NULL REFERENCES surveys(id) ON DELETE CASCADE,
            question_id TEXT NOT NULL REFERENCES survey_questions(id) ON DELETE CASCADE,
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            answer TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS custom_templates (
            id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            name TEXT NOT NULL, is_shared INTEGER NOT NULL DEFAULT 0,
            stored_path TEXT NOT NULL, recognized_json TEXT NOT NULL, unrecognized_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS fee_tariffs (
            id TEXT PRIMARY KEY, category TEXT NOT NULL, category_label TEXT NOT NULL,
            min_parties INTEGER NOT NULL, max_parties INTEGER,
            unit_price REAL NOT NULL, year INTEGER NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, actor_id TEXT, action TEXT NOT NULL,
            target_id TEXT, details TEXT, created_at TEXT NOT NULL
        );
        """)
        # NOT: Uygulama daha önce iban sütunu olmadan kurulmuş olabilir; CREATE TABLE IF NOT EXISTS
        # bu durumda sütunu eklemez. Var olan veritabanlarını bozmadan güvenle tamamlıyoruz.
        cols = [r["name"] for r in c.execute("PRAGMA table_info(users)").fetchall()]
        if "iban" not in cols:
            c.execute("ALTER TABLE users ADD COLUMN iban TEXT")
        case_cols = [r["name"] for r in c.execute("PRAGMA table_info(cases)").fetchall()]
        for col, ddl in (("file_type","TEXT"),("start_date","TEXT"),
                          ("status","TEXT NOT NULL DEFAULT 'open'"),("case_data_json","TEXT"),
                          ("deleted_at","TEXT"),("deleted_by","TEXT"),("deleted_from_status","TEXT")):
            if col not in case_cols:
                c.execute(f"ALTER TABLE cases ADD COLUMN {col} {ddl}")
        gd_cols = [r["name"] for r in c.execute("PRAGMA table_info(generated_documents)").fetchall()]
        if "doc_kind" not in gd_cols:
            c.execute("ALTER TABLE generated_documents ADD COLUMN doc_kind TEXT")
        msg_cols = [r["name"] for r in c.execute("PRAGMA table_info(messages)").fetchall()]
        if "case_id" not in msg_cols:
            c.execute("ALTER TABLE messages ADD COLUMN case_id TEXT REFERENCES cases(id) ON DELETE SET NULL")
        user_cols2 = [r["name"] for r in c.execute("PRAGMA table_info(users)").fetchall()]
        if "mediator_no" not in user_cols2:
            c.execute("ALTER TABLE users ADD COLUMN mediator_no INTEGER UNIQUE")
        case_cols2 = [r["name"] for r in c.execute("PRAGMA table_info(cases)").fetchall()]
        if "registry_no" not in case_cols2:
            c.execute("ALTER TABLE cases ADD COLUMN registry_no TEXT UNIQUE")
