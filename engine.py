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
('arabulucuSicil','Arabulucu Sicil No'),('arabulucuAdres','Arabulucu Adres'),
('basvurucuTarafTuru','Başvurucu Taraf Türü'),('basvurucuVergiNo','Başvurucu Vergi No'),('basvurucuTcKimlik','Başvurucu T.C. Kimlik No'),('basvurucuAdiSoyadi','Başvurucu Adı Soyadı'),
('basvurucuAdres','Başvurucu Adres'),('basvurucuVekili','Başvurucu Vekili'),
('basvurucuTelefon','Başvurucu Telefon'),('basvurucuEposta','Başvurucu E-Posta'),
('dosyaTuru','Dosya Türü'),('uyusmazlik','Arabuluculuk Konusu Uyuşmazlık'),('uyusmazlikTuru','Uyuşmazlık Türü'),('talep','Talep'),
('baslangicTarihi','Süreç Başlangıç Tarihi'),('bitisTarihi','Süreç Bitiş Tarihi'),
('duzenlemeYeri','Tutanak Düzenleme Yeri'),('duzenlemeTarihi','Tutanak Düzenleme Tarihi'),
('daireBilgisi','Dairesi (Harcama Pusulası için, örn. ANKARA CUMHURİYET BAŞSAVCILIĞI)'),
('sonuc','Sonuç'),('gorusmeSekli','Görüşme Şekli'),('gorusmeTarihi','Görüşme Tarihi'),('gorusmeSaati','Görüşme Saati'),('gorusmeAdresi','Görüşme Adresi')]
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
    'arabulucuadi':'arabulucuAdi','arabulucuadisoyadi':'arabulucuAdi','arabulucu':'arabulucuAdi',
    'arabulucutc':'arabulucuTc','arabulucutckimlikno':'arabulucuTc','arabulucutckimliknumarasi':'arabulucuTc',
    'arabulucusicil':'arabulucuSicil','arabulucusicilno':'arabulucuSicil','arbsicilno':'arabulucuSicil','arbsicilnumarasi':'arabulucuSicil',
    'arabulucuadres':'arabulucuAdres','arabulucubüroadresi':'arabulucuAdres','arabulucuburoadresi':'arabulucuAdres',
    'basvurucuadisoyadi':'basvurucuAdiSoyadi','basvurucuadi':'basvurucuAdiSoyadi','basvurucu':'basvurucuAdiSoyadi',
    'basvurucuadres':'basvurucuAdres',
    'basvurucuvekili':'basvurucuVekili','basvurucuvekil':'basvurucuVekili',
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

_RESP_PREFIX_RE = re.compile(r'^(?:karsitaraf|digertaraf)(\d+)(.+)$')

# Kutucuklardan gelmeyen, sistem tarafından otomatik hesaplanan köşeli parantez ifadeleri.
# Örn: [Bugün()], [tüm taraflar], [taraf sayısı].
COMPUTED_BRACKETS = {
    'bugun': lambda values,respondents: date.today().strftime('%d/%m/%Y'),
    'bugunuuntarihi': lambda values,respondents: date.today().strftime('%d/%m/%Y'),
    'tarih': lambda values,respondents: date.today().strftime('%d/%m/%Y'),
    'gununtarihi': lambda values,respondents: date.today().strftime('%d/%m/%Y'),
    # Başvurucu hariç, tüm karşı tarafların adları sırasıyla ve Türkçe liste biçiminde ("A, B ve C").
    'tumtaraflar': lambda values,respondents: join_turkish_list([(r.get('name') or '').strip() for r in respondents]),
    # Başvurucu dahil TOPLAM taraf sayısı, rakam + Türkçe yazıyla: "3 (üç)".
    'tarafsayisi': lambda values,respondents: (lambda t: f"{t} ({turkce_sayi_yazi(t)})")(1+len(respondents)),
}
COMPUTED_LABELS = {
    'bugun': "Bugünün Tarihi (otomatik doldurulur)",
    'tarih': "Bugünün Tarihi (otomatik doldurulur)",
    'tumtaraflar': "Tüm Karşı Tarafların Adları (otomatik, başvurucu hariç)",
    'tarafsayisi': "Toplam Taraf Sayısı (otomatik, rakam + yazıyla)",
}

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

PATTERNS={
'basvuruNo':[r'BAŞVURU\s*NO\s*[:：]\s*([^\n<]{1,100})',r'Başvuru\s*(?:Numarası|No)\s*[:：]\s*([^\n<]{1,100})'],
'dosyaNo':[r'DOSYA\s*NO\s*[:：]\s*([^\n<]{1,100})',r'Dosya\s*(?:Numarası|No)\s*[:：]\s*([^\n<]{1,100})'],
'arabulucuAdi':[r'ARABULUCU\s*[:：]\s*([^\n<]{2,150})',r'Adı\s+Soyadı\s*[:：]\s*([^\n<]{2,150})'],
'arabulucuTc':[r'T\.?\s*C\.?\s*(?:KİMLİK\s+NUMARASI|Kimlik\s+No)\s*[:：]\s*(\d{8,20})'],
'arabulucuSicil':[r'(?:ARB\.?\s*SİCİL\s+NUMARASI|Arb\.?\s*Sicil\s*No)\s*[:：]\s*([^\n<]{1,80})'],
'arabulucuAdres':[r'(?:ARABULUCU\s+BİLGİLERİ.*?Adresi|ADRESİ|Adresi)\s*[:：]\s*([^\n<]{5,300})'],
'basvurucuTcKimlik':[r'TC\s+Kimlik\s+No\s*[:：]\s*(\d{8,20})'],
'basvurucuAdiSoyadi':[r'Adı\s+Soyadı\s*[:：]\s*([^\n<]{2,200})'],
'basvurucuAdres':[r'Adres\s*[:：]\s*([^\n<]{2,400})'],
'basvurucuVekili':[r'Vekili\s*[:：]\s*([^\n<]{1,250})'],
'basvurucuTelefon':[r'(?:Cep\s*Tel|Telefon\s+Numarası|Telefon)\s*[:：]\s*([^\n<]{3,150})'],
'basvurucuEposta':[r'E-Posta\s+Adresi\s*[:：]\s*([^\n<]{3,250})'],
'dosyaTuru':[r'DOSYA\s*T[ÜU]R[ÜU]\s*[:：]\s*([^\n<]{2,300})'],
'uyusmazlik':[r'Arabuluculuk\s+Konusu\s+Uyuşmazlık\s*[:：]\s*([^\n<]{2,500})',r'Uyuşmazlık\s*(?:Türü|Konusu)?\s*[:：]\s*([^\n<]{2,500})'],
'talep':[r'Talep(?:ler)?\s*[:：]\s*([^\n<]{2,1000})',r'Talep\s+Konusu\s*[:：]\s*([^\n<]{2,1000})'],
'baslangicTarihi':[r'Arabuluculuk\s+Sürecinin\s+Başladığı\s+Tarih\s*[:：]\s*([^\n<]{2,80})'],
'bitisTarihi':[r'Arabuluculuk\s+Sürecinin\s+Bittiği\s+Tarih\s*[:：]\s*([^\n<]{2,80})'],
'duzenlemeYeri':[r'Son\s+Tutanağın\s+Düzenlendiği\s+Yer\s*[:：]\s*([^\n<]{2,120})'],
'duzenlemeTarihi':[r'Son\s+Tutanağın\s+Düzenlendiği\s+Tarih\s*[:：]\s*([^\n<]{2,80})'],
'sonuc':[r'Arabuluculuk\s+Sonucu\s*[:：]\s*([^\n<]{2,300})']}


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
    return v


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

def first(patterns,text,flags=re.I):
    for p in patterns:
        m=re.search(p,text,flags)
        if m:
            v=m.group(1).strip(' \t\r\n:;,-')
            if v:return v
    return ''

def section(text,start_terms,end_terms):
    positions=[text.find(t) for t in start_terms if text.find(t)>=0]
    s=min(positions) if positions else 0
    ends=[text.find(t,s+1) for t in end_terms]
    e=min([x for x in ends if x>=0] or [len(text)])
    return text[s:e]

def party_values(seg):
    tax=first([r'(?:Vergi\s*(?:Kimlik\s*)?No|VKN|Vergi\s*Numarası)\s*[:：]\s*([0-9]{8,20})'],seg)
    tc=first([r'TC\s+Kimlik\s+No\s*[:：]\s*(\d{8,20})'],seg)
    name=first([r'(?:Adı\s+Soyadı|Unvanı|Ünvanı)\s*[:：]\s*([^\n<]{2,250})'],seg)
    # Kurumlarda çoğu başvuru formunda "Şirket Unvanı / Kurum Adı" gibi etiketler kullanılabilir.
    if not name:
        name=first([r'(?:Şirket\s+Unvanı|Kurum\s+Adı|Firma\s+Adı)\s*[:：]\s*([^\n<]{2,250})'],seg)
    return {
        'type':'kurum' if tax and not tc else 'kisi',
        'tc':tc,'tax':tax,'name':name,
        'address':first([r'Adres\s*[:：]\s*([^\n<]{2,400})'],seg),
        'proxy':first([r'Vekili\s*[:：]\s*([^\n<]{1,250})'],seg),
        'phone':first([r'(?:Cep\s*Tel|Telefon\s+Numarası|Telefon)\s*[:：]\s*([^\n<]{3,150})'],seg),
        'email':first([r'E-Posta\s+Adresi\s*[:：]\s*([^\n<]{3,250})'],seg)
    }

def extract_respondents(ptext):
    seg=section(ptext,['KARŞI TARAF BİLGİLERİ','KARŞI TARAF'],['Arabuluculuk Konusu Uyuşmazlık','UYUŞMAZLIK','TALEP','Arabuluculuk Sürecinin'])
    # İlk yöntem: tekrar eden "Adı Soyadı" etiketlerine göre bloklara ayır.
    matches=list(re.finditer(r'Adı\s+Soyadı\s*[:：]',seg,re.I))
    parties=[]
    for i,m in enumerate(matches[:MAX_RESP]):
        starts=[seg.rfind('\nTC Kimlik No',0,m.start()),seg.rfind('\nVergi No',0,m.start()),seg.rfind('\nAdı Soyadı',0,m.start())]
        a=max([x for x in starts if x>=0] or [max(0,seg.rfind('\n',0,m.start()))])
        b=matches[i+1].start() if i+1<len(matches) else len(seg)
        chunk=seg[a:b]
        pv=party_values(chunk)
        if pv['name']:
            parties.append(pv)
    if parties:return parties
    # Tek blok için yedek yöntem.
    pv=party_values(seg)
    return [pv] if pv['name'] else []

def extract(text):
    ptext=udf_plain(text); out={k:'' for k,_ in FIELDS}
    for k in ['basvuruNo','dosyaNo']: out[k]=first(PATTERNS[k],ptext)
    screen=extract_dosya_bilgileri_screen(ptext)
    for k,v in screen.items():
        if v:
            out[k]=v
    arbsec=section(ptext,['ARABULUCU BİLGİLERİ','ARABULUCU'],['BAŞVURU SAHİBİ BİLGİLERİ','BAŞVURUCU BİLGİLERİ','BAŞVURU SAHİBİ'])
    out['arabulucuAdi']=first([r'Adı\s+Soyadı\s*[:：]\s*([^\n<]{2,150})',r'ARABULUCU\s*[:：]\s*([^\n<]{2,150})'],arbsec) or first([r'ARABULUCU\s*[:：]\s*([^\n<]{2,150})'],ptext)
    for k in ['arabulucuTc','arabulucuSicil','arabulucuAdres']: out[k]=first(PATTERNS[k],ptext)
    applicant=section(ptext,['BAŞVURU SAHİBİ BİLGİLERİ','BAŞVURUCU BİLGİLERİ','BAŞVURUCU'],['KARŞI TARAF BİLGİLERİ','KARŞI TARAF'])
    a=party_values(applicant)
    out.update({'basvurucuTcKimlik':a['tc'],'basvurucuAdiSoyadi':a['name'],'basvurucuAdres':a['address'],'basvurucuVekili':a['proxy'],'basvurucuTelefon':a['phone'],'basvurucuEposta':a['email'],'basvurucuTarafTuru':a.get('type','kisi'),'basvurucuVergiNo':a.get('tax','')})
    respondents=extract_respondents(ptext)
    generic_dosya=normalize_dosya_turu(first(PATTERNS['dosyaTuru'],ptext))
    if generic_dosya and not out.get('dosyaTuru'):
        out['dosyaTuru']=generic_dosya
    for k in ['uyusmazlik','talep','baslangicTarihi','bitisTarihi','duzenlemeYeri','duzenlemeTarihi','sonuc']:
        v=first(PATTERNS[k],ptext)
        if v and not out.get(k):
            out[k]=v
    if out.get('dosyaTuru'):
        out['uyusmazlik']=out['dosyaTuru']
    if out.get('baslangicTarihi'):
        out['baslangicTarihi']=normalize_date_value(out['baslangicTarihi'])
    return out,respondents

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
        if any(v for k,v in p.items() if k!='type'):respondents.append(p)
    locked=set(str(x) for x in form.getlist('locked'))
    locked_resp=set(int(x) for x in form.getlist('locked_resp') if str(x).isdigit())
    return values,respondents,locked,locked_resp

def merge_state(values,respondents,locked,locked_resp,new_values,new_resp):
    for k in values:
        if k not in locked and new_values.get(k):values[k]=new_values[k]
    # Kilitli satırlar korunur; yeni belgede bulunan taraflar boş/unlocked satırlara eklenir.
    for i,p in enumerate(new_resp):
        target=None
        # Aynı isim varsa onunla birleştir.
        if p.get('name'):
            for j,cur in enumerate(respondents):
                if cur.get('name','').strip().casefold()==p['name'].strip().casefold():target=j;break
        p['type']=('kontrol' if p.get('tax') and p.get('tc') else ('kurum' if p.get('tax') else 'kisi'))
        if target is None:
            for j,cur in enumerate(respondents):
                if j not in locked_resp and not cur.get('name'):target=j;break
        if target is None and len(respondents)<MAX_RESP:
            respondents.append({f:'' for f in RESP_FIELDS});target=len(respondents)-1
        if target is None:continue
        if target in locked_resp:continue
        for f in RESP_FIELDS:
            if p.get(f):respondents[target][f]=p[f]
    return values,respondents

def respondent_body_block(template_text):
    starts=[m.start() for m in re.finditer(r'KARŞI TARAF BİLGİLERİ',template_text,re.I)]
    if not starts:return ''
    s=starts[0]; e=text.find('Arabuluculuk Konusu Uyuşmazlık',s) if False else template_text.find('Arabuluculuk Konusu Uyuşmazlık',s)
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
        if id_value:
            seg=re.sub(r'(?:TC\s+Kimlik\s+No|Vergi\s+No|VKN|Vergi\s+Numarası)\s*[:：]\s*[^\n]*',
                       f'{id_label}\t\t: {id_value}',seg,count=1,flags=re.I)
        if applicant.get('name'):
            seg=re.sub(r'(?:Adı\s+Soyadı|Adı\s+Soyadı\s*/\s*Unvanı|Unvanı|Ünvanı)\s*[:：]\s*[^\n]*',
                       f'{name_label}\t\t: {applicant["name"]}',seg,count=1,flags=re.I)
        # Telefonu özellikle 'Telefon Numarası' satırına yaz. Şablonda ayrıca
        # 'Cep Tel' alanı bulunabiliyor; önce Telefon Numarası, yoksa Cep Tel kullanılır.
        replacements=[
            (r'Adres\s*[:：]\s*[^\n]*', applicant.get('address','')),
            (r'Vekili\s*[:：]\s*[^\n]*', applicant.get('proxy','')),
            (r'Telefon\s+Numarası\s*[:：]\s*[^\n]*', applicant.get('phone','')),
            (r'E-Posta\s+Adresi\s*[:：]\s*[^\n]*', applicant.get('email',''))
        ]
        for pat,val in replacements:
            if val:
                mm=re.search(pat,seg,re.I)
                if mm:
                    line=mm.group(0); c=line.find(':')
                    newline=line[:c+1]+' '+val if c>=0 else line
                    seg=seg[:mm.start()]+newline+seg[mm.end():]
        # Telefon Numarası satırı yoksa, Cep Tel satırını kullan; böylece değer kaybolmaz.
        if applicant.get('phone') and not re.search(r'Telefon\s+Numarası\s*[:：]',seg,re.I):
            mm=re.search(r'Cep\s*Tel\s*[:：]\s*[^\n]*',seg,re.I)
            if mm:
                line=mm.group(0); c=line.find(':')
                newline=line[:c+1]+' '+applicant['phone'] if c>=0 else line
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
        if not val:continue
        # First occurrence is generally the header field; for arabulucu ad we prefer explicit ARABULUCU line.
        m=re.search(p,text,re.I)
        if not m:continue
        # Preserve label and replace after colon.
        line=text[m.start():m.end()]
        colon=line.find(':')
        if colon>=0: line=line[:colon+1]+' '+val
        text=text[:m.start()]+line+text[m.end():]
    return text

def render_editor(filename,values,respondents,locked=set(),locked_resp=set(),message='',custom_templates=None):
    groups=[('Dosya Bilgileri',['basvuruNo','dosyaNo']),
            ('Arabulucu',['arabulucuAdi','arabulucuTc','arabulucuSicil','arabulucuAdres']),
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
    cards=''
    # Başvurucu türü otomatik belirlenir; kullanıcıdan ayrıca seçim istenmez.
    atax=escape(values.get('basvurucuVergiNo',''),quote=True)
    atc=escape(values.get('basvurucuTcKimlik',''),quote=True)
    if values.get('basvurucuVergiNo') and values.get('basvurucuTcKimlik'):
        type_note='⚠️ T.C. Kimlik No ve Vergi No birlikte dolu; lütfen kontrol edin.'
    elif values.get('basvurucuVergiNo'):
        type_note='Firma / kurum olarak algılandı (Vergi No mevcut).'
    elif values.get('basvurucuTcKimlik'):
        type_note='Gerçek kişi olarak algılandı (T.C. Kimlik No mevcut).'
    else:
        type_note='Taraf türü numara bilgisine göre otomatik belirlenecek.'
    # Kimlik (TC/Vergi No) ve iletişim bilgileri artık tek "Başvurucu" kartında birlikte.
    basvurucu_fields=''.join(field(k) for k in ['basvurucuAdiSoyadi','basvurucuAdres','basvurucuVekili','basvurucuTelefon','basvurucuEposta'])
    cards+=f'''<section class="card"><h2>Başvurucu</h2>
<label>T.C. Kimlik No</label><input name="basvurucuTcKimlik" value="{atc}">
<label>Vergi No</label><input name="basvurucuVergiNo" value="{atax}">
<p class="hint">{escape(type_note)}</p>
{basvurucu_fields}</section>'''
    for title,ks in groups:
        cards+=f'<section class="card"><h2>{escape(title)}</h2>'+''.join(field(k) for k in ks)+'</section>'

    resp_html=''
    count=max(len(respondents),1)
    for i in range(count):
        p=respondents[i] if i<len(respondents) else {f:'' for f in RESP_FIELDS}
        lk='checked' if i in locked_resp else ''
        h=f'<div class="party-head"><h3>Karşı Taraf {i+1}</h3><label class="lock"><input type="checkbox" name="locked_resp" value="{i}" {lk}> 🔒 Bu tarafı sabitle</label></div>'
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
        resp_html+=f'<section class="card respondent-card">{h}{body}</section>'

    options=''.join(f'<option value="{escape(k)}">{escape(v[0])}</option>' for k,v in TEMPLATES.items())
    options+=''.join(f'<option value="tpl_{escape(t["id"])}">{escape(t["name"])} (Kendi Şablonum)</option>' for t in (custom_templates or []))
    msg=f'<div class="ok">{escape(message)}</div>' if message else ''
    html='''<!doctype html><html lang="tr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Son Tutanak Bilgi Havuzu</title><style>
*{box-sizing:border-box}body{font-family:Arial,sans-serif;background:#f2f5f8;margin:0;color:#20252b}.wrap{max-width:1100px;margin:25px auto;padding:0 16px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:18px}.card{background:#fff;border-radius:16px;padding:22px;margin-bottom:18px;box-shadow:0 4px 20px #0001}label{display:block;font-weight:bold;margin-top:10px}input,textarea,select{width:100%;padding:10px;margin-top:5px;border:1px solid #ccd3db;border-radius:8px;font:inherit}textarea{min-height:70px;resize:vertical}button{background:#1769e0;color:white;border:0;border-radius:9px;padding:13px 18px;font-weight:bold;cursor:pointer;margin-top:12px}.secondary{background:#44515f}.lock{font-size:12px!important;font-weight:normal!important;color:#53606b}.lock input{width:auto}.party-head{display:flex;justify-content:space-between;gap:10px;align-items:center}.party-head h3{margin:0}.ok{background:#eaf8ee;color:#176b35;padding:12px;border-radius:8px;margin-bottom:15px}.hint{color:#65717d;font-size:13px}@media(max-width:800px){.grid{grid-template-columns:1fr}.party-head{display:block}}
</style></head><body><div class="wrap"><h1>Son Tutanak Bilgi Havuzu</h1><p class="hint">Kaynak belge: __FILENAME__</p>__MSG__<form id="mainform" action="/build" method="post" enctype="multipart/form-data"><div class="grid"><div>__CARDS__<section class="card"><h2>Karşı Taraflar</h2><p class="hint">Bir veya birden fazla karşı taraf ekleyebilirsiniz.</p><div id="respondents">__RESP__</div><button type="button" class="secondary" onclick="addRespondent()">+ Karşı Taraf Ekle</button></section></div><div><section class="card"><h2>Belgeleri Birleştir</h2><p class="hint">İlk belgedeki kontrol ettiğiniz alanları 🔒 sabitleyin. Yeni bir UDF yüklediğinizde sabit alanlar değişmez; diğer alanlar yeni belgeden tamamlanır.</p><input type="file" name="merge_file" accept=".udf"><button type="submit" formaction="/merge" class="secondary">Belgeyi Bilgi Havuzuna Ekle</button></section><section class="card"><h2>Son Tutanağı Oluştur</h2><label>Belge türü</label><select name="template_choice">__OPTIONS__<option value="custom">Kendi UDF şablonumu kullan</option></select><div id="custom"><label>Özel Son Tutanak UDF</label><input type="file" name="custom_file" accept=".udf"></div><button type="submit">✓ Son Tutanağı Oluştur</button></section><section class="card"><h2>Harcama Pusulası</h2><p class="hint">Bu ekrandaki Dosya Türü, Karşı Taraflar ve Arabulucu bilgilerini kullanarak, IBAN'ınızı (Profilim) da ekleyerek Harcama Pusulası üretir.</p><button type="submit" formaction="/harcama-pusulasi/build" class="secondary">📄 Harcama Pusulası Oluştur</button></section><section class="card"><h2>Bilgi Havuzu</h2><p class="hint">Kilitli alanlar yeni belgelerle değiştirilmez. Yeni belge yükleyerek eksik alanları tamamlayabilirsiniz.</p><button type="button" class="secondary" onclick="lockAll()">🔒 Dolu Alanların Tümünü Sabitle</button></section></div></div></form></div><script>
let rc=__COUNT__;function addRespondent(){if(rc>=10)return;const root=document.getElementById('respondents');const i=rc++;const d=document.createElement('section');d.className='card respondent-card';d.innerHTML='<div class="party-head"><h3>Karşı Taraf '+(i+1)+'</h3><label class="lock"><input type="checkbox" name="locked_resp" value="'+i+'"> 🔒 Bu tarafı sabitle</label></div><div class="party"><label>Taraf Türü</label><select name="resp_'+i+'_type"><option value="kisi">Kişi</option><option value="kurum">Kurum / Şirket</option></select></div><div class="party"><label>T.C. Kimlik No</label><input name="resp_'+i+'_tc"></div><div class="party"><label>Vergi No</label><input name="resp_'+i+'_tax"></div><div class="party"><label>Adı Soyadı / Unvanı</label><input name="resp_'+i+'_name"></div><div class="party"><label>Adres</label><textarea name="resp_'+i+'_address"></textarea></div><div class="party"><label>Vekili</label><input name="resp_'+i+'_proxy"></div><div class="party"><label>Telefon</label><input name="resp_'+i+'_phone"></div><div class="party"><label>E-posta</label><input name="resp_'+i+'_email"></div>';root.appendChild(d)}
function lockAll(){document.querySelectorAll('input,textarea').forEach(function(x){if(x.name && x.type!=='file' && !x.name.startsWith('locked') && x.value.trim() && !x.parentElement.querySelector('input[name=locked][value=\"'+x.name+'\"]')){let l=document.createElement('input');l.type='checkbox';l.name='locked';l.value=x.name;l.checked=true;x.parentElement.appendChild(l)}})}
function toggleMeeting(){const s=document.querySelector('select[name=gorusmeSekli]');const f=document.querySelector('textarea[name=gorusmeAdresi]');if(!s||!f)return;f.parentElement.style.display=s.value==='Yüz yüze'?'block':'none';}document.addEventListener('change',e=>{if(e.target.name==='gorusmeSekli')toggleMeeting()});document.addEventListener('DOMContentLoaded',toggleMeeting);</script></body></html>'''
    return html.replace('__FILENAME__',escape(filename)).replace('__MSG__',msg).replace('__CARDS__',cards).replace('__RESP__',resp_html).replace('__OPTIONS__',options).replace('__COUNT__',str(len(respondents)))


def extract_any_source(filename, data):
    if is_udf_filename(filename):
        _, text, _ = read_udf(data)
        return udf_plain(text), "udf"
    return extract_source_text(filename, data), "ocr"
