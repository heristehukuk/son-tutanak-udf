
from html import escape
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse
from app.auth.service import get_user_by_session, now
from app.database import connect
from app.database_layer import repos
from app.web import page
from app.customtemplates.service import list_all_templates
from app.feepusula.service import list_tariffs, add_tariff, delete_tariff, CATEGORY_LABELS
router=APIRouter()

def admin(request):
    u=get_user_by_session(request.cookies.get("session"))
    return u if u and u["is_super_admin"] else None

@router.get("/",response_class=HTMLResponse)
async def dashboard(request:Request):
    if not admin(request):return HTMLResponse("Yetkisiz.",403)
    with connect() as c:
        users=c.execute("""SELECT id,email,display_name,status,plan_id,created_at,last_ip
                           FROM users ORDER BY created_at DESC""").fetchall()
        docs=c.execute("""SELECT d.*,u.email FROM documents d JOIN users u ON u.id=d.owner_id
                          ORDER BY d.created_at DESC""").fetchall()
    us=[]
    for r in users:
        us.append(
            f'<div class="card"><b>{r["display_name"]}</b> — {r["email"]}'
            f'<p>Durum: {r["status"]} | Plan: {r["plan_id"]} | IP: {r["last_ip"] or "-"}</p>'
            f'<form method="post" action="/admin/users/{r["id"]}/status">'
            f'<select name="status"><option>pending</option><option>active</option>'
            f'<option>suspicious</option><option>rejected</option><option>banned</option></select>'
            f'<button>Durumu Kaydet</button></form></div>'
        )
    ds=[]
    for r in docs:
        ds.append(f'<div class="card"><b>{r["original_name"]}</b><p>{r["email"]} | {r["size_bytes"]} bytes</p>'
                  f'<a href="/admin/documents/{r["id"]}">Belgeyi Gör/İndir</a></div>')
    ts=[]
    for t in list_all_templates():
        paylasim = "Paylaşılan (ortak)" if t["is_shared"] else "Kişisel"
        ts.append(f'<div class="card"><b>{escape(t["name"])}</b>'
                  f'<p>{escape(t["owner_name"])} — {escape(t["owner_email"])} | {escape(paylasim)}</p>'
                  f'<a href="/admin/templates/{escape(t["id"])}">Şablonu Gör/İndir</a></div>')
    return page("Admin","<h1>Yönetim</h1><h2>Üyeler</h2>"+''.join(us)+
                "<h2>Yüklenen Belgeler</h2>"+''.join(ds)+
                "<h2>Kullanıcı Şablonları (Tümü)</h2>"+(''.join(ts) or "<p>Henüz özel şablon yok.</p>")+
                "<h2>Arabuluculuk Ücret Tarifesi</h2><p><a href=\"/admin/tariffs\"><button>Tarifeyi Yönet</button></a></p>")

@router.get("/tariffs",response_class=HTMLResponse)
async def tariffs_page(request:Request):
    if not admin(request):return HTMLResponse("Yetkisiz.",403)
    rows=list_tariffs()
    trs=[]
    for r in rows:
        trs.append(f'<tr><td>{r["year"]}</td><td>{r["category_label"]}</td>'
                   f'<td>{r["min_parties"]}{"+" if r["max_parties"] is None else "-"+str(r["max_parties"])}</td>'
                   f'<td>{r["unit_price"]:.2f} ₺</td>'
                   f'<td><form method="post" action="/admin/tariffs/{r["id"]}/delete" '
                   f'onsubmit="return confirm(\'Silinsin mi?\')"><button class="secondary">Sil</button></form></td></tr>')
    table = ('<table style="width:100%"><tr><th>Yıl</th><th>Kategori</th><th>Taraf Sayısı</th>'
             '<th>Birim Fiyat</th><th></th></tr>'+''.join(trs)+'</table>') if trs else "<p>Henüz tarife eklenmedi.</p>"
    cat_options=''.join(f'<option value="{k}">{v}</option>' for k,v in CATEGORY_LABELS.items())
    body=f"""<h1>Arabuluculuk Ücret Tarifesi</h1>
    <p><a href="/admin/">Yönetime Dön</a></p>
    <div class="card"><h2>Yeni Tarife Satırı Ekle</h2>
    <form method="post" action="/admin/tariffs/add">
    <label>Yıl</label><input type="number" name="year" value="2026" required>
    <label>Kategori</label><select name="category">{cat_options}</select>
    <label>Min. Taraf Sayısı</label><input type="number" name="min_parties" value="2" required>
    <label>Maks. Taraf Sayısı (sınırsızsa boş bırakın)</label><input type="number" name="max_parties">
    <label>Birim Fiyat (TL)</label><input type="number" step="0.01" name="unit_price" required>
    <button>Ekle</button></form></div>
    <div class="card">{table}</div>"""
    return page("Ücret Tarifesi",body)

@router.post("/tariffs/add")
async def add_tariff_row(request:Request,year:int=Form(...),category:str=Form(...),
                          min_parties:int=Form(...),max_parties:str=Form(""),unit_price:float=Form(...)):
    if not admin(request):return HTMLResponse("Yetkisiz.",403)
    add_tariff(category,min_parties,int(max_parties) if max_parties.strip() else None,unit_price,year)
    return RedirectResponse("/admin/tariffs",303)

@router.post("/tariffs/{tariff_id}/delete")
async def remove_tariff_row(request:Request,tariff_id:str):
    if not admin(request):return HTMLResponse("Yetkisiz.",403)
    delete_tariff(tariff_id)
    return RedirectResponse("/admin/tariffs",303)

@router.get("/templates/{template_id}")
async def download_template(request:Request,template_id:str):
    if not admin(request):return HTMLResponse("Yetkisiz.",403)
    with connect() as c:r=c.execute("SELECT * FROM custom_templates WHERE id=?",(template_id,)).fetchone()
    if not r:return HTMLResponse("Şablon bulunamadı.",404)
    return FileResponse(r["stored_path"],filename=r["name"]+".udf")

@router.post("/users/{user_id}/status")
async def status(request:Request,user_id:str,status:str=Form(...)):
    if not admin(request):return HTMLResponse("Yetkisiz.",403)
    repos.users.update(user_id,{"status":status,"approved_at":now().isoformat() if status=="active" else None})
    return HTMLResponse('<meta http-equiv="refresh" content="0;url=/admin/">')

@router.get("/documents/{doc_id}")
async def download_document(request:Request,doc_id:str):
    if not admin(request):return HTMLResponse("Yetkisiz.",403)
    with connect() as c:r=c.execute("SELECT * FROM documents WHERE id=?",(doc_id,)).fetchone()
    if not r:return HTMLResponse("Belge bulunamadı.",404)
    return FileResponse(r["stored_path"],filename=r["original_name"])
