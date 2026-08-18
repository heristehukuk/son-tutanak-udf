from html import escape
from fastapi import APIRouter, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from app.auth.service import require_active_user
from app.web import page
from app.customtemplates.service import create_template, list_visible_templates, delete_template

router = APIRouter()

def _current_user(request: Request):
    return require_active_user(request.cookies.get("session"))

def _template_card(t, user):
    owner_badge = "Sizin" if t["owner_id"] == user["id"] else ("Paylaşılan" if t["is_shared"] else "")
    can_delete = t["owner_id"] == user["id"] or user["is_super_admin"]
    del_btn = (f'<form action="/templates/{escape(t["id"])}/delete" method="post" '
               f'onsubmit="return confirm(\'Bu şablonu silmek istediğinize emin misiniz?\')">'
               f'<button class="secondary">Sil</button></form>') if can_delete else ""
    return (f'<div class="card"><h3>{escape(t["name"])}</h3>'
            f'<p class="hint">{escape(owner_badge)}</p>'
            f'<p>{len(t.get("recognized") or [])} tanınan alan · {len(t.get("unrecognized") or [])} tanınmayan ifade</p>'
            f'{del_btn}</div>')

@router.get("/", response_class=HTMLResponse)
async def list_templates(request: Request):
    u = _current_user(request)
    if not u: return HTMLResponse("Giriş yapmalısınız.", 401)
    import json
    rows = list_visible_templates(u["id"])
    for r in rows:
        r["recognized"] = json.loads(r["recognized_json"])
        r["unrecognized"] = json.loads(r["unrecognized_json"])
    cards = "".join(_template_card(t, u) for t in rows) or "<p>Henüz bir şablon eklenmedi.</p>"
    body = f"""<h1>Şablonlarım</h1>
    <p><a href="/templates/new"><button>+ Yeni Şablon Ekle</button></a> <a href="/">Ana Sayfa</a></p>
    <div class="grid">{cards}</div>"""
    return page("Şablonlarım", body)

@router.get("/new", response_class=HTMLResponse)
async def new_template_form(request: Request):
    u = _current_user(request)
    if not u: return HTMLResponse("Giriş yapmalısınız.", 401)
    share_option = ('<label><input type="checkbox" name="is_shared" value="1"> Tüm kullanıcılarla paylaş (ortak şablon havuzu)</label>'
                    if u["is_super_admin"] else "")
    body = f"""<h1>Yeni Şablon Ekle</h1>
    <div class="card narrow">
    <p class="hint">UDF şablonunuzda, kutucuk değerinin yazılmasını istediğiniz yerlere köşeli parantez
    içinde alan adı yazın. Örnek: <code>[dosya no]</code>, <code>[başvurucu adı]</code>,
    <code>[karşı taraf 1 adı]</code>. Sistem tanıdığı ifadeleri otomatik dolduracak, tanımadıklarını boş bırakacaktır.</p>
    <form action="/templates/new" method="post" enctype="multipart/form-data">
    <label>Şablon Adı</label><input name="name" required>
    <label>UDF Dosyası</label><input type="file" name="file" accept=".udf" required>
    {share_option}
    <button type="submit">Şablonu Kaydet</button>
    </form></div>"""
    return page("Yeni Şablon", body)

@router.post("/new", response_class=HTMLResponse)
async def upload_template(request: Request, name: str = Form(...), file: UploadFile = File(...), is_shared: str = Form(None)):
    u = _current_user(request)
    if not u: return HTMLResponse("Giriş yapmalısınız.", 401)
    if not (file.filename or "").lower().endswith(".udf"):
        return HTMLResponse("Sadece .udf dosyaları yüklenebilir.", 400)
    data = await file.read()
    shared = bool(is_shared) and bool(u["is_super_admin"])  # sadece admin paylaşımlı şablon oluşturabilir
    try:
        tid, recognized, unrecognized = create_template(u["id"], name, shared, data)
    except Exception as e:
        return HTMLResponse(f"Şablon okunamadı: {e}", 400)
    rec_html = "".join(f"<li>[{escape(r['raw'])}] → {escape(r['target'])}</li>" for r in recognized) or "<li>Hiçbir alan tanınmadı.</li>"
    unrec_html = "".join(f"<li>[{escape(r)}] — tanınmadı, belgede boş kalacak</li>" for r in unrecognized)
    body = f"""<h1>Şablon Kaydedildi</h1>
    <div class="card narrow">
    <p><b>{escape(name)}</b> kaydedildi{' ve tüm kullanıcılarla paylaşıldı.' if shared else '.'}</p>
    <h3>Tanınan Alanlar</h3><ul>{rec_html}</ul>
    {f'<h3>Tanınmayan İfadeler</h3><ul>{unrec_html}</ul>' if unrecognized else ''}
    <p><a href="/templates/"><button>Şablonlarıma Dön</button></a></p>
    </div>"""
    return page("Şablon Kaydedildi", body)

@router.post("/{template_id}/delete")
async def remove_template(request: Request, template_id: str):
    u = _current_user(request)
    if not u: return RedirectResponse("/auth/login", 303)
    delete_template(template_id, u)
    return RedirectResponse("/templates/", 303)
