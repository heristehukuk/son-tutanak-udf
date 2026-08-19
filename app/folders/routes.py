from html import escape
from uuid import uuid4
from datetime import datetime, timezone
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from app.auth.service import require_active_user
from app.database_layer import repos
from app.folders.service import (
    ensure_case_folders, visible_folders, delete_folder as svc_delete_folder,
    restore_folder as svc_restore_folder, grant_folder_access, revoke_folder_access,
    can_view_folder,
)

router = APIRouter(prefix="/folders", tags=["folders"])

def current_user(request):
    return require_active_user(request.cookies.get("session"))

def is_admin(u): return bool(u and u.get("is_super_admin"))

def stamp(): return datetime.now(timezone.utc).isoformat(timespec="seconds")

def get_case(u, case_id):
    c = repos.cases.get(case_id) if case_id else None
    return c if c and (is_admin(u) or c.get("owner_id") == u["id"]) else None

@router.get("", response_class=HTMLResponse)
async def folders_home(request: Request):
    u=current_user(request)
    if not u: return RedirectResponse("/auth/login",303)
    general=repos.folders.list_general()
    cases=repos.cases.list_by_owner(u["id"])
    cards=[f'<div class="card"><b>🌐 {escape(g.get("name") or "")}</b><p>Genel klasör</p></div>' for g in general]
    for c in cases:
        if c.get("status")=="deleted": continue
        ensure_case_folders(u["id"],c["id"])
        href=f'/folders/case/{c["id"]}'
        cards.append(f'<div class="card"><b>📁 {escape(c.get("title") or "Dosya")}</b><p>{escape(c.get("file_no") or "Dosya No yok")} · <a href="{href}">Klasörü Aç</a></p></div>')
    body="""<style>body{font-family:Arial;background:#f3f6f9}.wrap{max-width:1100px;margin:25px auto}.card{background:#fff;border-radius:14px;padding:18px;margin:10px 0;box-shadow:0 3px 16px #0001}a{color:#1769e0;text-decoration:none}</style>"""+"<div class='wrap'><h1>📁 Klasörlerim</h1><p><a href='/files/'>← Dosyalar</a></p>"+(''.join(cards) or '<p>Klasör bulunmuyor.</p>')+"</div>"
    return HTMLResponse(body)

@router.get("/case/{case_id}", response_class=HTMLResponse)
async def case_folder(request: Request, case_id: str):
    u=current_user(request)
    if not u: return RedirectResponse("/auth/login",303)
    case=get_case(u,case_id)
    if not case:return HTMLResponse("Dosya bulunamadı veya erişim yetkiniz yok.",404)
    ensure_case_folders(case.get("owner_id"),case_id)
    # A case folder page is strictly scoped to the selected case.
    # Do not include global folders, other cases, or deleted folders here.
    case_folders = repos.folders.list_for_case(case_id)
    folders = [
        f for f in case_folders
        if f.get("status") == "active" and can_view_folder(u, f)
    ]
    docs=repos.documents.list_by_case(case_id); gens=repos.generated_documents.list_by_case(case_id)
    by={}
    for d in docs: by.setdefault(d.get("folder_id"),[]).append((d.get("original_name") or "Belge","kaynak"))
    for d in gens: by.setdefault(d.get("folder_id"),[]).append((d.get("original_template") or "Belge","oluşturuldu"))
    cards=[]
    for f in folders:
        actions=[]
        can_owner=f.get("owner_id")==u["id"] and not f.get("is_system")
        if is_admin(u) or can_owner:
            actions.append(f'<form method="post" action="/folders/{f["id"]}/rename"><input name="name" value="{escape(f.get("name") or "")}" required><button>Adı Değiştir</button></form>')
            actions.append(f'<form method="post" action="/folders/{f["id"]}/delete" onsubmit="return confirm(\'Klasör silinsin mi?\')"><button class="danger">🗑️ Sil</button></form>')
        items=by.get(f.get("id"),[])
        cards.append(f'<div class="folder"><div class="row"><div><b>📁 {escape(f.get("name") or "")}</b><small>{"Sistem" if f.get("is_system") else "Özel"} · {escape(f.get("status") or "")}</small></div><div class="actions">{"".join(actions)}</div></div><div class="docs">{("".join(f"📄 {escape(n)} <small>({escape(k)})</small><br>" for n,k in items) or "<small>Henüz belge yok.</small>")}</div></div>')
    create=f'''<div class="card"><h3>➕ Özel klasör oluştur</h3><form method="post" action="/folders/create"><input type="hidden" name="case_id" value="{escape(case_id)}"><input name="name" placeholder="Klasör adı" required><button>Oluştur</button></form></div>''' if case.get("owner_id")==u["id"] else ""
    body='''<style>body{font-family:Arial;background:#f3f6f9}.wrap{max-width:1120px;margin:25px auto;padding:0 16px}.card,.folder{background:#fff;border-radius:14px;padding:18px;margin:12px 0;box-shadow:0 3px 16px #0001}.row{display:flex;justify-content:space-between;gap:12px;align-items:center;flex-wrap:wrap}.actions{display:flex;gap:8px;align-items:center;flex-wrap:wrap}button{border:0;border-radius:8px;padding:9px 12px;background:#1769e0;color:#fff;font-weight:700}button.danger{background:#b91c1c}input{padding:8px;border:1px solid #ccd4dc;border-radius:8px}small{display:block;color:#64748b;margin-top:4px}.docs{margin-top:12px;line-height:1.8}</style>'''+f'<div class="wrap"><h1>📁 {escape(case.get("title") or "Dosya")}</h1><p><b>Dosya No:</b> {escape(case.get("file_no") or "-")} · <b>Başvuru No:</b> {escape(case.get("application_no") or "-")}</p><p><a href="/files/">← Dosyalar</a> · <a href="/tasks/?case_id={case_id}">📋 Görevler</a> · <a href="/calendar">📅 Takvim</a></p>{create}{"".join(cards) or "<div class=card>Görüntülenebilir klasör yok.</div>"}</div>'
    return HTMLResponse(body)

@router.post("/create")
async def create_folder(request: Request, case_id: str=Form(...), name: str=Form(...)):
    u=current_user(request)
    if not u:return RedirectResponse("/auth/login",303)
    case=get_case(u,case_id)
    if not case or case.get("owner_id")!=u["id"]:return HTMLResponse("Yetkisiz.",403)
    rows=ensure_case_folders(u["id"],case_id); root=next((x for x in rows if x.get("folder_type")=="root" and x.get("status")=="active"),None)
    name=str(name).strip()
    if not name:return HTMLResponse("Klasör adı boş olamaz.",400)
    repos.folders.create({"id":str(uuid4()),"case_id":case_id,"owner_id":u["id"],"parent_id":root.get("id") if root else None,"name":name,"folder_type":"custom","code":None,"sort_order":1000,"is_system":0,"is_global":0,"status":"active","created_at":stamp(),"updated_at":stamp()})
    return RedirectResponse(f"/folders/case/{case_id}",303)

@router.post("/{folder_id}/rename")
async def rename_folder(request: Request, folder_id: str, name: str=Form(...)):
    u=current_user(request)
    if not u:return RedirectResponse("/auth/login",303)
    f=repos.folders.get(folder_id)
    if not f:return HTMLResponse("Klasör bulunamadı.",404)
    if not (is_admin(u) or (f.get("owner_id")==u["id"] and not f.get("is_system"))):return HTMLResponse("Yetkisiz.",403)
    if f.get("status")=="deleted":return HTMLResponse("Silinmiş klasör yeniden adlandırılamaz.",400)
    name=str(name).strip()
    if not name:return HTMLResponse("Klasör adı boş olamaz.",400)
    repos.folders.update(folder_id,{"name":name,"updated_at":stamp()})
    return RedirectResponse(f'/folders/case/{f.get("case_id")}',303) if f.get("case_id") else RedirectResponse('/folders/admin',303)

@router.post("/{folder_id}/delete")
async def delete_folder(request: Request, folder_id: str):
    u=current_user(request)
    if not u:return RedirectResponse("/auth/login",303)
    try:f=svc_delete_folder(u,folder_id)
    except PermissionError as e:return HTMLResponse(str(e),403)
    except ValueError as e:return HTMLResponse(str(e),404)
    return RedirectResponse(f'/folders/case/{f.get("case_id")}',303) if f.get("case_id") else RedirectResponse('/folders/admin',303)

@router.post("/{folder_id}/restore")
async def restore_folder(request: Request, folder_id: str):
    u=current_user(request)
    if not u:return RedirectResponse("/auth/login",303)
    try:svc_restore_folder(u,folder_id)
    except PermissionError as e:return HTMLResponse(str(e),403)
    except ValueError as e:return HTMLResponse(str(e),404)
    return RedirectResponse('/folders/admin',303)

@router.get("/admin",response_class=HTMLResponse)
async def admin_folders(request: Request):
    u=current_user(request)
    if not u or not u.get("is_super_admin"):return HTMLResponse("Yetkisiz.",403)
    rows=repos.folders.list_all_active_or_deleted(); users={x["id"]:x for x in repos.users.list_all() if not x.get("is_super_admin")}
    opts="".join(f'<option value="{escape(uid)}">{escape(x.get("display_name") or x.get("email") or uid)}</option>' for uid,x in users.items())
    cards=[]
    for f in rows:
        owner=users.get(f.get("owner_id")) or {}; action=(f'<form method="post" action="/folders/{f["id"]}/restore"><button>♻️ Geri Yükle</button></form>' if f.get("status")=="deleted" else f'<form method="post" action="/folders/{f["id"]}/delete" onsubmit="return confirm(\'Klasör silinsin mi?\')"><button class="danger">🗑️ Sil</button></form>')
        grant=f'<form method="post" action="/folders/admin/grant"><input type="hidden" name="folder_id" value="{escape(f["id"])}"><select name="user_id">{opts}</select><button>Erişim Ver</button></form>' if f.get("status") in ("active","restored") and opts else ""
        cards.append(f'<div class="card"><b>📁 {escape(f.get("name") or "")}</b><p>Sahip: {escape(owner.get("display_name") or "Sistem")} · Durum: {escape(f.get("status") or "")}</p><div class="actions">{action}{grant}</div></div>')
    body='''<style>body{font-family:Arial;background:#f3f6f9}.wrap{max-width:1150px;margin:25px auto}.card{background:#fff;border-radius:14px;padding:18px;margin:10px 0;box-shadow:0 3px 16px #0001}.actions{display:flex;gap:8px;flex-wrap:wrap}button{border:0;border-radius:8px;padding:9px 12px;background:#1769e0;color:#fff;font-weight:700}.danger{background:#b91c1c}input,select{padding:8px;border:1px solid #ccd4dc;border-radius:7px}</style>'''+"<div class='wrap'><h1>📁 Klasör Yönetimi</h1><p><a href='/admin/'>← Admin</a></p><div class='card'><h3>🌐 Genel klasör oluştur</h3><form method='post' action='/folders/admin/create-global'><input name='name' placeholder='Genel klasör adı' required><button>Oluştur</button></form></div>"+(''.join(cards) or '<p>Klasör yok.</p>')+"</div>"
    return HTMLResponse(body)

@router.post("/admin/create-global")
async def admin_create_global(request: Request,name: str=Form(...)):
    u=current_user(request)
    if not u or not u.get("is_super_admin"):return HTMLResponse("Yetkisiz.",403)
    name=str(name).strip()
    if not name:return HTMLResponse("Klasör adı boş olamaz.",400)
    repos.folders.create({"id":str(uuid4()),"case_id":None,"owner_id":u["id"],"parent_id":None,"name":name,"folder_type":"global","code":None,"sort_order":100,"is_system":0,"is_global":1,"status":"active","created_at":stamp(),"updated_at":stamp()})
    return RedirectResponse('/folders/admin',303)

@router.post("/admin/grant")
async def admin_grant(request: Request,folder_id: str=Form(...),user_id: str=Form(...)):
    u=current_user(request)
    if not u or not u.get("is_super_admin"):return HTMLResponse("Yetkisiz.",403)
    try:grant_folder_access(u,folder_id,user_id)
    except Exception as e:return HTMLResponse(str(e),400)
    return RedirectResponse('/folders/admin',303)

@router.post("/admin/revoke")
async def admin_revoke(request: Request,folder_id: str=Form(...),user_id: str=Form(...)):
    u=current_user(request)
    if not u or not u.get("is_super_admin"):return HTMLResponse("Yetkisiz.",403)
    try:revoke_folder_access(u,folder_id,user_id)
    except Exception as e:return HTMLResponse(str(e),400)
    return RedirectResponse('/folders/admin',303)
