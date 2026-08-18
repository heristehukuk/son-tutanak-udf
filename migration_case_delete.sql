-- Dosya silme (cop kutusu) ozelligi icin cases tablosuna 3 yeni kolon.
-- Mevcut Supabase projende cases tablosu zaten var oldugu icin
-- supabase_schema.sql'deki CREATE TABLE IF NOT EXISTS bunu otomatik
-- eklemez - bu yuzden ayrica calistirman gerekiyor. Tek seferlik,
-- tekrar calistirmak da guvenlidir.

ALTER TABLE cases ADD COLUMN IF NOT EXISTS deleted_at TEXT;
ALTER TABLE cases ADD COLUMN IF NOT EXISTS deleted_by TEXT;
ALTER TABLE cases ADD COLUMN IF NOT EXISTS deleted_from_status TEXT;
