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

## 2026-08-19 - 3 Render sorun düzeltmesi

1. **Silinmiş dosyaların takvimde görünmesi:** Takvim olayları artık bağlı `case` kaydı `status=deleted` ise `/calendar/events` ve `/calendar/warnings` sonuçlarından çıkarılıyor. Takvimdeki aktif dosya listesi de silinmiş case'leri göstermiyor.
2. **Görevler sayfasının boş kalması:** Görev oluşturma, `cases.start_date` boşsa `case_data_json.baslangicTarihi` değerini kullanıyor; eski kayıtlarda gerekiyorsa normal süre takvim olayından başlangıç tarihini geri hesaplayıp case'e kaydediyor. Tarih bulunamazsa görev sayfasında açık bir uyarı gösteriliyor.
3. **Dosyalarım ekranı:** Her aktif dosya kartına doğrudan `📁 Klasör` bağlantısı eklendi.

Ayrıca takvim oluşturma sırasında Dosya No'nun boş olmasına izin verildi; başvurucu, dosya türü ve geçerli süreç başlangıç tarihi varsa takvim/görev akışı devam eder ve başlıkta `Dosya No yok` kullanılır.

## V22 düzeltmeleri
- Belgeler arası kimlik çakışması denetimi eklendi: Dosya No, Başvuru No veya Başvurucu adı mevcut case ile çelişirse mevcut case korunur ve belge yeni case'e kaydedilir.
- Boş gelen alanlar mevcut case bilgilerini silmez; yeni belge yalnızca dolu alanları tamamlar.
- Case silindiğinde bağlı klasör ağacı da silinen duruma alınır; alt klasörler dahil.
- Admin klasör geri yüklemesinde bağlı alt klasörler de geri yüklenir.
- Bilgi Havuzu takvim açıklaması artık Dosya No'yu zorunlu göstermiyor.
- Supabase klasör migration'ına aynı case seviyesinde aktif/restored özel klasör adlarında benzersizlik indeksi eklendi.
