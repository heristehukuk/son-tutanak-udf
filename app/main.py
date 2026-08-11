import io,re,zipfile,difflib
from pathlib import Path
from html import escape
from fastapi import FastAPI,Request,UploadFile,File
from fastapi.responses import HTMLResponse,StreamingResponse

app=FastAPI(title="Son Tutanak UDF Düzenleyici")

FIELDS=[
('basvuruNo','Başvuru No'),('dosyaNo','Dosya No'),
('arabulucuAdi','Arabulucu Adı'),('arabulucuTc','Arabulucu T.C. Kimlik No'),
('arabulucuSicil','Arabulucu Sicil No'),('arabulucuAdres','Arabulucu Adres'),
('basvurucuTcKimlik','Başvurucu T.C. Kimlik No'),('basvurucuAdiSoyadi','Başvurucu Adı Soyadı'),
('basvurucuAdres','Başvurucu Adres'),('basvurucuVekili','Başvurucu Vekili'),
('basvurucuTelefon','Başvurucu Telefon'),('basvurucuEposta','Başvurucu E-Posta'),
('karsitarafTcKimlik','Karşı Taraf T.C. Kimlik No'),('karsitarafAdiSoyadi','Karşı Taraf Adı Soyadı'),
('karsitarafAdres','Karşı Taraf Adres'),('karsitarafVekili','Karşı Taraf Vekili'),
('uyusmazlik','Uyuşmazlık Konusu'),('talep','Talep'),
('baslangicTarihi','Süreç Başlangıç Tarihi'),('bitisTarihi','Süreç Bitiş Tarihi'),
('duzenlemeYeri','Tutanak Düzenleme Yeri'),('duzenlemeTarihi','Tutanak Düzenleme Tarihi'),
('sonuc','Sonuç')
]
LABELS=dict(FIELDS)

def read_udf(data):
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            if "content.xml" not in z.namelist(): raise ValueError("content.xml bulunamadı.")
            xml=z.read("content.xml").decode("utf-8")
            files={n:z.read(n) for n in z.namelist()}
    except zipfile.BadZipFile:
        raise ValueError("Geçerli bir UDF dosyası seçin.")
    m=re.search(r"<content><!\[CDATA\[(.*?)\]\]></content>",xml,re.S)
    if not m: raise ValueError("UDF metin alanı okunamadı.")
    return xml,m.group(1),files

def udf_plain(text):
    # Etiketleri kaldırırken satır sonlarını koru; UDF alanları çoğunlukla satır tabanlıdır.
    s=re.sub(r"<[^>]+>","",text)
    lines=[]
    for line in s.splitlines():
        line=re.sub(r"[ \t]+"," ",line).strip()
        if line:
            lines.append(line)
    return "\n".join(lines)

def first(patterns, text, flags=re.I):
    for p in patterns:
        m=re.search(p,text,flags)
        if m:
            v=m.group(1).strip(" \t\r\n:;,-")
            if v: return v
    return ""

def extract(text):
    ptext=udf_plain(text)
    out={k:"" for k,_ in FIELDS}

    out["basvuruNo"]=first([
        r"BAŞVURU\s*NO\s*[:：]\s*([^\n<]{1,100})",
        r"Başvuru\s*(?:Numarası|No)\s*[:：]\s*([^\n<]{1,100})"],ptext)
    out["dosyaNo"]=first([r"DOSYA\s*NO\s*[:：]\s*([^\n<]{1,100})",r"Dosya\s*(?:Numarası|No)\s*[:：]\s*([^\n<]{1,100})"],ptext)

    # Bölümleri sınırlayarak başvurucu/karşı taraf ayrımı yap
    def section(start_terms,end_terms):
        s=min([ptext.find(t) for t in start_terms if ptext.find(t)>=0] or [0])
        ends=[ptext.find(t,s+1) for t in end_terms]
        e=min([x for x in ends if x>=0] or [len(ptext)])
        return ptext[s:e]

    # Arabulucu: iki yaygın biçim
    arbsec=section(["ARABULUCU BİLGİLERİ","ARABULUCU"],["BAŞVURU SAHİBİ BİLGİLERİ","BAŞVURUCU BİLGİLERİ","BAŞVURU SAHİBİ"])
    out["arabulucuAdi"]=first([
        r"Adı\s+Soyadı\s*[:：]\s*([^\n<]{2,150})",
        r"ARABULUCU\s*[:：]\s*([^\n<]{2,150})"],arbsec)
    if not out["arabulucuAdi"]:
        out["arabulucuAdi"]=first([r"ARABULUCU\s*[:：]\s*([^\n<]{2,150})"],ptext)
    out["arabulucuTc"]=first([
        r"T\.?\s*C\.?\s*(?:KİMLİK\s+NUMARASI|Kimlik\s+No)\s*[:：]\s*(\d{8,20})"],ptext)
    out["arabulucuSicil"]=first([
        r"(?:ARB\.?\s*SİCİL\s+NUMARASI|Arb\.?\s*Sicil\s*No)\s*[:：]\s*([^\n<]{1,80})"],ptext)
    out["arabulucuAdres"]=first([
        r"ARABULUCU\s+BİLGİLERİ.*?Adresi\s*[:：]\s*([^\n<]{5,300})",
        r"ADRESİ\s*[:：]\s*([^\n<]{5,300})"],ptext)

    applicant=section(["BAŞVURU SAHİBİ BİLGİLERİ","BAŞVURUCU BİLGİLERİ","BAŞVURUCU"],["KARŞI TARAF BİLGİLERİ","KARŞI TARAF"])
    respondent=section(["KARŞI TARAF BİLGİLERİ","KARŞI TARAF"],["Arabuluculuk Konusu Uyuşmazlık","UYUŞMAZLIK","TALEP","Arabuluculuk Sürecinin"])

    def party_values(seg):
        return {
            "tc":first([r"TC\s+Kimlik\s+No\s*[:：]\s*(\d{8,20})"],seg),
            "name":first([r"Adı\s+Soyadı\s*[:：]\s*([^\n<]{2,200})"],seg),
            "address":first([r"Adres\s*[:：]\s*([^\n<]{2,400})"],seg),
            "proxy":first([r"Vekili\s*[:：]\s*([^\n<]{1,250})"],seg),
            "phone":first([r"(?:Cep\s*Tel|Telefon\s+Numarası|Telefon)\s*[:：]\s*([^\n<]{3,150})"],seg),
            "email":first([r"E-Posta\s+Adresi\s*[:：]\s*([^\n<]{3,250})"],seg)
        }
    a=party_values(applicant); r=party_values(respondent)
    out.update({
        "basvurucuTcKimlik":a["tc"],"basvurucuAdiSoyadi":a["name"],"basvurucuAdres":a["address"],
        "basvurucuVekili":a["proxy"],"basvurucuTelefon":a["phone"],"basvurucuEposta":a["email"],
        "karsitarafTcKimlik":r["tc"],"karsitarafAdiSoyadi":r["name"],"karsitarafAdres":r["address"],
        "karsitarafVekili":r["proxy"]
    })

    out["uyusmazlik"]=first([
        r"Arabuluculuk\s+Konusu\s+Uyuşmazlık\s*[:：]\s*([^\n<]{2,500})",
        r"Uyuşmazlık\s*(?:Türü|Konusu)?\s*[:：]\s*([^\n<]{2,500})",
        r"Uyuşmazlık\s+Türü\s*[:：]\s*([^\n<]{2,500})"],ptext)
    out["talep"]=first([
        r"Talep(?:ler)?\s*[:：]\s*([^\n<]{2,1000})",
        r"Talep\s+Konusu\s*[:：]\s*([^\n<]{2,1000})"],ptext)
    out["baslangicTarihi"]=first([r"Arabuluculuk\s+Sürecinin\s+Başladığı\s+Tarih\s*[:：]\s*([^\n<]{2,80})"],ptext)
    out["bitisTarihi"]=first([r"Arabuluculuk\s+Sürecinin\s+Bittiği\s+Tarih\s*[:：]\s*([^\n<]{2,80})"],ptext)
    out["duzenlemeYeri"]=first([r"Son\s+Tutanağın\s+Düzenlendiği\s+Yer\s*[:：]\s*([^\n<]{2,120})"],ptext)
    out["duzenlemeTarihi"]=first([r"Son\s+Tutanağın\s+Düzenlendiği\s+Tarih\s*[:：]\s*([^\n<]{2,80})"],ptext)
    out["sonuc"]=first([r"Arabuluculuk\s+Sonucu\s*[:：]\s*([^\n<]{2,300})"],ptext)
    return out

def make_mapper(a,b):
    sm=difflib.SequenceMatcher(a=a,b=b,autojunk=False)
    blocks=sm.get_matching_blocks()
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
        s,l=int(m.group(1)),int(m.group(2))
        ns,ne=mp(s),mp(s+l)
        return f'startOffset="{ns}" length="{max(0,ne-ns)}"'
    return re.sub(r'startOffset="(\d+)"\s+length="(\d+)"',f,xml)

def section_bounds(text,key):
    if key.startswith("basvurucu"):
        p=text.find("BAŞVURU SAHİBİ BİLGİLERİ")
        if p<0:p=text.find("BAŞVURUCU BİLGİLERİ")
        q=text.find("KARŞI TARAF BİLGİLERİ",max(p,0))
        return max(p,0), q if q>p else len(text)
    if key.startswith("karsitaraf"):
        q=text.find("KARŞI TARAF BİLGİLERİ")
        if q<0:q=text.find("KARŞI TARAF")
        e=min([x for x in [text.find("Arabuluculuk Konusu Uyuşmazlık",max(q,0)),text.find("Arabuluculuk Sürecinin",max(q,0))] if x>=0] or [len(text)])
        return max(q,0),e
    if key.startswith("arabulucu"):
        p=min([x for x in [text.find("ARABULUCU BİLGİLERİ"),text.find("ARABULUCU :")] if x>=0] or [0])
        e=min([x for x in [text.find("BAŞVURU SAHİBİ BİLGİLERİ",p),text.find("BAŞVURUCU BİLGİLERİ",p),text.find("BAŞVURU SAHİBİ",p)] if x>=0] or [len(text)])
        return p,e
    return 0,len(text)

def pattern_for(key):
    return {
      "basvuruNo":r"BAŞVURU\s*NO\s*[:：]\s*([^\n<]*)",
      "dosyaNo":r"DOSYA\s*NO\s*[:：]\s*([^\n<]*)",
      "arabulucuAdi":r"(?:ARABULUCU\s*[:：]|Adı\s+Soyadı\s*[:：])\s*([^\n<]*)",
      "arabulucuTc":r"(?:T\.?\s*C\.?\s*KİMLİK\s+NUMARASI|TC\s+Kimlik\s+No)\s*[:：]\s*(\d{8,20})",
      "arabulucuSicil":r"(?:ARB\.?\s*SİCİL\s+NUMARASI|Arb\.?\s*Sicil\s*No)\s*[:：]\s*([^\n<]*)",
      "arabulucuAdres":r"(?:ADRESİ|Adresi)\s*[:：]\s*([^\n<]*)",
      "basvurucuTcKimlik":r"TC\s+Kimlik\s+No\s*[:：]\s*(\d{8,20})",
      "basvurucuAdiSoyadi":r"Adı\s+Soyadı\s*[:：]\s*([^\n<]*)",
      "basvurucuAdres":r"Adres\s*[:：]\s*([^\n<]*)",
      "basvurucuVekili":r"Vekili\s*[:：]\s*([^\n<]*)",
      "basvurucuTelefon":r"(?:Cep\s*Tel|Telefon\s+Numarası|Telefon)\s*[:：]\s*([^\n<]*)",
      "basvurucuEposta":r"E-Posta\s+Adresi\s*[:：]\s*([^\n<]*)",
      "karsitarafTcKimlik":r"TC\s+Kimlik\s+No\s*[:：]\s*(\d{8,20})",
      "karsitarafAdiSoyadi":r"Adı\s+Soyadı\s*[:：]\s*([^\n<]*)",
      "karsitarafAdres":r"Adres\s*[:：]\s*([^\n<]*)",
      "karsitarafVekili":r"Vekili\s*[:：]\s*([^\n<]*)",
      "uyusmazlik":r"Arabuluculuk\s+Konusu\s+Uyuşmazlık\s*[:：]\s*([^\n<]*)",
      "baslangicTarihi":r"Arabuluculuk\s+Sürecinin\s+Başladığı\s+Tarih\s*[:：]\s*([^\n<]*)",
      "bitisTarihi":r"Arabuluculuk\s+Sürecinin\s+Bittiği\s+Tarih\s*[:：]\s*([^\n<]*)",
      "duzenlemeYeri":r"Son\s+Tutanağın\s+Düzenlendiği\s+Yer\s*[:：]\s*([^\n<]*)",
      "duzenlemeTarihi":r"Son\s+Tutanağın\s+Düzenlendiği\s+Tarih\s*[:：]\s*([^\n<]*)",
      "sonuc":r"Arabuluculuk\s+Sonucu\s*[:：]\s*([^\n<]*)"
    }[key]

def replace_value(text,key,value):
    value=(value or "").strip()
    s,e=section_bounds(text,key)
    seg=text[s:e]
    m=re.search(pattern_for(key),seg,re.I)
    if not m:return text,False
    new=text[:s]+seg[:m.start(1)]+value+seg[m.end(1):]+text[e:]
    return new,True

def build_udf(files,xml,old,new):
    xml=update_offsets(xml,old,new)
    xml=re.sub(r"(<content><!\[CDATA\[).*?(\]\]></content>)",
               lambda m:m.group(1)+new+m.group(2),xml,1,re.S)
    out=io.BytesIO()
    with zipfile.ZipFile(out,"w",zipfile.ZIP_DEFLATED) as z:
        for n,d in files.items():
            # Yeni belgeye eski elektronik imza dosyasını taşımıyoruz.
            if n=="sign.sgn": continue
            z.writestr(n,xml.encode("utf-8") if n=="content.xml" else d)
    return out.getvalue()

TEMPLATES={
 "anlasma_son_tutanagi":("Anlaşma Son Tutanağı","anlasma_son_tutanagi.udf","ANLAŞMA"),
 "anlasmama_son_tutanagi":("Anlaşmama Son Tutanağı","anlasmama_son_tutanagi.udf","ANLAŞMAMA"),
 "anlasma_belgesi":("Anlaşma Tutanağı (Anlaşma Belgesi)","anlasma_belgesi.udf","ANLAŞMA BELGESİ")
}
TEMPLATE_DIR=Path(__file__).parent/"templates"/"udf"

def template_bytes(choice):
    if choice=="custom": return None
    if choice not in TEMPLATES: raise ValueError("Geçersiz şablon seçimi.")
    p=TEMPLATE_DIR/TEMPLATES[choice][1]
    if not p.exists(): raise ValueError("Seçilen hazır şablon sunucuda bulunamadı.")
    return p.read_bytes()

def standard_result(choice):
    return TEMPLATES.get(choice,("", "", ""))[2]

def home_html(error=None):
    err=f'<div class="err">{escape(str(error))}</div>' if error else ""
    return f"""<!doctype html><html lang="tr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Son Tutanak UDF Asistanı</title><style>
body{{font-family:Arial,sans-serif;background:#f2f5f8;margin:0;color:#20252b}}.box{{max-width:760px;margin:45px auto;background:#fff;padding:32px;border-radius:18px;box-shadow:0 5px 25px #0001}}input{{padding:12px;border:1px solid #ccd3db;border-radius:8px;width:100%;box-sizing:border-box}}button{{background:#1769e0;color:#fff;border:0;border-radius:9px;padding:14px 22px;font-weight:bold;cursor:pointer;width:100%}}.hint{{color:#65717d;font-size:14px}}.err{{background:#fff0f0;color:#900;padding:12px;border-radius:8px;margin-top:15px}}
</style></head><body><div class="box"><h1>Son Tutanak UDF Asistanı</h1>
<p>Başvuru Formu UDF dosyasını yükleyin. Uygulama bulabildiği bilgileri çıkarır; siz kontrol edip eksikleri tamamlayabilirsiniz.</p>
<form action="/edit" method="post" enctype="multipart/form-data"><input type="file" name="file" accept=".udf" required><br><br>
<button type="submit">Başvuru Formunu Analiz Et</button></form>{err}</div></body></html>"""

def field_html(k,v):
    label=LABELS[k]
    v=escape(v or "",quote=True)
    if k in ("basvurucuAdres","karsitarafAdres","arabulucuAdres","uyusmazlik","talep"):
        return f'<label>{escape(label)}</label><textarea name="{k}">{v}</textarea>'
    return f'<label>{escape(label)}</label><input name="{k}" value="{v}">'

def editor_html(filename,values):
    groups=[
      ("Dosya Bilgileri",["basvuruNo","dosyaNo"]),
      ("Arabulucu",["arabulucuAdi","arabulucuTc","arabulucuSicil","arabulucuAdres"]),
      ("Başvurucu",["basvurucuAdiSoyadi","basvurucuTcKimlik","basvurucuAdres","basvurucuVekili","basvurucuTelefon","basvurucuEposta"]),
      ("Karşı Taraf",["karsitarafAdiSoyadi","karsitarafTcKimlik","karsitarafAdres","karsitarafVekili"]),
      ("Süreç",["uyusmazlik","talep","baslangicTarihi","bitisTarihi","duzenlemeYeri","duzenlemeTarihi"])
    ]
    cards=""
    for title,keys in groups:
        cards+=f'<section class="card"><h2>{escape(title)}</h2>'+''.join(field_html(k,values.get(k,"")) for k in keys)+'</section>'
    options=''.join(f'<option value="{escape(k)}">{escape(v[0])}</option>' for k,v in TEMPLATES.items())
    hidden=""
    return f"""<!doctype html><html lang="tr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Son Tutanak Hazırla</title><style>
*{{box-sizing:border-box}}body{{font-family:Arial,sans-serif;background:#f2f5f8;margin:0;color:#20252b}}.wrap{{max-width:1050px;margin:25px auto;padding:0 16px}}.grid{{display:grid;grid-template-columns:1fr 1fr;gap:18px}}.card{{background:#fff;border-radius:16px;padding:22px;margin-bottom:18px;box-shadow:0 4px 20px #0001}}h2{{font-size:20px}}label{{display:block;font-weight:bold;margin-top:12px}}input,textarea,select{{width:100%;padding:10px;margin-top:5px;border:1px solid #ccd3db;border-radius:8px;font:inherit}}textarea{{min-height:80px;resize:vertical}}button{{width:100%;background:#1769e0;color:#fff;border:0;border-radius:9px;padding:14px;font-weight:bold;margin-top:18px;cursor:pointer}}.hint{{color:#65717d;font-size:13px}}.badge{{background:#eef5ff;padding:10px;border-radius:8px;margin-bottom:15px}}@media(max-width:800px){{.grid{{grid-template-columns:1fr}}}}
</style></head><body><div class="wrap"><h1>Son Tutanak Hazırla</h1><p class="hint">Kaynak: {escape(filename)}</p>
<form action="/build" method="post" enctype="multipart/form-data"><div class="grid"><div>{cards}</div><div>
<section class="card"><h2>Sonuç ve Belge Türü</h2><label>Belge türü</label><select name="template_choice" id="template_choice">{options}<option value="custom">Kendi UDF şablonumu yükle</option></select>
<div id="custom_box" style="display:none"><label>Özel Son Tutanak UDF</label><input type="file" name="custom_file" accept=".udf"></div>
<p class="hint">Hazır şablon seçerseniz uygulama kayıtlı UDF şablonunu kullanır. Özel şablon seçerseniz kendi UDF'niz kullanılır.</p>
<button type="submit">✓ Son Tutanağı Oluştur</button></section>
<section class="card"><h2>Kontrol</h2><div class="badge">Otomatik bulunan bilgiler düzenlenebilir. Bulunamayan alanları siz doldurabilirsiniz.</div>
<p class="hint">Uygulama hazır şablonları biçimleriyle birlikte kullanır. Değiştirilmiş belgelerde eski elektronik imza dosyası taşınmaz.</p></section>
</div></div></form></div>
<script>
const s=document.getElementById('template_choice'), c=document.getElementById('custom_box');
function toggle(){{c.style.display=s.value==='custom'?'block':'none';}}
s.addEventListener('change',toggle);toggle();
</script></body></html>"""

@app.get("/",response_class=HTMLResponse)
async def home(request:Request):
    return HTMLResponse(home_html())

@app.post("/edit",response_class=HTMLResponse)
async def edit(request:Request,file:UploadFile=File(...)):
    try:
        if not (file.filename or "").lower().endswith(".udf"): raise ValueError("Lütfen .udf dosyası seçin.")
        _,text,_=read_udf(await file.read())
        return HTMLResponse(editor_html(file.filename or "Başvuru Formu UDF",extract(text)))
    except Exception as e:
        return HTMLResponse(home_html(str(e)),status_code=400)

@app.post("/build")
async def build(request:Request):
    form=await request.form()
    choice=str(form.get("template_choice",""))
    values={k:str(form.get(k,"")).strip() for k,_ in FIELDS}
    if not values.get("sonuc"):
        values["sonuc"]=standard_result(choice)

    if choice=="custom":
        upload=form.get("custom_file")
        if not isinstance(upload,UploadFile): return HTMLResponse("Özel UDF şablonu seçtiniz; lütfen dosya yükleyin.",400)
        data=await upload.read()
        if not (upload.filename or "").lower().endswith(".udf"): return HTMLResponse("Özel şablon .udf olmalıdır.",400)
        source_name=Path(upload.filename or "son_tutanak").stem
        try: xml,old,files=read_udf(data)
        except Exception as e: return HTMLResponse(str(e),400)
    else:
        try: data=template_bytes(choice); source_name=Path(TEMPLATES[choice][1]).stem
        except Exception as e: return HTMLResponse(str(e),500)
        xml,old,files=read_udf(data)

    # Sonuç, seçilen belge türüne göre şablonda da değiştirilebilir.
    result_text=standard_result(choice)
    if choice!="custom" and result_text:
        values["sonuc"] = result_text

    new=old
    changed=[]
    for k,_ in FIELDS:
        v=values.get(k,"")
        if not v: continue
        new,ok=replace_value(new,k,v)
        if ok: changed.append(k)

    if new==old:
        return HTMLResponse("Şablonda değiştirilecek alan bulunamadı. Lütfen seçtiğiniz UDF şablonunun geçerli bir UDF olduğunu kontrol edin.",400)

    result=build_udf(files,xml,old,new)
    label=TEMPLATES[choice][0] if choice in TEMPLATES else "Özel Son Tutanak"
    name=re.sub(r"[^A-Za-z0-9ÇĞİÖŞÜçğıöşü _-]","_",source_name)+"_hazir.udf"
    return StreamingResponse(io.BytesIO(result),media_type="application/octet-stream",
        headers={"Content-Disposition":f'attachment; filename="{name}"'})
