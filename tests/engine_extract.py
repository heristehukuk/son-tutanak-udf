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
        self.assertTrue(
            any("Arabulucu Bilgileri" in n for n in notices),
            "Arabulucu bölümü bulunamadığına dair bir uyarı üretilmeli",
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


if __name__ == "__main__":
    unittest.main()
