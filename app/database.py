
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
            created_at TEXT NOT NULL, approved_at TEXT, expires_at TEXT, last_ip TEXT
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
            file_no TEXT, application_no TEXT, title TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
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
            original_template TEXT NOT NULL, stored_path TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            metric TEXT NOT NULL, amount INTEGER NOT NULL DEFAULT 1, period TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY, sender_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            recipient_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            body TEXT NOT NULL, created_at TEXT NOT NULL, read_at TEXT
        );
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
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, actor_id TEXT, action TEXT NOT NULL,
            target_id TEXT, details TEXT, created_at TEXT NOT NULL
        );
        """)
