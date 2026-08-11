import io,re,zipfile,difflib
from pathlib import Path
from html import escape
from fastapi import FastAPI,Request,UploadFile,File
from fastapi.responses import HTMLResponse,StreamingResponse

app=FastAPI(title="Son Tutanak UDF Asistanı")

FIELDS=[
('basvuruNo','Başvuru No'),('dosyaNo','Dosya No'),
('arabulucuAdi','Arabulucu Adı'),('arabulucuTc','Arabulucu T.C. Kimlik No'),
('arabulucuSicil','Arabulucu Sicil No'),('arabulucuAdres','Arabulucu Adres'),
('basvurucuTarafTuru','Başvurucu Taraf Türü'),('basvurucuVergiNo','Başvurucu Vergi No'),('basvurucuTcKimlik','Başvurucu T.C. Kimlik No'),('basvurucuAdiSoyadi','Başvurucu Adı Soyadı'),
('basvurucuAdres','Başvurucu Adres'),('basvurucuVekili','Başvurucu Vekili'),
('basvurucuTelefon','Başvurucu Telefon'),('basvurucuEposta','Başvurucu E-Posta'),
('dosyaTuru','Dosya Türü'),('uyusmazlik','Uyuşmazlık Konusu'),('talep','Talep'),
('baslangicTarihi','Süreç Başlangıç Tarihi'),('bitisTarihi','Süreç Bitiş Tarihi'),
('duzenlemeYeri','Tutanak Düzenleme Yeri'),('duzenlemeTarihi','Tutanak Düzenleme Tarihi'),
('sonuc','Sonuç')]
LABELS=dict(FIELDS)
RESP_FIELDS=['type','tc','tax','name','address','proxy','phone','email']
RESP_LABELS={'type':'Taraf Türü','tc':'T.C. Kimlik No','tax':'Vergi No','name':'Adı Soyadı / Unvanı','address':'Adres','proxy':'Vekili','phone':'Telefon','email':'E-posta'}
MAX_RESP=10

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

def normalize_dosya_turu(value):
    value=re.sub(r"\s+", " ", (value or "").strip())
    value=re.sub(r"\s*Başvuru\s+Dosyası\s*$", "", value, flags=re.I)
    value=re.sub(r"\s*Başvuru\s*$", "", value, flags=re.I)
    value=re.sub(r"\s*Dosyası\s*$", "", value, flags=re.I)
    return value.strip(" :.-")

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
    arbsec=section(ptext,['ARABULUCU BİLGİLERİ','ARABULUCU'],['BAŞVURU SAHİBİ BİLGİLERİ','BAŞVURUCU BİLGİLERİ','BAŞVURU SAHİBİ'])
    out['arabulucuAdi']=first([r'Adı\s+Soyadı\s*[:：]\s*([^\n<]{2,150})',r'ARABULUCU\s*[:：]\s*([^\n<]{2,150})'],arbsec) or first([r'ARABULUCU\s*[:：]\s*([^\n<]{2,150})'],ptext)
    for k in ['arabulucuTc','arabulucuSicil','arabulucuAdres']: out[k]=first(PATTERNS[k],ptext)
    applicant=section(ptext,['BAŞVURU SAHİBİ BİLGİLERİ','BAŞVURUCU BİLGİLERİ','BAŞVURUCU'],['KARŞI TARAF BİLGİLERİ','KARŞI TARAF'])
    a=party_values(applicant)
    out.update({'basvurucuTcKimlik':a['tc'],'basvurucuAdiSoyadi':a['name'],'basvurucuAdres':a['address'],'basvurucuVekili':a['proxy'],'basvurucuTelefon':a['phone'],'basvurucuEposta':a['email'],'basvurucuTarafTuru':a.get('type','kisi'),'basvurucuVergiNo':a.get('tax','')})
    respondents=extract_respondents(ptext)
    out['dosyaTuru']=normalize_dosya_turu(first(PATTERNS['dosyaTuru'],ptext))
    for k in ['uyusmazlik','talep','baslangicTarihi','bitisTarihi','duzenlemeYeri','duzenlemeTarihi','sonuc']:
        out[k]=first(PATTERNS[k],ptext)
    if out['dosyaTuru']:
        out['uyusmazlik']=out['dosyaTuru']
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
TEMPLATE_DIR=Path(__file__).parent/'templates'/'udf'

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
                f'Vekili\t\t: {p.get("proxy","")}'
            ]
            if p.get('phone'):
                lines.append(f'Cep Tel\t\t: {p.get("phone","")}')
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
    for k,p in patterns.items():
        if not values.get(k):continue
        # First occurrence is generally the header field; for arabulucu ad we prefer explicit ARABULUCU line.
        m=re.search(p,text,re.I)
        if not m:continue
        # Preserve label and replace after colon.
        line=text[m.start():m.end()]
        colon=line.find(':')
        if colon>=0: line=line[:colon+1]+' '+values[k]
        text=text[:m.start()]+line+text[m.end():]
    return text

def render_editor(filename,values,respondents,locked=set(),locked_resp=set(),message=''):
    groups=[('Dosya Bilgileri',['basvuruNo','dosyaNo']),('Arabulucu',['arabulucuAdi','arabulucuTc','arabulucuSicil','arabulucuAdres']),('Başvurucu',['basvurucuAdiSoyadi','basvurucuAdres','basvurucuVekili','basvurucuTelefon','basvurucuEposta']),('Süreç',['dosyaTuru','uyusmazlik','talep','baslangicTarihi','bitisTarihi','duzenlemeYeri','duzenlemeTarihi'])]
    def field(k):
        lock='checked' if k in locked else ''
        v=escape(values.get(k,''),quote=True)
        if k in ('arabulucuAdres','basvurucuAdres','uyusmazlik','talep'):
            el=f'<textarea name="{k}">{v}</textarea>'
        else:
            el=f'<input name="{k}" value="{v}">'
        return f'<div class="field"><label>{escape(LABELS[k])}</label>{el}<label class="lock"><input type="checkbox" name="locked" value="{k}" {lock}> 🔒 Sabitle</label></div>'
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
    applicant_extra=f'''<section class="card"><h2>Başvurucu Kimlik Bilgisi</h2>
<label>T.C. Kimlik No</label><input name="basvurucuTcKimlik" value="{atc}">
<label>Vergi No</label><input name="basvurucuVergiNo" value="{atax}">
<p class="hint">{escape(type_note)}</p>
</section>'''
    cards+=applicant_extra
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
    msg=f'<div class="ok">{escape(message)}</div>' if message else ''
    html='''<!doctype html><html lang="tr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Son Tutanak Bilgi Havuzu</title><style>
*{box-sizing:border-box}body{font-family:Arial,sans-serif;background:#f2f5f8;margin:0;color:#20252b}.wrap{max-width:1100px;margin:25px auto;padding:0 16px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:18px}.card{background:#fff;border-radius:16px;padding:22px;margin-bottom:18px;box-shadow:0 4px 20px #0001}label{display:block;font-weight:bold;margin-top:10px}input,textarea,select{width:100%;padding:10px;margin-top:5px;border:1px solid #ccd3db;border-radius:8px;font:inherit}textarea{min-height:70px;resize:vertical}button{background:#1769e0;color:white;border:0;border-radius:9px;padding:13px 18px;font-weight:bold;cursor:pointer;margin-top:12px}.secondary{background:#44515f}.lock{font-size:12px!important;font-weight:normal!important;color:#53606b}.lock input{width:auto}.party-head{display:flex;justify-content:space-between;gap:10px;align-items:center}.party-head h3{margin:0}.ok{background:#eaf8ee;color:#176b35;padding:12px;border-radius:8px;margin-bottom:15px}.hint{color:#65717d;font-size:13px}@media(max-width:800px){.grid{grid-template-columns:1fr}.party-head{display:block}}
</style></head><body><div class="wrap"><h1>Son Tutanak Bilgi Havuzu</h1><p class="hint">Kaynak belge: __FILENAME__</p>__MSG__<form id="mainform" action="/build" method="post" enctype="multipart/form-data"><div class="grid"><div>__CARDS__<section class="card"><h2>Karşı Taraflar</h2><p class="hint">Bir veya birden fazla karşı taraf ekleyebilirsiniz.</p><div id="respondents">__RESP__</div><button type="button" class="secondary" onclick="addRespondent()">+ Karşı Taraf Ekle</button></section></div><div><section class="card"><h2>Belgeleri Birleştir</h2><p class="hint">İlk belgedeki kontrol ettiğiniz alanları 🔒 sabitleyin. Yeni bir UDF yüklediğinizde sabit alanlar değişmez; diğer alanlar yeni belgeden tamamlanır.</p><input type="file" name="merge_file" accept=".udf"><button type="submit" formaction="/merge" class="secondary">Belgeyi Bilgi Havuzuna Ekle</button></section><section class="card"><h2>Son Tutanağı Oluştur</h2><label>Belge türü</label><select name="template_choice">__OPTIONS__<option value="custom">Kendi UDF şablonumu kullan</option></select><div id="custom"><label>Özel Son Tutanak UDF</label><input type="file" name="custom_file" accept=".udf"></div><button type="submit">✓ Son Tutanağı Oluştur</button></section><section class="card"><h2>Bilgi Havuzu</h2><p class="hint">Kilitli alanlar yeni belgelerle değiştirilmez. Yeni belge yükleyerek eksik alanları tamamlayabilirsiniz.</p><button type="button" class="secondary" onclick="lockAll()">🔒 Dolu Alanların Tümünü Sabitle</button></section></div></div></form></div><script>
let rc=__COUNT__;function addRespondent(){if(rc>=10)return;const root=document.getElementById('respondents');const i=rc++;const d=document.createElement('section');d.className='card respondent-card';d.innerHTML='<div class="party-head"><h3>Karşı Taraf '+(i+1)+'</h3><label class="lock"><input type="checkbox" name="locked_resp" value="'+i+'"> 🔒 Bu tarafı sabitle</label></div><div class="party"><label>Taraf Türü</label><select name="resp_'+i+'_type"><option value="kisi">Kişi</option><option value="kurum">Kurum / Şirket</option></select></div><div class="party"><label>T.C. Kimlik No</label><input name="resp_'+i+'_tc"></div><div class="party"><label>Vergi No</label><input name="resp_'+i+'_tax"></div><div class="party"><label>Adı Soyadı / Unvanı</label><input name="resp_'+i+'_name"></div><div class="party"><label>Adres</label><textarea name="resp_'+i+'_address"></textarea></div><div class="party"><label>Vekili</label><input name="resp_'+i+'_proxy"></div><div class="party"><label>Telefon</label><input name="resp_'+i+'_phone"></div><div class="party"><label>E-posta</label><input name="resp_'+i+'_email"></div>';root.appendChild(d)}
function lockAll(){document.querySelectorAll('input,textarea').forEach(function(x){if(x.name && x.type!=='file' && !x.name.startsWith('locked') && x.value.trim() && !x.parentElement.querySelector('input[name=locked][value=\"'+x.name+'\"]')){let l=document.createElement('input');l.type='checkbox';l.name='locked';l.value=x.name;l.checked=true;x.parentElement.appendChild(l)}})}
</script></body></html>'''
    return html.replace('__FILENAME__',escape(filename)).replace('__MSG__',msg).replace('__CARDS__',cards).replace('__RESP__',resp_html).replace('__OPTIONS__',options).replace('__COUNT__',str(len(respondents)))

@app.get('/',response_class=HTMLResponse)
async def home(request:Request):return HTMLResponse('''<!doctype html><html lang="tr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Son Tutanak UDF Asistanı</title><style>body{font-family:Arial;background:#f2f5f8;margin:0}.box{max-width:760px;margin:50px auto;background:#fff;padding:32px;border-radius:18px;box-shadow:0 5px 25px #0001}input,button{width:100%;padding:13px;margin-top:10px}button{background:#1769e0;color:#fff;border:0;border-radius:9px;font-weight:bold}</style></head><body><div class="box"><h1>Son Tutanak UDF Asistanı</h1><p>Başvuru Formu UDF yükleyin; bilgileri çıkarın, sabitleyin, başka belgelerden tamamlayın ve son tutanağı oluşturun.</p><form action="/edit" method="post" enctype="multipart/form-data"><input type="file" name="file" accept=".udf" required><button>Başvuru Formunu Analiz Et</button></form></div></body></html>''')

@app.post('/edit',response_class=HTMLResponse)
async def edit(request:Request,file:UploadFile=File(...)):
    try:
        data=await file.read();xml,text,files=read_udf(data);values,respondents=extract(text)
        return HTMLResponse(render_editor(file.filename or 'Başvuru Formu UDF',values,respondents))
    except Exception as e:return HTMLResponse(str(e),400)

@app.post('/merge',response_class=HTMLResponse)
async def merge(request:Request,merge_file:UploadFile=File(...)):
    try:
        form=await request.form();values,respondents,locked,locked_resp=form_state(form)
        data=await merge_file.read();_,text,_=read_udf(data);nv,nr=extract(text)
        values,respondents=merge_state(values,respondents,locked,locked_resp,nv,nr)
        return HTMLResponse(render_editor(merge_file.filename or 'Birleştirilmiş Bilgi Havuzu',values,respondents,locked,locked_resp,'Yeni belgeden bilgiler bilgi havuzuna eklendi. Kilitli alanlar korunmuştur.'))
    except Exception as e:return HTMLResponse(str(e),400)

@app.post('/build')
async def build(request:Request):
    try:
        form=await request.form();values,respondents,locked,locked_resp=form_state(form);choice=str(form.get('template_choice',''))
        if not values.get('sonuc'):values['sonuc']=standard_result(choice)
        if choice=='custom':
            upload=form.get('custom_file')
            if not isinstance(upload,UploadFile):return HTMLResponse('Özel UDF şablonu seçtiniz; lütfen dosya yükleyin.',400)
            data=await upload.read();source_name=Path(upload.filename or 'son_tutanak').stem
        else:data=template_bytes(choice);source_name=Path(TEMPLATES[choice][1]).stem
        xml,old,files=read_udf(data)
        applicant={'type':('kontrol' if values.get('basvurucuVergiNo') and values.get('basvurucuTcKimlik') else ('kurum' if values.get('basvurucuVergiNo') else 'kisi')),'tax':values.get('basvurucuVergiNo',''),'name':values.get('basvurucuAdiSoyadi',''),'tc':values.get('basvurucuTcKimlik',''),'address':values.get('basvurucuAdres',''),'proxy':values.get('basvurucuVekili',''),'phone':values.get('basvurucuTelefon',''),'email':values.get('basvurucuEposta','')}
        arb={'name':values.get('arabulucuAdi',''),'sicil':values.get('arabulucuSicil','')}
        new=set_parties_and_signatures(old,applicant,respondents,arb)
        # Kullanıcının editörde gördüğü son uyuşmazlık/talep değeri kaynak alınır.
        new=fill_general(new,values)
        if values.get('talep'):
            new=replace_talep_in_narrative(new,values['talep'])
        # Önce mevcut paragraf/biçim offsetlerini eski metinden yeni metne taşı.
        # Daha sonra yeni eklenen satırlar için gerçek <paragraph> öğeleri üret.
        # Böylece UYAP Doküman Editörü eklenen tarafları tek satıra birleştirmez.
        xml=update_offsets(xml,old,new)
        xml=rebuild_region_paragraphs(xml,old,new,'KARŞI TARAF BİLGİLERİ','Arabuluculuk Konusu Uyuşmazlık')
        xml=rebuild_region_paragraphs(xml,old,new,'İMZALAR',None)
        if new==old:return HTMLResponse('Şablonda değişiklik yapılamadı. Alanları kontrol edin.',400)
        result=build_udf(files,xml,old,new);label=TEMPLATES[choice][0] if choice in TEMPLATES else 'Özel Son Tutanak'
        name=re.sub(r'[^A-Za-z0-9ÇĞİÖŞÜçğıöşü _-]','_',source_name)+'_hazir.udf'
        return StreamingResponse(io.BytesIO(result),media_type='application/octet-stream',headers={'Content-Disposition':f'attachment; filename="{name}"'})
    except Exception as e:return HTMLResponse(f'Belge oluşturulurken hata: {escape(str(e))}',500)
