
import re
from html import escape
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from app.auth.service import create_user, authenticate, create_session, delete_session, get_user_by_session
from app.database_layer import repos
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

@router.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request):
    u = get_user_by_session(request.cookies.get("session"))
    if not u: return RedirectResponse("/auth/login", 303)
    current = escape(u["iban"] or "", quote=True)
    return page("Profilim", f"""<div class="card narrow"><h1>Profilim</h1>
    <p class="hint">Buraya girdiğiniz IBAN, kendi oluşturduğunuz belgelerde şablonda <code>[iban]</code>
    yazan yerlere otomatik olarak yazılır. Her belgede tekrar girmenize gerek kalmaz.</p>
    <form method="post" action="/auth/profile">
    <label>IBAN</label><input name="iban" value="{current}" placeholder="TR__ ____ ____ ____ ____ ____ __">
    <button>Kaydet</button></form></div>""")

@router.post("/profile")
async def update_profile(request: Request, iban: str = Form("")):
    u = get_user_by_session(request.cookies.get("session"))
    if not u: return RedirectResponse("/auth/login", 303)
    clean = re.sub(r"\s+", "", iban or "").upper()
    if clean and not re.fullmatch(r"TR\d{24}", clean):
        return page("Profilim", '<div class="card narrow"><p class="err">Geçersiz IBAN. '
                    'Türkiye IBAN\'ları "TR" ile başlamalı ve TR dahil toplam 26 karakter olmalıdır.</p>'
                    '<a href="/auth/profile"><button>Geri Dön</button></a></div>', 400)
    repos.users.update(u["id"], {"iban": clean or None})
    return page("Profilim", '<div class="card narrow"><p class="ok">IBAN kaydedildi.</p>'
                '<a href="/"><button>Ana Sayfa</button></a></div>')
