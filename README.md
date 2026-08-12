# Son Tutanak UDF Asistanı v16

v15'in çalışan OCR/UDF motoru korunarak modüler üyelik, plan/limit, dosya,
admin, mesaj ve anket katmanları eklenmiştir.

## Render
Build Command:
`pip install -r requirements.txt`

Start Command:
`uvicorn app.main:app --host 0.0.0.0 --port $PORT`

İlk Super Admin için Render Environment Variables:
- ADMIN_EMAIL
- ADMIN_PASSWORD

Şifreler geri okunabilir biçimde saklanmaz.

## Kaynak belgeler
UDF, PDF, JPG, JPEG ve PNG kabul edilir. Görüntü ve taranmış PDF'lerde
Tesseract `tur+eng` OCR kullanılır; PDF'de seçilebilir metin yoksa sayfalar OCR edilir.

## Modüller
- auth: üyelik, onay, oturum ve güvenlik
- plans: plan, özellik ve limit
- files: UUID tabanlı dosya ve belge arşivi
- documents: v15 OCR/UDF motoru
- admin: üyelik ve yüklenen belgelerin yönetimi
- messaging: mesaj altyapısı
- surveys: anket altyapısı

Üretimde HTTPS altında secure cookie kullanılmalıdır.
