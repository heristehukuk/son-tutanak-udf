-- Son Tutanak UDF - klasor sistemi migration
-- Mevcut Supabase kurulumunu bozmadan calistirilabilir.

CREATE TABLE IF NOT EXISTS folders (
    id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    owner_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    parent_id TEXT REFERENCES folders(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    folder_type TEXT NOT NULL DEFAULT 'custom',
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_system INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

ALTER TABLE documents ADD COLUMN IF NOT EXISTS folder_id TEXT REFERENCES folders(id) ON DELETE SET NULL;
ALTER TABLE generated_documents ADD COLUMN IF NOT EXISTS folder_id TEXT REFERENCES folders(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_folders_case ON folders(case_id);
CREATE INDEX IF NOT EXISTS idx_folders_parent ON folders(parent_id);
CREATE INDEX IF NOT EXISTS idx_documents_folder_id ON documents(folder_id);
CREATE INDEX IF NOT EXISTS idx_generated_documents_folder_id ON generated_documents(folder_id);
