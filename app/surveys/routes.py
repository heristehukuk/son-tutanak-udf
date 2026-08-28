
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from app.auth.service import get_user_by_session
from app.web import page
router=APIRouter()

@router.get("/",response_class=HTMLResponse)
async def surveys(request:Request):
    u=get_user_by_session(request.cookies.get("session"))
    if not u:return HTMLResponse("Giriş yapmalısınız.",401)
    return page("Anketler","<h1>Anketler</h1><p>Anket altyapısı hazır. Kişisel cevaplar yöneticiye, toplu sonuçlar anonim görünüme ayrılacaktır.</p>")
