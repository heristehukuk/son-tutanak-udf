# Son Tutanak UDF Asistanı – V28

Bu README, mevcut proje README'sini ve proje geliştirme notlarını tek dosyada toplar. İçerikler kısaltılmadan korunmuştur.

## V28 çalışma kuralları

- Kod değişikliği öncesinde ilgili dosyanın güncel hali incelenir.
- Kullanıcı açıkça **“kodla”** demeden kod değişikliği yapılmaz.
- Normal geliştirmelerde tüm ZIP yerine yalnızca değişen/yeni dosyalar paylaşılır.
- Bu sürümde, kullanıcının özel isteği nedeniyle tam ve temiz proje ZIP'i hazırlanmıştır.
- Kaynak ZIP'inde `__pycache__`, `*.pyc`, `*.pyo` ve çalışma verileri bulunmaz.

## Bu V28 güncellemesinin ana amacı

Davet Mektubu sisteminin uygulamaya tam entegrasyonudur. `app/templates/udf/sablonlar/davet_mektubu.udf` şablonu; dosya türüne göre dava şartı ve süre paragraflarını seçer, telekonferans/yüz yüze toplantı paragrafını doldurur, başvurucu ve her karşı taraf için ayrı UDF üretir, belge türünü `davet_mektubu` olarak kaydeder ve üretilen belge üzerinden **Davet Gönder** görevini otomatik tamamlar.

Profil kaydetme sorunu için eski SQLite veritabanlarında eksik profil sütunlarını tamamlayan idempotent migration da eklenmiştir. Bilgi Havuzu'ndaki daha önce düzeltilmiş Arabulucu Bilgileri ve Dosya Bilgileri çift görünme davranışı yeniden değiştirilmemiştir.

---

# Önceki ana README içeriği

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

## Render OCR
`apt.txt` installs Tesseract OCR, Turkish/English language data and Poppler. JPG/JPEG/PNG and scanned PDFs can therefore be OCR'd on Render.


---

# Proje notları – V23 Görev Düzeltmeleri

# V23 Görev Modülü Düzeltmeleri

Kaynak: `son-tutanak-udf-main (6).zip`

Yalnızca görev/takvim görev oluşturma akışı güncellendi.

## Düzeltilenler
- CalendarService artık `tasks_created=6` değerini sabit döndürmüyor; gerçek `create_standard_tasks()` sonucunu döndürüyor.
- `CalendarService.add_case()` görev oluşturma sonucunu (`tasks_created`, `tasks_existing`, `tasks_result`) bildiriyor.
- `/case/schedule` artık gerçekten 6 standart görevin oluştuğunu kontrol ediyor; 6'dan azsa başarı gibi yönlendirme yapmıyor.
- Eski dosyalarda şablon seed'i eksikse ikinci güvenlik çağrısıyla standart görev oluşturma deneniyor.
- Görev sayfası hata durumunda gerçek nedeni kullanıcıya gösteriyor.
- `/tasks?case_id=...` yönlendirmesi korunuyor.

## Korunanlar
- Takvimde normal süre + ek süre olmak üzere 2 kayıt mantığı.
- 6 standart görev başlığı ve tarih offsetleri.
- Özel görevler, görev geçmişi ve görev düzenleme sistemi.
- Üyelik, admin, mesajlaşma, belge motoru, ücret pusulası ve klasör sistemi.

## Test
- İlk `create_standard_tasks()` çağrısı: 6 görev.
- Aynı case için ikinci çağrı: 0 yeni görev.
- Takvim akışı: 2 takvim olayı + 6 standart görev.
- Python compile: başarılı.


---

# Proje notları – V25 Çakışma / Pending Değişiklikleri

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


---

# Proje notları – V26 Görev Düzeltmeleri

# V26 Görevler Düzeltmeleri

Kaynak: `son-tutanak-udf-main (6)`/V25 görev akışı.

## Düzeltmeler
1. `app/modules/tasks/router.py`: görev sayfasındaki `showHistory()` JavaScript newline escape düzeltildi. Inline JS Node syntax kontrolünden geçirildi.
2. `app/modules/tasks/router.py`: eksik Başvurucu durumunda server-side uyarı gösterilir.
3. `app/modules/tasks/storage.py`: `Yeni Dosya` placeholder'ı gerçek başvurucu kabul edilmez; standart görev üretimi `applicant_missing` ile durur.
4. `app/main.py`: Takvime Ekle / Görevleri Oluştur akışında `Yeni Dosya` gerçek başvurucu kabul edilmez ve doğru uyarı verilir.
5. Standart görev üretimi için test: başlangıç tarihi ve başvurucu mevcutsa ilk çalışmada 6 görev, tekrar çalışmada 0 yeni görev.

## Korunanlar
Mevcut klasör, belge, pending/çakışma, profil, alias, takvim, ücret pusulası, üyelik, admin, mesajlaşma ve diğer çalışan modüller değiştirilmedi.


---

# Proje notları – Klasör Sistemi Değişiklikleri

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


---

# Proje notları – Şablon / Klasör Birleştirme Notu

# Birleştirme Notu

Temel: case-folder-scope-final
Şablon güncellemeleri: main-2-sablon-guncel-final

Korunan: case-bazlı klasör izolasyonu, 3 fixes, güncel repository ve diğer uygulama modülleri.
Birleştirilen: custom template doc_kind, güncel engine şablon keşfi, üst yazı türleri, şablon ekranı, Supabase/SQLite doc_kind desteği.
Ücret Pusulası şablon türü seçiminden çıkarılmış ayrı üretim akışıdır.

