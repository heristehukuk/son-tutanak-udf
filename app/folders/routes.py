from html import escape
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from app.auth.service import get_user_by_session, now
from app.database_layer import repos
from app.web import page
from app.folders.service import ensure_case_folders, get_folder

router = APIRouter()

def user(request):
    return get_user_by_session(request.cookies.get("session"))

def case_owned(u, case_id):
    c = repos.cases.get(case_id)
    return c if c and c.get("owner_id") == u["id"] else None

@router.get("/case/{case_id}", response_class=HTMLResponse)
async def case_folder(request: Request, case_id: str):
    u = user(request)
    if not u: return RedirectResponse("/auth/login", 303)
    case = case_owned(u, case_id)
    if not case: return HTMLResponse("Dosya bulunamadı.", 404)
    folders = ensure_case_folders(u["id"], case_id)
    docs = [d for d in repos.documents.list_by_owner(u["id"]) if d.get("case_id") == case_id]
    generated = [d for d in repos.generated_documents.list_by_owner(u["id"]) if d.get("case_id") == case_id]
    children = [f for f in folders if f.get("parent_id")]
    cards=[]
    for f in children:
        fid=f["id"]
        fd=[d for d in docs if d.get("folder_id")==fid]
        fg=[d for d in generated if d.get("folder_id")==fid]
        options = ''.join(f'<option value="{escape(x["id"])}">{escape(x["name"])}</option>' for x in children if x["id"] != fid)
        items=''.join(f'<li>{escape(d["original_name"])} <form style="display:inline" method="post" action="/folders/document/{d["id"]}/move"><select name="folder_id">{options}</select><button>Taşı</button></form></li>' for d in fd)
        items += ''.join(f'<li>{escape(d["original_template"])} (oluşturuldu)</li>' for d in fg)
        cards.append(f'''<div class="card"><h3>📁 {escape(f["name"])}</h3><p>{len(fd)+len(fg)} belge</p>
        <ul>{items or '<li>Bu klasör boş.</li>'}</ul>
        <form method="post" action="/folders/{fid}/rename"><input name="name" value="{escape(f["name"])}" required><button {'disabled' if f.get('folder_type') != 'custom' else ''}>Adı Değiştir</button></form>
        {('<form method="post" action="/folders/'+fid+'/delete"><button type="submit">Klasörü Sil</button></form>') if f.get('folder_type') == 'custom' else ''}
        </div>''')
    body=f'''<h1>📁 {escape(case.get("title") or "Dosya")}</h1>
    <p><b>Dosya No:</b> {escape(case.get("file_no") or "-")} &nbsp; <b>Başvuru No:</b> {escape(case.get("application_no") or "-")}</p>
    <p><a href="/files/">← Dosyalarıma dön</a></p>
    <div class="card"><h3>➕ Özel klasör ekle</h3><form method="post" action="/folders/create">
    <input type="hidden" name="case_id" value="{case_id}"><input name="name" placeholder="Klasör adı" required>
    <input type="hidden" name="parent_id" value="{next((f["id"] for f in folders if f.get("folder_type")=="root"), "")}"><button>Klasör Oluştur</button></form></div><div class="grid">{"".join(cards)}</div>'''
    return page("Dosya Klasörü", body)

@router.post("/{folder_id}/rename")
async def rename_folder(request: Request, folder_id: str, name: str = Form(...)):
    u=user(request)
    if not u:return RedirectResponse("/auth/login",303)
    f=get_folder(u["id"],folder_id)
    if not f:return HTMLResponse("Klasör bulunamadı.",404)
    if f.get("folder_type") != "custom":return HTMLResponse("Sistem klasörlerinin adı değiştirilemez.",403)
    if not name.strip():return HTMLResponse("Klasör adı boş olamaz.",400)
    repos.folders.update(folder_id,{"name":name.strip(),"updated_at":now().isoformat()})
    return RedirectResponse(f'/folders/case/{f["case_id"]}',303)

@router.post("/create")
async def create_folder(request: Request, case_id: str = Form(...), name: str = Form(...), parent_id: str = Form("")):
    u=user(request)
    if not u:return RedirectResponse("/auth/login",303)
    case=case_owned(u,case_id)
    if not case:return HTMLResponse("Dosya bulunamadı.",404)
    ensure_case_folders(u["id"],case_id)
    repos.folders.create({"id":str(__import__('uuid').uuid4()),"owner_id":u["id"],"case_id":case_id,
        "parent_id":parent_id or None,"name":name.strip(),"folder_type":"custom",
        "created_at":now().isoformat(),"updated_at":now().isoformat()})
    return RedirectResponse(f'/folders/case/{case_id}',303)

@router.post("/document/{document_id}/move")
async def move_document(request: Request, document_id: str, folder_id: str = Form(...)):
    u=user(request)
    if not u:return RedirectResponse("/auth/login",303)
    d=repos.documents.get(document_id)
    f=get_folder(u["id"],folder_id) if folder_id else None
    if not d or d.get("owner_id")!=u["id"] or not f or d.get("case_id")!=f.get("case_id"):
        return HTMLResponse("Belge veya klasör bulunamadı.",404)
    repos.documents.update(document_id,{"folder_id":folder_id})
    return RedirectResponse(f'/folders/case/{f["case_id"]}',303)


@router.post("/{folder_id}/delete")
async def delete_folder(request: Request, folder_id: str):
    u=user(request)
    if not u:return RedirectResponse("/auth/login",303)
    f=get_folder(u["id"],folder_id)
    if not f:return HTMLResponse("Klasör bulunamadı.",404)
    if f.get("folder_type") != "custom":return HTMLResponse("Sistem klasörleri silinemez.",403)
    case_id=f.get("case_id")
    repos.folders.delete(folder_id)
    return RedirectResponse(f'/folders/case/{case_id}',303)
