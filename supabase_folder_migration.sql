-- Güvenli klasör sistemi migration; tekrar çalıştırılabilir.
CREATE TABLE IF NOT EXISTS folders (
    id TEXT PRIMARY KEY, case_id TEXT REFERENCES cases(id) ON DELETE CASCADE,
    owner_id TEXT REFERENCES users(id) ON DELETE SET NULL, parent_id TEXT REFERENCES folders(id) ON DELETE SET NULL,
    name TEXT NOT NULL, folder_type TEXT NOT NULL DEFAULT 'custom', code TEXT, sort_order INTEGER NOT NULL DEFAULT 1000,
    is_system INTEGER NOT NULL DEFAULT 0, is_global INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL DEFAULT 'active',
    deleted_at TEXT, deleted_by TEXT, restored_at TEXT, restored_by TEXT, restored_parent_id TEXT,
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS folder_permissions (
    id TEXT PRIMARY KEY, folder_id TEXT NOT NULL REFERENCES folders(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE, granted_by TEXT REFERENCES users(id) ON DELETE SET NULL,
    granted_at TEXT NOT NULL, UNIQUE(folder_id,user_id)
);
ALTER TABLE documents ADD COLUMN IF NOT EXISTS folder_id TEXT REFERENCES folders(id) ON DELETE SET NULL;
ALTER TABLE generated_documents ADD COLUMN IF NOT EXISTS folder_id TEXT REFERENCES folders(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_folders_case ON folders(case_id,status);
CREATE INDEX IF NOT EXISTS idx_folders_owner ON folders(owner_id,status);
CREATE INDEX IF NOT EXISTS idx_folders_parent ON folders(parent_id,status);
CREATE INDEX IF NOT EXISTS idx_folder_permissions_user ON folder_permissions(user_id);
CREATE INDEX IF NOT EXISTS idx_documents_folder ON documents(folder_id);
CREATE INDEX IF NOT EXISTS idx_generated_documents_folder ON generated_documents(folder_id);
