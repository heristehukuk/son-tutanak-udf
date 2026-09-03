import os
import io,re,zipfile,difflib
from PIL import Image
import pytesseract
pytesseract.pytesseract.tesseract_cmd = os.environ.get('TESSERACT_CMD', '/usr/bin/tesseract')
from pypdf import PdfReader
from pdf2image import convert_from_bytes
from pathlib import Path
from html import escape
from datetime import date

FIELDS=[
('basvuruNo','Başvuru No'),('dosyaNo','Dosya No'),
('arabulucuAdi','Arabulucu Adı'),('arabulucuTc','Arabulucu T.C. Kimlik No'),
('arabulucuSicil','Arabulucu Sicil No'),('arabulucuAdres','Arabulucu Adres'),('arabulucuTelefon','Arabulucu Telefon'),('arabulucuEposta','Arabulucu E-posta'),
('basvurucuTarafTuru','Başvurucu Taraf Türü'),('basvurucuVergiNo','Başvurucu Vergi No'),('basvurucuTcKimlik','Başvurucu T.C. Kimlik No'),('basvurucuAdiSoyadi','Başvurucu Adı Soyadı'),
('basvurucuAdres','Başvurucu Adres'),('basvurucuVekili','Başvurucu Vekili'),('basvurucuVekilTelefon','Başvurucu Vekili Telefon'),
('basvurucuTelefon','Başvurucu Telefon'),('basvurucuEposta','Başvurucu E-Posta'),
('dosyaTuru','Dosya Türü'),('uyusmazlik','Arabuluculuk Konusu Uyuşmazlık'),('uyusmazlikTuru','Uyuşmazlık Türü'),('talep','Talep'),
('baslangicTarihi','Süreç Başlangıç Tarihi'),('bitisTarihi','Süreç Bitiş Tarihi'),
('duzenlemeYeri','Tutanak Düzenleme Yeri'),('duzenlemeTarihi','Tutanak Düzenleme Tarihi'),
('daireBilgisi','Dairesi (Harcama Pusulası için, örn. ANKARA CUMHURİYET BAŞSAVCILIĞI)'),
('sonuc','Sonuç'),('gorusmeSekli','Görüşme Şekli'),('gorusmeTarihi','Görüşme Tarihi'),('gorusmeSaati','Görüşme Saati'),('gorusmeAdresi','Görüşme Adresi'),
('arabuluculukBurosu','Arabuluculuk Bürosu (şehir/ad)')]
LABELS=dict(FIELDS)
LABELS['_userIban']='Arabulucu IBAN (kullanıcı profilinden, otomatik)'
RESP_FIELDS=['type','tc','tax','name','address','proxy','phone','email']
RESP_LABELS={'type':'Taraf Türü','tc':'T.C. Kimlik No','tax':'Vergi No','name':'Adı Soyadı / Unvanı','address':'Adres','proxy':'Vekili','phone':'Telefon','email':'E-posta'}
MAX_RESP=10

# ---------------------------------------------------------------------------
# ÖZEL ("Kendi Şablonum") KÖŞELİ PARANTEZ SİSTEMİ
# Kullanıcı kendi .udf şablonunu yükler; içindeki [dosya no], [başvurucu adı],
# [karşı taraf 1 adı] gibi köşeli parantezli ifadeler otomatik olarak mevcut
# kutucuklarla eşleştirilir. Tanınmayan ifadeler boş bırakılır.
# ---------------------------------------------------------------------------
BRACKET_RE = re.compile(r'\[([^\[\]]{1,80})\]')

_TR_ASCII_MAP = str.maketrans({'ç':'c','ğ':'g','ı':'i','ö':'o','ş':'s','ü':'u','İ':'i','I':'i'})

def normalize_bracket_text(s):
    s = (s or '').strip().lower().translate(_TR_ASCII_MAP)
    return re.sub(r'[^a-z0-9]+', '', s)

# Şablon alanı -> normalize edilmiş eş anlamlı ifadeler
FIELD_SYNONYMS = {
    'basvuruno':'basvuruNo','basvurunumarasi':'basvuruNo',
    'dosyano':'dosyaNo','dosyanumarasi':'dosyaNo',
    'arabulucuadi':'arabulucuAdi','arabulucuadisoyadi':'arabulucuAdi','arabulucu':'arabulucuAdi','arbadi':'arabulucuAdi','arabulucuad':'arabulucuAdi',
    'arabulucutc':'arabulucuTc','arabulucutckimlikno':'arabulucuTc','arabulucutckimliknumarasi':'arabulucuTc','arbtc':'arabulucuTc','arbutc':'arabulucuTc',
    'arabulucusicil':'arabulucuSicil','arabulucusicilno':'arabulucuSicil','arabulucusicilnumarasi':'arabulucuSicil','arbsicil':'arabulucuSicil','arbsicilno':'arabulucuSicil','arbsicilnumarasi':'arabulucuSicil',
    'arabulucuadres':'arabulucuAdres','arabulucubüroadresi':'arabulucuAdres','arabulucuburoadresi':'arabulucuAdres',
    'arbtel':'arabulucuTelefon','arabulucutelefon':'arabulucuTelefon','arabulucutelefonno':'arabulucuTelefon','arabulucutelefonnumarasi':'arabulucuTelefon','arabulucuceptelefonu':'arabulucuTelefon','arabulucuceptel':'arabulucuTelefon','arbtelefon':'arabulucuTelefon','arbtelefonno':'arabulucuTelefon','arbtelefonnumarasi':'arabulucuTelefon','arbceptelefonu':'arabulucuTelefon','arbceptel':'arabulucuTelefon',
    'arbeposta':'arabulucuEposta','arabulucueposta':'arabulucuEposta','arabulucuepostaadresi':'arabulucuEposta','arabulucuemail':'arabulucuEposta','arbemail':'arabulucuEposta','arbepostaadresi':'arabulucuEposta',
    'basvurucuadisoyadi':'basvurucuAdiSoyadi','basvurucuadi':'basvurucuAdiSoyadi','basvurucu':'basvurucuAdiSoyadi',
    'basvurucuadres':'basvurucuAdres',
    'basvurucuvekili':'basvurucuVekili','basvurucuvekil':'basvurucuVekili',
    'basvurucuvekiladi':'basvurucuVekili',
    'basvurucuvekiltelefon':'basvurucuVekilTelefon','basvurucuvekilitelefon':'basvurucuVekilTelefon',
    'basvurucutelefon':'basvurucuTelefon','basvurucuceptel':'basvurucuTelefon','basvurucutelefonnumarasi':'basvurucuTelefon',
    'basvurucueposta':'basvurucuEposta','basvurucuepostaadresi':'basvurucuEposta','basvurucuemail':'basvurucuEposta',
    'basvurucutckimlikno':'basvurucuTcKimlik','basvurucutc':'basvurucuTcKimlik','basvurucutckimliknumarasi':'basvurucuTcKimlik',
    'basvurucuvergino':'basvurucuVergiNo','basvurucuverginumarasi':'basvurucuVergiNo',
    'dosyaturu':'dosyaTuru',
    'uyusmazlik':'uyusmazlik','uyusmazlikkonusu':'uyusmazlik','arabuluculukkonusuuyusmazlik':'uyusmazlik',
    'uyusmazlikturu':'uyusmazlikTuru',
    'talep':'talep','talepkonusu':'talep',
    'baslangictarihi':'baslangicTarihi','surecbaslangictarihi':'baslangicTarihi',
    'bitistarihi':'bitisTarihi','surecbitistarihi':'bitisTarihi',
    'duzenlemeyeri':'duzenlemeYeri','tutanagindüzenlendigiyer':'duzenlemeYeri','sontutanagindüzenlendigiyer':'duzenlemeYeri',
    'duzenlemetarihi':'duzenlemeTarihi','tutanagindüzenlendigitarih':'duzenlemeTarihi',
    'sonuc':'sonuc','arabuluculuksonucu':'sonuc',
    'gorusmesekli':'gorusmeSekli',
    'gorusmetarihi':'gorusmeTarihi',
    'gorusmesaati':'gorusmeSaati',
    'gorusmeadresi':'gorusmeAdresi',
    'arabuluculukburosu':'arabuluculukBurosu','arabuluculukburosuadi':'arabuluculukBurosu',
    'iban':'_userIban',
}
FIELD_SYNONYMS = {normalize_bracket_text(k):v for k,v in FIELD_SYNONYMS.items()}

# Karşı taraf alt-alanları (ör. "karşı taraf 1 adı" -> ('resp', 0, 'name'))
RESP_FIELD_SYNONYMS = {
    'adi':'name','adisoyadi':'name','unvani':'name','adisoyadiunvani':'name',
    'adres':'address',
    'vekili':'proxy','vekil':'proxy',
    'tc':'tc','tckimlikno':'tc','tckimliknumarasi':'tc',
    'vergino':'tax','verginumarasi':'tax',
    'telefon':'phone','ceptel':'phone',
    'eposta':'email','email':'email',
}
_TR_ONES=["", "bir", "iki", "üç", "dört", "beş", "altı", "yedi", "sekiz", "dokuz"]
_TR_TENS=["", "on", "yirmi", "otuz", "kırk", "elli", "altmış", "yetmiş", "seksen", "doksan"]

def _tr_three_digit_words(n):
    parts=[]
    yuz,kalan=divmod(n,100)
    if yuz==1: parts.append("yüz")
    elif yuz>1: parts.append(_TR_ONES[yuz]); parts.append("yüz")
    on,bir=divmod(kalan,10)
    if on: parts.append(_TR_TENS[on])
    if bir: parts.append(_TR_ONES[bir])
    return parts

def turkce_sayi_yazi(n):
    """Tamsayıyı Türkçe yazıyla ifade eder. Örn: 3 -> 'üç', 11 -> 'on bir'."""
    if n==0: return "sıfır"
    if n<0: return "eksi "+turkce_sayi_yazi(-n)
    parts=[]
    milyon,n=divmod(n,1_000_000)
    bin_,kalan=divmod(n,1000)
    if milyon:
        parts += (["milyon"] if milyon==1 else _tr_three_digit_words(milyon)+["milyon"])
    if bin_:
        parts += (["bin"] if bin_==1 else _tr_three_digit_words(bin_)+["bin"])
    if kalan: parts += _tr_three_digit_words(kalan)
    return " ".join(parts)

def join_turkish_list(items):
    """['A','B','C'] -> 'A, B ve C' (Türkçe liste biçimi)."""
    items=[i for i in items if i]
    if not items: return ""
    if len(items)==1: return items[0]
    return ", ".join(items[:-1])+" ve "+items[-1]

_TR_WORD_RE = re.compile(r"[A-Za-zÇĞİIıöÖşŞüÜçğ]+")

def turkce_title_case(s):
    """Her kelimenin ilk harfini büyük, geri kalanını küçük yapar (Türkçe İ/I kuralına uygun).
    Python'un yerleşik .title()/.capitalize()'ı Türkçe'de 'iki'->'Iki' gibi hatalar yapar
    (doğrusu 'İki'); bu fonksiyon İ/I ayrımını doğru uygular. Noktalama (A.Ş., Av. gibi
    kısaltmalar) kelime sınırı sayıldığından bozulmaz."""
    if not s: return s
    def cap_word(m):
        w=m.group(0); first=w[0]; rest=w[1:]
        first_cap='İ' if first=='i' else ('I' if first=='ı' else first.upper())
        rest_lower=rest.replace('İ','i').replace('I','ı').lower()
        return first_cap+rest_lower
    return _TR_WORD_RE.sub(cap_word,s)

_RESP_PREFIX_RE = re.compile(r'^(?:karsitaraf|digertaraf)(\d+)(.+)$')

# Kutucuklardan gelmeyen, sistem tarafından otomatik hesaplanan köşeli parantez ifadeleri.
# Örn: [Bugün()], [tüm taraflar], [taraf sayısı].
def _recipient(values):
    r = values.get('_recipient') or {}
    return r if isinstance(r, dict) else {}

def _recipient_value(values, key):
    return str(_recipient(values).get(key) or '').strip()

def _davet_kind(values):
    """Dosya türü metnini kategoriye ayırır. OCR/yazım farkları (Türkçe
    karaktersiz girilmiş olması gibi) yüzünden kategori kaçırılmasın diye
    ASCII'ye çevrilmiş (ş->s, ü->u, ı->i vb.) hâliyle karşılaştırılır."""
    kind_raw = ' '.join(str(values.get(k) or '') for k in ('dosyaTuru','uyusmazlik','uyusmazlikTuru'))
    # NOT: str.lower() Türkçe büyük 'İ' harfini yanlış çevirir (görünmez bir
    # "combining dot" karakteriyle "i̇" yapar, alt metin eşleşmesini bozar).
    # Bu yüzden önce _TR_ASCII_MAP ile çeviriyoruz (İ->i tek karakter), sonra lower().
    kind = kind_raw.strip().translate(_TR_ASCII_MAP).lower()
    if 'ticari' in kind or 'ticaret' in kind:
        return 'ticari'
    if 'tuketici' in kind:
        return 'tuketici'
    if 'isci' in kind or 'is hukuku' in kind or re.search(r'\bis\b', kind):
        return 'isci'
    if 'kira' in kind:
        return '18b_kira'
    if 'ortakligin giderilmesi' in kind or 'ortaklik' in kind:
        return '18b_ortaklik'
    if 'kat mulkiyeti' in kind:
        return '18b_kat'
    if 'komsu' in kind:
        return '18b_komsu'
    return 'diger'

_18B_UYUSMAZLIK_METNI = {
    '18b_kira': 'kira ilişkisinden kaynaklanan',
    '18b_ortaklik': 'taşınır ve taşınmazların paylaştırılmasına ve ortaklığın giderilmesine ilişkin',
    '18b_kat': '634 sayılı Kat Mülkiyeti Kanunundan kaynaklanan',
    '18b_komsu': 'komşu hakkından kaynaklanan',
}

def _davet_dava_sarti(values, respondents):
    kind = _davet_kind(values)
    if kind == 'ticari':
        return '6102 sayılı Türk Ticaret Kanunun 5/A maddesi uyarınca ticari davalardan, konusu bir miktar paranın ödenmesi olan alacak ve tazminat talepleri hakkında dava açılmadan önce arabulucuya başvurulmuş olması dava şartıdır.'
    if kind == 'isci':
        return ('İşçi alacaklarına ait hukuki uyuşmazlığının 6325 sayılı Hukuk Uyuşmazlıklarında Arabuluculuk Kanunu kapsamında tarafların üzerinde serbestçe tasarruf edebileceği iş ve işlemlerden doğan özel hukuk uyuşmazlığı olduğu anlaşılmaktadır.\n\n'
                '7036 sayılı İş Mahkemeleri Kanunun 3 üncü maddesi uyarınca kanuna, bireysel veya toplu iş sözleşmesine dayanan işçi veya işveren alacağı ve tazminatı ile işe iade talebiyle açılan davalarda, arabulucuya başvurulmuş olması dava şartıdır.')
    if kind == 'tuketici':
        return '6502 sayılı Tüketicinin Korunması Hakkında Kanunun 73/A maddesi uyarınca tüketici mahkemelerinde görülen uyuşmazlıklarda dava açılmadan önce arabulucuya başvurulmuş olması dava şartıdır.'
    if kind in _18B_UYUSMAZLIK_METNI:
        return (f'6325 sayılı Hukuk Uyuşmazlıklarında Arabuluculuk Kanununun 18/B maddesi uyarınca '
                f'{_18B_UYUSMAZLIK_METNI[kind]} uyuşmazlıklarda dava açılmadan önce arabulucuya başvurulmuş olması dava şartıdır.')
    return ''

def _davet_ucret_ek(values, respondents):
    kind = _davet_kind(values)
    if kind == 'tuketici':
        return ('Tüketicinin ödemesi gereken arabuluculuk ücreti, Adalet Bakanlığı bütçesinden karşılanır. '
                'Ancak belirtilen hâlde tüketicinin ödeyeceği arabuluculuk ücreti, Arabuluculuk Asgari Ücret '
                'Tarifesinin eki Arabuluculuk Ücret Tarifesinin Birinci Kısmına göre iki saatlik ücret tutarını geçemez.')
    if kind == 'isci':
        return ('İşe iade talebiyle yapılan görüşmelerde tarafların anlaşmaları durumunda, arabulucuya ödenecek '
                'ücretin belirlenmesinde işçiye işe başlatılmaması hâlinde ödenecek tazminat miktarı ile '
                'çalıştırılmadığı süre için ödenecek ücret ve diğer haklarının toplamı, Tarifenin İkinci Kısmı '
                'uyarınca üzerinde anlaşılan miktar olarak kabul edilir.')
    return ''

def _davet_katilim_ek(values, respondents):
    if _davet_kind(values) == 'isci':
        return 'İşverenin yazılı belgeyle yetkilendirdiği çalışanı da görüşmelerde işvereni temsil edebilir ve son tutanağı imzalayabilir.'
    return ''

def _davet_sure(values, respondents):
    if _davet_kind(values) == 'ticari':
        return 'Arabulucu, yapılan başvuruyu görevlendirildiği tarihten itibaren altı hafta içinde sonuçlandırır. Bu süre zorunlu hâllerde arabulucu tarafından en fazla iki hafta uzatılabilir.'
    return 'Arabulucu, yapılan başvuruyu görevlendirildiği tarihten itibaren üç hafta içinde sonuçlandırır. Bu süre zorunlu hâllerde arabulucu tarafından en fazla bir hafta uzatılabilir.'

def _davet_baslik(values, respondents):
    return 'ARABULUCULUK İLK TOPLANTI DAVET MEKTUBU'

def _davet_katilim(values, respondents):
    sekil = str(values.get('gorusmeSekli') or 'Telekonferans').strip().lower()
    tarih = str(values.get('gorusmeTarihi') or '').strip()
    saat = str(values.get('gorusmeSaati') or '').strip()
    telefon = str(values.get('arabulucuTelefon') or '').strip()
    if sekil.startswith('yüz'):
        adres = str(values.get('gorusmeAdresi') or '').strip()
        date_phrase = f'{tarih} tarihinde saat {saat}’de' if tarih and saat else (f'{tarih} tarihinde' if tarih else (f'saat {saat}’de' if saat else ''))
        return (f'Sizlerle yapacağımız ilk toplantı, {date_phrase} {adres} adresinde yüz yüze gerçekleştirilecektir.'
                + _davet_katilimcilar_notu(values, respondents)).replace('  ',' ').strip()
    date_phrase = f'{tarih} tarihinde saat {saat}’de' if tarih and saat else (f'{tarih} tarihinde' if tarih else (f'saat {saat}’de' if saat else ''))
    return (f'Sizlerle yapacağımız ilk toplantı, toplantıya katılımı kolay sağlamak adına telekonferans yöntemiyle {date_phrase} gerçekleşecektir. '
            f'Bunun için toplantı saatinden önce aşağıda yer alan numaradan ({telefon}) benimle iletişime geçmeniz önem arz etmektedir. '
            'Talebiniz halinde yüz yüze toplantıda yapılabilecektir.' + _davet_katilimcilar_notu(values, respondents)).replace('  ',' ').strip()

def _davet_katilimcilar_notu(values, respondents):
    """Birden fazla karşı taraf varsa, toplantı cümlesinin ardına kimlerin
    katılacağını hatırlatan kısa bir bilgi notu eklenir - tek taraf varsa
    (muhatap zaten kim olduğunu bildiği için) hiçbir şey eklenmez."""
    if len(respondents) < 2:
        return ''
    liste = _karsi_taraflar_vekilleri(values, respondents)
    return f' Toplantıya {liste} de davetlidir.' if liste else ''

def _karsi_taraflar_vekilleri(values, respondents):
    """Birden fazla karşı taraf olduğunda hepsini vekilleriyle birlikte
    'X vekili A, Y vekili B ve Z' şeklinde tek bir listede birleştirir."""
    parts = []
    for r in respondents:
        name = str(r.get('name') or '').strip()
        if not name:
            continue
        proxy = str(r.get('proxy') or '').strip()
        parts.append(f'{name} vekili {proxy}' if proxy else name)
    return join_turkish_list(parts)

def _davet_basvurucu_vekil(values, respondents):
    name = str(values.get('basvurucuAdiSoyadi') or '').strip()
    proxy = str(values.get('basvurucuVekili') or '').strip()
    return f'{name} vekili {proxy}' if name and proxy else name

def _davet_uyusmazlik_aciklama(values, respondents):
    applicant = str(values.get('basvurucuAdiSoyadi') or '').strip()
    others = [str(r.get('name') or '').strip() for r in respondents if str(r.get('name') or '').strip()]
    subject = str(values.get('uyusmazlik') or values.get('dosyaTuru') or '').strip()
    if not others:
        return f'{applicant} ile ilgili {subject} konusundaki uyuşmazlığın arabuluculuk yoluyla çözümlenmesi amaçlanmaktadır.'.strip()
    return f'{applicant} ile {join_turkish_list(others)} arasındaki {subject} konusundaki uyuşmazlığın arabuluculuk yoluyla çözümlenmesi amaçlanmaktadır.'.strip()

def _davet_muhatap_baslik(values, respondents):
    """Mektubun üst hitap bloğu. Muhatabın (bu mektubun kime gittiğinin) bir
    vekili varsa 'Sayın Av. X,' hitabı kullanılır; vekili yoksa (ister
    başvurucu ister karşı taraf olsun) mektup doğrudan kendisine, isim +
    açık adres bloğu formatında gider - resmi tebligat mantığına uygun."""
    r = _recipient(values)
    proxy = str(r.get('proxy') or '').strip()
    if proxy:
        # Vekil adı zaten "Av." ile girilmiş olabilir - unvan çift basılmasın.
        proxy_clean = re.sub(r'^(av\.?\s*)+', '', proxy, flags=re.I).strip()
        return f'Sayın Av. {proxy_clean},'
    name = str(r.get('name') or '').strip()
    address = str(r.get('address') or '').strip()
    return f'{name}\n{address}'.strip() if address else name

def _davet_basvuru_cumlesi(values, respondents):
    """Mektubun 'başvuru üzerine...' cümlesi. Muhatap BAŞVURUCUNUN kendisiyse
    (ya da onun vekiliyse) 2. şahısla ('tarafınızca yapmış olduğunuz
    başvurunuz'), muhatap KARŞI TARAF ise 3. şahısla ('X tarafından yapılan
    başvuru') yazılır - kim kime hitap ediyorsa ona göre değişir."""
    buro = str(values.get('arabuluculukBurosu') or '').strip()
    buro_phrase = f'{buro} Arabuluculuk Bürosuna' if buro else 'Arabuluculuk Bürosuna'
    role = str(values.get('_davetRole') or 'karsi_taraf')
    if role == 'basvurucu':
        return f'{buro_phrase} yapmış olduğunuz başvurunuz üzerine'
    applicant = str(values.get('basvurucuAdiSoyadi') or '').strip()
    applicant_proxy = str(values.get('basvurucuVekili') or '').strip()
    who = f'{applicant} adına vekili {applicant_proxy}' if applicant_proxy else applicant
    return f'{who} tarafından {buro_phrase} yapılan başvuru üzerine'

def _tutanak_basvurucu_kimlik_etiketi(values, respondents):
    return 'Vergi No' if str(values.get('basvurucuVergiNo') or '').strip() else 'TC Kimlik No'

def _tutanak_basvurucu_kimlik_no(values, respondents):
    return str(values.get('basvurucuVergiNo') or values.get('basvurucuTcKimlik') or '').strip()

def _tutanak_basvurucu_adi_etiketi(values, respondents):
    return 'Adı Soyadı / Unvanı' if str(values.get('basvurucuVergiNo') or '').strip() else 'Adı Soyadı'

def _tutanak_karsi_taraf_blogu(values, respondents):
    """KARŞI TARAF BİLGİLERİ başlığından sonraki tüm 'Diğer Taraf N' bloklarını
    üretir. Taraf sayısı değişken olduğu için tek bir metin bloğu olarak
    birleştirilip [KARŞI TARAF BİLGİLERİ BLOĞU] köşeli parantezine yerleştirilir;
    update_offsets_exact bu değerin içindeki satır sonlarını otomatik olarak
    ayrı paragraflara böler (bkz. update_offsets_exact)."""
    blocks = []
    for i, p in enumerate(respondents, 1):
        typ = (p.get('type') or 'kisi').lower()
        id_label = 'Vergi No' if typ == 'kurum' else 'TC Kimlik No'
        id_value = p.get('tax', '') if typ == 'kurum' else p.get('tc', '')
        name_label = 'Adı Soyadı / Unvanı' if typ == 'kurum' else 'Adı Soyadı'
        lines = [
            f'Diğer Taraf {i}', '',
            f'{id_label}\t\t: {id_value}',
            f'{name_label}\t\t: {p.get("name","")}',
            f'Adres\t\t: {p.get("address","")}',
            f'Vekili\t\t: {p.get("proxy","")}',
            f'Cep Tel\t\t: {p.get("phone","")}',
        ]
        if p.get('email'):
            lines.append(f'E-posta\t\t: {p.get("email","")}')
        blocks.append('\n'.join(lines))
    return '\n\n'.join(blocks)

def _tutanak_gorusme_cumlesi(values, respondents):
    applicant = {
        'name': values.get('basvurucuAdiSoyadi', ''),
        'proxy': values.get('basvurucuVekili', ''),
        '_arb_name': values.get('arabulucuAdi', ''),
    }
    return build_meeting_sentence(values, applicant, respondents)

def _tutanak_talep_anlatimi(values, respondents):
    name = str(values.get('basvurucuAdiSoyadi') or '').strip()
    proxy = str(values.get('basvurucuVekili') or '').strip()
    talep = str(values.get('talep') or '').strip().strip('"“”')
    if not talep:
        return ''
    others = [str(r.get('name') or '').strip() for r in respondents if str(r.get('name') or '').strip()]
    karsi = join_turkish_list(others) if others else ''
    prefix = f'Başvurucu vekili; Başvurucu {name}' if proxy else f'Başvurucu {name}'
    orta = f' ile {karsi} arasında' if karsi else ''
    return f'{prefix}{orta} {talep} hususunda talebi olduğunu beyan etmiştir.'

def _tutanak_final_hukuki_paragraf(values, respondents):
    return final_legal_paragraph(values)

def _tutanak_imza_blogu(values, respondents):
    """Değişken sayıda taraf içeren İMZALAR bloğunu üretir (bkz. _tutanak_karsi_taraf_blogu
    ile aynı 'satır sonu içeren tek değer' yaklaşımı)."""
    name = str(values.get('basvurucuAdiSoyadi') or '').strip()
    proxy = str(values.get('basvurucuVekili') or '').strip()
    lines = [f'Taraf 1        : {name}' + (f' - Vekili {proxy}' if proxy else '') + '  (e-imza)', '']
    for i, p in enumerate(respondents, start=2):
        nm = str(p.get('name') or '').strip()
        if not nm:
            continue
        pr = str(p.get('proxy') or '').strip()
        lines.append(f'Taraf {i}        : {nm}' + (f' - Vekili {pr}' if pr else '') + '  (e-imza)')
        lines.append('')
    arb_name = str(values.get('arabulucuAdi') or '').strip()
    arb_sicil = str(values.get('arabulucuSicil') or '').strip()
    lines.append(f'Arabulucu      : {arb_name}' + (f' ({arb_sicil})' if arb_sicil else '') + ' (e-imza)')
    return '\n'.join(lines)

COMPUTED_BRACKETS = {
    'bugun': lambda values,respondents: date.today().strftime('%d/%m/%Y'),
    'bugunuuntarihi': lambda values,respondents: date.today().strftime('%d/%m/%Y'),
    'tarih': lambda values,respondents: date.today().strftime('%d/%m/%Y'),
    'gununtarihi': lambda values,respondents: date.today().strftime('%d/%m/%Y'),
    'tumtaraflar': lambda values,respondents: join_turkish_list([(r.get('name') or '').strip() for r in respondents]),
    'tarafsayisi': lambda values,respondents: (lambda t: f"{t} ({turkce_sayi_yazi(t)})")(1+len(respondents)),
    'dosyaturunegorebaslik': _davet_baslik,
    'dosyaturunegoredavasartiparagrafi': _davet_dava_sarti,
    'dosyaturunegoresureparagrafi': _davet_sure,
    'telekonferansyuzyuze': _davet_katilim,
    'telekonferansyuzyuzetoplantiparagrafi': _davet_katilim,
    'basvurucuvekili': _davet_basvurucu_vekil,
    'uyusmazlikkonusununaciklamasi': _davet_uyusmazlik_aciklama,
    'muhatapbaslikblogu': _davet_muhatap_baslik,
    'basvurucumlesi': _davet_basvuru_cumlesi,
    'karsitaraflarvekilleri': _karsi_taraflar_vekilleri,
    'dosyaturunegoreucretekparagrafi': _davet_ucret_ek,
    'dosyaturunegorekatilimekcumlesi': _davet_katilim_ek,
    'muhatapadiunvani': lambda values,respondents: _recipient_value(values,'name'),
    'muhatapadres': lambda values,respondents: _recipient_value(values,'address'),
    'muhatapadresi': lambda values,respondents: _recipient_value(values,'address'),
    'muhatapvekili': lambda values,respondents: _recipient_value(values,'proxy'),
    'muhataptel': lambda values,respondents: _recipient_value(values,'phone'),
    'muhatape posta': lambda values,respondents: _recipient_value(values,'email'),
    'muhatapeposta': lambda values,respondents: _recipient_value(values,'email'),
    'basvurucukimliketiketi': _tutanak_basvurucu_kimlik_etiketi,
    'basvurucukimlikno': _tutanak_basvurucu_kimlik_no,
    'basvurucuadietiketi': _tutanak_basvurucu_adi_etiketi,
    'karsitarafbilgileriblogu': _tutanak_karsi_taraf_blogu,
    'gorusmecumlesi': _tutanak_gorusme_cumlesi,
    'talepanlatimi': _tutanak_talep_anlatimi,
    'finalhukukiparagraf': _tutanak_final_hukuki_paragraf,
    'imzablogu': _tutanak_imza_blogu,
}
COMPUTED_LABELS = {
    'bugun': "Bugünün Tarihi (otomatik doldurulur)", 'tarih': "Bugünün Tarihi (otomatik doldurulur)",
    'tumtaraflar': "Tüm Karşı Tarafların Adları (otomatik, başvurucu hariç)",
    'tarafsayisi': "Toplam Taraf Sayısı (otomatik, rakam + yazıyla)",
    'dosyaturunegorebaslik': "Davet Mektubu Başlığı (dosya türüne göre)",
    'dosyaturunegoredavasartiparagrafi': "Dava şartı paragrafı (dosya türüne göre)",
    'dosyaturunegoresureparagrafi': "Arabuluculuk süresi paragrafı (dosya türüne göre)",
    'telekonferansyuzyuze': "Toplantı yöntemi paragrafı",
    'basvurucuvekili': "Başvurucu ve varsa vekili",
    'uyusmazlikkonusununaciklamasi': "Uyuşmazlık açıklaması",
}

# Kullanıcı şablonlarındaki boşluk, slash ve Türkçe karakter farklarını computed alanlarda da tolere et.
COMPUTED_BRACKETS = {normalize_bracket_text(k): v for k, v in COMPUTED_BRACKETS.items()}
COMPUTED_LABELS = {normalize_bracket_text(k): v for k, v in COMPUTED_LABELS.items()}

def resolve_bracket_token(raw_text):
    """Köşeli parantez içindeki metni ('dosya no', 'karşı taraf 1 adı', 'Bugün()' vb.) çözer.
    Dönüş: ('field', field_key) | ('resp', index, resp_field_key) | ('computed', fn) | None (tanınmadı)"""
    norm = normalize_bracket_text(raw_text)
    if not norm: return None
    if norm in COMPUTED_BRACKETS:
        return ('computed', norm)
    m = _RESP_PREFIX_RE.match(norm)
    if m:
        idx = int(m.group(1)) - 1
        rf = RESP_FIELD_SYNONYMS.get(m.group(2))
        return ('resp', idx, rf) if rf else None
    fk = FIELD_SYNONYMS.get(norm)
    return ('field', fk) if fk else None

def scan_custom_template(text):
    """Şablon metnindeki tüm [..] ifadelerini tarar. (tanınan, tanınmayan) listelerini döner."""
    recognized, unrecognized, seen = [], [], set()
    for m in BRACKET_RE.finditer(text):
        raw = m.group(1).strip()
        key = raw.lower()
        if key in seen: continue
        seen.add(key)
        res = resolve_bracket_token(raw)
        if res is None:
            unrecognized.append(raw)
        elif res[0]=='field':
            recognized.append({'raw':raw,'target':LABELS.get(res[1],res[1])})
        elif res[0]=='computed':
            recognized.append({'raw':raw,'target':COMPUTED_LABELS.get(res[1],'Otomatik Hesaplanan Alan')})
        else:
            _,idx,rf = res
            recognized.append({'raw':raw,'target':f'Karşı Taraf {idx+1} – {RESP_LABELS.get(rf,rf)}'})
    return recognized, unrecognized

def fill_custom_template(text, values, respondents):
    """[dosya no] gibi köşeli parantezleri ilgili kutucuk değerleriyle değiştirir.
    Tanınmayan ifadeler boş bırakılır (silinir)."""
    def repl(m):
        res = resolve_bracket_token(m.group(1))
        if res is None: return ''
        if res[0]=='field':
            return values.get(res[1]) or ''
        if res[0]=='computed':
            try:return COMPUTED_BRACKETS[res[1]](values,respondents)
            except Exception:return ''
        _,idx,rf = res
        if 0<=idx<len(respondents):
            return respondents[idx].get(rf) or ''
        return ''
    return BRACKET_RE.sub(repl, text)

# NOT: Aşağıdaki tüm girdilerde ':' ile değer arasında SADECE '[ \t]*' kullanılır,
# '\s*' DEĞİL. '\s*' satır sonunu (\n) da yuttuğu için, bir alan boş bırakıldığında
# (ör. "DOSYA TÜRÜ :" boş, hemen altında "Uyuşmazlık Türü : ...") regex bir sonraki
# satırdaki başka bir etiketin değerinin tamamını yanlışlıkla yakalayabiliyordu.
# (party_values() içinde aynı sınıf hata daha önce düzeltilmişti; burada da aynı
# kural genele yayılmıştır.) Ayrıca, kullanılmayan (party_values() tarafından zaten
# karşılanan) basvurucuXXX girdileri kaldırıldı; iki ayrı yerde aynı alanın farklı
# regex'lerle tanımlanması, bir düzeltmenin diğerinde unutulmasına yol açıyordu.
PATTERNS={
'basvuruNo':[r'BAŞVURU\s*NO\s*[:：][ \t]*([^\n<]{1,100})',r'Başvuru\s*(?:Numarası|No)\s*[:：][ \t]*([^\n<]{1,100})'],
'dosyaNo':[r'DOSYA\s*NO\s*[:：][ \t]*([^\n<]{1,100})',r'Dosya\s*(?:Numarası|No)\s*[:：][ \t]*([^\n<]{1,100})'],
'arabulucuTc':[r'T\.?\s*C\.?\s*(?:KİMLİK\s+NUMARASI|Kimlik\s+No)\s*[:：][ \t]*(\d{8,20})'],
'arabulucuSicil':[r'(?:ARB\.?\s*SİCİL\s+NUMARASI|Arb\.?\s*Sicil\s*No)\s*[:：][ \t]*([^\n<]{1,80})'],
'arabulucuAdres':[r'(?:ARABULUCU\s+BİLGİLERİ.*?Adresi|ADRESİ|Adresi)\s*[:：][ \t]*([^\n<]{5,300})'],
'dosyaTuru':[r'DOSYA\s*T[ÜU]R[ÜU]\s*[:：][ \t]*([^\n<]{2,300})'],
'uyusmazlik':[r'Arabuluculuk\s+Konusu\s+Uyuşmazlık\s*[:：][ \t]*([^\n<]{2,500})',r'Uyuşmazlık\s*(?:Türü|Konusu)?\s*[:：][ \t]*([^\n<]{2,500})'],
'talep':[r'Talep(?:ler)?\s*[:：][ \t]*([^\n<]{2,1000})',r'Talep\s+Konusu\s*[:：][ \t]*([^\n<]{2,1000})'],
'baslangicTarihi':[r'Arabuluculuk\s+Sürecinin\s+Başladığı\s+Tarih\s*[:：][ \t]*([^\n<]{2,80})'],
'bitisTarihi':[r'Arabuluculuk\s+Sürecinin\s+Bittiği\s+Tarih\s*[:：][ \t]*([^\n<]{2,80})'],
'duzenlemeYeri':[r'Son\s+Tutanağın\s+Düzenlendiği\s+Yer\s*[:：][ \t]*([^\n<]{2,120})'],
'duzenlemeTarihi':[r'Son\s+Tutanağın\s+Düzenlendiği\s+Tarih\s*[:：][ \t]*([^\n<]{2,80})'],
'sonuc':[r'Arabuluculuk\s+Sonucu\s*[:：][ \t]*([^\n<]{2,300})']}


def normalize_date_value(value):
    """Normalize common OCR/date forms to dd/mm/yyyy without guessing missing dates."""
    v=re.sub(r'\s+',' ',(value or '').strip())
    v=v.replace('.', '/').replace('-', '/')
    m=re.search(r'(?<!\d)(\d{1,2})\s*/\s*(\d{1,2})\s*/\s*(\d{4})(?!\d)',v)
    if m:
        return f"{int(m.group(1)):02d}/{int(m.group(2)):02d}/{m.group(3)}"
    # OCR frequently reads 24/07/2026 as 2410712026. Only accept exactly 8 digits
    # when the middle pair forms a plausible month and the last four a year.
    d=re.sub(r'\D','',v)
    if len(d)==8:
        dd,mm,yyyy=int(d[:2]),int(d[2:4]),d[4:]
        if 1<=dd<=31 and 1<=mm<=12 and 1900<=int(yyyy)<=2200:
            return f"{dd:02d}/{mm:02d}/{yyyy}"
    # Common screenshot OCR error: 24/07/2026 -> 2410712026 (one extra digit).
    if len(d)==10:
        dd=int(d[:2]); yyyy=d[-4:]; middle=d[2:-4]
        if len(middle)==4 and 1<=dd<=31:
            mm=int(middle[1:3])
            if 1<=mm<=12 and 1900<=int(yyyy)<=2200:
                return f"{dd:02d}/{mm:02d}/{yyyy}"
    return v

def _label_value(text, labels, max_len=500):
    """Read a table value after a label, tolerating OCR colon/tab/one-space loss."""
    for label in labels:
        # Most screenshot OCR output is one line: 'Dosya No 20261132654'.
        pat=rf'(?im)^\s*{label}[ \t]*(?:[:：][ \t]*|[ \t]+)([^\n\r]+)'
        m=re.search(pat,text)
        if m:
            value=re.sub(r'\s+',' ',m.group(1)).strip(' :：\t')
            if value:
                return value[:max_len]
    return ''

def normalize_case_number(value, full_text=''):
    v=re.sub(r'\s+','',(value or '').strip())
    # Prefer the exact case number printed in the page title/header.
    m=re.search(r'(?im)^\s*(\d{4}/\d{3,})\s*[-–—]', full_text or '')
    if m:
        return m.group(1)
    m=re.search(r'(?<!\d)(\d{4})\s*/\s*(\d{3,})(?!\d)', value or '')
    if m:
        return f"{m.group(1)}/{m.group(2)}"
    # Bazı belgelerde yıl/sıra ayracı '/' değil '-' olabilir (ör. "2026-123").
    # Bu durumda da standart "YIL/SIRA" biçimine çeviriyoruz; aksi halde aynı
    # dosyanın iki farklı belgesi arasında yanlış bir "çakışma" tespit edilebilir
    # ya da gerçek bir çakışma normalize edilmediği için fark edilmeyebilir.
    m=re.search(r'(?<!\d)(\d{4})\s*-\s*(\d{3,})(?!\d)', value or '')
    if m:
        return f"{m.group(1)}/{m.group(2)}"
    return v

def is_valid_tc_kimlik(tc):
    """T.C. Kimlik Numarası resmi checksum algoritmasını uygular.
    OCR/kaynak belgeden gelen numaranın bozuk olup olmadığını tespit etmek için
    kullanılır; hiçbir alanı bloke etmez, yalnızca notices uyarısı üretmek içindir."""
    d=re.sub(r'\D','',tc or '')
    if len(d)!=11 or d[0]=='0':
        return False
    digits=[int(c) for c in d]
    odd_sum=sum(digits[0:9:2])
    even_sum=sum(digits[1:8:2])
    d10=((odd_sum*7)-even_sum)%10
    d11=sum(digits[:10])%10
    return d10==digits[9] and d11==digits[10]

def is_valid_vkn(vkn):
    """Vergi Kimlik Numarası (10 hane) için bilinen resmi checksum algoritması.
    is_valid_tc_kimlik ile aynı amaçla kullanılır: hiçbir alanı bloke etmez,
    yalnızca 'bu numara OCR/ayrıştırma hatası içeriyor olabilir' uyarısı için."""
    d=re.sub(r'\D','',vkn or '')
    if len(d)!=10:
        return False
    digits=[int(c) for c in d]
    total=0
    for i in range(9):
        tmp=(digits[i]+9-i)%10
        v=9 if tmp==0 else (tmp*(2**(9-i)))%9
        if v==0 and tmp!=0:
            v=9
        total+=v
    check=(10-(total%10))%10
    return check==digits[9]


def extract_dosya_bilgileri_screen(ptext):
    """
    Parses the UYAP/Arabuluculuk 'Dosya Bilgileri' screenshot/table.
    This is intentionally independent from the application-form parser so that
    screenshots can be merged with a form later.
    """
    t=clean_ocr_text(ptext)
    out={}
    out['dosyaTuru']=_label_value(t,[r'Dosya\s+Türü',r'Dosya\s+T[ÜU]r[ÜU]'])
    out['dosyaNo']=normalize_case_number(_label_value(t,[r'Dosya\s+No',r'Dosya\s+Numarası']), t)
    out['basvuruNo']=_label_value(t,[r'Başvuru\s+Dosya\s+No',r'Başvuru\s+Dosya\s+Numarası',r'Başvuru\s+No'])
    out['baslangicTarihi']=normalize_date_value(_label_value(t,[r'Açılış\s+Tarihi',r'Başlangıç\s+Tarihi']))
    out['uyusmazlikTuru']=_label_value(t,[r'Uyuşmazlık\s+Türü'])
    out['sonuc']=_label_value(t,[r'Arabuluculuk\s+Sonucu'])
    # The existing application intentionally uses DOSYA TÜRÜ as the value
    # printed after 'Arabuluculuk Konusu Uyuşmazlık' in the final record.
    out['dosyaTuru']=normalize_dosya_turu(out.get('dosyaTuru',''))
    if out.get('dosyaTuru'):
        out['uyusmazlik']=out['dosyaTuru']
    return out

def normalize_dosya_turu(value):
    value=re.sub(r"\s+", " ", (value or "").strip())
    value=re.sub(r"\s*Başvuru\s+Dosyası\s*$", "", value, flags=re.I)
    value=re.sub(r"\s*Başvuru\s*$", "", value, flags=re.I)
    value=re.sub(r"\s*Dosyası\s*$", "", value, flags=re.I)
    return value.strip(" :.-")

SUPPORTED_SOURCE_EXTS={'.jpg','.jpeg','.png','.pdf'}

def clean_ocr_text(text):
    text=text.replace('\x0c','\n')
    text=re.sub(r'[ \t]+',' ',text)
    text=re.sub(r'\n{3,}','\n\n',text)
    return text.strip()

def ocr_image_bytes(data):
    img=Image.open(io.BytesIO(data))
    # Upscale smaller screenshots for better OCR while keeping memory reasonable.
    w,h=img.size
    if w < 1800:
        scale=min(2.5, 1800/max(w,1))
        img=img.resize((int(w*scale),int(h*scale)), Image.Resampling.LANCZOS)
    # Turkish language model; fall back to English if Turkish data is unavailable.
    try:
        txt=pytesseract.image_to_string(img, lang='tur+eng', config='--psm 6')
    except Exception:
        txt=pytesseract.image_to_string(img, lang='eng', config='--psm 6')
    return clean_ocr_text(txt)

def pdf_text_or_ocr(data):
    text_parts=[]
    try:
        reader=PdfReader(io.BytesIO(data))
        for page in reader.pages:
            t=page.extract_text() or ''
            if t.strip():
                text_parts.append(t)
    except Exception:
        pass
    text=clean_ocr_text('\n'.join(text_parts))
    # If the PDF contains little/no selectable text, OCR every page.
    if len(re.sub(r'\s','',text)) < 80:
        pages=convert_from_bytes(data, dpi=220, fmt='png', thread_count=1)
        ocr_parts=[]
        for img in pages:
            try:
                t=pytesseract.image_to_string(img, lang='tur+eng', config='--psm 6')
            except Exception:
                t=pytesseract.image_to_string(img, lang='eng', config='--psm 6')
            ocr_parts.append(t)
        text=clean_ocr_text('\n'.join(ocr_parts))
    return text

def extract_source_text(filename,data):
    ext=Path(filename or '').suffix.lower()
    if ext=='.pdf':
        return pdf_text_or_ocr(data)
    if ext in {'.jpg','.jpeg','.png'}:
        return ocr_image_bytes(data)
    raise ValueError('Desteklenen kaynak formatları: UDF, PDF, JPG, JPEG ve PNG.')

def is_udf_filename(filename):
    return Path(filename or '').suffix.lower()=='.udf'


def read_udf(data):
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            if 'content.xml' not in z.namelist(): raise ValueError('content.xml bulunamadı.')
            xml=z.read('content.xml').decode('utf-8'); files={n:z.read(n) for n in z.namelist()}
    except zipfile.BadZipFile: raise ValueError('Geçerli bir UDF dosyası seçin.')
    m=re.search(r'<content><!\[CDATA\[(.*?)\]\]></content>',xml,re.S)
    if not m: raise ValueError('UDF metin alanı okunamadı.')
    return xml,m.group(1),files

def udf_plain(text):
    s=re.sub(r'<[^>]+>','',text); lines=[]
    for line in s.splitlines():
        line=re.sub(r'[ \t]+',' ',line).strip()
        if line: lines.append(line)
    return '\n'.join(lines)

# ---------------------------------------------------------------------------
# BİLİNEN ALAN ETİKETLERİ (merkezi sözlük)
# Adres/telefon/vergi no vb. etiketler eskiden party_values(), PATTERNS ve
# extract_dosya_bilgileri_screen() içinde birbirinden bağımsız regex'lerle
# aranıyordu; bir etiket varyasyonu (ör. "Adres ve Cep(Zorunlu)") bir yerde
# eklense bile diğerinde unutuluyordu. Ortak varyantlar burada TEK yerde
# tutulur ve hem party_values() hem de _LABEL_BLEED_RE bundan beslenir.
# PAREN_ANNOTATION: "(Zorunlu)", "(Cep-Zorunlu)" gibi UYAP formlarında sık
# görülen açıklama parantezlerini, etiket ile ':' arasında tolere eder.
# ---------------------------------------------------------------------------
_PAREN_ANNOTATION = r'(?:\s*\([^)]{0,60}\))?'
_ADDRESS_LABEL = r'Adres(?:\s+ve\s+Cep)?'
_PHONE_LABEL = r'(?:Cep\s*Tel(?:efonu)?|İletişim|Telefon(?:\s+Numarası)?)'
_TAX_LABEL = r'Vergi(?:\s*/\s*Mersis)?(?:\s*/\s*Detsis)?\s*(?:Kimlik\s*)?No|VKN|Vergi\s*Numarası|Mersis\s*No|Detsis\s*No'
_NAME_LABEL = r'Adı\s+Soyadı|Kurum\s+Adı|Unvanı|Ünvanı|Şirket\s+Unvanı|Firma\s+Adı'

# Bilinen bölüm başlıkları + alan etiketleri: first() bir değeri yakaladığında,
# bu değer AKTÜEL OLARAK bu etiketlerden biriyle başlıyorsa ("Uyuşmazlık Türü : ..."
# gibi), bu neredeyse kesin bir "satır sızması" (regex'in boş bir alanı atlayıp
# bir sonraki etiketin/değerin tamamını yanlışlıkla yakalaması) belirtisidir.
# NOT: Bu liste kasıtlı olarak SPESİFİK bilinen etiketlerle sınırlı tutulur;
# genel bir "Büyük Harfli Kelimeler + :" sezgiseli, "... No:5 Ankara" gibi
# tamamen geçerli adres değerlerinde yanlış pozitif üretir.
_KNOWN_FIELD_LABELS = [
    r'Başvuru\s*(?:Numarası|No)', r'Dosya\s*(?:Numarası|No)', r'Dosya\s*T[üu]r[üu]',
    r'Uyuşmazlık\s*(?:Türü|Konusu)?', r'Arabuluculuk\s+Konusu\s+Uyuşmazlık',
    r'Talep(?:ler)?', r'Talep\s+Konusu',
    r'Arabuluculuk\s+Sürecinin\s+Başladığı\s+Tarih', r'Arabuluculuk\s+Sürecinin\s+Bittiği\s+Tarih',
    r'Son\s+Tutanağın\s+Düzenlendiği\s+(?:Yer|Tarih)', r'Arabuluculuk\s+Sonucu',
    _NAME_LABEL, r'T\.?\s*C\.?\s*Kimlik\s*No(?:su)?', _TAX_LABEL,
    _ADDRESS_LABEL, r'Vekili', r'Baro\s+Sicil\s+Numarası', _PHONE_LABEL,
    r'E-Posta(?:\s+Adresi)?',
    r'BAŞVURU\s+SAHİBİ\s+BİLGİLERİ', r'BAŞVURUCU\s+BİLGİLERİ', r'KARŞI\s+TARAF\s+BİLGİLERİ',
    r'ARABULUCU\s+BİLGİLERİ', r'BAŞVURU\s+BİLGİLERİ',
]
_LABEL_BLEED_RE = re.compile(r'^(?:'+'|'.join(_KNOWN_FIELD_LABELS)+r')'+_PAREN_ANNOTATION+r'\s*[:：]', re.I)
_KNOWN_LABEL_ONLY_RE = re.compile(r'^(?:'+'|'.join(_KNOWN_FIELD_LABELS)+r')'+_PAREN_ANNOTATION+r'$', re.I)

def find_unmatched_labels(ptext):
    """DEV/DEBUG amaçlıdır (varsayılan olarak devrede DEĞİLDİR, bkz. extract()
    içindeki TUTANAK_DEBUG_LABELS kontrolü). Metindeki 'Etiket : değer' biçimli
    satırlardan, bilinen _KNOWN_FIELD_LABELS listesinde OLMAYAN etiketleri
    döndürür. Yalnızca ETİKET METNİ toplanır, DEĞER hiçbir zaman toplanmaz;
    bu yüzden KVKK/gizlilik açısından risksizdir. Amaç: farklı arabuluculuk
    bürolarının ürettiği yeni form varyasyonlarını (yeni etiket kelimeleri)
    zaman içinde keşfedip LABEL sözlüğünü genişletebilmektir."""
    found=[]
    seen=set()
    for line in ptext.splitlines():
        line=line.strip()
        m=re.match(r'^-?\s*([^\n:：]{2,60}?)\s*[:：]',line)
        if not m:
            continue
        label=m.group(1).strip()
        if not label or label in seen:
            continue
        seen.add(label)
        if not _KNOWN_LABEL_ONLY_RE.match(label) and not re.match(r'^\d',label):
            found.append(label)
    return found


def first(patterns,text,flags=re.I,notices=None,field_label=None):
    """İlk eşleşen pattern'in yakaladığı değeri döner. `notices` verilirse ve
    yakalanan değer bilinen başka bir etikete ait metinle başlıyorsa (satır
    sızması şüphesi), bu eşleşme reddedilir, sıradaki pattern denenir ve
    (varsa field_label ile birlikte) notices listesine bir uyarı eklenir."""
    for p in patterns:
        m=re.search(p,text,flags)
        if m:
            v=m.group(1).strip(' \t\r\n:;,-')
            if v:
                if _LABEL_BLEED_RE.match(v):
                    if notices is not None:
                        etiket=f'"{field_label}" alanı' if field_label else 'Bir alan'
                        notices.append(f'{etiket}, başka bir etikete ait metinle başladığı için ("{v[:40]}...") boş bırakıldı; lütfen elle kontrol edin.')
                    continue
                return v
    return ''

def section(text,start_terms,end_terms):
    """Belirtilen start_terms etiketlerinden biri metinde bulunursa, en erken
    geçenden başlayıp ilk end_terms etiketine kadar olan alt metni döndürür.
    HİÇBİR start_terms bulunamazsa boş dize döner.
    NOT: Eskiden bulunamama durumunda tüm belge (text[0:]) döndürülüyordu; bu,
    ilgili bölüm belgede yoksa (ör. "ARABULUCU BİLGİLERİ" başlığı olmayan bir
    başvuru formunda) o bölüme özgü alanların başka bir bölümden -örn. karşı
    tarafın TC kimlik numarasından- yanlışlıkla doldurulmasına yol açabiliyordu.
    Artık böyle bir durumda çağıran taraf boş bir sonuç alır; extract() içindeki
    ilgili alanlar boş kalır (yanlış kişiye ait veri yazılmaz)."""
    positions=[text.find(t) for t in start_terms if text.find(t)>=0]
    if not positions:
        return ''
    s=min(positions)
    ends=[text.find(t,s+1) for t in end_terms]
    e=min([x for x in ends if x>=0] or [len(text)])
    return text[s:e]

def _strip_inline_trailing_label(value):
    """Bazı UYAP formlarında aynı satırda birden fazla alan yer alır
    (ör. 'Adres\t: .    Cep Tel : 05054462124'). Adres regex'i satırın tamamını
    yakaladığı için, değerin içine sonradan başka bir etiketin (Cep Tel,
    Telefon, Vekili) karışmasını burada ayıklıyoruz."""
    if not value:
        return value
    m=re.search(rf'\s+(?:{_PHONE_LABEL}|Vekili)\s*[:：]',value,re.I)
    return value[:m.start()].strip() if m else value

_PARTY_SUBHEADER_RE = re.compile(r'-\s*(Kişi|Kurum|Şirket|Tüzel\s*Kişi)\s+için', re.I)

_COMPANY_NAME_RE = re.compile(
    r'\b(?:A\.?\s*Ş\.?|Anonim\s+Şirket\w*|Ltd\.?\s*Şti\.?|Limited\s+Şirket\w*|'
    r'Şirket(?:i|imiz)?|Kooperatif\w*|Holding\w*|San(?:ayi)?\.?\s*(?:ve\s*)?Tic(?:aret)?\.?)\b',
    re.IGNORECASE)

def _is_company_name(name):
    """Adı/unvanı alanında 'A.Ş.', 'Şti', 'Limited Şirketi' gibi tüzel kişi
    ibareleri geçiyorsa True döner; vergi no alanı boş/okunamamış olsa bile
    tarafın 'kurum' olarak sınıflandırılmasını sağlamak için kullanılır."""
    return bool(name and _COMPANY_NAME_RE.search(name))

def _subheader_type(text):
    """Bloğun başında '-Kişi İçin' / '-Kurum için' / '-Şirket İçin' gibi bir
    UYAP alt başlığı varsa, taraf türünü doğrudan bu başlıktan belirler.
    Bulunamazsa None döner (çağıran, tax/tc varlığına göre eski yönteme düşer).
    Bu, vergi no regex'i (etiket varyasyonu nedeniyle) eşleşmese bile kurumun
    yanlışlıkla 'kişi' sayılmasını önler."""
    m=_PARTY_SUBHEADER_RE.search(text)
    if not m:
        return None
    return 'kisi' if m.group(1).strip().lower()=='kişi' else 'kurum'

def _normalize_phone(phone):
    """Bir telefon alanında '-' , ',' veya '/' ile ayrılmış birden fazla numara
    olabilir (ör. "05077045252 -05327205414 -05550516564"). Her parçayı ayrı ayrı
    yalnızca rakam+baştaki '+' kalacak şekilde temizleyip aralarına '- ' koyarak
    geri birleştiriyoruz; aksi halde tüm numaralar tek bir okunaksız rakam
    yığınında birleşiyordu."""
    if not phone:
        return phone
    parts=[p for p in re.split(r'[-/,;]+',phone) if p.strip()]
    if not parts:
        return phone
    cleaned=[re.sub(r'[^\d+]','',p) for p in parts]
    cleaned=[c for c in cleaned if c]
    return '- '.join(cleaned) if cleaned else phone

def party_values(seg,notices=None):
    # NOT: iki nokta üst üste sonrası [ \t]* kullanılır (\s* DEĞİL); \s* satır
    # sonunu (\n) da yuttuğu için, değer boş bırakılmış bir alanda arama bir
    # sonraki satıra/bölüm başlığına kayıp yanlış veri yakalayabiliyordu
    # (ör. boş "Vekili :" alanının hemen altındaki "BAŞVURU BİLGİLERİ" başlığının
    # vekil adı sanılması gibi).
    tax=first([rf'(?:{_TAX_LABEL})\s*[:：][ \t]*([0-9]{{8,20}})'],seg,notices=notices,field_label='Vergi/Mersis/Detsis No')
    tc=first([r'T\.?\s*C\.?\s*Kimlik\s*No(?:su)?\s*[:：][ \t]*(\d{8,20})'],seg,notices=notices,field_label='T.C. Kimlik No')
    name=first([rf'(?:{_NAME_LABEL})\s*[:：][ \t]*([^\n<]{{2,250}})'],seg,notices=notices,field_label='Adı Soyadı/Unvanı')
    address=_strip_inline_trailing_label(first([rf'{_ADDRESS_LABEL}{_PAREN_ANNOTATION}\s*[:：][ \t]*([^\n<]{{2,400}})'],seg,notices=notices,field_label='Adres'))
    phone=first([rf'{_PHONE_LABEL}{_PAREN_ANNOTATION}\s*[:：][ \t]*([^\n<]{{3,150}})'],seg,notices=notices,field_label='Telefon')
    # Telefon numaralarındaki iç boşlukları normalize et (ör. "0505 446 21 24" -> "05054462124").
    # Yalnızca rakam ve baştaki '+' korunur; UYAP formlarında telefon serbest metin
    # olduğu için farklı boşluklu biçimler aynı bilgi havuzunda tutarsız görünebiliyordu.
    # Bazı belgelerde birden fazla telefon numarası '-' ile ayrılmış tek bir alanda
    # gelir (ör. "05077045252 -05327205414 -05550516564"); bunları tek bir rakam
    # yığınına birleştirmek yerine, her numarayı ayrı ayrı normalize edip aralarına
    # "- " koyarak okunur biçimde geri birleştiriyoruz.
    phone_norm=_normalize_phone(phone) if phone else phone
    party_type=_subheader_type(seg) or ('kurum' if tax and not tc else None) or ('kurum' if _is_company_name(name) else 'kisi')
    return {
        'type':party_type,
        'tc':tc,'tax':tax,'name':turkce_title_case(name),
        'address':turkce_title_case(address),
        'proxy':turkce_title_case(first([r'Vekili\s*[:：][ \t]*([^\n<]{1,250})'],seg,notices=notices,field_label='Vekili')),
        'phone':phone_norm,
        'email':first([r'E-Posta(?:\s+Adresi)?\s*[:：][ \t]*([^\n<]{3,250})'],seg,notices=notices,field_label='E-Posta')
    }

def extract_respondents(ptext,notices=None):
    seg=section(ptext,['KARŞI TARAF BİLGİLERİ','KARŞI TARAF','DİĞER TARAF BİLGİLERİ','DİĞER TARAF'],['Arabuluculuk Konusu Uyuşmazlık','UYUŞMAZLIK','TALEP','Arabuluculuk Sürecinin'])

    # Yöntem 1 (en güvenilir): UYAP formlarında sık görülen '-Kişi İçin' /
    # '-Kurum için' / '-Şirket İçin' alt başlıkları varsa, blok sınırlarını
    # doğrudan bunlardan çıkar. Bu, kurum bloğunun adının "Kurum Adı" yerine
    # başka bir etiketle yazıldığı durumlarda bile taraf sayısını doğru verir.
    subheaders=list(_PARTY_SUBHEADER_RE.finditer(seg))
    if subheaders:
        starts=[m.start() for m in subheaders]
        dropped=max(0,len(starts)-MAX_RESP)
        parties=[]
        for i,s in enumerate(starts[:MAX_RESP]):
            e=starts[i+1] if i+1<len(starts) else len(seg)
            chunk=seg[s:e]
            pv=party_values(chunk,notices=notices)
            if pv['name']:
                parties.append(pv)
            elif notices is not None:
                notices.append(f'"{chunk.splitlines()[0].strip()}" alt başlıklı karşı taraf bloğunda ad/unvan tespit edilemedi; lütfen elle kontrol edin.')
        if parties:
            return parties,dropped

    # Yöntem 2 (yedek): alt başlık yoksa, gerçek/tüzel kişi ayrımı yapmadan
    # TÜM bilinen isim/unvan etiketlerine ("Adı Soyadı", "Kurum Adı", "Unvanı",
    # "Şirket Unvanı", "Firma Adı") göre böl. Eskiden yalnızca "Adı Soyadı"
    # aranıyordu; bu yüzden kurum karşı taraflar (etiketi "Kurum Adı" olanlar)
    # hiçbir uyarı üretmeden tamamen atlanıyordu.
    matches=list(re.finditer(rf'(?:{_NAME_LABEL})\s*[:：]',seg,re.I))
    dropped=max(0,len(matches)-MAX_RESP)
    parties=[]
    for i,m in enumerate(matches[:MAX_RESP]):
        starts=[seg.rfind('\nTC Kimlik No',0,m.start()),seg.rfind('\nVergi',0,m.start()),
                seg.rfind('\n-',0,m.start())]+[seg.rfind('\n'+lbl,0,m.start()) for lbl in ('Adı Soyadı','Kurum Adı','Unvanı','Ünvanı','Şirket Unvanı','Firma Adı')]
        a=max([x for x in starts if x>=0] or [max(0,seg.rfind('\n',0,m.start()))])
        b=matches[i+1].start() if i+1<len(matches) else len(seg)
        chunk=seg[a:b]
        pv=party_values(chunk,notices=notices)
        if pv['name']:
            parties.append(pv)
    if parties:return parties,dropped
    # Tek blok için son yedek yöntem.
    pv=party_values(seg,notices=notices)
    return ([pv] if pv['name'] else []),0

def extract(text):
    ptext=udf_plain(text); out={k:'' for k,_ in FIELDS}
    # NOT: Bu liste, ayrıştırıcının hangi bölümleri ARADIĞINI ve BULAMADIĞINI
    # kullanıcıya açıkça bildirmek için toplanır. Eskiden bir alan boş kaldığında
    # kullanıcı bunun "belgede gerçekten yok" mu yoksa "ayrıştırma başarısız oldu" mu
    # olduğunu ayırt edemiyordu; render_editor artık bu notices listesini bir uyarı
    # şeridi olarak gösteriyor.
    notices=[]
    for k in ['basvuruNo','dosyaNo']: out[k]=first(PATTERNS[k],ptext,notices=notices,field_label=LABELS.get(k,k))
    screen=extract_dosya_bilgileri_screen(ptext)
    for k,v in screen.items():
        if v:
            out[k]=v
    # NOT: başlangıç terimi olarak yalnızca 'ARABULUCU' (tek kelime) kullanmak
    # riskliydi; "ARABULUCULUK BÜROSU" gibi ifadelerin içinde alt-dize olarak
    # geçtiği için section() belgenin çok daha erken bir noktasından başlıyor,
    # bu da arabulucuTc/Sicil/Adres aramasının -aşağıda tüm belgede yapıldığı
    # için- karşı tarafın TC kimlik numarasını arabulucununmuş gibi yakalamasına
    # yol açabiliyordu. Artık: (1) tam başlık aranıyor, (2) bölüm bulunamazsa
    # tüm belgede arama yapılmıyor (veriler boş kalır, yanlış kişiye ait veri
    # yazılmaz; profil varsayılanları zaten bu alanları sonradan dolduruyor).
    arbsec=section(ptext,['ARABULUCU BİLGİLERİ'],['BAŞVURU SAHİBİ BİLGİLERİ','BAŞVURUCU BİLGİLERİ','BAŞVURU SAHİBİ'])
    if arbsec:
        out['arabulucuAdi']=turkce_title_case(first([r'Adı\s+Soyadı\s*[:：][ \t]*([^\n<]{2,150})',r'ARABULUCU\s*[:：][ \t]*([^\n<]{2,150})'],arbsec,notices=notices,field_label='Arabulucu Adı'))
        for k in ['arabulucuTc','arabulucuSicil','arabulucuAdres']: out[k]=first(PATTERNS[k],arbsec,notices=notices,field_label=LABELS.get(k,k))
        out['arabulucuAdres']=turkce_title_case(out['arabulucuAdres'])
    # NOT: Arabulucu bilgileri bu belgelerde ZATEN normal şartlarda bulunmuyor -
    # arabulucu, arabulucunun kendi PROFİLİNDEN otomatik dolduruluyor (bkz.
    # apply_mediator_profile_defaults, main.py). Bu yüzden "Arabulucu Bilgileri
    # bölümü bulunamadı" uyarısı burada BİLEREK üretilmiyor; bu, gerçek bir
    # ayrıştırma sorunu değil, beklenen/normal bir durumdur. (Başvurucu ve Karşı
    # Taraf bölümleri için aynı durum geçerli DEĞİL - onlar gerçekten belgeden
    # gelmesi gereken veriler olduğu için ilgili uyarılar aşağıda korunuyor.)
    if out.get('arabulucuTc') and not is_valid_tc_kimlik(out['arabulucuTc']):
        notices.append(f"Arabulucu T.C. Kimlik No ({out['arabulucuTc']}) geçerli bir kontrol basamağına sahip değil; OCR/ayrıştırma hatası olabilir, lütfen kontrol edin.")
    applicant=section(ptext,['BAŞVURU SAHİBİ BİLGİLERİ','BAŞVURUCU BİLGİLERİ','BAŞVURUCU'],['KARŞI TARAF BİLGİLERİ','KARŞI TARAF','DİĞER TARAF BİLGİLERİ','DİĞER TARAF'])
    if not applicant:
        notices.append("Belgede \"Başvuru Sahibi Bilgileri\" bölümü bulunamadı; başvurucu alanları boş kalmış olabilir, lütfen kontrol edin.")
    a=party_values(applicant,notices=notices)
    out.update({'basvurucuTcKimlik':a['tc'],'basvurucuAdiSoyadi':a['name'],'basvurucuAdres':a['address'],'basvurucuVekili':a['proxy'],'basvurucuTelefon':a['phone'],'basvurucuEposta':a['email'],'basvurucuTarafTuru':a.get('type','kisi'),'basvurucuVergiNo':a.get('tax','')})
    if a['tc'] and not is_valid_tc_kimlik(a['tc']):
        notices.append(f"Başvurucu T.C. Kimlik No ({a['tc']}) geçerli bir kontrol basamağına sahip değil; OCR/ayrıştırma hatası olabilir, lütfen kontrol edin.")
    if a['tax'] and not is_valid_vkn(a['tax']):
        notices.append(f"Başvurucu Vergi No ({a['tax']}) geçerli bir kontrol basamağına sahip değil; OCR/ayrıştırma hatası olabilir, lütfen kontrol edin.")
    respondents,dropped_resp=extract_respondents(ptext,notices=notices)
    if not respondents:
        notices.append("Belgede \"Karşı Taraf Bilgileri\" bölümü bulunamadı veya taraf adı tespit edilemedi; lütfen karşı taraf bilgilerini elle kontrol edip ekleyin.")
    if dropped_resp:
        notices.append(f"Belgede {dropped_resp} karşı taraf, en fazla {MAX_RESP} karşı taraf sınırı nedeniyle okunamadı; gerekirse elle ekleyin.")
    for idx,p in enumerate(respondents,1):
        if p.get('tc') and not is_valid_tc_kimlik(p['tc']):
            notices.append(f"{idx}. karşı tarafın T.C. Kimlik No ({p['tc']}) geçerli bir kontrol basamağına sahip değil; OCR/ayrıştırma hatası olabilir, lütfen kontrol edin.")
        if p.get('tax') and not is_valid_vkn(p['tax']):
            notices.append(f"{idx}. karşı tarafın Vergi No ({p['tax']}) geçerli bir kontrol basamağına sahip değil; OCR/ayrıştırma hatası olabilir, lütfen kontrol edin.")
    generic_dosya=normalize_dosya_turu(first(PATTERNS['dosyaTuru'],ptext,notices=notices,field_label='Dosya Türü'))
    if generic_dosya and not out.get('dosyaTuru'):
        out['dosyaTuru']=generic_dosya
    for k in ['uyusmazlik','talep','baslangicTarihi','bitisTarihi','duzenlemeYeri','duzenlemeTarihi','sonuc']:
        v=first(PATTERNS[k],ptext,notices=notices,field_label=LABELS.get(k,k))
        if v and not out.get(k):
            out[k]=v
    if out.get('duzenlemeYeri'):
        out['duzenlemeYeri']=turkce_title_case(out['duzenlemeYeri'])
    if out.get('dosyaTuru'):
        out['uyusmazlik']=out['dosyaTuru']
    if out.get('baslangicTarihi'):
        out['baslangicTarihi']=normalize_date_value(out['baslangicTarihi'])
    if os.environ.get('TUTANAK_DEBUG_LABELS')=='1':
        for lbl in find_unmatched_labels(ptext):
            notices.append(f'[DEBUG] Tanınmayan etiket: "{lbl}" (değer loglanmadı; farklı bir UYAP form varyasyonu olabilir, LABEL sözlüğüne eklenmesi değerlendirilebilir)')
    return out,respondents,notices

def make_mapper(a,b):
    sm=difflib.SequenceMatcher(a=a,b=b,autojunk=False); blocks=sm.get_matching_blocks()
    def mp(p):
        if p<=0:return 0
        if p>=len(a):return len(b)
        for x in blocks:
            if x.a<=p<=x.a+x.size:return x.b+p-x.a
        prev=max((x for x in blocks if x.a<p),default=None,key=lambda x:x.a)
        return prev.b+min(p-prev.a,prev.size) if prev else 0
    return mp

def update_offsets(xml,a,b):
    mp=make_mapper(a,b)
    def f(m):
        s,l=int(m.group(1)),int(m.group(2)); ns,ne=mp(s),mp(s+l)
        return f'startOffset="{ns}" length="{max(0,ne-ns)}"'
    return re.sub(r'startOffset="(\d+)"\s+length="(\d+)"',f,xml)


def fill_custom_template_tracked(text, values, respondents):
    """fill_custom_template ile aynı işi yapar ([bracket] alanlarını değerlerle
    değiştirir) ama SequenceMatcher'ın tahmin etmesine gerek kalmasın diye her
    değişikliğin eski metindeki ve yeni metindeki tam konumunu da döner.

    Dönüş: (yeni_metin, edits)
      edits: [(old_start, old_end, new_start, new_end), ...] eski metindeki
             sıraya göre, üst üste binmeyen aralıklar.

    Bu bilgi update_offsets_exact ile birlikte kullanıldığında <elements>
    ofsetleri fuzzy diff yerine kesin aritmetikle güncellenir; tekrar eden
    hukuki ifadeler (ör. "hâlinde", "taraflarca") yüzünden SequenceMatcher'ın
    yanlış "çapa" seçip ofsetleri kümülatif olarak kaydırması riski ortadan
    kalkar.
    """
    edits = []
    out = []
    last = 0
    new_pos = 0
    for m in BRACKET_RE.finditer(text):
        gap = text[last:m.start()]
        out.append(gap)
        new_pos += len(gap)
        res = resolve_bracket_token(m.group(1))
        if res is None:
            value = ''
        elif res[0] == 'field':
            value = values.get(res[1]) or ''
        elif res[0] == 'computed':
            try:
                value = COMPUTED_BRACKETS[res[1]](values, respondents)
            except Exception:
                value = ''
        else:
            _, idx, rf = res
            value = respondents[idx].get(rf) or '' if 0 <= idx < len(respondents) else ''
        out.append(value)
        edits.append((m.start(), m.end(), new_pos, new_pos + len(value)))
        new_pos += len(value)
        last = m.end()
    out.append(text[last:])
    new_text = ''.join(out)
    return new_text, edits


def update_offsets_exact(xml, edits, old_len, new_text):
    """update_offsets'ın deterministik sürümü. Fuzzy diff (difflib.SequenceMatcher)
    yerine fill_custom_template_tracked'dan gelen kesin (old_start,old_end,new_start,new_end)
    listesini kullanarak her startOffset/length çiftini eşler. Metnin nerede
    değiştiğini tahmin etmeye gerek yok, zaten biliniyor -> yanlış eşleşme imkansız.

    Ayrıca: bazı hesaplanan alanlar (ör. vekilsiz muhatap için "İsim\\nAdres" gibi)
    kendi DEĞERİNİN İÇİNDE satır sonu taşıyabilir. Böyle bir durumda, o değeri
    saran tek paragraf artık iki (veya daha fazla) görsel satırı birden kapsar
    hale gelir; UYAP gibi sıkı bir ayrıştırıcı bunu reddedebilir. Bu fonksiyon,
    eşleme sonrası bir paragrafın kapsadığı metinde satır sonu tespit ederse,
    o paragrafı satır sınırlarında otomatik olarak ayrı <paragraph> bloklarına
    böler; bold/size/Alignment öznitelikleri korunur."""
    new_len = len(new_text)

    def mp(p):
        if p <= 0:
            return 0
        if p >= old_len:
            return new_len
        cum = 0
        for os, oe, ns, ne in edits:
            if p <= os:
                return p + cum
            if os < p <= oe:
                return ne
            cum += (ne - ns) - (oe - os)
        return p + cum

    em = re.search(r'(<elements\b[^>]*>)(.*?)(</elements>)', xml, re.S)
    if not em:
        # <elements> bölümü bulunamazsa eski (blok bazlı olmayan) davranışa dön.
        def f(m):
            s, l = int(m.group(1)), int(m.group(2))
            ns, ne = mp(s), mp(s + l)
            return f'startOffset="{ns}" length="{max(0,ne-ns)}"'
        return re.sub(r'startOffset="(\d+)"\s+length="(\d+)"', f, xml)

    head, body, tail = em.group(1), em.group(2), em.group(3)
    blocks = re.findall(r'<paragraph\b[^>]*>.*?</paragraph>\s*', body, re.S)

    out_blocks = []
    for b in blocks:
        align_m = re.search(r'Alignment="([^"]*)"', b)
        align = align_m.group(1) if align_m else ''
        runs = []
        for cm in re.finditer(r'<content\b([^>]*?)startOffset="(\d+)"\s+length="(\d+)"([^>]*)/>', b):
            pre, s, l, post = cm.group(1), int(cm.group(2)), int(cm.group(3)), cm.group(4)
            bold_m = re.search(r'bold="([^"]*)"', pre + post)
            size_m = re.search(r'size="([^"]*)"', pre + post)
            bold = bold_m.group(1) if bold_m else 'false'
            size = size_m.group(1) if size_m else '12'
            ns, ne = mp(s), mp(s + l)
            runs.append((ns, max(ns, ne), bold, size))
        if not runs:
            out_blocks.append(b)
            continue

        span_start, span_end = runs[0][0], runs[-1][1]
        span_text = new_text[span_start:span_end]
        if chr(10) not in span_text:
            # tek satırda kalıyor, orijinal yapıyı koru (sadece ofsetleri yaz)
            piece = f'<paragraph Alignment="{align}">' if align else '<paragraph>'
            for ns, ne, bold, size in runs:
                piece += f'<content bold="{bold}" size="{size}" startOffset="{ns}" length="{max(0,ne-ns)}" />'
            piece += '</paragraph>\n'
            out_blocks.append(piece)
            continue

        # satır sonu içeriyor -> satır satır ayrı paragraflara böl
        lines = span_text.splitlines(keepends=True)
        pos = span_start
        run_idx = 0
        for line in lines:
            ln = len(line)
            line_start, line_end = pos, pos + ln
            sub_runs = []
            while run_idx < len(runs) and runs[run_idx][0] < line_end:
                rs, re_, bold, size = runs[run_idx]
                seg_s, seg_e = max(rs, line_start), min(re_, line_end)
                if seg_e > seg_s:
                    sub_runs.append((seg_s, seg_e, bold, size))
                if re_ <= line_end:
                    run_idx += 1
                else:
                    break
            if not sub_runs:
                sub_runs = [(line_start, line_end, runs[0][2], runs[0][3])]
            piece = f'<paragraph Alignment="{align}">' if align else '<paragraph>'
            for ns, ne, bold, size in sub_runs:
                piece += f'<content bold="{bold}" size="{size}" startOffset="{ns}" length="{max(0,ne-ns)}" />'
            piece += '</paragraph>\n'
            out_blocks.append(piece)
            pos = line_end

    new_body = ''.join(out_blocks)
    return xml[:em.start()] + head + new_body + tail + xml[em.end():]

def replace_once(text,patterns,value):
    for p in patterns:
        m=re.search(p,text,re.I)
        if m:return text[:m.start(1)]+value+text[m.end(1):],True
    return text,False

def replace_labeled(text,label_patterns,value):
    return replace_once(text,label_patterns,value)



def _paragraph_blocks(xml):
    """Return paragraph XML blocks with their old text offsets."""
    em=re.search(r'(<elements\b[^>]*>)(.*?)(</elements>)',xml,re.S)
    if not em:return []
    body=em.group(2); out=[]
    for m in re.finditer(r'<paragraph\b[^>]*>.*?</paragraph>',body,re.S):
        block=m.group(0)
        pairs=[(int(a),int(b)) for a,b in re.findall(r'startOffset="(\d+)"\s+length="(\d+)"',block)]
        if pairs:
            out.append({'start':min(a for a,b in pairs),'end':max(a+b for a,b in pairs),'xml':block})
    return out


def _simple_paragraph(template, start, length):
    """Clone paragraph formatting but replace its internal field structure with one text run."""
    if not template:
        return f'<paragraph><content startOffset="{start}" length="{length}" /></paragraph>'
    op=re.match(r'<paragraph\b[^>]*>',template,re.S).group(0)
    # Adres satırları iki yana yaslanınca uzun adreslerde kelimeler arasına büyük boşluklar giriyor.
    # Yeni oluşturulan tüm paragraflar içinde adres satırlarının şablon stilini aşağıda ayrıca sola çekeceğiz.
    children=re.findall(r'<(?:content|field|space|tab)\b[^>]*/>',template,re.S)
    attrs=''
    if children:
        raw=children[0]
        raw=re.sub(r'\s+(?:startOffset|length)="\d+"','',raw)
        raw=re.sub(r'^<(?:content|field|space|tab)\b','<content',raw)
        raw=re.sub(r'\s*/>$','',raw)
        attrs=raw[len('<content'):]
    return op[:-1]+f'><content{attrs} startOffset="{start}" length="{length}" /></paragraph>'


def rebuild_region_paragraphs(xml, old_text, new_text, start_term, end_term, line_kind='party'):
    """Rebuild paragraph elements for a region whose text gained/changed paragraphs.
    This is essential in UDF: inserting '\\n' in CDATA alone does not create paragraph elements.
    """
    os=old_text.find(start_term)
    if os<0:return xml
    oe_candidates=[old_text.find(end_term,os+len(start_term))] if end_term else []
    oe=min([x for x in oe_candidates if x>=0] or [len(old_text)])
    ns=new_text.find(start_term)
    if ns<0:return xml
    ne_candidates=[new_text.find(end_term,ns+len(start_term))] if end_term else []
    ne=min([x for x in ne_candidates if x>=0] or [len(new_text)])

    blocks=_paragraph_blocks(xml)
    region=[b for b in blocks if b['start']>=ns and b['end']<=ne]
    if not region:return xml
    # Pick formatting templates from the old region.
    def txt(b):return old_text[b['start']:b['end']]
    heading_t=next((b['xml'] for b in region if 'KARŞI TARAF BİLGİLERİ' in txt(b)),region[0]['xml'])
    blank_t=next((b['xml'] for b in region if txt(b).strip()==''),region[0]['xml'])
    id_t=next((b['xml'] for b in region if re.search(r'(?:TC\s+Kimlik\s+No|Vergi\s+No)',txt(b),re.I)),region[-1]['xml'])
    name_t=next((b['xml'] for b in region if re.search(r'Adı\s+Soyadı|Unvanı|Ünvanı',txt(b),re.I)),id_t)
    addr_t=next((b['xml'] for b in region if re.search(r'^Adres\s*',txt(b),re.I)),id_t)
    proxy_t=next((b['xml'] for b in region if re.search(r'^Vekili\s*',txt(b),re.I)),id_t)

    new_region=new_text[ns:ne]
    lines=new_region.splitlines(True)
    if not lines:return xml
    generated=[]; pos=ns
    for line in lines:
        ln=len(line); stripped=line.strip()
        if not stripped: templ=blank_t
        elif stripped=='KARŞI TARAF BİLGİLERİ': templ=heading_t
        elif stripped.startswith('Diğer Taraf '): templ=id_t
        elif re.match(r'(?:TC\s+Kimlik\s+No|Vergi\s+No)\s*[:：]',stripped,re.I): templ=id_t
        elif re.match(r'(?:Adı\s+Soyadı|Adı\s+Soyadı\s*/\s*Unvanı)\s*[:：]',stripped,re.I): templ=name_t
        elif re.match(r'Adres\s*[:：]',stripped,re.I): templ=addr_t
        elif re.match(r'Vekili\s*[:：]',stripped,re.I): templ=proxy_t
        else: templ=id_t
        pxml=_simple_paragraph(templ,pos,ln)
        if re.match(r'Adres\s*[:：]', stripped, re.I):
            pxml=re.sub(r'\sAlignment="[^"]*"', ' Alignment="0"', pxml, count=1)
        generated.append(pxml); pos+=ln
    new_paras=''.join(generated)
    em=re.search(r'(<elements\b[^>]*>)(.*?)(</elements>)',xml,re.S)
    body=em.group(2)
    # Replace exactly the old region's paragraph blocks while leaving non-paragraph elements intact.
    first_start=region[0]['start']; last_end=region[-1]['end']
    indices=[]
    for m in re.finditer(r'<paragraph\b[^>]*>.*?</paragraph>',body,re.S):
        block=m.group(0); pairs=[(int(a),int(b)) for a,b in re.findall(r'startOffset="(\d+)"\s+length="(\d+)"',block)]
        if pairs:
            bs=min(a for a,b in pairs); be=max(a+b for a,b in pairs)
            if bs>=first_start and be<=last_end: indices.append((m.start(),m.end()))
    if not indices:return xml
    a,b=indices[0][0],indices[-1][1]
    body2=body[:a]+new_paras+body[b:]
    return xml[:em.start(2)]+body2+xml[em.end(2):]

def left_align_address_paragraphs(xml):
    """Adres alanlarının paragraf hizasını sola çeker; uzun adreslerde kelime aralıklarının açılmasını önler."""
    def repl(m):
        block=m.group(0)
        if re.search(r'fieldName="(?:basvurucuAdres|karsitarafAdres)"', block):
            if re.search(r'\sAlignment="[^"]*"', block):
                block=re.sub(r'\sAlignment="[^"]*"', ' Alignment="0"', block, count=1)
            else:
                block=block.replace('<paragraph ', '<paragraph Alignment="0" ', 1)
        return block
    return re.sub(r'<paragraph\b[^>]*>.*?</paragraph>', repl, xml, flags=re.S)

def build_udf(files,xml,old,new):
    # Offsetler build aşamasından önce güncellendi; burada tekrar güncelleme yapma.
    # Aksi halde yeni oluşturulan paragraph offsetleri ikinci kez kayar.
    xml=re.sub(r'(<content><!\[CDATA\[).*?(\]\]></content>)',lambda m:m.group(1)+new+m.group(2),xml,1,re.S)
    xml=left_align_address_paragraphs(xml)
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        for n,d in files.items():
            if n=='sign.sgn':continue
            z.writestr(n,xml.encode('utf-8') if n=='content.xml' else d)
    return out.getvalue()

TEMPLATES={
 'anlasma_son_tutanagi':('Anlaşma Son Tutanağı','anlasma_son_tutanagi.udf','ANLAŞMA'),
 'anlasmama_son_tutanagi':('Anlaşmama Son Tutanağı','anlasmama_son_tutanagi.udf','ANLAŞMAMA'),
 'anlasma_belgesi':('Anlaşma Tutanağı (Anlaşma Belgesi)','anlasma_belgesi.udf','ANLAŞMA BELGESİ')}
TEMPLATE_DIR=Path(__file__).resolve().parents[1]/'templates'/'udf'
# Sabit 3 şablonun hepsi "Son Tutanak" türündendir (belge oluşturma takibi/checklist için).
FIXED_TEMPLATE_DOC_KIND='son_tutanak'

DOC_KIND_LABELS={
    'son_tutanak':'Son Tutanak',
    'davet_mektubu':'Davet Mektubu',
    'ust_yazi_son_tutanak':'Üst Yazı – Son Tutanak',
    'ust_yazi_ucret_pusulasi':'Üst Yazı – Ücret Pusulası',
    'diğer':'Diğer',
    'diger':'Diğer',
}

def _infer_folder_template_doc_kind(path: Path) -> str:
    """Şablon dosyasının adından belirgin belge türünü çıkarır.
    Ücret Pusulası şablonları burada seçenek olarak sunulmaz; ayrı üretim akışı vardır.
    """
    raw=(path.stem or "").strip().lower()
    norm=re.sub(r'[\W_]+', ' ', raw, flags=re.UNICODE).strip()
    compact=norm.replace(" ","")
    if "davet" in compact or "davetiye" in compact:
        return "davet_mektubu"
    if ("ucret" in compact or "ücret" in compact) and ("ustyazi" in compact or "ust yaz" in norm or "üstyaz" in compact):
        return "ust_yazi_ucret_pusulasi"
    if "ustyazi" in compact or "üst yaz" in norm or "ust yaz" in norm:
        return "ust_yazi_son_tutanak"
    if "sontutanak" in compact or "anlasma" in compact or "anlasmama" in compact:
        return "son_tutanak"
    # Şablon klasöründeki tür seçimi belirgin değilse Diğer'e düşür.
    return "diger"

def discover_folder_templates():
    """templates/udf/sablonlar altındaki gerçek .udf şablonlarını tarar.
    Klasörün dışındaki yardımcı/eski UDF dosyalarını belge türü seçimine katmaz.
    Alt klasörler korunur; tüm gerçek şablonlar seçim listesinde görünür.
    """
    registry={}
    base=TEMPLATE_DIR/"sablonlar"
    if not base.exists():
        return registry
    def _decode_udf_escapes(text: str) -> str:
        def repl(m):
            try:
                return chr(int(m.group(1),16))
            except Exception:
                return m.group(0)
        return re.sub(r'[#_]?U([0-9A-Fa-f]{4})_?', repl, text or '')
    for f in sorted(base.rglob("*.udf")):
        if not f.is_file():
            continue
        stem=f.stem
        # Eski/yanlış oluşturulmuş Unicode-escape artıkları seçim listesine girmesin.
        if re.search(r'[#_]?U[0-9A-Fa-f]{4}', stem):
            continue
        doc_kind=_infer_folder_template_doc_kind(f)
        slug=re.sub(r'[^a-zA-Z0-9]+','_',stem).strip('_').lower()
        rel_slug=re.sub(r'[^a-zA-Z0-9]+','_',str(f.relative_to(base).with_suffix(''))).strip('_').lower()
        choice=f"folder__{doc_kind}__{rel_slug or slug}"
        label=_decode_udf_escapes(stem.replace('_',' ').replace('#','').strip())
        registry[choice]={'doc_kind':doc_kind,'path':f,'label':label}
    return registry

def template_bytes(choice):
    if choice=='custom':return None
    if choice not in TEMPLATES:raise ValueError('Geçersiz şablon seçimi.')
    p=TEMPLATE_DIR/TEMPLATES[choice][1]
    if not p.exists():raise ValueError('Seçilen hazır şablon sunucuda bulunamadı.')
    return p.read_bytes()

def standard_result(choice):return TEMPLATES.get(choice,('', '', ''))[2]

def form_state(form):
    values={k:str(form.get(k,'')).strip() for k,_ in FIELDS}
    values['dosyaTuru']=normalize_dosya_turu(values.get('dosyaTuru',''))
    if values['dosyaTuru'] and not values.get('uyusmazlik'): values['uyusmazlik']=values['dosyaTuru']
    # Taraf türü kullanıcıdan seçilmez: Vergi No varsa kurum, aksi halde T.C. varsa kişi.
    values['basvurucuTarafTuru']=('kontrol' if values.get('basvurucuVergiNo') and values.get('basvurucuTcKimlik') else ('kurum' if values.get('basvurucuVergiNo') else 'kisi'))
    respondents=[]
    for i in range(MAX_RESP):
        p={f:str(form.get(f'resp_{i}_{f}','')).strip() for f in RESP_FIELDS}
        if p.get('tax') and p.get('tc'): p['type']='kontrol'
        elif p.get('tax'): p['type']='kurum'
        else: p['type']='kisi'
        # NOT: 'exclude' RESP_FIELDS listesinde DEĞİL (kasıtlı) - RESP_FIELDS,
        # şablon/bracket fonksiyonlarının döngüyle bastığı gerçek belge alanlarını
        # temsil eder; 'exclude' yalnızca bilgi havuzu ekranında kullanılan bir
        # UI bayrağıdır (bkz. render_editor, main.py /build - belgeye yazılmadan
        # önce hariç tutulan taraflar filtrelenir).
        p['exclude']=bool(form.get(f'resp_{i}_exclude'))
        if any(v for k,v in p.items() if k not in ('type','exclude')):respondents.append(p)
    locked=set(str(x) for x in form.getlist('locked'))
    locked_resp=set(int(x) for x in form.getlist('locked_resp') if str(x).isdigit())
    return values,respondents,locked,locked_resp

def _norm_person_name(s):
    """Karşı taraf isim karşılaştırmasında kullanılan normalizasyon: birden
    fazla boşluğu tek boşluğa indirger ve casefold uygular. Böylece iki belge
    arasında OCR/yazım kaynaklı fazladan boşluk gibi ufak farklar aynı kişiyi
    farklı bir taraf olarak mükerrer eklemez."""
    return re.sub(r'\s+',' ',(s or '').strip()).casefold()

def merge_state(values,respondents,locked,locked_resp,new_values,new_resp):
    dropped=0
    for k in values:
        if k not in locked and new_values.get(k):values[k]=new_values[k]
    # Kilitli satırlar korunur; yeni belgede bulunan taraflar boş/unlocked satırlara eklenir.
    for i,p in enumerate(new_resp):
        target=None
        # Önce TC kimlik/vergi no ile eşleştir; isimdeki küçük yazım farklarına
        # (nokta, boşluk, unvan kısaltması vb.) karşı isim eşleştirmesinden daha
        # güvenilirdir. TC/Vergi No yoksa (veya eşleşme bulunamazsa) isimle denenir.
        p_tc=(p.get('tc') or '').strip(); p_tax=(p.get('tax') or '').strip()
        if p_tc or p_tax:
            for j,cur in enumerate(respondents):
                cur_tc=(cur.get('tc') or '').strip(); cur_tax=(cur.get('tax') or '').strip()
                if (p_tc and cur_tc and p_tc==cur_tc) or (p_tax and cur_tax and p_tax==cur_tax):
                    target=j;break
        # Aynı isim varsa onunla birleştir.
        if target is None and p.get('name'):
            for j,cur in enumerate(respondents):
                if _norm_person_name(cur.get('name'))==_norm_person_name(p['name']):target=j;break
        p['type']=('kontrol' if p.get('tax') and p.get('tc') else ('kurum' if p.get('tax') else 'kisi'))
        if target is None:
            for j,cur in enumerate(respondents):
                if j not in locked_resp and not cur.get('name'):target=j;break
        if target is None and len(respondents)<MAX_RESP:
            respondents.append({f:'' for f in RESP_FIELDS});target=len(respondents)-1
        if target is None:
            dropped+=1;continue
        if target in locked_resp:continue
        for f in RESP_FIELDS:
            if p.get(f):respondents[target][f]=p[f]
    return values,respondents,dropped

def respondent_body_block(template_text):
    starts=[m.start() for m in re.finditer(r'KARŞI TARAF BİLGİLERİ',template_text,re.I)]
    if not starts:return ''
    s=starts[0]; e=template_text.find('Arabuluculuk Konusu Uyuşmazlık',s)
    return template_text[s:e] if e>s else ''

def fill_respondent_block(block,p):
    typ=(p.get('type') or 'kisi').lower()
    id_label='Vergi No' if typ=='kurum' else 'TC Kimlik No'
    id_value=p.get('tax','') if typ=='kurum' else p.get('tc','')
    name_label='Adı Soyadı / Unvanı' if typ=='kurum' else 'Adı Soyadı'
    # Başlık satırları hariç mevcut ilk kimlik/adres/vekil satırlarını koruyarak sadece değerleri değiştir.
    out=block
    out=re.sub(r'(?:TC\s+Kimlik\s+No|Vergi\s+No|VKN|Vergi\s+Numarası)\s*[:：]\s*[^\n]*',
               f'{id_label}\t\t: {id_value}',out,count=1,flags=re.I)
    out=re.sub(r'(?:Adı\s+Soyadı|Adı\s+Soyadı\s*/\s*Unvanı|Unvanı|Ünvanı)\s*[:：]\s*[^\n]*',
               f'{name_label}\t\t: {p.get("name","")}',out,count=1,flags=re.I)
    out=re.sub(r'Adres\s*[:：]\s*[^\n]*',
               f'Adres\t\t: {p.get("address","")}',out,count=1,flags=re.I)
    out=re.sub(r'Vekili\s*[:：]\s*[^\n]*',
               f'Vekili\t\t: {p.get("proxy","")}',out,count=1,flags=re.I)
    # Telefon satırı varsa, yalnızca karşı tarafın telefonunu güncelle.
    if re.search(r'(?:Cep\s*Tel|Telefon\s+Numarası|Telefon)\s*[:：]',out,re.I):
        out=re.sub(r'(?:Cep\s*Tel|Telefon\s+Numarası|Telefon)\s*[:：]\s*[^\n]*',
                   f'Cep Tel\t\t: {p.get("phone","")}',out,count=1,flags=re.I)
    return out

def _find_section(text, starts, ends):
    positions=[text.find(t) for t in starts if text.find(t)>=0]
    s=min(positions) if positions else -1
    if s<0:return -1,-1
    endpos=[text.find(t,s+1) for t in ends if text.find(t,s+1)>=0]
    return s,(min(endpos) if endpos else len(text))

def _replace_all_occurrences(text, old, new):
    if not old or not new or old==new:return text
    return text.replace(old,new)

def set_parties_and_signatures(text,applicant,respondents,arb):
    # v13: Şablondaki eski isimleri, herhangi bir alanı değiştirmeden ÖNCE yakala.
    # Böylece anlatım metninde geçen Birsen SALMAN vb. isimler de yeni taraflarla değiştirilir.
    old_names_map = {}
    ss, ee = _find_section(text,
        ['BAŞVURU SAHİBİ BİLGİLERİ','BAŞVURUCU BİLGİLERİ','BAŞVURUCU'],
        ['KARŞI TARAF BİLGİLERİ','KARŞI TARAF'])
    if ss >= 0:
        old_app_name = first([r'(?:Adı\s+Soyadı|Adı\s+Soyadı\s*/\s*Unvanı|Unvanı|Ünvanı)\s*[:：]\s*([^\n]+)'], text[ss:ee])
        if old_app_name:
            old_names_map[old_app_name.strip()] = (applicant.get('name') or '').strip()
    rs, re_ = _find_section(text,
        ['KARŞI TARAF BİLGİLERİ','KARŞI TARAF'],
        ['Arabuluculuk Konusu Uyuşmazlık','UYUŞMAZLIK'])
    if rs >= 0:
        old_resp_names = re.findall(r'(?:Adı\s+Soyadı|Adı\s+Soyadı\s*/\s*Unvanı|Unvanı|Ünvanı)\s*[:：]\s*([^\n]+)', text[rs:re_], re.I)
        for old, newp in zip(old_resp_names, respondents):
            old = old.strip()
            new = (newp.get('name') or '').strip()
            if old:
                old_names_map[old] = new
    old_arb_name = ''
    as_, ae = _find_section(text,['ARABULUCU BİLGİLERİ','ARABULUCU'],
                             ['BAŞVURU SAHİBİ BİLGİLERİ','BAŞVURUCU BİLGİLERİ','BAŞVURUCU'])
    if as_ >= 0:
        old_arb_name = first([r'(?:ARABULUCU|Adı\s+Soyadı)\s*[:：]\s*([^\n]+)'], text[as_:ae]).strip()
        if old_arb_name:
            old_names_map[old_arb_name] = (arb.get('name') or '').strip()
    # 1) Başvurucu bölümündeki alanları doldur.
    s,e=_find_section(text,['BAŞVURU SAHİBİ BİLGİLERİ','BAŞVURUCU BİLGİLERİ','BAŞVURUCU'],
                      ['KARŞI TARAF BİLGİLERİ','KARŞI TARAF'])
    if s>=0:
        seg=text[s:e]
        typ=(applicant.get('type') or 'kisi').lower()
        id_label='Vergi No' if typ=='kurum' else 'TC Kimlik No'
        id_value=applicant.get('tax','') if typ=='kurum' else applicant.get('tc','')
        name_label='Adı Soyadı / Unvanı' if typ=='kurum' else 'Adı Soyadı'
        # NOT: Değer boş olsa bile satır güncellenir (boşaltılır) - aksi halde eski belgedeki
        # kalıntı değer görünmeye devam eder. "Yeni belgede bu alan çıkarılamadı" ile
        # "eski değeri koru" birbirine karıştırılmamalı.
        seg=re.sub(r'(?:TC\s+Kimlik\s+No|Vergi\s+No|VKN|Vergi\s+Numarası)\s*[:：]\s*[^\n]*',
                   f'{id_label}\t\t: {id_value}',seg,count=1,flags=re.I)
        seg=re.sub(r'(?:Adı\s+Soyadı|Adı\s+Soyadı\s*/\s*Unvanı|Unvanı|Ünvanı)\s*[:：]\s*[^\n]*',
                   f'{name_label}\t\t: {applicant.get("name","")}',seg,count=1,flags=re.I)
        # Telefonu özellikle 'Telefon Numarası' satırına yaz. Şablonda ayrıca
        # 'Cep Tel' alanı bulunabiliyor; önce Telefon Numarası, yoksa Cep Tel kullanılır.
        replacements=[
            (r'Adres\s*[:：]\s*[^\n]*', applicant.get('address','')),
            (r'Vekili\s*[:：]\s*[^\n]*', applicant.get('proxy','')),
            (r'Telefon\s+Numarası\s*[:：]\s*[^\n]*', applicant.get('phone','')),
            (r'E-Posta\s+Adresi\s*[:：]\s*[^\n]*', applicant.get('email',''))
        ]
        for pat,val in replacements:
            mm=re.search(pat,seg,re.I)
            if mm:
                line=mm.group(0); c=line.find(':')
                newline=line[:c+1]+' '+(val or '') if c>=0 else line
                seg=seg[:mm.start()]+newline+seg[mm.end():]
        # Telefon Numarası satırı yoksa, Cep Tel satırını kullan; böylece değer kaybolmaz.
        if not re.search(r'Telefon\s+Numarası\s*[:：]',seg,re.I):
            mm=re.search(r'Cep\s*Tel\s*[:：]\s*[^\n]*',seg,re.I)
            if mm:
                line=mm.group(0); c=line.find(':')
                newline=line[:c+1]+' '+(applicant.get('phone') or '') if c>=0 else line
                seg=seg[:mm.start()]+newline+seg[mm.end():]
        text=text[:s]+seg+text[e:]

    # 2) Eski başvurucu/arabulucu adını metnin gövdesinde yeni adla değiştir.
    if applicant.get('name'):
        # Yalnızca eski değeri alan etiketinden bul; yanlışlıkla başka kişi adlarını değiştirmemek için.
        ss,ee=_find_section(text,['BAŞVURU SAHİBİ BİLGİLERİ','BAŞVURUCU BİLGİLERİ','BAŞVURUCU'],
                            ['KARŞI TARAF BİLGİLERİ','KARŞI TARAF'])
        old_app=first([r'(?:Adı\s+Soyadı|Adı\s+Soyadı\s*/\s*Unvanı|Unvanı|Ünvanı)\s*[:：]\s*([^\n]+)'],text[ss:ee] if ss>=0 else '')
        if old_app and old_app.strip()!=applicant['name'].strip():
            text=text.replace(old_app.strip(),applicant['name'].strip())
    if arb.get('name'):
        ss,ee=_find_section(text,['ARABULUCU BİLGİLERİ','ARABULUCU'],
                            ['BAŞVURU SAHİBİ BİLGİLERİ','BAŞVURUCU BİLGİLERİ','BAŞVURUCU'])
        old_arb=first([r'ARABULUCU\s*[:：]\s*([^\n]+)',r'Adı\s+Soyadı\s*[:：]\s*([^\n]+)'],
                      text[ss:ee] if ss>=0 else '')
        if old_arb and old_arb.strip()!=arb['name'].strip():
            text=text.replace(old_arb.strip(),arb['name'].strip())

    # 3) Karşı taraf bölümünü tek üst başlık + birbirinden tamamen ayrı "Diğer Taraf N" blokları olarak kur.
    s,e=_find_section(text,['KARŞI TARAF BİLGİLERİ','KARŞI TARAF'],
                      ['Arabuluculuk Konusu Uyuşmazlık','UYUŞMAZLIK'])
    if s>=0 and e>s and respondents:
        original=text[s:e]
        heading='KARŞI TARAF BİLGİLERİ'
        # Şablondaki ilk tarafın alanlarının olduğu bölümü al.
        body=original[original.find(heading)+len(heading):]
        # İlk satırlarda gereksiz boşlukları korumak yerine her blok için kontrollü satır yapısı kullan.
        blocks=[]
        for i,p in enumerate(respondents[:MAX_RESP],1):
            typ=(p.get('type') or 'kisi').lower()
            id_label='Vergi No' if typ=='kurum' else 'TC Kimlik No'
            id_value=p.get('tax','') if typ=='kurum' else p.get('tc','')
            name_label='Adı Soyadı / Unvanı' if typ=='kurum' else 'Adı Soyadı'
            lines=[
                f'Diğer Taraf {i}',
                '',
                f'{id_label}\t\t: {id_value}',
                f'{name_label}\t\t: {p.get("name","")}',
                f'Adres\t\t: {p.get("address","")}',
                f'Vekili\t\t: {p.get("proxy","")}',
                f'Cep Tel\t\t: {p.get("phone","")}'
            ]
            if p.get('email'):
                lines.append(f'E-posta\t\t: {p.get("email","")}')
            blocks.append('\n'.join(lines))
        new_section=heading+'\n\n'+'\n\n'.join(blocks)+'\n\n\n'
        text=text[:s]+new_section+text[e:]

    # 4) Şablondaki eski başvurucu/karşı taraf isimlerini gövde metninde yeni taraf isimleriyle değiştir.
    # Eski karşı taraf adlarını, yeni adlarla eşleştirerek değiştir; her yeni taraf için aynı sayıda isim varsa sırayla kullan.
    # Bunun için bölümün eski halinden isimleri yeniden çıkarıyoruz.
    # Yeni bölümün dışında kalan metinde en azından şablondaki ilk karşı taraf adını ilk yeni tarafla değiştir.
    if respondents:
        # Yaygın şablonlarda ilk karşı taraf adı "Adı Soyadı" satırında bulunur.
        old_names=[]
        # Metnin anlatı kısmında, başlık sonrasındaki ilk isimleri yakala.
        rs=re.search(r'KARŞI TARAF BİLGİLERİ.*?(?:Arabuluculuk Konusu Uyuşmazlık)',text,re.I|re.S)
        if rs:
            old_names=[x.strip() for x in re.findall(r'(?:Adı\s+Soyadı|Adı\s+Soyadı\s*/\s*Unvanı|Unvanı|Ünvanı)\s*[:：]\s*([^\n]+)',rs.group(0),re.I) if x.strip()]
        # Şablonun eski adını bulmak için kayıtlı template dışındaki ilk uygun "Adı Soyadı" satırı yeterlidir.
        # Eğer blok yeni isimlerle değiştirildiyse burada eski isim kalmaz; bu nedenle ilk UDF örneğindeki tipik
        # anlatı kalıplarında "ile X" / "ile X vekili" gibi yerleri doğrudan yeni isimlerle değiştirmek için
        # old_names'ı bölüm değiştirmeden önce saklamak daha sağlıklıdır. Aşağıdaki genel dönüşüm, mevcut metindeki
        # yeni isimlerin zaten bulunduğu yerleri bozmaz.
        pass

    # 5) İmza bloğu.
    sig=text.find('İMZALAR')
    if sig>=0:
        prefix=text[:sig]
        lines=['İMZALAR','',
               f'Taraf 1        : {applicant.get("name","")}'
               +(f' - Vekili {applicant.get("proxy","")}' if applicant.get('proxy') else '')+
               '  (e-imza)','']
        for i,p in enumerate(respondents[:MAX_RESP],start=2):
            nm=p.get('name','').strip()
            if not nm:continue
            lines += [f'Taraf {i}        : {nm}'
                      +(f' - Vekili {p.get("proxy","")}' if p.get('proxy') else '')+
                      '  (e-imza)','']
        lines += [f'Arabulucu      : {arb.get("name","")}'
                  +(f' ({arb.get("sicil","")})' if arb.get("sicil") else '')+
                  ' (e-imza)','']
        text=prefix+'\n'.join(lines)+'\n'
    # v13: Belgenin anlatım bölümleri dahil olmak üzere eski isimleri yeni isimlerle değiştir.
    # Uzun isimleri önce ele alıp regex callback kullanıyoruz; böylece bir değişiklik diğerini etkilemez.
    replacements={k:v for k,v in old_names_map.items() if k and v and k != v}
    if replacements:
        pattern=re.compile('|'.join(re.escape(k) for k in sorted(replacements, key=len, reverse=True)))
        text=pattern.sub(lambda m: replacements[m.group(0)], text)
    return text

def replace_talep_in_narrative(text, talep):
    """Editördeki Talep kutusunu, son tutanaktaki anlatımda yer alan mevcut talep metninin yerine koyar."""
    talep=(talep or '').strip().strip('"“”')
    if not talep:
        return text

    # Anlaşmama şablonundaki tipik yapı:
    # "... Başvurucu ... arasında ... sözleşmesine konu [MEVCUT TALEP] hususunda talebi olduğunu ..."
    # Burada tırnakların biçimi şablondan şablona değişebildiği için tırnağa bağımlı değiliz.
    patterns=[
        r'(\bsözleşmesine\s+konu\s+)(.*?)(\s+hususunda\s+talebi\s+olduğunu\s+beyan\s+etmiştir)',
        r'(\bkonu\s+)(.*?)(\s+hususunda\s+talebi\s+olduğunu\s+beyan\s+etmiştir)',
        r'(\bkonu\s+)(.*?)(\s+talebi\s+olduğunu\s+beyan\s+etmiştir)',
    ]
    for pat in patterns:
        m=re.search(pat,text,re.I|re.S)
        if m:
            # Yeni talebin başına/sonuna tırnak eklemiyoruz.
            return text[:m.start(2)] + talep + text[m.end(2):]

    # Bazı şablonlarda talep doğrudan etiketli olabilir.
    m=re.search(r'(Talep(?:ler)?\s*[:：]\s*)([^\n]+)',text,re.I)
    if m:
        return text[:m.start(2)] + talep + text[m.end(2):]
    return text


def build_meeting_sentence(values, applicant, respondents):
    tarih=(values.get("gorusmeTarihi") or "").strip()
    saat=(values.get("gorusmeSaati") or "").strip()
    sekil=(values.get("gorusmeSekli") or "Telekonferans").strip().lower()
    arb=(applicant.get("_arb_name") or "").strip()
    parts=[]
    an=applicant.get("name","").strip()
    if an:
        s=f"başvurucu {an}"
        if applicant.get("proxy","").strip(): s+=f" vekili {applicant['proxy'].strip()}"
        parts.append(s)
    for p in respondents:
        n=p.get("name","").strip()
        if not n: continue
        s=n
        if p.get("proxy","").strip(): s+=f" vekili {p['proxy'].strip()}"
        parts.append(s)
    if len(parts)>=2: subject=parts[0]+" ile "+", ".join(parts[1:])
    elif parts: subject=parts[0]
    else: subject="taraflar"
    date_phrase=""
    if tarih and saat: date_phrase=f"{tarih} tarihinde saat {saat}'de"
    elif tarih: date_phrase=f"{tarih} tarihinde"
    elif saat: date_phrase=f"saat {saat}'de"
    if sekil.startswith("yüz"):
        addr=(values.get("gorusmeAdresi") or "").strip()
        tail=f"{date_phrase} {addr} adresinde yüz yüze görüşme gerçekleştirdiler." if addr else f"{date_phrase} yüz yüze görüşme gerçekleştirdiler."
    else:
        tail=f"{date_phrase} telekonferans yöntemiyle görüşme gerçekleştirdiler."
    return f"Arabulucu {arb} aracılığında; {subject} {tail}".strip()

def replace_meeting_paragraph(text, sentence):
    if not sentence: return text
    # NOT: 'Arabulucu\s+.*?' başlıktaki 'ARABULUCU\t: Ad Soyad' alanına da (case-insensitive) eşleşip
    # araya giren tüm taraf/dosya bilgilerini siliyordu. Başlık alanı her zaman ':' içerdiğinden,
    # ilk boşluk aralığında ':' olmamasını şart koşarak yalnızca gerçek anlatım cümlesini hedefliyoruz.
    pat=r"Arabulucu\s+[^:\n]*?aracılığında;.*?görüşme\s+gerçekleştirdiler\."
    m=re.search(pat,text,re.I|re.S)
    return text[:m.start()]+sentence+text[m.end():] if m else text

def final_legal_paragraph(values):
    kind=" ".join([values.get("dosyaTuru", ""), values.get("uyusmazlik", ""), values.get("uyusmazlikTuru", "")]).lower()
    if "iş" in kind or "işçilik" in kind or "iş hukuku" in kind:
        return "İşbu arabuluculuk son tutanağı ÜÇ SAYFA olarak 6325 sayılı Hukuk Uyuşmazlıklarında Arabuluculuk Kanunu m. 17 ve 7036 sayılı İş Mahkemeleri Kanunu m. 3 uyarınca hep birlikte imza altına alındı."
    if "ticari" in kind or "ticaret" in kind:
        return "İşbu arabuluculuk son tutanağı ÜÇ SAYFA olarak 6325 sayılı Hukuk Uyuşmazlıklarında Arabuluculuk Kanunu m. 17, m. 18/A ve 6102 sayılı Türk Ticaret Kanunu m. 5/A uyarınca hep birlikte imza altına alındı."
    if "tüketici" in kind:
        return "İşbu arabuluculuk son tutanağı ÜÇ SAYFA olarak 6325 sayılı Hukuk Uyuşmazlıklarında Arabuluculuk Kanunu m. 17, m. 18/A ve 6502 sayılı Tüketicinin Korunması Hakkındaki Kanunun m. 73/A uyarınca hep birlikte imza altına alındı."
    return "İşbu arabuluculuk son tutanağı ÜÇ SAYFA olarak 6325 sayılı Hukuk Uyuşmazlıklarında Arabuluculuk Kanunu m. 17, 18/B ve 7445 sayılı Kanunun m. 37 uyarınca imza altına alındı."

def replace_final_legal_paragraph(text, values):
    return re.sub(r"İşbu\s+arabuluculuk\s+son\s+tutanağı.*?imza\s+altına\s+alındı\.", final_legal_paragraph(values), text, count=1, flags=re.I|re.S)

def fill_general(text,values):
    # Şablonun etiketli alanlarını değiştir.
    patterns={
    'basvuruNo':r'BAŞVURU\s*NO\s*[:：]\s*[^\n]*','dosyaNo':r'DOSYA\s*NO\s*[:：]\s*[^\n]*',
    'arabulucuAdi':r'(?:ARABULUCU\s*[:：]|Adı\s+Soyadı\s*[:：])\s*[^\n]*',
    'arabulucuTc':r'(?:T\.?\s*C\.?\s*(?:KİMLİK\s+NUMARASI|Kimlik\s+No))\s*[:：]\s*[^\n]*',
    'arabulucuSicil':r'(?:ARB\.?\s*SİCİL\s+NUMARASI|Arb\.?\s*Sicil\s*No)\s*[:：]\s*[^\n]*',
    'arabulucuAdres':r'(?:ADRESİ|Adresi)\s*[:：]\s*[^\n]*',
    'uyusmazlik':r'Arabuluculuk\s+Konusu\s+Uyuşmazlık\s*[:：]\s*[^\n]*',
    'talep':r'Talep(?:ler)?\s*[:：]\s*[^\n]*',
    'baslangicTarihi':r'Arabuluculuk\s+Sürecinin\s+Başladığı\s+Tarih\s*[:：]\s*[^\n]*',
    'bitisTarihi':r'Arabuluculuk\s+Sürecinin\s+Bittiği\s+Tarih\s*[:：]\s*[^\n]*',
    'duzenlemeYeri':r'Son\s+Tutanağın\s+Düzenlendiği\s+Yer\s*[:：]\s*[^\n]*',
    'duzenlemeTarihi':r'Son\s+Tutanağın\s+Düzenlendiği\s+Tarih\s*[:：]\s*[^\n]*',
    'sonuc':r'Arabuluculuk\s+Sonucu\s*[:：]\s*[^\n]*'}
    labels={'basvuruNo':'BAŞVURU NO','dosyaNo':'DOSYA  NO','arabulucuAdi':'ARABULUCU','arabulucuTc':'T.C KİMLİK NUMARASI','arabulucuSicil':'ARB. SİCİL NUMARASI','arabulucuAdres':'ADRESİ','uyusmazlik':'Arabuluculuk Konusu Uyuşmazlık','talep':'Talep','baslangicTarihi':'Arabuluculuk Sürecinin Başladığı Tarih','bitisTarihi':'Arabuluculuk Sürecinin Bittiği Tarih','duzenlemeYeri':'Son Tutanağın Düzenlendiği Yer','duzenlemeTarihi':'Son Tutanağın Düzenlendiği Tarih','sonuc':'Arabuluculuk Sonucu'}
    # "Arabuluculuk Konusu Uyuşmazlık" alanına yazılacak esas değer: Dosya Türü kutucuğu esas alınır.
    # Uyuşmazlık kutucuğu yalnızca kontrol/karşılaştırma amaçlıdır ve belgeye yazılmaz.
    # Uyuşmazlık Türü doluysa, esas değerin yanına parantez içinde eklenir.
    dosya_turu=(values.get('dosyaTuru') or '').strip()
    uyusmazlik_turu=(values.get('uyusmazlikTuru') or '').strip()
    base=dosya_turu or (values.get('uyusmazlik') or '').strip()
    effective_uyusmazlik=f"{base} ({uyusmazlik_turu})" if base and uyusmazlik_turu else base
    for k,p in patterns.items():
        val=effective_uyusmazlik if k=='uyusmazlik' else values.get(k)
        # NOT: Değer boş olsa bile alan güncellenir (boşaltılır) - "sonuc" hariç, o zaten
        # main.py'de şablon varsayılanıyla önceden dolduruluyor. Diğerlerinde boş kalmak,
        # eski belgeden kalıntı bir değer göstermekten daha doğru.
        m=re.search(p,text,re.I)
        if not m:continue
        # Preserve label and replace after colon.
        line=text[m.start():m.end()]
        colon=line.find(':')
        if colon>=0: line=line[:colon+1]+' '+(val or '')
        text=text[:m.start()]+line+text[m.end():]
    return text

def render_editor(filename,values,respondents,locked=set(),locked_resp=set(),message='',custom_templates=None,notices=None):
    groups=[('Dosya Bilgileri',['basvuruNo','dosyaNo']),
            ('Arabulucu',['arabulucuAdi','arabulucuTc','arabulucuSicil','arabulucuAdres','arabulucuTelefon','arabulucuEposta']),
            ('Uyuşmazlık / Süreç Bilgileri',['dosyaTuru','uyusmazlik','uyusmazlikTuru','talep','baslangicTarihi','bitisTarihi','duzenlemeYeri','duzenlemeTarihi','sonuc']),
            ('Görüşme',['gorusmeSekli','gorusmeTarihi','gorusmeSaati','gorusmeAdresi']),
            ('Harcama Pusulası',['daireBilgisi'])]
    # Belgeye hangi alanın esas alındığını netleştiren kısa ipuçları.
    HINTS={
        'dosyaTuru':'Son tutanağa "Arabuluculuk Konusu Uyuşmazlık" olarak esas bu alan yazılır.',
        'uyusmazlik':'Yalnızca kontrol/karşılaştırma amaçlıdır; belgeye yazılmaz (Dosya Türü esas alınır).',
        'uyusmazlikTuru':'Doluysa Dosya Türü değerinin yanına parantez içinde eklenir.',
    }
    def field(k):
        lock='checked' if k in locked else ''
        v=escape(values.get(k,''),quote=True)
        if k=='gorusmeSekli':
            sel=(values.get(k) or 'Telekonferans').strip().lower()
            el=f'<select name="{k}"><option value="Telekonferans" {"selected" if sel=="telekonferans" else ""}>Telekonferans</option><option value="Yüz yüze" {"selected" if sel.startswith("yüz") else ""}>Yüz yüze</option></select>'
        elif k in ('arabulucuAdres','basvurucuAdres','uyusmazlik','talep','gorusmeAdresi','sonuc'):
            el=f'<textarea name="{k}">{v}</textarea>'
        else:
            el=f'<input name="{k}" value="{v}">'
        hint=f'<p class="hint">{escape(HINTS[k])}</p>' if k in HINTS else ''
        return f'<div class="field"><label>{escape(LABELS[k])}</label>{el}{hint}<label class="lock"><input type="checkbox" name="locked" value="{k}" {lock}> 🔒 Sabitle</label></div>'
    def section_card(title, inner, filled, total, open_default=False, extra_class=''):
        state=' open' if open_default else ''
        badge = f'<span class="section-status">✓ {filled}/{total}</span>' if total and filled==total else (f'<span class="section-status">⚠ {filled}/{total}</span>' if filled else f'<span class="section-status">○ 0/{total}</span>')
        return f'<details class="card info-section {extra_class}"{state}><summary><span>{escape(title)}</span>{badge}</summary><div class="section-body">{inner}</div></details>'
    cards=''
    def make_fields(ks): return ''.join(field(k) for k in ks)
    def filled_count(ks): return sum(1 for k in ks if str(values.get(k,'')).strip())
    atax=escape(values.get('basvurucuVergiNo',''),quote=True); atc=escape(values.get('basvurucuTcKimlik',''),quote=True)
    if values.get('basvurucuVergiNo') and values.get('basvurucuTcKimlik'): type_note='⚠️ T.C. Kimlik No ve Vergi No birlikte dolu; lütfen kontrol edin.'
    elif values.get('basvurucuVergiNo'): type_note='Firma / kurum olarak algılandı (Vergi No mevcut).'
    elif values.get('basvurucuTcKimlik'): type_note='Gerçek kişi olarak algılandı (T.C. Kimlik No mevcut).'
    else: type_note='Taraf türü numara bilgisine göre otomatik belirlenecek.'
    applicant_keys=['basvurucuAdiSoyadi','basvurucuAdres','basvurucuVekili','basvurucuVekilTelefon','basvurucuTelefon','basvurucuEposta','basvurucuTcKimlik','basvurucuVergiNo']
    applicant_inner=(f'<label>T.C. Kimlik No</label><input name="basvurucuTcKimlik" value="{atc}"><label>Vergi No</label><input name="basvurucuVergiNo" value="{atax}"><p class="hint">{escape(type_note)}</p>'+make_fields(['basvurucuAdiSoyadi','basvurucuAdres','basvurucuVekili','basvurucuVekilTelefon','basvurucuTelefon','basvurucuEposta']))
    cards+=section_card('Başvurucu Bilgileri',applicant_inner,filled_count(applicant_keys),len(applicant_keys),False)
    for title,ks in groups: cards+=section_card(title,make_fields(ks),filled_count(ks),len(ks),False)

    resp_html=''
    count=max(len(respondents),1)
    for i in range(count):
        p=respondents[i] if i<len(respondents) else {f:'' for f in RESP_FIELDS}
        lk='checked' if i in locked_resp else ''
        exc='checked' if p.get('exclude') else ''
        h=(f'<div class="party-head"><h3>Karşı Taraf {i+1}</h3>'
           f'<label class="lock"><input type="checkbox" name="locked_resp" value="{i}" {lk}> 🔒 Bu tarafı sabitle</label>'
           f'<button type="button" class="danger" onclick="removeRespondent(this)">🗑 Bu Tarafı Sil</button></div>'
           f'<label class="lock exclude-toggle"><input type="checkbox" name="resp_{i}_exclude" value="1" {exc}> '
           f'🚫 Bu tarafı tutanağa dahil etme (bilgi havuzunda kalır, üretilecek belgeye yazılmaz)</label>')
        body=''
        for f in RESP_FIELDS:
            v=escape(p.get(f,''),quote=True)
            if f=='type':
                if p.get('tax') and p.get('tc'): note='⚠️ T.C. Kimlik No ve Vergi No birlikte dolu; kontrol edin.'
                elif p.get('tax'): note='Firma / kurum (Vergi No mevcut).'
                elif p.get('tc'): note='Gerçek kişi (T.C. Kimlik No mevcut).'
                else: note='Tür numara bilgisine göre otomatik belirlenecek.'
                el=f'<p class="hint">{escape(note)}</p>'
            elif f=='address':
                el=f'<textarea name="resp_{i}_{f}">{v}</textarea>'
            else:
                el=f'<input name="resp_{i}_{f}" value="{v}">'
            body+=f'<div class="party"><label>{escape(RESP_LABELS[f])}</label>{el}</div>'
        resp_html+=f'<details class="card respondent-card"><summary><span>Karşı Taraf {i+1}</span><span class="section-status">{"✓ Dolu" if p.get("name") else "○ Boş"}{" · 🚫 Hariç" if p.get("exclude") else ""}</span></summary><div class="section-body">{h}{body}</div></details>'

    # Ücret Pusulası ayrı üretim akışıdır; şablon seçiminde gösterilmez.
    fixed_choices=[]
    for k,v in TEMPLATES.items():
        fixed_choices.append(f'<option value="{escape(k)}">{escape(v[0])}</option>')
    options=''.join(fixed_choices)
    options+=''.join(
        f'<option value="{escape(choice)}">{escape(t["label"])} '
        f'({escape(DOC_KIND_LABELS.get(t["doc_kind"], "Diğer"))})</option>'
        for choice,t in discover_folder_templates().items()
        if t["doc_kind"] != "ucret_pusulasi"
    )
    options+=''.join(
        f'<option value="tpl_{escape(t["id"])}">{escape(t["name"])} '
        f'({escape(DOC_KIND_LABELS.get(t.get("doc_kind") or "diger", "Diğer"))})</option>'
        for t in (custom_templates or [])
    )
    msg=f'<div class="ok">{escape(message)}</div>' if message else ''
    notice_html=''
    if notices:
        items=''.join(f'<li>{escape(n)}</li>' for n in notices)
        notice_html=f'<div class="parse-warn"><b>⚠️ Ayrıştırma uyarısı:</b> Belgede aşağıdaki bölümler beklenen biçimde bulunamadı; ilgili alanları lütfen elle kontrol edin.<ul>{items}</ul></div>'
    nav='<p><a href="/"><button type="button" class="secondary">← Ana Sayfa</button></a> <a href="/templates/"><button type="button" class="secondary">Şablonlarım</button></a></p>'
    html='''<!doctype html><html lang="tr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Son Tutanak Bilgi Havuzu</title><style>
*{box-sizing:border-box}body{font-family:Arial,sans-serif;background:#f2f5f8;margin:0;color:#20252b}.wrap{max-width:1100px;margin:25px auto;padding:0 16px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:18px}.card{background:#fff;border-radius:16px;padding:22px;margin-bottom:18px;box-shadow:0 4px 20px #0001}label{display:block;font-weight:bold;margin-top:10px}input,textarea,select{width:100%;padding:10px;margin-top:5px;border:1px solid #ccd3db;border-radius:8px;font:inherit}textarea{min-height:70px;resize:vertical}button{background:#1769e0;color:white;border:0;border-radius:9px;padding:13px 18px;font-weight:bold;cursor:pointer;margin-top:12px}.secondary{background:#44515f}.lock{font-size:12px!important;font-weight:normal!important;color:#53606b}.lock input{width:auto}.info-section>summary,.respondent-card>summary{list-style:none;cursor:pointer;display:flex;justify-content:space-between;align-items:center;gap:10px;font-size:18px;font-weight:bold}.info-section>summary::-webkit-details-marker,.respondent-card>summary::-webkit-details-marker{display:none}.info-section>summary:before,.respondent-card>summary:before{content:'▶';font-size:12px;margin-right:8px}.info-section[open]>summary:before,.respondent-card[open]>summary:before{content:'▼'}.section-status{font-size:12px;font-weight:normal;color:#53606b;white-space:nowrap}.section-body{padding-top:12px}.pool-controls{display:flex;gap:8px;flex-wrap:wrap;margin:10px 0 16px}.pool-controls button{margin-top:0}.party-head{display:flex;justify-content:space-between;gap:10px;align-items:center;flex-wrap:wrap}.party-head h3{margin:0}.danger{background:#c0392b;padding:6px 12px;font-size:12px;margin:0}.exclude-toggle{background:#fff7ed;border:1px solid #fdba74;border-radius:8px;padding:8px 10px;margin-top:8px}.ok{background:#eaf8ee;color:#176b35;padding:12px;border-radius:8px;margin-bottom:15px}.parse-warn{background:#fff7ed;color:#7c2d12;border:1px solid #fdba74;padding:12px 14px;border-radius:8px;margin-bottom:15px;font-size:14px}.parse-warn ul{margin:6px 0 0;padding-left:20px}.hint{color:#65717d;font-size:13px}@media(max-width:800px){.grid{grid-template-columns:1fr}.party-head{display:block}}
</style></head><body><div class="wrap"><h1>Son Tutanak Bilgi Havuzu</h1>{nav}<div class="pool-controls"><button type="button" class="secondary" onclick="setAllSections(true)">▼ Tümünü Aç</button><button type="button" class="secondary" onclick="setAllSections(false)">▶ Tümünü Kapat</button></div><p class="hint">Kaynak belge: __FILENAME__</p>__NOTICES__ __MSG__<form id="mainform" action="/build" method="post" enctype="multipart/form-data"><div class="grid"><div>__CARDS__<section class="card"><h2>Karşı Taraflar</h2><p class="hint">Bir veya birden fazla karşı taraf ekleyebilirsiniz.</p><div id="respondents">__RESP__</div><button type="button" class="secondary" onclick="addRespondent()">+ Karşı Taraf Ekle</button></section></div><div><section class="card"><h2>Belgeleri Birleştir</h2><p class="hint">İlk belgedeki kontrol ettiğiniz alanları 🔒 sabitleyin. Yeni bir UDF yüklediğinizde sabit alanlar değişmez; diğer alanlar yeni belgeden tamamlanır.</p><input type="file" name="merge_file" accept=".udf"><button type="submit" formaction="/merge" class="secondary">Belgeyi Bilgi Havuzuna Ekle</button></section><section class="card"><h2>Son Tutanağı Oluştur</h2><label>Belge türü</label><select name="template_choice">__OPTIONS__<option value="custom">Kendi UDF şablonumu kullan</option></select><div id="custom"><label>Özel Son Tutanak UDF</label><input type="file" name="custom_file" accept=".udf"></div><button type="submit">✓ Son Tutanağı Oluştur</button></section><section class="card"><h2>Harcama Pusulası</h2><p class="hint">Bu ekrandaki Dosya Türü, Karşı Taraflar ve Arabulucu bilgilerini kullanarak, IBAN'ınızı (Profilim) da ekleyerek Harcama Pusulası üretir.</p><button type="submit" formaction="/harcama-pusulasi/build" class="secondary">📄 Harcama Pusulası Oluştur</button></section><section class="card"><h2>📅 Takvim ve Görevler</h2><p class="hint">Başvurucu Adı Soyadı, Dosya Türü ve Süreç Başlangıç Tarihi doldurulduysa bu dosya için otomatik süre hatırlatıcıları ve 6 standart görev oluşturur (zaten oluşturulmuşsa tekrar oluşturmaz, sadece günceller).</p><button type="submit" formaction="/case/schedule" class="secondary">📅 Takvime Ekle / Görevleri Oluştur</button></section><section class="card"><h2>Bilgi Havuzu</h2><p class="hint">Kilitli alanlar yeni belgelerle değiştirilmez. Yeni belge yükleyerek eksik alanları tamamlayabilirsiniz.</p><button type="button" class="secondary" onclick="lockAll()">🔒 Dolu Alanların Tümünü Sabitle</button></section></div></div></form></div><script>
let rc=__COUNT__;function addRespondent(){if(rc>=10)return;const root=document.getElementById('respondents');const i=rc++;const d=document.createElement('section');d.className='card respondent-card';d.innerHTML='<div class="party-head"><h3>Karşı Taraf '+(i+1)+'</h3><label class="lock"><input type="checkbox" name="locked_resp" value="'+i+'"> 🔒 Bu tarafı sabitle</label><button type="button" class="danger" onclick="removeRespondent(this)">🗑 Bu Tarafı Sil</button></div><label class="lock exclude-toggle"><input type="checkbox" name="resp_'+i+'_exclude" value="1"> 🚫 Bu tarafı tutanağa dahil etme (bilgi havuzunda kalır, üretilecek belgeye yazılmaz)</label><div class="party"><label>Taraf Türü</label><select name="resp_'+i+'_type"><option value="kisi">Kişi</option><option value="kurum">Kurum / Şirket</option></select></div><div class="party"><label>T.C. Kimlik No</label><input name="resp_'+i+'_tc"></div><div class="party"><label>Vergi No</label><input name="resp_'+i+'_tax"></div><div class="party"><label>Adı Soyadı / Unvanı</label><input name="resp_'+i+'_name"></div><div class="party"><label>Adres</label><textarea name="resp_'+i+'_address"></textarea></div><div class="party"><label>Vekili</label><input name="resp_'+i+'_proxy"></div><div class="party"><label>Telefon</label><input name="resp_'+i+'_phone"></div><div class="party"><label>E-posta</label><input name="resp_'+i+'_email"></div>';root.appendChild(d)}
function removeRespondent(btn){const card=btn.closest('.respondent-card');if(card)card.remove()}
function setAllSections(open){document.querySelectorAll('details.info-section,details.respondent-card').forEach(function(d){d.open=open})}
function lockAll(){document.querySelectorAll('input,textarea').forEach(function(x){if(x.name && x.type!=='file' && !x.name.startsWith('locked') && x.value.trim() && !x.parentElement.querySelector('input[name=locked][value=\"'+x.name+'\"]')){let l=document.createElement('input');l.type='checkbox';l.name='locked';l.value=x.name;l.checked=true;x.parentElement.appendChild(l)}})}
function toggleMeeting(){const s=document.querySelector('select[name=gorusmeSekli]');const f=document.querySelector('textarea[name=gorusmeAdresi]');if(!s||!f)return;f.parentElement.style.display=s.value==='Yüz yüze'?'block':'none';}document.addEventListener('change',e=>{if(e.target.name==='gorusmeSekli')toggleMeeting()});document.addEventListener('DOMContentLoaded',toggleMeeting);</script></body></html>'''
    return html.replace('{nav}',nav).replace('__FILENAME__',escape(filename)).replace('__NOTICES__',notice_html).replace('__MSG__',msg).replace('__CARDS__',cards).replace('__RESP__',resp_html).replace('__OPTIONS__',options).replace('__COUNT__',str(len(respondents)))

def inject_case_binding(html, case_id):
    """render_editor() çıktısını bir case_id'ye bağlar: /build, /merge gibi
    işlemlerin ilgili dosyayı (case) güncellemesini sağlayan gizli alanı ekler
    ve dosyayı belge oluşturmadan doğrudan kaydetmek için bir buton ekler."""
    html = html.replace(
        '<form id="mainform" action="/build" method="post" enctype="multipart/form-data">',
        '<form id="mainform" action="/build" method="post" enctype="multipart/form-data">'
        f'<input type="hidden" name="case_id" value="{escape(str(case_id),quote=True)}">',
        1)
    html = html.replace(
        '<button type="button" class="secondary" onclick="lockAll()">🔒 Dolu Alanların Tümünü Sabitle</button>',
        '<button type="button" class="secondary" onclick="lockAll()">🔒 Dolu Alanların Tümünü Sabitle</button>'
        f'<button type="submit" formaction="/files/case/{escape(str(case_id),quote=True)}/save" class="secondary">💾 Değişiklikleri Kaydet (belge oluşturmadan)</button>',
        1)
    return html


def extract_any_source(filename, data):
    if is_udf_filename(filename):
        _, text, _ = read_udf(data)
        return udf_plain(text), "udf"
    return extract_source_text(filename, data), "ocr"
