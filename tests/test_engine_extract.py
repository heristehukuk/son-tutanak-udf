# -*- coding: utf-8 -*-
"""
app/documents/engine.py içindeki UDF/OCR bilgi çıkarma (extraction) motoru için
regresyon testleri.

Çalıştırma:
    python -m unittest tests/test_engine_extract.py -v
    (veya pytest kuruluysa: pytest tests/test_engine_extract.py)

ÖNEMLİ: Buradaki örnek belgeler tamamen KURGUSALDIR (uydurma isim/TC/adres).
Gerçek bir kullanıcı belgesi bu dosyaya asla eklenmemelidir (KVKK/gizlilik).

Bu dosya, 2026-09 tarihli bir inceleme sırasında gerçek bir başvuru formunda
tespit edilip düzeltilen üç somut hatayı regresyona karşı sabitler:
  1) Arabulucu bölümü belgede yoksa, arabulucuTc/Sicil/Adres alanlarına
     karşı tarafın (veya başka bir bölümün) verisi sızmamalı.
  2) Boş bırakılmış bir etiket (ör. "Vekili :") kendisinden sonraki
     satırdaki/bölüm başlığındaki metni değer olarak yakalamamalı.
  3) Aynı satırda birden fazla alan varsa (ör. "Adres : . Cep Tel : ..."),
     adres alanına sonraki alanın değeri karışmamalı.
Ayrıca section() yardımcı fonksiyonunun "bölüm bulunamadıysa boş döner"
davranışını ve "ARABULUCU BİLGİLERİ" bölümü GERÇEKTEN var olduğunda alanların
hâlâ doğru okunduğunu (olumlu / happy-path senaryo) doğrular.
"""
import unittest

from app.documents.engine import extract, section, party_values


class SectionHelperTests(unittest.TestCase):
    def test_section_returns_empty_when_start_term_missing(self):
        text = "BAŞKA BİR BAŞLIK\nAdı Soyadı : Test Kişi\n"
        self.assertEqual(section(text, ["ARABULUCU BİLGİLERİ"], ["SONRAKI BAŞLIK"]), "")

    def test_section_finds_bounded_region(self):
        text = "ÖNCE\nARABULUCU BİLGİLERİ\nAdı Soyadı : Ayşe Yılmaz\nBAŞVURU SAHİBİ BİLGİLERİ\nSONRA"
        seg = section(text, ["ARABULUCU BİLGİLERİ"], ["BAŞVURU SAHİBİ BİLGİLERİ"])
        self.assertIn("Ayşe Yılmaz", seg)
        self.assertNotIn("SONRA", seg)


class ArabulucuBolumuYokTests(unittest.TestCase):
    """Regresyon: 'ARABULUCU BİLGİLERİ' başlığı olmayan bir başvuru formunda,
    arabulucuTc/Sicil/Adres alanlarına başka bir bölümden veri sızmamalı."""

    SAMPLE = """
T.C. ANKARA ARABULUCULUK BÜROSU
ARABULUCULUK BAŞVURU FORMU
BAŞVURU NUMARASI : 2026/99999
DOSYA TÜRÜ : Ticari Dava Şartı Arabuluculuk Başvuru Dosyası
BAŞVURU SAHİBİ BİLGİLERİ
Unvanı : Örnek Sigorta Anonim Şirketi
Adres : . Cep Tel : 05001234567
Vekili : Av. Test Vekil
Telefon Numarası : 05001234567
KARŞI TARAF BİLGİLERİ
TC Kimlik No : 11111111111
Adı Soyadı : Deneme Kişi
Adres : Örnek Mahalle Örnek Cadde No:1 Çankaya/Ankara
Vekili :
BAŞVURU BİLGİLERİ
Dava Türü : [Örnek Dava Türü]
"""

    def test_arabulucu_alanlari_bos_kalmali(self):
        values, respondents, notices = extract(self.SAMPLE)
        self.assertEqual(values["arabulucuTc"], "", "Arabulucu bölümü yokken arabulucuTc dolu olmamalı")
        self.assertEqual(values["arabulucuSicil"], "")
        self.assertEqual(values["arabulucuAdres"], "")
        # NOT: Arabulucu bilgileri normalde belgede bulunmaz (profilden gelir),
        # bu yüzden bunun için artık BİLEREK bir uyarı üretilmiyor - bkz. engine.py.
        self.assertFalse(
            any("Arabulucu Bilgileri" in n for n in notices),
            "Arabulucu bölümü için artık uyarı üretilmemeli (beklenen/normal durum)",
        )

    def test_bos_vekili_sonraki_basligi_yakalamamali(self):
        values, respondents, notices = extract(self.SAMPLE)
        self.assertEqual(respondents[0]["proxy"], "", "Boş 'Vekili :' alanı bir sonraki başlığı yakalamamalı")

    def test_adres_alanina_telefon_karismamali(self):
        values, respondents, notices = extract(self.SAMPLE)
        self.assertNotIn("Cep Tel", values["basvurucuAdres"])
        self.assertNotIn("0500", values["basvurucuAdres"])

    def test_karsi_taraf_dogru_okunmali(self):
        values, respondents, notices = extract(self.SAMPLE)
        self.assertEqual(len(respondents), 1)
        self.assertEqual(respondents[0]["tc"], "11111111111")
        self.assertEqual(respondents[0]["name"], "Deneme Kişi")


class MaxRespTests(unittest.TestCase):
    """Regresyon: MAX_RESP sınırı aşıldığında artık sessizce kesmek yerine
    kullanıcıya bir uyarı (notice) döner."""

    def _build_sample_with_many_respondents(self, count):
        lines = ["KARŞI TARAF BİLGİLERİ"]
        for i in range(count):
            lines.append(f"Adı Soyadı : Taraf {i}")
            lines.append(f"TC Kimlik No : {10000000000 + i}")
            lines.append(f"Adres : Örnek Adres {i}")
        lines.append("Arabuluculuk Konusu Uyuşmazlık")
        return "\n".join(lines)

    def test_max_resp_asilinca_uyari_uretilir(self):
        from app.documents.engine import MAX_RESP

        text = self._build_sample_with_many_respondents(MAX_RESP + 3)
        values, respondents, notices = extract(text)
        self.assertEqual(len(respondents), MAX_RESP)
        self.assertTrue(any(str(MAX_RESP) in n and "karşı taraf" in n for n in notices))


class ArabulucuBolumuVarTests(unittest.TestCase):
    """Olumlu senaryo: 'ARABULUCU BİLGİLERİ' bölümü GERÇEKTEN varsa, alanlar
    hâlâ doğru şekilde (ve yalnızca o bölümden) okunmalı."""

    SAMPLE = """
ARABULUCU BİLGİLERİ
Adı Soyadı : Deneme Arabulucu
TC Kimlik No : 22222222222
Sicil No : 12345
Adresi : Örnek Büro Adresi No:5 Çankaya/Ankara
BAŞVURU SAHİBİ BİLGİLERİ
Adı Soyadı : Test Başvurucu
TC Kimlik No : 33333333333
Adres : Örnek Adres 2
KARŞI TARAF BİLGİLERİ
Adı Soyadı : Test Karşı Taraf
TC Kimlik No : 44444444444
Adres : Örnek Adres 3
"""

    def test_arabulucu_dogru_bolumden_okunmali(self):
        values, respondents, notices = extract(self.SAMPLE)
        self.assertEqual(values["arabulucuTc"], "22222222222")
        self.assertNotEqual(values["arabulucuTc"], "33333333333")
        self.assertNotEqual(values["arabulucuTc"], "44444444444")
        self.assertFalse(any("Arabulucu Bilgileri" in n for n in notices))


class PartyValuesTests(unittest.TestCase):
    def test_bos_alan_sonraki_satiri_yakalamaz(self):
        seg = "Adı Soyadı : Test Kişi\nVekili :\nBAŞKA BAŞLIK\nAdres : Bir Adres\n"
        pv = party_values(seg)
        self.assertEqual(pv["proxy"], "")

    def test_adres_ayni_satirdaki_telefonu_kesmeli(self):
        seg = "Adı Soyadı : Test Kişi\nAdres : . Cep Tel : 05001112233\n"
        pv = party_values(seg)
        self.assertNotIn("Cep Tel", pv["address"])

    def test_telefon_normalize_edilir(self):
        seg = "Adı Soyadı : Test Kişi\nCep Tel : 0505 446 21 24\n"
        pv = party_values(seg)
        self.assertEqual(pv["phone"], "05054462124")


class MergeStateTests(unittest.TestCase):
    """Regresyon: karşı taraf birleştirmesi artık önce TC/Vergi No ile,
    yalnızca o yoksa isimle eşleştiriyor (yazım farklarına karşı daha güvenilir)."""

    def test_tc_ile_eslesen_taraf_isim_farkli_olsa_bile_birlesir(self):
        from app.documents.engine import merge_state, RESP_FIELDS

        respondents = [{f: "" for f in RESP_FIELDS}]
        respondents[0].update({"name": "Ahmet Yilmaz", "tc": "12345678901"})
        new_resp = [{"name": "Ahmet YILMAZ.", "tc": "12345678901", "address": "Yeni Adres"}]

        values, merged, dropped = merge_state({}, respondents, set(), set(), {}, new_resp)
        self.assertEqual(len(merged), 1, "Aynı TC'ye sahip taraf mükerrer eklenmemeli")
        self.assertEqual(merged[0]["address"], "Yeni Adres")


class KurumKarsiTarafTests(unittest.TestCase):
    """Regresyon: 2026-09 tarihli bir incelemede, birden fazla karşı tarafın
    (biri kurum, biri kişi) '-Kurum için' / '-Kişi İçin' alt başlıklarıyla
    ayrıldığı gerçek bir formda, kurum bloğu ('Kurum Adı' etiketiyle) tamamen
    sessizce atlanıyordu (yalnızca 'Adı Soyadı' etiketine göre bölünüyordu)."""

    SAMPLE = """
BAŞVURU SAHİBİ BİLGİLERİ
-Kişi İçin
Adı Soyadı : Örnek Başvurucu
TC Kimlik No : 12345678901
Adres ve Cep(Zorunlu) : Örnek Mahalle No:1 Çankaya/Ankara
Cep Telefonu(Zorunlu) : 0532 111 2233

KARŞI TARAF BİLGİLERİ
-Kurum için
Kurum Adı : Örnek İnşaat Ticaret A.Ş.
Vergi/Mersis/Detsis No : 1234567890
Adres ve Cep(Zorunlu) : Örnek Cadde No:2 Çankaya/Ankara
İletişim (Cep-Zorunlu) : 05321234567
-Kişi İçin
Adı Soyadı : Örnek Karşı Taraf
TC Kimlik No : 98765432109
Adres ve Cep(Zorunlu) : Örnek Sokak No:3 Çankaya/Ankara

BAŞVURU BİLGİLERİ
Dosya Türü :
Uyuşmazlık Türü : Örnek uyuşmazlık açıklaması metni.
"""

    def test_kurum_karsi_taraf_atlanmamali(self):
        values, respondents, notices = extract(self.SAMPLE)
        self.assertEqual(len(respondents), 2, "Kurum ve kişi karşı taraflar birlikte tespit edilmeli")

    def test_kurum_bloğu_dogru_alanlarla_okunmali(self):
        values, respondents, notices = extract(self.SAMPLE)
        kurum = next(r for r in respondents if r["name"].startswith("Örnek İnşaat"))
        self.assertEqual(kurum["type"], "kurum")
        self.assertEqual(kurum["tax"], "1234567890")
        self.assertIn("Örnek Cadde", kurum["address"])
        self.assertEqual(kurum["phone"], "05321234567")

    def test_kisi_blogu_dogru_alanlarla_okunmali(self):
        values, respondents, notices = extract(self.SAMPLE)
        kisi = next(r for r in respondents if r["name"].startswith("Örnek Karşı"))
        self.assertEqual(kisi["type"], "kisi")
        self.assertEqual(kisi["tc"], "98765432109")

    def test_basvurucu_birlesik_adres_cep_etiketi_okunmali(self):
        values, respondents, notices = extract(self.SAMPLE)
        self.assertIn("Örnek Mahalle", values["basvurucuAdres"])
        self.assertEqual(values["basvurucuTelefon"], "05321112233")

    def test_bos_dosya_turu_sonraki_alani_calmamali(self):
        """Regresyon: 'Dosya Türü :' boş bırakıldığında, eski PATTERNS
        sözlüğündeki '\\s*' regex'i bir sonraki satırdaki 'Uyuşmazlık Türü'
        değerinin tamamını 'Dosya Türü' alanına yanlışlıkla yazıyordu."""
        values, respondents, notices = extract(self.SAMPLE)
        self.assertNotIn("Uyuşmazlık Türü", values.get("dosyaTuru", ""))
        self.assertEqual(values["uyusmazlikTuru"], "Örnek uyuşmazlık açıklaması metni.")


class LabelBleedTests(unittest.TestCase):
    """first() içindeki _LABEL_BLEED_RE korumasının genel davranışını test eder."""

    def test_bilinen_etiketle_baslayan_deger_reddedilir(self):
        from app.documents.engine import first

        text = "Talep :\nUyuşmazlık Türü : Gerçek değer burada.\n"
        # 'Talep' boş olduğu için first(), 'Uyuşmazlık Türü :' ile başlayan bir
        # sonraki satırı YANLIŞLIKLA yakalarsa bile bunu reddetmeli.
        v = first([r"Talep\s*[:：]\s*([^\n<]{2,200})"], text)
        self.assertEqual(v, "", "Bilinen bir etiketle başlayan sızıntı değeri kabul edilmemeli")

    def test_gecerli_adres_no_ile_yanlis_reddedilmez(self):
        """Yanlış pozitif kontrolü: 'No:5' gibi adres içeriği, genel bir
        'Büyük harf + :' sezgiseli kullanılsaydı yanlışlıkla etiket sanılabilirdi."""
        from app.documents.engine import party_values

        seg = "Adı Soyadı : Test Kişi\nAdres : Çankaya Mahallesi Atatürk Bulvarı No:5 Ankara\n"
        pv = party_values(seg)
        self.assertIn("No:5", pv["address"])


class VknChecksumTests(unittest.TestCase):
    """is_valid_vkn() algoritmasının kendi içinde tutarlı çalıştığını doğrular
    (bir değişiklik algoritmayı yanlışlıkla bozarsa regresyonu yakalar)."""

    def test_bozuk_vkn_reddedilir(self):
        from app.documents.engine import is_valid_vkn

        self.assertFalse(is_valid_vkn("123456789"))  # 9 hane, eksik
        self.assertFalse(is_valid_vkn("12345678901"))  # 11 hane, fazla
        self.assertFalse(is_valid_vkn("1111111111"))  # kontrol basamağı tutmuyor

    def test_kontrol_basamagi_tutan_vkn_kabul_edilir(self):
        from app.documents.engine import is_valid_vkn

        # Algoritmanın kendisiyle üretilmiş, kontrol basamağı doğru bir örnek.
        base = [1, 2, 3, 4, 5, 6, 7, 8, 9]
        total = 0
        for i in range(9):
            tmp = (base[i] + 9 - i) % 10
            v = 9 if tmp == 0 else (tmp * (2 ** (9 - i))) % 9
            if v == 0 and tmp != 0:
                v = 9
            total += v
        check = (10 - (total % 10)) % 10
        vkn = "".join(str(d) for d in base) + str(check)
        self.assertTrue(is_valid_vkn(vkn))


class SubheaderTypeTests(unittest.TestCase):
    """Taraf türü artık öncelikle '-Kişi İçin' / '-Kurum için' alt başlığından
    belirleniyor; vergi no regex'i etiket varyasyonu nedeniyle eşleşmese bile
    kurum yanlışlıkla 'kişi' sayılmamalı."""

    def test_vergi_no_etiketi_taninmasa_bile_kurum_dogru_tespit_edilir(self):
        from app.documents.engine import party_values

        seg = "-Kurum için\nKurum Adı : Tanınmayan Etiketli Şirket\nBilinmeyen Vergi Etiketi : 1234567890\n"
        pv = party_values(seg)
        self.assertEqual(pv["type"], "kurum")


if __name__ == "__main__":
    unittest.main()
