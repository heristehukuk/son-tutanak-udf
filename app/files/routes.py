
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from app.auth.service import get_user_by_session
from app.database import connect
from app.web import page
router=APIRouter()

@router.get("/",response_class=HTMLResponse)
async def files(request:Request):
    u=get_user_by_session(request.cookies.get("session"))
    if not u:return HTMLResponse("Giriş yapmalısınız.",401)
    with connect() as c:
        cases=c.execute("SELECT * FROM cases WHERE owner_id=? ORDER BY updated_at DESC",(u["id"],)).fetchall()
    rows=[]
    for r in cases:
        rows.append(f'<div class="card"><h3>{r["title"] or "Dosya"}</h3>'
                    f'<p>Sistem ID: {r["id"]}</p><p>Dosya No: {r["file_no"] or "-"}</p>'
                    f'<p>Başvuru No: {r["application_no"] or "-"}</p></div>')
    return page("Dosyalar", "<h1>Dosyalarım</h1>"+("".join(rows) or "<p>Henüz dosyanız yok.</p>"))
