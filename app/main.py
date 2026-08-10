import io,re,zipfile,difflib
from pathlib import Path
from fastapi import FastAPI,Request,UploadFile,File
from fastapi.responses import HTMLResponse,StreamingResponse
from html import escape

app=FastAPI(title="Son Tutanak UDF Düzenleyici")

FIELDS=[('basvuruNo', 'Başvuru No'), ('dosyaNo', 'Dosya No'), ('arabulucuAdi', 'Arabulucu'), ('arabulucuTc', 'Arabulucu T.C. Kimlik No'), ('arabulucuSicil', 'Arabulucu Sicil No'), ('arabulucuAdres', 'Arabulucu Adres'), ('basvurucuTcKimlik', 'Başvurucu T.C. Kimlik No'), ('basvurucuAdiSoyadi', 'Başvurucu Adı Soyadı'), ('basvurucuAdres', 'Başvurucu Adres'), ('basvurucuVekili', 'Başvurucu Vekili'), ('basvurucuTelefon', 'Başvurucu Telefon'), ('basvurucuEposta', 'Başvurucu E-Posta'), ('karsitarafTcKimlik', 'Karşı Taraf T.C. Kimlik No'), ('karsitarafAdiSoyadi', 'Karşı Taraf Adı Soyadı'), ('karsitarafAdres', 'Karşı Taraf Adres'), ('karsitarafVekili', 'Karşı Taraf Vekili'), ('uyusmazlik', 'Uyuşmazlık Konusu'), ('baslangicTarihi', 'Süreç Başlangıç Tarihi'), ('bitisTarihi', 'Süreç Bitiş Tarihi'), ('duzenlemeYeri', 'Tutanak Düzenleme Yeri'), ('duzenlemeTarihi', 'Tutanak Düzenleme Tarihi'), ('sonuc', 'Sonuç')]
PAT={
"basvuruNo":r"BAŞVURU NO\s*[:：]\s*([^\n]*)","dosyaNo":r"DOSYA\s+NO\s*[:：]\s*([^\n]*)",
"arabulucuAdi":r"ARABULUCU\s*[:：]\s*([^\n]*)","arabulucuTc":r"T\.C KİMLİK NUMARASI\s*[:：]\s*([^\n]*)",
"arabulucuSicil":r"ARB\. SİCİL NUMARASI\s*[:：]\s*([^\n]*)","arabulucuAdres":r"ADRESİ\s*[:：]\s*([^\n]*)",
"basvurucuTcKimlik":r"TC Kimlik No\s*[:：]\s*([^\n]*)","basvurucuAdiSoyadi":r"Adı Soyadı\s*[:：]\s*([^\n]*)",
"basvurucuAdres":r"Adres\s*[:：]\s*([^\n]*)","basvurucuVekili":r"Vekili\s*[:：]\s*([^\n]*)",
"basvurucuTelefon":r"Telefon Numarası\s*[:：]\s*([^\n]*)","basvurucuEposta":r"E-Posta Adresi\s*[:：]\s*([^\n]*)",
"karsitarafTcKimlik":r"TC Kimlik No\s*[:：]\s*([^\n]*)","karsitarafAdiSoyadi":r"Adı Soyadı\s*[:：]\s*([^\n]*)",
"karsitarafAdres":r"Adres\s*[:：]\s*([^\n]*)","karsitarafVekili":r"Vekili\s*[:：]\s*([^\n]*)",
"uyusmazlik":r"Arabuluculuk Konusu Uyuşmazlık\s*[:：]\s*([^\n]*)",
"baslangicTarihi":r"Arabuluculuk Sürecinin Başladığı Tarih\s*[:：]\s*([^\n]*)",
"bitisTarihi":r"Arabuluculuk Sürecinin Bittiği Tarih\s*[:：]\s*([^\n]*)",
"duzenlemeYeri":r"Son Tutanağın Düzenlendiği Yer\s*[:：]\s*([^\n]*)",
"duzenlemeTarihi":r"Son Tutanağın Düzenlendiği Tarih\s*[:：]\s*([^\n]*)",
"sonuc":r"Arabuluculuk Sonucu\s*[:：]\s*([^\n]*)"}

def read_udf(data):
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            if "content.xml" not in z.namelist(): raise ValueError("content.xml bulunamadı.")
            xml=z.read("content.xml").decode("utf-8")
            files={n:z.read(n) for n in z.namelist()}
    except zipfile.BadZipFile: raise ValueError("Geçerli bir UDF dosyası seçin.")
    m=re.search(r"<content><!\[CDATA\[(.*?)\]\]></content>",xml,re.S)
    if not m: raise ValueError("UDF metin alanı okunamadı.")
    return xml,m.group(1),files

def extract(text):
    out={k:"" for k,_ in FIELDS}; p=text.find("BAŞVURU SAHİBİ BİLGİLERİ"); q=text.find("KARŞI TARAF BİLGİLERİ")
    for k,_ in FIELDS:
        seg=text[p:q] if k.startswith("basvurucu") and p>=0 and q>p else text[q:] if k.startswith("karsitaraf") and q>=0 else text
        m=re.search(PAT[k],seg,re.I)
        if m: out[k]=m.group(1).strip()
    return out

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

def replace_value(text,key,value):
    value=(value or "").strip()
    if key.startswith("basvurucu"):
        p=text.find("BAŞVURU SAHİBİ BİLGİLERİ"); q=text.find("KARŞI TARAF BİLGİLERİ"); s=max(p,0); e=q if q>p else len(text)
    elif key.startswith("karsitaraf"):
        q=text.find("KARŞI TARAF BİLGİLERİ"); s=max(q,0); e=len(text)
    else:s,e=0,len(text)
    seg=text[s:e]; m=re.search(PAT[key],seg,re.I)
    return text if not m else text[:s]+seg[:m.start(1)]+value+seg[m.end(1):]+text[e:]

def build_udf(files,xml,a,b):
    xml=update_offsets(xml,a,b)
    xml=re.sub(r"(<content><!\[CDATA\[).*?(\]\]></content>)",lambda m:m.group(1)+b+m.group(2),xml,1,re.S)
    out=io.BytesIO()
    with zipfile.ZipFile(out,"w",zipfile.ZIP_DEFLATED) as z:
        for n,d in files.items(): z.writestr(n,xml.encode() if n=="content.xml" else d)
    return out.getvalue()


def home_html(error=None):
    err = f'<div class="err">{escape(str(error))}</div>' if error else ''
    return f"""<!doctype html><html lang="tr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Son Tutanak UDF Düzenleyici</title>
<style>
body{{font-family:Arial,sans-serif;background:#f2f5f8;margin:0;color:#20252b}}
.box{{max-width:720px;margin:45px auto;background:#fff;padding:30px;border-radius:18px;box-shadow:0 5px 25px #0001}}
input{{padding:12px;border:1px solid #ccd3db;border-radius:8px;width:100%;box-sizing:border-box}}
button{{background:#1769e0;color:#fff;border:0;border-radius:9px;padding:14px 22px;font-weight:bold;cursor:pointer}}
.err{{background:#fff0f0;color:#900;padding:12px;border-radius:8px;margin-top:15px}}
</style></head><body><div class="box">
<h1>Son Tutanak UDF Düzenleyici</h1>
<p>UDF dosyanızı yükleyin; mevcut bilgiler otomatik olarak düzenleme ekranına getirilecektir.</p>
<form action="/edit" method="post" enctype="multipart/form-data">
<input type="file" name="file" accept=".udf" required><br><br>
<button type="submit">Dosyayı Aç ve Analiz Et</button></form>{err}</div></body></html>"""

def editor_html(filename, values):
    def val(k): return escape(values.get(k, ''), quote=True)
    def area(k): return escape(values.get(k, ''), quote=False)
    labels = dict(FIELDS)
    groups=[
      ("Dosya Bilgileri",["basvuruNo","dosyaNo"]),
      ("Arabulucu",["arabulucuAdi","arabulucuTc","arabulucuSicil","arabulucuAdres"]),
      ("Başvurucu",["basvurucuTcKimlik","basvurucuAdiSoyadi","basvurucuAdres","basvurucuVekili","basvurucuTelefon","basvurucuEposta"]),
      ("Karşı Taraf",["karsitarafTcKimlik","karsitarafAdiSoyadi","karsitarafAdres","karsitarafVekili"])
    ]
    cards=''
    for title, keys in groups:
        fields=''
        for k in keys:
            label=labels[k]
            if "Adres" in label:
                fields += f'<label>{escape(label)}</label><textarea name="{k}">{area(k)}</textarea>'
            else:
                fields += f'<label>{escape(label)}</label><input name="{k}" value="{val(k)}">'
        cards += f'<div class="card"><h2>{escape(title)}</h2>{fields}</div>'
    process=''
    for k in ["uyusmazlik","baslangicTarihi","bitisTarihi","duzenlemeYeri","duzenlemeTarihi"]:
        process += f'<label>{escape(labels[k])}</label><input name="{k}" value="{val(k)}">'
    sonuc=values.get("sonuc","")
    a_sel='selected' if sonuc=="Anlaşma" else ''
    aa_sel='selected' if sonuc!="Anlaşma" else ''
    return f"""<!doctype html><html lang="tr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Son Tutanak Düzenle</title>
<style>
*{{box-sizing:border-box}}body{{font-family:Arial,sans-serif;background:#f2f5f8;margin:0;color:#20252b}}
.wrap{{max-width:1100px;margin:25px auto;padding:0 16px}}.grid{{display:grid;grid-template-columns:1fr 1fr;gap:18px}}
.card{{background:#fff;border-radius:16px;padding:22px;margin-bottom:18px;box-shadow:0 4px 20px #0001}}
label{{display:block;font-weight:bold;margin-top:12px}}input,textarea,select{{width:100%;padding:10px;margin-top:5px;border:1px solid #ccd3db;border-radius:8px;font:inherit}}
textarea{{min-height:75px;resize:vertical}}button{{width:100%;background:#1769e0;color:#fff;border:0;border-radius:9px;padding:14px;font-weight:bold;margin-top:18px}}
.hint{{color:#65717d;font-size:13px}}@media(max-width:800px){{.grid{{grid-template-columns:1fr}}}}
</style></head><body><div class="wrap">
<h1>Son Tutanak Düzenleyici</h1><p class="hint">{escape(filename)} — mevcut bilgiler otomatik getirildi.</p>
<form action="/build" method="post" enctype="multipart/form-data">
<div class="grid"><div>{cards}</div><div>
<div class="card"><h2>Süreç ve Sonuç</h2>{process}
<label>Arabuluculuk Sonucu</label>
<select name="sonuc"><option value="Anlaşamama" {aa_sel}>Anlaşamama</option>
<option value="Anlaşma" {a_sel}>Anlaşma</option></select></div>
<div class="card"><h2>UDF Oluştur</h2><p class="hint">Orijinal UDF dosyasını tekrar seçin.</p>
<input type="file" name="file" accept=".udf" required>
<button type="submit">✓ Otomatik Düzenle ve UDF Oluştur</button>
<p class="hint">UDF içindeki ofsetler yeniden hesaplanır. Elektronik imza üretilmez veya yenilenmez.</p>
</div></div></div></form></div></body></html>"""

@app.get("/",response_class=HTMLResponse)
async def home(request:Request):
    return HTMLResponse(home_html())

@app.post("/edit",response_class=HTMLResponse)
async def edit(request:Request,file:UploadFile=File(...)):
    try:
        if not (file.filename or "").lower().endswith(".udf"): raise ValueError("Lütfen .udf dosyası seçin.")
        _,text,_=read_udf(await file.read())
        return HTMLResponse(editor_html(file.filename or "UDF", extract(text)))
    except Exception as e:
        return HTMLResponse(home_html(str(e)), status_code=400)

@app.post("/build")
async def build(request:Request,file:UploadFile=File(...)):
    if not (file.filename or "").lower().endswith(".udf"): return HTMLResponse("Lütfen .udf dosyası seçin.",400)
    xml,old,files=read_udf(await file.read()); form=await request.form(); new=old
    for k,_ in FIELDS:
        if k in form: new=replace_value(new,k,str(form[k]))
    result=build_udf(files,xml,old,new)
    name=Path(file.filename or "son_tutanak.udf").stem+"_duzenlenmis.udf"
    return StreamingResponse(io.BytesIO(result),media_type="application/octet-stream",headers={"Content-Disposition":f'attachment; filename="{name}"'})
