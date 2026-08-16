
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse
from app.auth.service import get_user_by_session, now
from app.database_layer import repos
from app.web import page
router=APIRouter()

@router.get("/",response_class=HTMLResponse)
async def inbox(request:Request):
    u=get_user_by_session(request.cookies.get("session"))
    if not u:return HTMLResponse("Giriş yapmalısınız.",401)
    rows=repos.messages.list_inbox_with_sender_name(u["id"])
    body=[]
    for r in rows:body.append(f'<div class="card"><b>{r["display_name"]}</b><p>{r["body"]}</p></div>')
    return page("Mesajlar","<h1>Mesajlar</h1>"+("".join(body) or "<p>Mesaj yok.</p>"))

@router.post("/")
async def send(request:Request,recipient_id:str=Form(...),body:str=Form(...)):
    u=get_user_by_session(request.cookies.get("session"))
    if not u:return HTMLResponse("Giriş yapmalısınız.",401)
    repos.messages.create({"sender_id":u["id"],"recipient_id":recipient_id,"body":body,"created_at":now().isoformat()})
    return HTMLResponse('<meta http-equiv="refresh" content="0;url=/messages/">')
