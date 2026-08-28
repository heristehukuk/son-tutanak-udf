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
