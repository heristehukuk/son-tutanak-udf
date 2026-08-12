
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse
from uuid import uuid4
from app.auth.service import get_user_by_session, now
from app.database import connect
from app.web import page
router=APIRouter()

@router.get("/",response_class=HTMLResponse)
async def inbox(request:Request):
    u=get_user_by_session(request.cookies.get("session"))
    if not u:return HTMLResponse("Giriş yapmalısınız.",401)
    with connect() as c:
        rows=c.execute("""SELECT m.*,u.display_name FROM messages m JOIN users u ON u.id=m.sender_id
                          WHERE m.recipient_id=? ORDER BY m.created_at DESC""",(u["id"],)).fetchall()
    body=[]
    for r in rows:body.append(f'<div class="card"><b>{r["display_name"]}</b><p>{r["body"]}</p></div>')
    return page("Mesajlar","<h1>Mesajlar</h1>"+("".join(body) or "<p>Mesaj yok.</p>"))

@router.post("/")
async def send(request:Request,recipient_id:str=Form(...),body:str=Form(...)):
    u=get_user_by_session(request.cookies.get("session"))
    if not u:return HTMLResponse("Giriş yapmalısınız.",401)
    with connect() as c:
        c.execute("""INSERT INTO messages(id,sender_id,recipient_id,body,created_at)
                     VALUES(?,?,?,?,?)""",(str(uuid4()),u["id"],recipient_id,body,now().isoformat()))
    return HTMLResponse('<meta http-equiv="refresh" content="0;url=/messages/">')
