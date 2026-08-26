from html import escape
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from app.auth.service import require_active_user, get_user_by_session, now
from app.auth.permissions import require_permission
from app.database_layer import repos
from app.web import page
from app.surveys import service

router = APIRouter()

STYLE = '''<style>
.survey-card{margin-bottom:10px}
.survey-card .hint{margin:4px 0 0}
.badge-done{background:#176b35;color:#fff;border-radius:999px;padding:1px 9px;font-size:12px;margin-left:6px}
.badge-closed{background:#8a95a1;color:#fff;border-radius:999px;padding:1px 9px;font-size:12px;margin-left:6px}
.q-block{margin:16px 0;padding-top:14px;border-top:1px solid #e6eaee}
.q-block:first-child{border-top:0;padding-top:0}
.q-title{font-weight:700;margin-bottom:8px}
.opt-row{display:block;font-weight:normal;margin:6px 0}
.opt-row input{width:auto;margin-right:8px}
.bar-row{display:flex;align-items:center;gap:10px;margin:4px 0}
.bar-label{min-width:150px;font-size:13px}
.bar-track{flex:1;background:#eef1f4;border-radius:6px;height:14px;overflow:hidden}
.bar-fill{background:#1769e0;height:100%}
.bar-count{min-width:40px;text-align:right;font-size:12px;color:#53606b}
.text-answer{background:#f6f8fa;border-radius:8px;padding:8px 12px;margin:6px 0;font-size:14px}
.avg{color:#53606b;font-size:13px;margin-bottom:6px}
</style>'''


def _can_manage(user):
    return bool(user and require_permission(user, "surveys.create"))


def _can_view_individual(user):
    return bool(user and require_permission(user, "surveys.view_individual_answers"))


def _log(actor_id, action, target_id=None, details=""):
    repos.audit.create({"actor_id": actor_id, "action": action, "target_id": target_id,
                        "details": details, "created_at": now().isoformat()})


def _kind_label(kind):
    return {"text": "Serbest Metin", "single_choice": "Çoktan Seçmeli", "rating": "Puanlama (1-5)"}.get(kind, kind)


# --- Kullanıcı görünümü -----------------------------------------------------

@router.get("/", response_class=HTMLResponse)
async def surveys_index(request: Request):
    u = require_active_user(request.cookies.get("session"))
    if not u:
        return HTMLResponse("Giriş yapmalısınız.", 401)
    rows = service.list_visible_surveys(u["id"])
    items = []
    for s in rows:
        badge = ""
        if s["answered"]:
            badge = '<span class="badge-done">✓ Cevaplandı</span>'
        elif not s.get("active"):
            badge = '<span class="badge-closed">Kapalı</span>'
        items.append(
            f'<a class="card survey-card" href="/surveys/{s["id"]}" style="display:block;text-decoration:none;color:inherit">'
            f'<b>{escape(s["title"])}</b>{badge}'
            f'<p class="hint">{escape(s.get("description") or "")}</p></a>'
        )
    manage_link = '<p><a href="/surveys/admin"><button class="secondary">⚙️ Anketleri Yönet</button></a></p>' if _can_manage(u) else ""
    body = f"<h1>Anketler</h1>{manage_link}" + (STYLE + "".join(items) if items else "<p>Şu an görebileceğiniz bir anket yok.</p>")
    return page("Anketler", body)


@router.get("/{survey_id}", response_class=HTMLResponse)
async def survey_detail(request: Request, survey_id: str):
    u = require_active_user(request.cookies.get("session"))
    if not u:
        return HTMLResponse("Giriş yapmalısınız.", 401)
    survey, questions = service.get_survey_with_questions(survey_id)
    if not survey:
        return HTMLResponse("Anket bulunamadı.", 404)
    answered = service.has_answered(survey_id, u["id"])
    if not survey.get("active") and not answered:
        return HTMLResponse("Bu anket artık kapalı.", 403)

    if answered:
        return HTMLResponse(_results_page(survey, questions, viewer=u))

    if not questions:
        return page(survey["title"], f"<h1>{escape(survey['title'])}</h1><p>Bu ankette henüz soru eklenmemiş.</p>")

    blocks = []
    for q in questions:
        blocks.append(_question_form_block(q))
    body = (f"<h1>{escape(survey['title'])}</h1>"
            f"<p class=\"hint\">{escape(survey.get('description') or '')}</p>"
            + STYLE
            + f'<form method="post" action="/surveys/{survey_id}/answer" class="card">'
            + "".join(blocks)
            + '<button type="submit" style="margin-top:14px">Cevapları Gönder</button></form>')
    return page(survey["title"], body)


def _question_form_block(q):
    qid = q["id"]
    kind = q["kind"]
    inner = ""
    if kind == "text":
        inner = f'<textarea name="q_{escape(qid)}" placeholder="Cevabınız..."></textarea>'
    elif kind == "single_choice":
        opts = service.question_options(q)
        rows = "".join(
            f'<label class="opt-row"><input type="radio" name="q_{escape(qid)}" value="{escape(o)}"> {escape(o)}</label>'
            for o in opts
        )
        inner = rows
    elif kind == "rating":
        rows = "".join(
            f'<label class="opt-row"><input type="radio" name="q_{escape(qid)}" value="{n}"> {"⭐" * n} ({n})</label>'
            for n in range(service.RATING_MIN, service.RATING_MAX + 1)
        )
        inner = rows
    return f'<div class="q-block"><div class="q-title">{escape(q["question"])}</div>{inner}</div>'


@router.post("/{survey_id}/answer")
async def submit_survey_answer(request: Request, survey_id: str):
    u = require_active_user(request.cookies.get("session"))
    if not u:
        return HTMLResponse("Giriş yapmalısınız.", 401)
    form = await request.form()
    answers = {}
    for key, val in form.multi_items():
        if key.startswith("q_"):
            answers[key[2:]] = str(val)
    try:
        service.submit_answers(survey_id, u["id"], answers)
    except ValueError as e:
        survey, questions = service.get_survey_with_questions(survey_id)
        body = (f"<h1>{escape(survey['title'] if survey else 'Anket')}</h1>"
                f'<div class="card" style="color:#a11">Hata: {escape(str(e))}</div>'
                f'<p><a href="/surveys/{survey_id}">← Geri dön</a></p>')
        return page("Anket", body, status=400)
    return HTMLResponse(f'<meta http-equiv="refresh" content="0;url=/surveys/{survey_id}">')


def _results_page(survey, questions, viewer):
    results = service.compute_aggregate_results(survey["id"])
    blocks = []
    for r in results:
        if r["kind"] == "single_choice":
            rows = ""
            total = r["total"] or 1
            for opt, cnt in r["counts"].items():
                pct = round(100 * cnt / total)
                rows += (f'<div class="bar-row"><span class="bar-label">{escape(opt)}</span>'
                          f'<span class="bar-track"><span class="bar-fill" style="width:{pct}%"></span></span>'
                          f'<span class="bar-count">{cnt}</span></div>')
            inner = rows or "<p class=\"hint\">Henüz cevap yok.</p>"
        elif r["kind"] == "rating":
            rows = ""
            total = r["total"] or 1
            for n in range(service.RATING_MIN, service.RATING_MAX + 1):
                cnt = r["counts"].get(n, 0)
                pct = round(100 * cnt / total)
                rows += (f'<div class="bar-row"><span class="bar-label">{"⭐" * n}</span>'
                          f'<span class="bar-track"><span class="bar-fill" style="width:{pct}%"></span></span>'
                          f'<span class="bar-count">{cnt}</span></div>')
            avg = f'<p class="avg">Ortalama: {r["average"]} / {service.RATING_MAX} ({r["total"]} cevap)</p>' if r["average"] is not None else '<p class="hint">Henüz cevap yok.</p>'
            inner = avg + rows
        else:  # text
            if r["answers"]:
                inner = "".join(f'<div class="text-answer">{escape(a)}</div>' for a in r["answers"])
            else:
                inner = "<p class=\"hint\">Henüz cevap yok.</p>"
        blocks.append(f'<div class="q-block"><div class="q-title">{escape(r["question"])}</div>{inner}</div>')

    admin_link = ""
    if _can_view_individual(viewer):
        admin_link = f'<p><a href="/surveys/admin/{survey["id"]}/answers">👤 İsimli cevapları gör (staff)</a></p>'

    body = (f"<h1>{escape(survey['title'])}</h1>"
            f"<p class=\"hint\">{escape(survey.get('description') or '')}</p>"
            f'<p class="hint">✓ Bu anketi cevapladınız. Aşağıda anonim toplu sonuçları görüyorsunuz.</p>'
            + STYLE + '<div class="card">' + "".join(blocks) + "</div>" + admin_link
            + '<p><a href="/surveys/">← Anketler</a></p>')
    html = f"""<!doctype html><html lang="tr"><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(survey['title'])}</title>
    <style>*{{box-sizing:border-box}}body{{font-family:Arial,sans-serif;background:#f3f6f9;color:#20252b;margin:0}}
    nav{{background:#17212b;color:white;padding:14px 5%;display:flex;gap:18px;align-items:center;flex-wrap:wrap}}nav a{{color:white;text-decoration:none}}
    .wrap{{max-width:1100px;margin:28px auto;padding:0 18px}}.card{{background:white;border-radius:14px;padding:20px;margin:15px 0;box-shadow:0 3px 18px #0001}}
    button{{background:#1769e0;color:#fff;border:0;border-radius:8px;padding:11px 16px;font-weight:700;cursor:pointer}}.hint{{color:#65717d;font-size:13px}}</style>
    </head><body><nav><a href="/">Son Tutanak UDF</a><a href="/files/">Dosyalar</a><a href="/templates/">Şablonlarım</a>
    <a href="/messages/">Mesajlar</a><a href="/surveys/">Anketler</a><a href="/plans/">Planlar</a>
    <a href="/auth/profile">Profilim</a></nav><main class="wrap">{body}</main></body></html>"""
    return html


# --- Admin: anket yönetimi ---------------------------------------------------

@router.get("/admin", response_class=HTMLResponse)
async def admin_index(request: Request):
    u = get_user_by_session(request.cookies.get("session"))
    if not _can_manage(u):
        return HTMLResponse("Yetkisiz.", 403)
    rows = service.list_all_surveys()
    items = []
    for s in rows:
        status = "🟢 Aktif" if s.get("active") else "⚪ Kapalı"
        items.append(
            f'<div class="card"><b>{escape(s["title"])}</b> <span class="hint">({status})</span>'
            f'<p class="hint">{escape(s.get("description") or "")}</p>'
            f'<p class="links"><a href="/surveys/admin/{s["id"]}">Düzenle</a>'
            + (f' · <a href="/surveys/admin/{s["id"]}/answers">İsimli Cevaplar</a>' if _can_view_individual(u) else "")
            + f' · <a href="/surveys/{s["id"]}">Önizle</a></p></div>'
        )
    form = '''<div class="card"><h2>Yeni Anket</h2>
    <form method="post" action="/surveys/admin/create">
    <label>Başlık</label><input name="title" required>
    <label>Açıklama</label><textarea name="description"></textarea>
    <button>Oluştur</button></form></div>'''
    body = "<h1>Anket Yönetimi</h1><p><a href=\"/surveys/\">← Anketler</a></p>" + form + "".join(items)
    return page("Anket Yönetimi", body)


@router.post("/admin/create")
async def admin_create(request: Request, title: str = Form(...), description: str = Form("")):
    u = get_user_by_session(request.cookies.get("session"))
    if not _can_manage(u):
        return HTMLResponse("Yetkisiz.", 403)
    try:
        s = service.create_survey(u["id"], title, description)
    except ValueError as e:
        return HTMLResponse(f"Hata: {escape(str(e))}", 400)
    _log(u["id"], "survey_create", s["id"], title)
    return RedirectResponse(f"/surveys/admin/{s['id']}", 303)


@router.get("/admin/{survey_id}", response_class=HTMLResponse)
async def admin_edit(request: Request, survey_id: str):
    u = get_user_by_session(request.cookies.get("session"))
    if not _can_manage(u):
        return HTMLResponse("Yetkisiz.", 403)
    survey, questions = service.get_survey_with_questions(survey_id)
    if not survey:
        return HTMLResponse("Anket bulunamadı.", 404)

    q_items = []
    for q in questions:
        opts = service.question_options(q)
        opts_line = f'<p class="hint">Şıklar: {escape(", ".join(opts))}</p>' if opts else ""
        q_items.append(
            f'<div class="card"><b>{escape(q["question"])}</b> <span class="hint">({escape(_kind_label(q["kind"]))})</span>'
            f'{opts_line}'
            f'<form method="post" action="/surveys/admin/questions/{q["id"]}/delete" style="display:inline" '
            f'onsubmit="return confirm(\'Bu soru ve tüm cevapları silinsin mi?\')"><button class="secondary">Soruyu Sil</button></form></div>'
        )

    toggle_label = "Anketi Kapat" if survey.get("active") else "Anketi Yeniden Aç"
    body = f"""<h1>{escape(survey['title'])}</h1>
    <p><a href="/surveys/admin">← Anket Yönetimi</a></p>
    <div class="card"><h2>Anket Bilgileri</h2>
    <form method="post" action="/surveys/admin/{survey_id}/update">
    <label>Başlık</label><input name="title" value="{escape(survey['title'])}" required>
    <label>Açıklama</label><textarea name="description">{escape(survey.get('description') or '')}</textarea>
    <button>Kaydet</button></form>
    <form method="post" action="/surveys/admin/{survey_id}/toggle" style="margin-top:10px">
    <button class="secondary">{toggle_label}</button></form>
    <form method="post" action="/surveys/admin/{survey_id}/delete" style="margin-top:10px"
    onsubmit="return confirm('Bu anket, tüm sorular ve cevaplar kalıcı olarak silinsin mi?')">
    <button class="secondary">🗑️ Anketi Sil</button></form></div>

    <div class="card"><h2>Yeni Soru Ekle</h2>
    <form method="post" action="/surveys/admin/{survey_id}/questions/add">
    <label>Soru Metni</label><input name="question" required>
    <label>Soru Tipi</label>
    <select name="kind" onchange="document.getElementById('opts-field').style.display=this.value==='single_choice'?'block':'none'">
    <option value="text">Serbest Metin</option>
    <option value="single_choice">Çoktan Seçmeli</option>
    <option value="rating">Puanlama (1-5)</option>
    </select>
    <div id="opts-field" style="display:none">
    <label>Şıklar (her satıra bir şık)</label><textarea name="options" placeholder="Çok memnunum&#10;Memnunum&#10;Kararsızım"></textarea>
    </div>
    <button>Soru Ekle</button></form></div>

    <h2>Sorular</h2>{"".join(q_items) or "<p>Henüz soru yok.</p>"}"""
    return page(survey["title"], body)


@router.post("/admin/{survey_id}/update")
async def admin_update(request: Request, survey_id: str, title: str = Form(...), description: str = Form("")):
    u = get_user_by_session(request.cookies.get("session"))
    if not _can_manage(u):
        return HTMLResponse("Yetkisiz.", 403)
    try:
        service.update_survey_meta(survey_id, title, description)
    except ValueError as e:
        return HTMLResponse(f"Hata: {escape(str(e))}", 400)
    _log(u["id"], "survey_update", survey_id, title)
    return RedirectResponse(f"/surveys/admin/{survey_id}", 303)


@router.post("/admin/{survey_id}/toggle")
async def admin_toggle(request: Request, survey_id: str):
    u = get_user_by_session(request.cookies.get("session"))
    if not _can_manage(u):
        return HTMLResponse("Yetkisiz.", 403)
    survey = service.get_survey(survey_id)
    if not survey:
        return HTMLResponse("Anket bulunamadı.", 404)
    service.set_survey_active(survey_id, not survey.get("active"))
    _log(u["id"], "survey_toggle_active", survey_id, "kapatıldı" if survey.get("active") else "açıldı")
    return RedirectResponse(f"/surveys/admin/{survey_id}", 303)


@router.post("/admin/{survey_id}/delete")
async def admin_delete(request: Request, survey_id: str):
    u = get_user_by_session(request.cookies.get("session"))
    if not _can_manage(u):
        return HTMLResponse("Yetkisiz.", 403)
    try:
        service.delete_survey(survey_id)
    except ValueError as e:
        return HTMLResponse(f"Hata: {escape(str(e))}", 400)
    _log(u["id"], "survey_delete", survey_id)
    return RedirectResponse("/surveys/admin", 303)


@router.post("/admin/{survey_id}/questions/add")
async def admin_add_question(request: Request, survey_id: str, question: str = Form(...),
                              kind: str = Form(...), options: str = Form("")):
    u = get_user_by_session(request.cookies.get("session"))
    if not _can_manage(u):
        return HTMLResponse("Yetkisiz.", 403)
    opts = [line.strip() for line in options.splitlines() if line.strip()]
    try:
        service.add_question(survey_id, question, kind, opts)
    except ValueError as e:
        return HTMLResponse(f"Hata: {escape(str(e))} <a href=\"/surveys/admin/{survey_id}\">← Geri dön</a>", 400)
    _log(u["id"], "survey_question_add", survey_id, question)
    return RedirectResponse(f"/surveys/admin/{survey_id}", 303)


@router.post("/admin/questions/{question_id}/delete")
async def admin_delete_question(request: Request, question_id: str):
    u = get_user_by_session(request.cookies.get("session"))
    if not _can_manage(u):
        return HTMLResponse("Yetkisiz.", 403)
    row = repos.survey_questions.get(question_id)
    if not row:
        return HTMLResponse("Soru bulunamadı.", 404)
    survey_id = row["survey_id"]
    service.delete_question(question_id)
    _log(u["id"], "survey_question_delete", survey_id, question_id)
    return RedirectResponse(f"/surveys/admin/{survey_id}", 303)


@router.get("/admin/{survey_id}/answers", response_class=HTMLResponse)
async def admin_individual_answers(request: Request, survey_id: str):
    u = get_user_by_session(request.cookies.get("session"))
    if not _can_view_individual(u):
        return HTMLResponse("Yetkisiz.", 403)
    survey = service.get_survey(survey_id)
    if not survey:
        return HTMLResponse("Anket bulunamadı.", 404)
    rows = service.compute_individual_answers(survey_id)
    items = [
        f'<div class="card"><b>{escape(r["user_name"])}</b> <span class="hint">{escape(r["updated_at"] or "")}</span>'
        f'<p class="hint">{escape(r["question"])}</p><p>{escape(r["answer"])}</p></div>'
        for r in rows
    ]
    body = (f"<h1>{escape(survey['title'])} — İsimli Cevaplar</h1>"
            f'<p><a href="/surveys/admin/{survey_id}">← Anketi Düzenle</a></p>'
            + ("".join(items) or "<p>Henüz cevap yok.</p>"))
    return page("İsimli Cevaplar", body)
