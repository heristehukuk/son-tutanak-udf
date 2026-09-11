
from html import escape
from fastapi.responses import HTMLResponse

CSS = """*{box-sizing:border-box}body{font-family:Arial,sans-serif;background:#f3f6f9;color:#20252b;margin:0}
nav{background:#17212b;color:white;padding:14px 5%;display:flex;gap:18px;align-items:center;flex-wrap:wrap}nav a{color:white;text-decoration:none}
.wrap{max-width:1100px;margin:28px auto;padding:0 18px}.card{background:white;border-radius:14px;padding:20px;margin:15px 0;box-shadow:0 3px 18px #0001}
.narrow{max-width:520px;margin:40px auto}input,textarea,select{width:100%;padding:11px;border:1px solid #ccd4dc;border-radius:8px;margin:6px 0 12px;font:inherit}
button{background:#1769e0;color:#fff;border:0;border-radius:8px;padding:11px 16px;font-weight:700;cursor:pointer}.err{color:#a11}.ok{color:#176b35}
.badge{background:#dc2626;color:#fff;border-radius:999px;padding:1px 8px;font-size:12px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:14px}
.stats-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:12px;margin-top:10px}
.stat{background:#f3f6f9;border-radius:10px;padding:14px 10px;text-align:center}
.stat-num{display:block;font-size:22px;font-weight:700;color:#1769e0}
.stat-label{display:block;font-size:12px;color:#66717c;margin-top:4px}
.opts{display:flex;flex-direction:column;gap:4px;margin:6px 0 14px}.opt{display:flex;align-items:center;gap:6px;font-weight:400}.opt input{width:auto;margin:0}
.tbl{width:100%;border-collapse:collapse;background:#fff;border-radius:10px;overflow:hidden;box-shadow:0 3px 18px #0001}.tbl th,.tbl td{padding:10px 12px;text-align:left;border-bottom:1px solid #eef1f4}.tbl th{background:#f3f6f9}
.danger{background:#a11}
.actions{display:flex;gap:8px;margin-top:10px;flex-wrap:wrap}.actions form{margin:0}.actions button{padding:9px 12px;font-size:13px}
.secondary{background:#eef1f4;color:#20252b}
.preview-box{background:#fbfcfd;border:1px solid #e3e8ed;border-radius:10px;padding:16px;margin-top:10px;max-height:520px;overflow:auto;font-size:14px;line-height:1.6}
.preview-box mark.fill-ok{background:#d9f2e3;color:#176b35;padding:0 3px;border-radius:4px;font-weight:700;text-decoration:none}
.preview-box mark.fill-warn{background:#fbdcdc;color:#a11;padding:0 3px;border-radius:4px;font-weight:700;text-decoration:none}
.preview-legend{font-size:13px;color:#66717c;margin-top:8px}
.preview-legend mark{padding:0 6px;border-radius:4px;margin-right:4px}
.deadline-hero{background:#eef4ff;border-radius:10px;padding:14px 16px;margin-bottom:12px}
.deadline-hero .num{font-size:26px;font-weight:800;color:#1769e0}
.deadline-row{display:flex;justify-content:space-between;align-items:center;padding:9px 0;border-bottom:1px solid #eef1f4;font-size:14px}
.deadline-row:last-child{border-bottom:none}
.dl-tag{border-radius:999px;padding:2px 10px;font-size:12px;font-weight:700;white-space:nowrap}
.dl-expired{background:#fbdcdc;color:#a11}.dl-today{background:#ffe6c7;color:#a15a00}
.dl-soon{background:#fff6c7;color:#8a7300}.dl-ok{background:#d9f2e3;color:#176b35}
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
