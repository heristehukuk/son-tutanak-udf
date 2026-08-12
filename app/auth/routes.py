
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from app.auth.service import create_user, authenticate, create_session, delete_session
from app.web import page

router = APIRouter()

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return page("Giriş", """<div class="card narrow"><h1>Giriş</h1>
    <form method="post"><label>E-posta</label><input name="email" type="email" required>
    <label>Şifre</label><input name="password" type="password" required><button>Giriş Yap</button></form>
    <p><a href="/auth/register">Yeni üyelik</a></p></div>""")

@router.post("/login")
async def login(request: Request, email: str=Form(...), password: str=Form(...)):
    u = authenticate(email, password)
    if not u:
        return page("Giriş", '<div class="card narrow"><p class="err">E-posta veya şifre hatalı.</p><a href="/auth/login">Tekrar dene</a></div>', 401)
    if u["status"] == "banned":
        return page("Hesap", '<div class="card narrow"><p class="err">Bu hesap kullanıma kapatılmıştır.</p></div>', 403)
    token = create_session(u["id"], request.client.host if request.client else "")
    response = RedirectResponse("/", status_code=303)
    response.set_cookie("session", token, httponly=True, secure=False, samesite="lax", max_age=7*86400)
    return response

@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return page("Üyelik Başvurusu", """<div class="card narrow"><h1>Üyelik Başvurusu</h1>
    <p>Başvurular yönetici onayından sonra aktifleşir.</p>
    <form method="post"><label>Ad Soyad</label><input name="display_name" required>
    <label>E-posta</label><input name="email" type="email" required><label>Şifre</label>
    <input name="password" type="password" minlength="10" required><button>Başvuruyu Gönder</button></form></div>""")

@router.post("/register")
async def register(request: Request, display_name: str=Form(...), email: str=Form(...), password: str=Form(...)):
    try:
        create_user(email, display_name, password, request.client.host if request.client else "")
    except Exception:
        return page("Üyelik", '<div class="card narrow"><p class="err">Bu e-posta zaten kayıtlı veya bilgiler geçersiz.</p></div>', 400)
    return page("Başvuru Alındı", '<div class="card narrow"><h1>Başvurunuz alındı</h1><p>Yönetici onayı bekleniyor.</p><a href="/auth/login">Giriş</a></div>')

@router.post("/logout")
async def logout(request: Request):
    token = request.cookies.get("session")
    delete_session(token)
    response = RedirectResponse("/", status_code=303)
    response.delete_cookie("session")
    return response
