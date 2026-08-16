-- =====================================================================
-- supabase_schema.sql
-- son-tutanak-udf projesi icin Supabase (PostgreSQL) semasi.
--
-- Bu dosya app/database_layer/supabase_repository.py ile BIREBIR uyumlu
-- olacak sekilde hazirlanmistir. Sadece Supabase repository katmaninin
-- gercekten kullandigi 11 tablo icerir:
--   users, sessions, plans, cases, documents, generated_documents,
--   usage, messages, custom_templates, fee_tariffs, audit_logs
--
-- NOT: SQLite semasinda (app/database.py) ayrica surveys,
-- survey_questions, survey_answers tablolari da var, ancak
-- app/surveys/routes.py bu tablolara hic dokunmuyor (anket modulu
-- henuz DB'ye baglanmamis). O yuzden bu dosyaya dahil edilmediler.
-- Ileride anket modulunu Supabase'e baglarsan bu dosyanin sonuna
-- ekleyebilirsin.
--
-- Kullanim: Supabase Dashboard -> SQL Editor -> New query -> bu dosyanin
-- tamamini yapistir -> Run. Tek seferde calistirilir, tekrar
-- calistirmak da guvenlidir (IF NOT EXISTS kullanildi).
-- =====================================================================

-- Uygulama kendi id'lerini (uuid4 string, veya "free"/"pro" gibi sabit
-- metinler) Python tarafinda uretip gonderiyor. Bu yuzden PRIMARY KEY
-- kolonlari native "uuid" tipi degil, TEXT olarak tanimlandi.

CREATE TABLE IF NOT EXISTS plans (
    id             TEXT PRIMARY KEY,
    name           TEXT NOT NULL,
    price_monthly  DOUBLE PRECISION NOT NULL DEFAULT 0,
    active         INTEGER NOT NULL DEFAULT 1,
    features_json  TEXT NOT NULL,
    limits_json    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id              TEXT PRIMARY KEY,
    email           TEXT UNIQUE NOT NULL,
    display_name    TEXT NOT NULL,
    password_hash   TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending',
    plan_id         TEXT NOT NULL DEFAULT 'free' REFERENCES plans(id),
    is_super_admin  INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL,
    approved_at     TEXT,
    expires_at      TEXT,
    last_ip         TEXT,
    iban            TEXT
);

CREATE TABLE IF NOT EXISTS sessions (
    token       TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at  TEXT NOT NULL,
    expires_at  TEXT NOT NULL,
    ip          TEXT
);

CREATE TABLE IF NOT EXISTS cases (
    id               TEXT PRIMARY KEY,
    owner_id         TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    file_no          TEXT,
    application_no   TEXT,
    title            TEXT,
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS documents (
    id             TEXT PRIMARY KEY,
    case_id        TEXT REFERENCES cases(id) ON DELETE SET NULL,
    owner_id       TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    original_name  TEXT NOT NULL,
    stored_path    TEXT NOT NULL,
    kind           TEXT NOT NULL,
    size_bytes     INTEGER NOT NULL,
    created_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS generated_documents (
    id                 TEXT PRIMARY KEY,
    case_id            TEXT REFERENCES cases(id) ON DELETE SET NULL,
    owner_id           TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    original_template  TEXT NOT NULL,
    stored_path        TEXT NOT NULL,
    created_at         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS usage (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    metric      TEXT NOT NULL,
    amount      INTEGER NOT NULL DEFAULT 1,
    period      TEXT NOT NULL,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id            TEXT PRIMARY KEY,
    sender_id     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    recipient_id  TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    body          TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    read_at       TEXT
);

CREATE TABLE IF NOT EXISTS custom_templates (
    id                TEXT PRIMARY KEY,
    owner_id          TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name              TEXT NOT NULL,
    is_shared         INTEGER NOT NULL DEFAULT 0,
    stored_path       TEXT NOT NULL,
    recognized_json   TEXT NOT NULL,
    unrecognized_json TEXT NOT NULL,
    created_at        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS fee_tariffs (
    id              TEXT PRIMARY KEY,
    category        TEXT NOT NULL,
    category_label  TEXT NOT NULL,
    min_parties     INTEGER NOT NULL,
    max_parties     INTEGER,
    unit_price      DOUBLE PRECISION NOT NULL,
    year            INTEGER NOT NULL,
    updated_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    actor_id    TEXT,
    action      TEXT NOT NULL,
    target_id   TEXT,
    details     TEXT,
    created_at  TEXT NOT NULL
);

-- =====================================================================
-- Anket modulu tablolari (surveys, survey_questions, survey_answers)
--
-- NOT: Bu tablolar olusturuldu, ama app/surveys/routes.py henuz bunlara
-- hic dokunmuyor (su an sadece sabit bir bilgi sayfasi gosteriyor).
-- Aneti gercekten aktif etmek icin ayrica su kod parcalarinin
-- yazilmasi gerekiyor:
--   1) app/database_layer/base.py    -> SurveyRepository arayuzu
--   2) app/database_layer/sqlite_repository.py -> SQLite implementasyonu
--   3) app/database_layer/supabase_repository.py -> Supabase implementasyonu
--   4) app/database_layer/__init__.py -> factory'ye ekleme
--   5) app/surveys/routes.py -> gercek liste/cevap-kaydetme/sonuc mantigi
-- Bu adimlari Render kurulumundan sonra birlikte yapacagiz.
-- =====================================================================

CREATE TABLE IF NOT EXISTS surveys (
    id           TEXT PRIMARY KEY,
    title        TEXT NOT NULL,
    description  TEXT,
    active       INTEGER NOT NULL DEFAULT 1,
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS survey_questions (
    id         TEXT PRIMARY KEY,
    survey_id  TEXT NOT NULL REFERENCES surveys(id) ON DELETE CASCADE,
    question   TEXT NOT NULL,
    kind       TEXT NOT NULL DEFAULT 'text'
);

CREATE TABLE IF NOT EXISTS survey_answers (
    id           TEXT PRIMARY KEY,
    survey_id    TEXT NOT NULL REFERENCES surveys(id) ON DELETE CASCADE,
    question_id  TEXT NOT NULL REFERENCES survey_questions(id) ON DELETE CASCADE,
    user_id      TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    answer       TEXT NOT NULL,
    created_at   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_survey_questions_survey_id ON survey_questions(survey_id);
CREATE INDEX IF NOT EXISTS idx_survey_answers_survey_id ON survey_answers(survey_id);
CREATE INDEX IF NOT EXISTS idx_survey_answers_user_id ON survey_answers(user_id);

-- Faydali indeksler (opsiyonel ama onerilir)
CREATE INDEX IF NOT EXISTS idx_cases_owner_id ON cases(owner_id);
CREATE INDEX IF NOT EXISTS idx_documents_owner_id ON documents(owner_id);
CREATE INDEX IF NOT EXISTS idx_documents_case_id ON documents(case_id);
CREATE INDEX IF NOT EXISTS idx_generated_documents_owner_id ON generated_documents(owner_id);
CREATE INDEX IF NOT EXISTS idx_usage_user_metric_period ON usage(user_id, metric, period);
CREATE INDEX IF NOT EXISTS idx_messages_recipient_id ON messages(recipient_id);
CREATE INDEX IF NOT EXISTS idx_messages_sender_id ON messages(sender_id);
CREATE INDEX IF NOT EXISTS idx_fee_tariffs_category_year ON fee_tariffs(category, year);

-- =====================================================================
-- ONEMLI: Bu tablolara sadece backend (SUPABASE_SECRET_KEY / service_role
-- anahtari) erisecek. Row Level Security (RLS) acmiyoruz cunku
-- service_role anahtari zaten RLS'i bypass eder; RLS'i sonradan
-- acmak istersen once her tablo icin policy yazman gerekir, yoksa
-- backend istekleri 0 satir donmeye baslar.
-- =====================================================================
