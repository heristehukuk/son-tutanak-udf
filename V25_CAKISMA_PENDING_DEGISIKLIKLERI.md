# V25 – Çakışma / Pending Belge Güncellemesi

Kaynak sürüm: `son-tutanak-udf-v24.zip`

## Eklenenler

- Çakışmalı belgeler için `pending_merges` metadata tablosu ve repository katmanı eklendi.
- Çakışma çözülene kadar belge `pending/` altında geçici tutulur.
- Pending kayıtları 24 saat geçerlidir; süre dolunca storage ve metadata kaydı birlikte temizlenir.
- Pending belgeyi yalnızca belge sahibi veya süper admin görebilir.
- Çözüm ekranı artık gizli form alanlarındaki JSON'a güvenmez; veriler sunucu tarafındaki pending kaydından alınır.
- Admin panelinde bekleyen çakışmalı belgeler görünür.
- Mevcut V24 çakışma ekranı (eski / yeni / özel değer veya ayrı yeni dosya) korunmuştur.

## Temizlik doğrulaması

- `app/folders/` kanonik klasör modülüdür.
- `app/modules/folders.py` yoktur.
- `app/modules/folders/` yoktur.
- `app/templates/udf/sablonlar/` yoktur.
- Bozuk/öksüz şablon dosyası yoktur.
