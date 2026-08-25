# Otomatik Şablon Tanıma

Bu klasördeki (`templates/udf/`) her ALT KLASÖR bir "belge türü" (doc_kind) temsil eder.
Bir alt klasöre `.udf` uzantılı bir şablon bıraktığında, sistem yeniden başlatmaya
gerek kalmadan (her belge düzenleme ekranı açıldığında) onu otomatik tarar ve
"Belge türü" listesine ekler.

Şablon içindeki köşeli parantez alanları ([dosya no], [arabulucu adı], [karşı taraf 1 adı]
gibi) otomatik olarak bilgi havuzundaki karşılık gelen değerlerle doldurulur.
Tanınan/tanınmayan alanları görmek için Şablonlarım (Kendi Şablonum) ekranındaki
önizleme mekanizmasını kullanabilirsin.

Klasör adı = belge türü (doc_kind):

- `davet_mektubu/`     → Davet Mektubu şablonları
- `ust_yazi/`          → Üst Yazı şablonları
- (istediğin başka bir isimle yeni bir klasör açarsan, o da otomatik tanınır)

NOT: `son_tutanak`, `anlasma_belgesi` gibi 3 sabit şablon (anlasma_son_tutanagi.udf,
anlasmama_son_tutanagi.udf, anlasma_belgesi.udf) bu klasörün KÖKÜNDE düz dosya
olarak duruyor - bunlar özel/elle yazılmış motoru kullanıyor, bu otomatik tanıma
sistemine dahil değil, dokunma. Sen sadece yeni belge türleri için alt klasör aç.

`users_sablon/` klasörüne dokunma - o, kullanıcıların "Kendi Şablonum" ekranından
yüklediği şablonların sistem tarafından yönetilen deposu.
