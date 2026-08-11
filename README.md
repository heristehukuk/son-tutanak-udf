# Son Tutanak UDF Asistanı v10

Bu sürüm UDF içindeki gerçek `<paragraph>` yapısını da günceller. Böylece birden fazla karşı taraf eklendiğinde satırlar UYAP Doküman Editörü'nde birbirine yapışmaz.

Özellikler:
- Başvuru UDF'sinden bilgi çıkarma
- Birden fazla belgeyi bilgi havuzunda birleştirme
- Alanları ve tarafları sabitleme
- Birden fazla karşı taraf
- Kişi/kurum ayrımı ve T.C. Kimlik No/Vergi No
- Üç hazır son tutanak şablonu
- Özel UDF şablonu
- Karşı taraf ve imza bölümlerinde gerçek UDF paragraf yapısının korunması
- Başvurucu/arabulucu isimlerinin belge içindeki ilgili kullanımlarının güncellenmesi

Render:
Build: pip install -r requirements.txt
Start: uvicorn app.main:app --host 0.0.0.0 --port $PORT
