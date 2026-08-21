
from html import escape
from fastapi.responses import HTMLResponse

CSS = """*{box-sizing:border-box}body{font-family:Arial,sans-serif;background:#f3f6f9;color:#20252b;margin:0}
nav{background:#17212b;color:white;padding:14px 5%;display:flex;gap:18px;align-items:center;flex-wrap:wrap}nav a{color:white;text-decoration:none}
.wrap{max-width:1100px;margin:28px auto;padding:0 18px}.card{background:white;border-radius:14px;padding:20px;margin:15px 0;box-shadow:0 3px 18px #0001}
.narrow{max-width:520px;margin:40px auto}input,textarea,select{width:100%;padding:11px;border:1px solid #ccd4dc;border-radius:8px;margin:6px 0 12px;font:inherit}
button{background:#1769e0;color:#fff;border:0;border-radius:8px;padding:11px 16px;font-weight:700;cursor:pointer}.err{color:#a11}.ok{color:#176b35}
.badge{background:#dc2626;color:#fff;border-radius:999px;padding:1px 8px;font-size:12px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:14px}
"""

def page(title, body, status=200):
    html = f"""<!doctype html><html lang="tr"><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)}</title>
    <style>{CSS}</style></head><body><nav>
    <a href="/">Son Tutanak UDF</a><a href="/files/">Dosyalar</a><a href="/templates/">Şablonlarım</a>
    <a href="/messages/">Mesajlar</a><a href="/surveys/">Anketler</a><a href="/plans/">Planlar</a>
    <a href="/auth/profile">Profilim</a><a href="/auth/login">Giriş</a>
    </nav><main class="wrap">{body}</main></body></html>"""
    return HTMLResponse(html, status_code=status)
