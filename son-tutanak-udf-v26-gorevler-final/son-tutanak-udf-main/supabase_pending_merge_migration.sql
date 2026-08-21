CREATE TABLE IF NOT EXISTS pending_merges (
    id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    case_id TEXT REFERENCES cases(id) ON DELETE SET NULL, pending_key TEXT UNIQUE NOT NULL,
    original_filename TEXT NOT NULL, kind TEXT NOT NULL DEFAULT 'source',
    incoming_json TEXT NOT NULL, respondents_json TEXT NOT NULL,
    base_values_json TEXT NOT NULL, base_respondents_json TEXT NOT NULL,
    locked_json TEXT NOT NULL, locked_resp_json TEXT NOT NULL, conflicts_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending', created_at TEXT NOT NULL, expires_at TEXT NOT NULL,
    resolved_at TEXT, resolved_by TEXT REFERENCES users(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_pending_merges_owner_status ON pending_merges(owner_id,status);
CREATE INDEX IF NOT EXISTS idx_pending_merges_expires ON pending_merges(status,expires_at);
