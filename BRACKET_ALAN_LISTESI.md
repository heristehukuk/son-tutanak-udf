# Köşeli Parantez (Bracket) Şablon Alan Listesi

Bu liste `app/documents/engine.py` içindeki `FIELD_SYNONYMS`, `RESP_FIELD_SYNONYMS`
ve `COMPUTED_BRACKETS` sözlüklerinden çıkarılmıştır (2026-09 itibarıyla).

**Genel kural:** Köşeli parantez içindeki metin büyük/küçük harf, boşluk ve Türkçe
karakter farkına duyarlı DEĞİLDİR (`normalize_bracket_text` hepsini sadeleştirip
karşılaştırır). Yani `[Dosya No]`, `[dosya no]`, `[DOSYANO]` ve `[dosya  no]` hepsi
aynı alana eşlenir. Aşağıda her alan için en doğal/okunur yazımı verdim; parantez
içine onu yazmanız yeterli.

Tanınmayan bir ifade yazarsanız (yazım hatası, listede olmayan bir kelime), o
bracket **boş bırakılır** (sessizce silinir) — belge üretilmeden önce uygulama
"tanınmayan ifadeler" uyarısı gösterir, o yüzden şablonu yükledikten sonra bu
uyarıyı mutlaka kontrol edin.

---

## 1) Genel alanlar (tek değerli, kutucuklardan gelir)

| Köşeli parantez | Karşılığı |
|---|---|
| `[başvuru no]` | Başvuru No |
| `[dosya no]` | Dosya No |
| `[arabulucu adı]` | Arabulucu Adı |
| `[arabulucu tc]` | Arabulucu T.C. Kimlik No |
| `[arabulucu sicil]` | Arabulucu Sicil No |
| `[arabulucu adres]` | Arabulucu Adres |
| `[arabulucu telefon]` | Arabulucu Telefon |
| `[arabulucu eposta]` | Arabulucu E-posta |
| `[iban]` | Arabulucu IBAN (kullanıcı profilinden, otomatik) |
| `[başvurucu adı soyadı]` | Başvurucu Adı Soyadı |
| `[başvurucu adres]` | Başvurucu Adres |
| `[başvurucu vekili]` | Başvurucu Vekili |
| `[başvurucu vekil telefon]` | Başvurucu Vekili Telefon |
| `[başvurucu telefon]` | Başvurucu Telefon |
| `[başvurucu eposta]` | Başvurucu E-Posta |
| `[başvurucu tc kimlik no]` | Başvurucu T.C. Kimlik No |
| `[başvurucu vergi no]` | Başvurucu Vergi No (kurum ise) |
| `[dosya türü]` | Dosya Türü |
| `[uyuşmazlık konusu]` | Arabuluculuk Konusu Uyuşmazlık |
| `[uyuşmazlık türü]` | Uyuşmazlık Türü |
| `[talep]` | Talep |
| `[başlangıç tarihi]` | Süreç Başlangıç Tarihi |
| `[bitiş tarihi]` | Süreç Bitiş Tarihi |
| `[düzenleme yeri]` | Tutanak Düzenleme Yeri |
| `[düzenleme tarihi]` | Tutanak Düzenleme Tarihi |
| `[sonuç]` | Sonuç (Anlaşma / Anlaşmama vb.) |
| `[görüşme şekli]` | Görüşme Şekli |
| `[görüşme tarihi]` | Görüşme Tarihi |
| `[görüşme saati]` | Görüşme Saati |
| `[görüşme adresi]` | Görüşme Adresi |
| `[arabuluculuk bürosu]` | Arabuluculuk Bürosu (şehir/ad) |

> Not: `[daire bilgisi]` (Harcama Pusulası alanı) `FIELD_SYNONYMS` içinde bracket
> eş anlamlısı olarak tanımlı DEĞİL — sadece kutucuk olarak var. İsterseniz
> bunu da ekleyebiliriz.

---

## 2) Karşı taraf (değişken sayıda taraf) — TEK TEK alanlar

Belirli bir tarafın belirli bir alanını tek başına yazdırmak isterseniz, format:
**`[karşı taraf N <alt alan>]`** ya da **`[diğer taraf N <alt alan>]`** — N, 1'den
başlar (1. karşı taraf = respondents listesindeki 1. kişi), en fazla 10 taraf
desteklenir (`MAX_RESP=10`).

| Alt alan yazımı | Karşılığı |
|---|---|
| `adı` / `adı soyadı` / `unvanı` | Adı Soyadı / Unvanı |
| `adres` | Adres |
| `vekili` / `vekil` | Vekili |
| `tc` / `tc kimlik no` | T.C. Kimlik No |
| `vergi no` | Vergi No |
| `telefon` / `cep tel` | Telefon |
| `eposta` / `email` | E-posta |

**Örnekler:** `[karşı taraf 1 adı]`, `[karşı taraf 2 tc]`, `[diğer taraf 1 adres]`

⚠️ **Dikkat:** Bu tek-tek yazım şekli SABİT sayıda taraf varsayar — şablonda kaç
"karşı taraf N" bloğu yazarsanız, dosyada en fazla o kadar taraf görünür (fazlası
sessizce atlanır). **Değişken sayıda taraf olabilecek belgelerde (çoğu durumda
öyledir) bunun yerine aşağıdaki §3'teki `[karşı taraf bilgileri bloğu]` ve
`[imza bloğu]` hesaplanan alanlarını kullanmanızı öneririm** — onlar taraf
sayısına göre otomatik büyür/küçülür, veri kaybı riski yoktur.

---

## 3) Hesaplanan (otomatik) alanlar — en önemlileri

Bunlar tek bir değer değil, kutucuklardaki verilerden **kod tarafından hesaplanıp
üretilen** metin bloklarıdır.

| Köşeli parantez | Ne üretir |
|---|---|
| `[bugün]` / `[tarih]` / `[bugünün tarihi]` / `[günün tarihi]` | Bugünün tarihi (gg/aa/yyyy) |
| `[tüm taraflar]` | Tüm karşı tarafların adları, Türkçe liste formatında ("A, B ve C") |
| `[taraf sayısı]` | Toplam taraf sayısı, rakam + yazıyla (örn. "3 (üç)") |
| **`[karşı taraf bilgileri bloğu]`** | **KARŞI TARAF BİLGİLERİ bölümünün tamamı** — kaç taraf varsa o kadar "Diğer Taraf N" bloğu, adı/TC-vergi/adres/vekil/telefon/e-posta satırlarıyla birlikte, alt alta. **Değişken sayıda taraf için doğru yol budur.** |
| **`[imza bloğu]`** | **İMZALAR bölümünün tamamı** — başvurucu + tüm karşı taraflar + arabulucu, her biri "(e-imza)" etiketiyle, kaç taraf varsa o kadar satır. **Değişken sayıda taraf için doğru yol budur.** |
| `[görüşme cümlesi]` | Toplantının nasıl/ne zaman/kimlerle yapıldığını anlatan otomatik cümle |
| `[talep anlatımı]` | "Başvurucu ... ile ... arasında ... hususunda talebi olduğunu beyan etmiştir." cümlesi |
| `[final hukuki paragraf]` | Sonuca (anlaşma/anlaşmama) göre değişen kapanış hukuki paragrafı |
| `[başvurucu kimlik etiketi]` | Kurum ise "Vergi No", kişi ise "TC Kimlik No" yazar (etiket metni) |
| `[başvurucu kimlik no]` | Kurum ise vergi no, kişi ise TC kimlik no değerini yazar |
| `[başvurucu adı etiketi]` | Kurum ise "Adı Soyadı / Unvanı", kişi ise "Adı Soyadı" yazar |

> Davet mektubu şablonuna özel ek hesaplanan alanlar da var (`[dosya türüne göre
> başlık]`, `[muhatap adı unvanı]`, `[telekonferans/yüz yüze]` vb.) — bunlar
> `anlasma_son_tutanagi.udf` / `anlasma_belgesi.udf` için muhtemelen gerekmez,
> istersen ayrıca listeleyebilirim.

---

## Pratik öneri

`anlasma_son_tutanagi.udf` ve `anlasma_belgesi.udf`'yi elle düzenlerken:

1. Şablondaki sabit örnek metni (örn. "ARABULUCU: Ahmet Yılmaz") ilgili
   bracket'la değiştirin: "ARABULUCU: `[arabulucu adı]`".
2. "KARŞI TARAF BİLGİLERİ" başlığının altındaki tüm örnek taraf blok(lar)ını
   **tek bir** `[karşı taraf bilgileri bloğu]` ile değiştirin (başlık satırı
   kalsın, altındaki içerik tamamen bu tek bracket olsun).
3. "İMZALAR" başlığının altındaki tüm örnek imza satırlarını da **tek bir**
   `[imza bloğu]` ile değiştirin.
4. Değiştirdikten sonra dosyayı yükleyip uygulamanın "tanınan/tanınmayan alanlar"
   önizlemesini mutlaka kontrol edin — yazım hatası varsa orada görünür.

Sorularınız olursa (özellikle §2 ile §3 arasında hangisini seçeceğiniz konusunda)
belgenin ilgili kısmını paylaşırsanız birlikte netleştirebiliriz.
