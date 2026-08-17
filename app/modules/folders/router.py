from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from app.auth.service import get_user_by_session
from app.database_layer import repos
router=APIRouter(prefix="/folders", tags=["folders"])

def user(request):
    return get_user_by_session(request.cookies.get("session"))

@router.get("",response_class=HTMLResponse)
async def folder_index(request:Request, case_id:str=""):
    u=user(request)
    if not u:return RedirectResponse("/auth/login",303)
    case=repos.cases.get(case_id) if case_id else None
    if not case or case.get("owner_id")!=u["id"]: return HTMLResponse("Dosya bulunamadı.",404)
    folders=repos.folders.create_standard(case_id,u["id"]); docs=repos.documents.list_by_owner(u["id"]); gens=repos.generated_documents.list_by_owner(u["id"])
    by={}
    for d in docs:
        if d.get("case_id")==case_id: by.setdefault(d.get("folder_id"),[]).append((d.get("original_name"),d.get("kind")))
    for d in gens:
        if d.get("case_id")==case_id: by.setdefault(d.get("folder_id"),[]).append((d.get("original_template"),d.get("doc_kind") or "generated"))
    html=["<h1>📁 Dosya Klasörleri</h1>",f"<p><b>{case.get('title') or 'Dosya'}</b> · Dosya No: {case.get('file_no') or '-'}</p>","<p><a href='/files/'>← Dosyalar</a> · <a href='/tasks/?case_id=%s'>Görevler</a> · <a href='/calendar'>Takvim</a></p>"%case_id]
    for f in folders:
        items=by.get(f["id"],[]); html.append(f"<div style='border:1px solid #ddd;padding:14px;margin:10px 0;border-radius:10px'><h3>📁 {f['name']}</h3>")
        html.extend(f"<div>📄 {n} <small>({k})</small></div>" for n,k in items)
        if not items: html.append("<div style='color:#777'>Henüz belge yok.</div>")
        html.append("</div>")
    return HTMLResponse("<html><meta charset='utf-8'><body style='font-family:Arial;max-width:900px;margin:30px auto'>"+''.join(html)+"</body></html>")

@router.post("/create")
async def create_folder(request:Request, case_id:str=Form(...), name:str=Form(...)):
    u=user(request)
    if not u:return RedirectResponse("/auth/login",303)
    case=repos.cases.get(case_id)
    if not case or case.get("owner_id")!=u["id"]: return HTMLResponse("Yetkisiz.",403)
    repos.folders.create({"case_id":case_id,"owner_id":u["id"],"parent_id":None,"name":name.strip(),"code":None,"is_system":0,"sort_order":99})
    return RedirectResponse(f"/folders?case_id={case_id}",303)

@router.post("/delete")
async def delete_folder(request:Request, folder_id:str=Form(...), case_id:str=Form(...)):
    u=user(request)
    if not u:return RedirectResponse("/auth/login",303)
    try: repos.folders.delete(folder_id,u["id"])
    except ValueError as e:return HTMLResponse(str(e),400)
    return RedirectResponse(f"/folders?case_id={case_id}",303)
