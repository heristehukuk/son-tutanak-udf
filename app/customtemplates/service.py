
import json
import html as _html
from pathlib import Path
from uuid import uuid4
from app.database_layer import repos
from app.auth.service import now
from app.documents.engine import scan_custom_template
from app.storage import storage

MAX_NAME_LEN = 120

# Şablon canlı önizlemesi için sabit örnek (mock) veri seti. Kasıtlı olarak
# hem gerçek kişi hem tüzel kişi karşı taraf içerir - kurumsal unvanların
# bracket şablonlarında doğru yerleştiğini de aynı önizlemede test etmek için
# (bkz. bellek notu: "silent drops of corporate party names").
PREVIEW_MOCK_VALUES = {
    'basvuruNo': '2026/12345', 'dosyaNo': '2026/54',
    'arabulucuAdi': 'Ayşe Yılmaz', 'arabulucuTc': '12345678901',
    'arabulucuSicil': '12345', 'arabulucuAdres': 'Kızılay Mah. Atatürk Bulvarı No:10 Çankaya/Ankara',
    'arabulucuTelefon': '0532 000 00 00', 'arabulucuEposta': 'ayse.yilmaz@example.com',
    'basvurucuTarafTuru': 'Gerçek Kişi', 'basvurucuVergiNo': '',
    'basvurucuTcKimlik': '98765432109', 'basvurucuAdiSoyadi': 'Mehmet Demir',
    'basvurucuAdres': 'Cumhuriyet Mah. İnönü Cad. No:5 Çankaya/Ankara',
    'basvurucuVekili': 'Av. Zeynep Kaya', 'basvurucuVekilTelefon': '0533 111 11 11',
    'basvurucuTelefon': '0533 222 22 22', 'basvurucuEposta': 'mehmet.demir@example.com',
    'dosyaTuru': 'İş Hukuku', 'uyusmazlik': 'İşçilik Alacakları',
    'uyusmazlikTuru': 'İşçi-İşveren Uyuşmazlığı', 'talep': 'Kıdem ve ihbar tazminatı talebi',
    'baslangicTarihi': '01/09/2026', 'bitisTarihi': '15/09/2026',
    'duzenlemeYeri': 'Ankara Arabuluculuk Bürosu', 'duzenlemeTarihi': '15/09/2026',
    'sonuc': 'Anlaşma', 'gorusmeSekli': 'Yüz Yüze', 'gorusmeTarihi': '10/09/2026',
    'gorusmeSaati': '14:00', 'gorusmeAdresi': 'Kızılay Mah. Atatürk Bulvarı No:10 Çankaya/Ankara',
    'arabuluculukBurosu': 'ANKARA ARABULUCULUK BÜROSU',
    '_userIban': 'TR00 0000 0000 0000 0000 0000 00',
}
PREVIEW_MOCK_RESPONDENTS = [
    {'type': 'Gerçek Kişi', 'tc': '11122233344', 'tax': '', 'name': 'Ali Kaya',
     'address': 'Bahçelievler Mah. No:3 Çankaya/Ankara', 'proxy': 'Av. Canan Öztürk',
     'phone': '0534 333 33 33', 'email': 'ali.kaya@example.com'},
    {'type': 'Tüzel Kişi', 'tc': '', 'tax': '1234567890', 'name': 'ABC Lojistik A.Ş.',
     'address': 'Organize Sanayi Bölgesi No:12 Sincan/Ankara', 'proxy': 'Av. Burak Şahin',
     'phone': '0312 444 44 44', 'email': 'info@abclojistik.example.com'},
]

def render_preview_html(data: bytes) -> str:
    """Bir UDF şablon dosyasının (bracket'lı) CDATA metnini örnek verilerle
    doldurup, tanınan alanları yeşil, tanınmayan ifadeleri kırmızı vurgulu
    olarak gösteren güvenli (escape edilmiş) bir HTML parçası döner."""
    from app.documents.engine import (
        read_udf, udf_plain, fill_custom_template_preview,
        PREVIEW_OK_OPEN, PREVIEW_OK_CLOSE, PREVIEW_WARN_OPEN, PREVIEW_WARN_CLOSE,
    )
    _, raw_text, _files = read_udf(data)
    marked = fill_custom_template_preview(raw_text, PREVIEW_MOCK_VALUES, PREVIEW_MOCK_RESPONDENTS)
    plain = udf_plain(marked)
    esc = _html.escape(plain)
    esc = esc.replace(PREVIEW_OK_OPEN, '<mark class="fill-ok">').replace(PREVIEW_OK_CLOSE, '</mark>')
    esc = esc.replace(PREVIEW_WARN_OPEN, '<mark class="fill-warn">').replace(PREVIEW_WARN_CLOSE, '</mark>')
    return esc.replace('\n', '<br>')

def create_template(owner_id, name, is_shared, data, doc_kind='diger'):
    """UDF şablonunu tarar (köşeli parantezleri çözer), depoya kaydeder, DB satırı oluşturur.
    Dönüş: (template_id, recognized, unrecognized)"""
    from app.documents.engine import read_udf
    _, old_text, _ = read_udf(data)
    recognized, unrecognized = scan_custom_template(old_text)
    tid = str(uuid4())
    key = f"templates/{tid}.udf"
    storage.save(key, data)
    clean_name = (name or "Adsız Şablon").strip()[:MAX_NAME_LEN] or "Adsız Şablon"
    repos.templates.create({
        "id":tid,"owner_id":owner_id,"name":clean_name,"is_shared":1 if is_shared else 0,
        "stored_path":key,"doc_kind":doc_kind or "diger","recognized_json":json.dumps(recognized,ensure_ascii=False),
        "unrecognized_json":json.dumps(unrecognized,ensure_ascii=False),"created_at":now().isoformat(),
    })
    return tid, recognized, unrecognized

def list_visible_templates(user_id):
    """Kullanıcının kendi şablonları + paylaşılan (is_shared) tüm şablonlar."""
    return repos.templates.list_visible(user_id)

def list_all_templates():
    """Admin için: sistemdeki TÜM özel şablonlar (sahibiyle birlikte)."""
    return repos.templates.list_all()

def get_template(template_id):
    return repos.templates.get(template_id)

def get_template_bytes(row):
    return storage.read(row["stored_path"])

def can_use_template(row, user):
    """Kullanıcı bu şablonu şablon seçiminde kullanabilir mi? (kendisininki, paylaşılan, ya da admin)"""
    if not row: return False
    if row["owner_id"] == user["id"]: return True
    if row["is_shared"]: return True
    if user["is_super_admin"]: return True
    return False

def delete_template(template_id, user):
    row = get_template(template_id)
    if not row: return False
    if row["owner_id"] != user["id"] and not user["is_super_admin"]:
        return False
    try:
        storage.delete(row["stored_path"])
    except Exception:
        pass
    repos.templates.delete(template_id)
    return True
