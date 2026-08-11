# Son Tutanak UDF Asistanı v7

Akış:
1. Başvuru Formu UDF yüklenir.
2. Uygulama bulabildiği bilgileri çıkarır.
3. Kullanıcı bilgileri kontrol eder ve eksikleri manuel tamamlar.
4. Kayıtlı üç şablondan biri seçilir:
   - Anlaşma Son Tutanağı
   - Anlaşmama Son Tutanağı
   - Anlaşma Tutanağı (Anlaşma Belgesi)
5. İstenirse "Kendi UDF şablonumu yükle" seçeneğiyle özel son tutanak şablonu kullanılabilir.
6. Yeni UDF, seçilen şablonun metin/biçim yapısı korunarak oluşturulur.

Render:
Build Command: pip install -r requirements.txt
Start Command: uvicorn app.main:app --host 0.0.0.0 --port $PORT

Notlar:
- Değiştirilen UDF'de eski sign.sgn taşınmaz; uygulama elektronik imza üretmez veya yenilemez.
- Dosya boyutu kontrolü ve kalıcı dosya depolama yoktur.
- Hazır şablonlar kullanıcı tarafından sağlanan UDF dosyalarıdır.
