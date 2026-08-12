
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, FileResponse
from app.auth.service import get_user_by_session, now
from app.database import connect
from app.web import page
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
    return page("Admin","<h1>Yönetim</h1><h2>Üyeler</h2>"+''.join(us)+
                "<h2>Yüklenen Belgeler</h2>"+''.join(ds))

@router.post("/users/{user_id}/status")
async def status(request:Request,user_id:str,status:str=Form(...)):
    if not admin(request):return HTMLResponse("Yetkisiz.",403)
    with connect() as c:
        c.execute("UPDATE users SET status=?,approved_at=? WHERE id=?",
                  (status,now().isoformat() if status=="active" else None,user_id))
    return HTMLResponse('<meta http-equiv="refresh" content="0;url=/admin/">')

@router.get("/documents/{doc_id}")
async def download_document(request:Request,doc_id:str):
    if not admin(request):return HTMLResponse("Yetkisiz.",403)
    with connect() as c:r=c.execute("SELECT * FROM documents WHERE id=?",(doc_id,)).fetchone()
    if not r:return HTMLResponse("Belge bulunamadı.",404)
    return FileResponse(r["stored_path"],filename=r["original_name"])
