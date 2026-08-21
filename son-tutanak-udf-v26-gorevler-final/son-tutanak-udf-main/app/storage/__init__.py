"""
Storage fabrikası.

Uygulama kodu depolamaya buradan erişir, örn:
    from app.storage import storage
    storage.save("uploads/abc.pdf", data)

Hangi backend'in aktif olduğu, veritabanı katmanıyla AYNI DB_BACKEND ortam
değişkeniyle kontrol edilir - mantık gereği: Supabase'i (kalıcı) veritabanı
için kullanıyorsan, dosyaların da kalıcı olması için Supabase Storage
kullanman gerekir; SQLite (yerel/test) kullanıyorsan dosyalar da yerel
diske yazılır. Render gibi platformlarda yerel disk KALICI DEĞİLDİR - bu
yüzden production'da DB_BACKEND=supabase iken dosyaların da otomatik
olarak Supabase Storage'a gitmesi kritik önem taşır.

ÖN KOŞUL (Supabase kullanılıyorsa): Supabase panelinde Storage sekmesinden
PRIVATE bir bucket oluşturulmuş olmalı (varsayılan ad: "documents", bkz.
app/storage/supabase_storage.py). Bucket SQL ile oluşturulamaz.
"""

import os
from pathlib import Path

_BACKEND = os.getenv("DB_BACKEND", "sqlite").strip().lower()

if _BACKEND == "supabase":
    from app.storage.supabase_storage import SupabaseStorage
    storage = SupabaseStorage()
else:
    from app.storage.local_storage import LocalStorage
    _ROOT = Path(__file__).resolve().parents[2] / "data"
    storage = LocalStorage(_ROOT)
