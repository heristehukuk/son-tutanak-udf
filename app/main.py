import io,re,zipfile,difflib
from pathlib import Path
from fastapi import FastAPI,Request,UploadFile,File,Form
from fastapi.responses import HTMLResponse,StreamingResponse
from fastapi.templating import Jinja2Templates

app=FastAPI(title="Son Tutanak UDF Web")
templates=Jinja2Templates(directory=str(Path(__file__).parent/"templates"))

FIELDS=[
("basvuruNo","Başvuru No"),("dosyaNo","Dosya No"),
("arabulucuAdi","Arabulucu"),("arabulucuTc","Arabulucu T.C. Kimlik No"),
("arabulucuSicil","Arabulucu Sicil No"),("arabulucuAdres","Arabulucu Adres"),
("basvurucuTcKimlik","Başvurucu T.C. Kimlik No"),("basvurucuAdiSoyadi","Başvurucu Adı Soyadı"),
("basvurucuAdres","Başvurucu Adres"),("basvurucuVekili","Başvurucu Vekili"),
("basvurucuTelefon","Başvurucu Telefon"),("basvurucuEposta","Başvurucu E-Posta"),
("karsitarafTcKimlik","Karşı Taraf T.C. Kimlik No"),("karsitarafAdiSoyadi","Karşı Taraf Adı Soyadı"),
("karsitarafAdres","Karşı Taraf Adres"),("karsitarafVekili","Karşı Taraf Vekili"),
("uyusmazlik","Uyuşmazlık Konusu"),("baslangicTarihi","Süreç Başlangıç Tarihi"),
("bitisTarihi","Süreç Bitiş Tarihi"),("duzenlemeYeri","Tutanak Düzenleme Yeri"),
("duzenlemeTarihi","Tutanak Düzenleme Tarihi"),("sonuc","Sonuç")]

PAT={
"basvuruNo":r"BAŞVURU NO\s*:\s*([^\n]*)","dosyaNo":r"DOSYA\s+NO\s*[:：]\s*([^\n]*)",
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

def read(data):
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        xml=z.read("content.xml").decode()
        files={n:z.read(n) for n in z.namelist()}
    m=re.search(r"<content><!\[CDATA\[(.*?)\]\]></content>",xml,re.S)
    if not m: raise ValueError("UDF content.xml okunamadı")
    return xml,m.group(1),files

def extract(text):
    out={}
    p=text.find("BAŞVURU SAHİBİ BİLGİLERİ"); q=text.find("KARŞI TARAF BİLGİLERİ")
    for key,_ in FIELDS:
        if key.startswith("basvurucu"): seg=text[p:q] if p>=0 and q>p else text
        elif key.startswith("karsitaraf"): seg=text[q:] if q>=0 else text
        else: seg=text
        m=re.search(PAT[key],seg,re.I)
        out[key]=m.group(1).strip() if m else ""
    return out

def mapper(a,b):
    sm=difflib.SequenceMatcher(a=a,b=b,autojunk=False); blocks=sm.get_matching_blocks()
    def mp(p):
        if p<=0:return 0
        if p>=len(a):return len(b)
        for x in blocks:
            if x.a<=p<=x.a+x.size:return x.b+p-x.a
        prev=max((x for x in blocks if x.a<p),default=None,key=lambda x:x.a)
        return (prev.b+min(p-prev.a,prev.size)) if prev else 0
    return mp

def rebuild(xml,a,b):
    mp=mapper(a,b)
    def f(m):
        s,l=int(m.group(1)),int(m.group(2)); ns=mp(s); ne=mp(s+l)
        return f'startOffset="{ns}" length="{max(0,ne-ns)}"'
    return re.sub(r'startOffset="(\d+)"\s+length="(\d+)"',f,xml)

def replace(text,key,val):
    val=(val or "").strip()
    if key.startswith("basvurucu"):
        p=text.find("BAŞVURU SAHİBİ BİLGİLERİ"); q=text.find("KARŞI TARAF BİLGİLERİ"); s,e=max(p,0),q if q>p else len(text)
    elif key.startswith("karsitaraf"):
        q=text.find("KARŞI TARAF BİLGİLERİ"); s,e=max(q,0),len(text)
    else:s,e=0,len(text)
    chunk=text[s:e]; m=re.search(PAT[key],chunk,re.I)
    if not m:return text
    return text[:s]+chunk[:m.start(1)]+val+chunk[m.end(1):]+text[e:]

def make(files,xml,a,b):
    xml=rebuild(xml,a,b)
    xml=re.sub(r"(<content><!\[CDATA\[).*?(\]\]></content>)",lambda m:m.group(1)+b+m.group(2),xml,1,re.S)
    out=io.BytesIO()
    with zipfile.ZipFile(out,"w",zipfile.ZIP_DEFLATED) as z:
        for n,d in files.items(): z.writestr(n,xml.encode() if n=="content.xml" else d)
    return out.getvalue()

@app.get("/",response_class=HTMLResponse)
async def home(request:Request):
    return templates.TemplateResponse("index.html",{"request":request})

@app.post("/edit",response_class=HTMLResponse)
async def edit(request:Request,file:UploadFile=File(...)):
    try:
        data=await file.read(); xml,text,files=read(data); vals=extract(text)
        return templates.TemplateResponse("editor.html",{"request":request,"filename":file.filename,"values":vals,"fields":FIELDS})
    except Exception as e:
        return templates.TemplateResponse("index.html",{"request":request,"error":str(e)})

@app.post("/build")
async def build(request:Request,file:UploadFile=File(...)):
    data=await file.read(); xml,old,files=read(data); form=await request.form()
    new=old
    for key,_ in FIELDS:
        if key in form:new=replace(new,key,str(form[key]))
    result=make(files,xml,old,new)
    name=Path(file.filename or "son_tutanak.udf").stem+"_duzenlenmis.udf"
    return StreamingResponse(io.BytesIO(result),media_type="application/octet-stream",
        headers={"Content-Disposition":f'attachment; filename="{name}"'})
