-- İstatistik paneli için: generated_documents tablosuna ücret tutarını
-- kaydedecek 'amount' sütununu ekler. Sadece Harcama Pusulası üretildiğinde
-- doldurulur (son tutanak gibi diğer belgelerde NULL kalır).
ALTER TABLE generated_documents ADD COLUMN IF NOT EXISTS amount DOUBLE PRECISION;
