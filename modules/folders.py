"""Dosya klasör sistemi.

Her klasör bir `case` kaydına bağlıdır. Sistem klasörleri dosya ilk oluşturulduğunda
otomatik açılır; kullanıcı ayrıca alt/özel klasörler oluşturabilir.
"""
from datetime import datetime
from uuid import uuid4
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from app.auth.service import get_user_by_session
from app.database_layer import repos

router = APIRouter(prefix="/folders", tags=["folders"])

SYSTEM_FOLDERS = [
    ("01", "01 - Başvuru ve Kaynak Belgeler", "source"),
    ("02", "02 - Davetler", "davet_mektubu"),
    ("03", "03 - Görüşme Belgeleri", "meeting"),
    ("04", "04 - Son Tutanaklar", "son_tutanak"),
    ("05", "05 - Ücret Pusulaları", "ucret_pusulasi"),
    ("06", "06 - Üst Yazılar", "ust_yazi"),
    ("07", "07 - Diğer Belgeler", "other"),
]
DOC_FOLDER_TYPES = {
    "son_tutanak": "04",
    "davet_mektubu": "02",
    "ucret_pusulasi": "05",
    "ust_yazi": "06",
}


def _now():
    return datetime.now().isoformat(timespec="seconds")


def current_user(request):
    u = get_user_by_session(request.cookies.get("session"))
    return u if u and u.get("status") not in ("banned", "rejected") else None


def _case(owner_id, case_id):
    c = repos.cases.get(case_id)
    if not c or c.get("owner_id") != owner_id:
        return None
    return c


def ensure_case_folders(owner_id, case_id):
    case = _case(owner_id, case_id)
    if not case:
        return []
    existing = repos.folders.list_for_case(case_id)
    by_key = {f.get("folder_type"): f for f in existing if f.get("is_system")}
    stamp = _now()
    for key, name, ftype in SYSTEM_FOLDERS:
        if key in by_key:
            continue
        repos.folders.create({
            "id": str(uuid4()), "case_id": case_id, "owner_id": owner_id,
            "parent_id": None, "name": name, "folder_type": key,
            "sort_order": int(key), "is_system": 1,
            "created_at": stamp, "updated_at": stamp,
        })
    return sorted(repos.folders.list_for_case(case_id), key=lambda x: (x.get("sort_order", 0), x.get("name", "")))


def get_system_folder(owner_id, case_id, key):
    ensure_case_folders(owner_id, case_id)
    rows = repos.folders.list_for_case(case_id)
    return next((r for r in rows if r.get("is_system") and r.get("folder_type") == key), None)


def default_document_folder(owner_id, case_id, kind="source"):
    if not case_id:
        return None
    key = DOC_FOLDER_TYPES.get(kind, "01" if kind in ("source", "ocr", "upload") else "07")
    return get_system_folder(owner_id, case_id, key)


def document_folder_for_generated(owner_id, case_id, doc_kind=None):
    if not case_id:
        return None
    return get_system_folder(owner_id, case_id, DOC_FOLDER_TYPES.get(doc_kind, "07"))


def _tree(rows):
    by_parent = {}
    for row in rows:
        by_parent.setdefault(row.get("parent_id"), []).append(row)
    for values in by_parent.values():
        values.sort(key=lambda x: (x.get("sort_order", 0), x.get("name", "")))
    return by_parent


@router.get("/api/{case_id}")
def folders_api(request: Request, case_id: str):
    u = current_user(request)
    if not u: raise HTTPException(401, "Giriş gerekli.")
    case = _case(u["id"], case_id)
    if not case: raise HTTPException(404, "Dosya bulunamadı.")
    rows = ensure_case_folders(u["id"], case_id)
    return {"case": case, "folders": rows, "tree": _tree(rows),
            "documents": [d for d in repos.documents.list_by_owner(u["id"]) if d.get("case_id") == case_id],
            "generated_documents": [d for d in repos.generated_documents.list_by_owner(u["id"]) if d.get("case_id") == case_id]}


@router.post("/api/{case_id}")
async def create_folder(request: Request, case_id: str):
    u = current_user(request)
    if not u: raise HTTPException(401, "Giriş gerekli.")
    if not _case(u["id"], case_id): raise HTTPException(404, "Dosya bulunamadı.")
    data = await request.json()
    name = str(data.get("name", "")).strip()
    if not name: raise HTTPException(400, "Klasör adı boş olamaz.")
    parent_id = data.get("parent_id") or None
    if parent_id:
        parent = repos.folders.get(parent_id)
        if not parent or parent.get("case_id") != case_id: raise HTTPException(400, "Geçersiz üst klasör.")
    stamp = _now()
    row = repos.folders.create({"id": str(uuid4()), "case_id": case_id, "owner_id": u["id"],
        "parent_id": parent_id, "name": name, "folder_type": "custom", "sort_order": 1000,
        "is_system": 0, "created_at": stamp, "updated_at": stamp})
    return {"ok": True, "folder": row}


@router.post("/api/folder/{folder_id}")
async def update_folder(request: Request, folder_id: str):
    u = current_user(request)
    if not u: raise HTTPException(401, "Giriş gerekli.")
    folder = repos.folders.get(folder_id)
    if not folder or folder.get("owner_id") != u["id"]: raise HTTPException(404, "Klasör bulunamadı.")
    data = await request.json()
    name = str(data.get("name", "")).strip()
    if not name: raise HTTPException(400, "Klasör adı boş olamaz.")
    if folder.get("is_system"): raise HTTPException(400, "Sistem klasörlerinin adı değiştirilemez.")
    return {"ok": True, "folder": repos.folders.update(folder_id, {"name": name, "updated_at": _now()})}


@router.delete("/api/folder/{folder_id}")
def delete_folder(request: Request, folder_id: str):
    u = current_user(request)
    if not u: raise HTTPException(401, "Giriş gerekli.")
    folder = repos.folders.get(folder_id)
    if not folder or folder.get("owner_id") != u["id"]: raise HTTPException(404, "Klasör bulunamadı.")
    if folder.get("is_system"): raise HTTPException(400, "Sistem klasörü silinemez.")
    repos.folders.delete(folder_id)
    return {"ok": True}


@router.get("", response_class=HTMLResponse)
def folders_page(request: Request, case_id: str = ""):
    u = current_user(request)
    if not u: return RedirectResponse("/auth/login", 303)
    case = _case(u["id"], case_id)
    if not case: return HTMLResponse("Dosya bulunamadı veya erişim yetkiniz yok.", 404)
    return HTMLResponse(_page(case))


def _page(case):
    import json
    cid = json.dumps(case["id"])
    return f'''<!doctype html><html lang="tr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Dosya Klasörleri</title>
<style>body{{font-family:Arial,sans-serif;background:#f3f6f9;margin:0;color:#20252b}}.wrap{{max-width:1100px;margin:25px auto;padding:0 16px}}.card{{background:#fff;border-radius:16px;padding:20px;margin:15px 0;box-shadow:0 4px 20px #0001}}.folder{{border:1px solid #e1e6eb;border-radius:12px;padding:13px;margin:8px 0}}.system{{background:#f8fafc}}button{{border:0;border-radius:8px;padding:9px 13px;background:#1769e0;color:#fff;cursor:pointer;font-weight:700}}button.red{{background:#b91c1c}}button.gray{{background:#475569}}input{{padding:9px;border:1px solid #ccd4dc;border-radius:8px}}a{{color:#1769e0;text-decoration:none}}.row{{display:flex;gap:8px;align-items:center;justify-content:space-between;flex-wrap:wrap}}small{{color:#64748b}}</style></head><body><div class="wrap">
<div class="row"><div><h1>📁 Dosya Klasörleri</h1><div>Dosya No: <b>{case.get('file_no') or ''}</b> — {case.get('title') or ''}</div></div><div><a href="/tasks/?case_id={case['id']}">📋 Görevler</a> &nbsp; <a href="/calendar">📅 Takvim</a> &nbsp; <a href="/">Ana Sayfa</a></div></div>
<div class="card"><div class="row"><h2>Belgeler ve Klasörler</h2><div><input id="name" placeholder="Yeni klasör adı"><button onclick="addFolder()">+ Klasör Ekle</button></div></div><div id="folders"></div></div>
<script>const CASE_ID={cid};let DATA=null;async function load(){{const r=await fetch('/folders/api/'+CASE_ID);DATA=await r.json();render()}}function render(){{const box=document.getElementById('folders');box.innerHTML='';for(const f of DATA.folders){{const docs=[...(DATA.documents||[]).map(x=>({{...x,generated:false}})),...(DATA.generated_documents||[]).map(x=>({{...x,generated:true}}))].filter(x=>x.folder_id===f.id);box.innerHTML+=`<div class="folder ${{f.is_system?'system':''}}"><div class="row"><div><b>📁 ${{esc(f.name)}}</b><br><small>${{f.is_system?'Sistem klasörü':'Özel klasör'}}</small></div>${{f.is_system?'':'<button class="red" onclick="delFolder(\\''+f.id+'\\')">Sil</button>'}}</div>${{docs.length?'<div style="margin-top:10px">'+docs.map(d=>'📄 '+esc(d.original_name||d.original_template||'Belge')).join('<br>')+'</div>':'<small>Henüz belge yok.</small>'}}</div>`}}}}function esc(s){{return String(s||'').replace(/[&<>"']/g,m=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[m]))}}async function addFolder(){{const n=document.getElementById('name').value.trim();if(!n)return;const r=await fetch('/folders/api/'+CASE_ID,{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{name:n}})}});if(!r.ok){{alert((await r.json()).detail||'Hata');return}}document.getElementById('name').value='';load()}}async function delFolder(id){{if(!confirm('Klasör silinsin mi?'))return;const r=await fetch('/folders/api/folder/'+id,{{method:'DELETE'}});if(!r.ok){{alert((await r.json()).detail||'Hata');return}}load()}}load();</script></div></body></html>'''
