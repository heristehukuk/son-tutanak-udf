# Klasör Sistemi Güncellemesi

Kaynak: son-tutanak-udf-main (4).zip. Önceki ZIP sürümleri kaynak alınmamıştır.

## Eklenen / değiştirilen
- `app/folders/` tek kanonik klasör modülü olarak bırakıldı; `app/modules/folders.py` ve `app/modules/folders/` kaldırıldı.
- SQLite ve Supabase repository katmanlarına `FolderRepository` eklendi.
- `folders` ve `folder_permissions` tabloları eklendi.
- `documents.folder_id` ve `generated_documents.folder_id` eklendi.
- İlk case oluşturulurken kök klasör + 7 standart klasör idempotent olarak oluşturuluyor.
- Case bilgileri değiştiğinde kök klasör görünen adı güncelleniyor.
- Kaynak/oluşturulan belgeler belge türüne göre otomatik klasöre bağlanıyor.
- Kullanıcı: kendi klasörleri + genel klasörler + adminin izin verdiği klasörleri görür.
- Başka kullanıcıların özel klasörleri görünmez.
- Kullanıcı yalnızca kendi oluşturduğu özel klasörleri silebilir/yeniden adlandırabilir.
- Admin tüm klasörleri görebilir, silebilir, genel klasör oluşturabilir ve kullanıcıya klasör erişimi verebilir.
- Silinen klasörler `deleted` durumuna alınır; kullanıcıdan anında gizlenir.
- Admin geri yüklediğinde klasör `Geri Yüklenenler` ağacına taşınır ve kullanıcıya otomatik erişim verilmez.
- Silinen klasörler 15 gün sonra kalıcı olarak temizlenir; belgelerin klasör bağlantısı kaldırılır, belge içeriği korunur.
- Bilgi Havuzu/merge akışında mevcut case bilgileri yeni belge bilgileriyle güncellenirken mevcut boş olmayan bilgiler korunur.
- Takvim oluşturma için Dosya No artık zorunlu değil; Başvurucu + Dosya Türü + Süreç Başlangıç Tarihi gerekir.

## Korunan mevcut sistemler
- `app/documents/engine.py`
- `app/feepusula/`
- üyelik/auth
- admin
- messaging
- calendar
- tasks / task history / task templates
- mevcut Supabase/SQLite repository mimarisi
- UDF/PDF/JPG/JPEG/PNG/OCR akışı
