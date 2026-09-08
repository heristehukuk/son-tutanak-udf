from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from app.auth.service import require_active_user
from app.auth.permissions import has_permission
from app.web import page
from app.database_layer import repos
from app.surveys import service as svc

router = APIRouter()


def escape(v):
    return (str(v or "")
            .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;"))


def can_manage(u):
    return bool(u and (u.get("is_super_admin") or has_permission(u["id"], "surveys.create")))


def can_view_results(u, survey_id):
    if not u:
        return False
    if u.get("is_super_admin") or has_permission(u["id"], "surveys.view_results"):
        return True
    return svc.has_answered(survey_id, u["id"])  # cevaplayan herkes kendi anketinin sonucunu görebilir


def can_view_individual(u):
    return bool(u and (u.get("is_super_admin") or has_permission(u["id"], "surveys.view_individual_answers")))


KIND_LABELS = {"text": "Serbest metin", "single_choice": "Çoktan seçmeli", "rating": "Puanlama (1-5)"}


# --- Kullanıcı: anket listeleme / cevaplama --------------------------------

@router.get("/", response_class=HTMLResponse)
async def surveys_home(request: Request):
    u = require_active_user(request.cookies.get("session"))
    if not u:
        return HTMLResponse("Giriş yapmalısınız.", 401)
    rows = svc.list_visible_surveys(u["id"])
    manage_link = '<p><a href="/surveys/admin">🛠️ Anket Yönetimi</a></p>' if can_manage(u) else ""
    if not rows:
        body = f"<h1>Anketler</h1>{manage_link}<p>Şu an görüntüleyebileceğiniz bir anket yok.</p>"
        return page("Anketler", body)
    items = []
    for s in rows:
        badge = "✅ Cevaplandı" if s["answered"] else ("🟢 Aktif" if s.get("active") else "🔒 Kapalı")
        items.append(
            f'<div class="card"><b>{escape(s["title"])}</b> <span class="badge">{badge}</span>'
            f'<p>{escape(s.get("description") or "")}</p>'
            f'<a href="/surveys/{s["id"]}">{"Sonuçları/anketi gör" if s["answered"] else "Anketi cevapla"}</a></div>'
        )
    body = f"<h1>Anketler</h1>{manage_link}" + "".join(items)
    return page("Anketler", body)


@router.get("/admin", response_class=HTMLResponse)
async def admin_home(request: Request):
    u = require_active_user(request.cookies.get("session"))
    if not u or not can_manage(u):
        return page("Yetkisiz", "<p>Bu sayfayı görüntüleme yetkiniz yok.</p>", 403)
    rows = svc.list_all_surveys()
    items = []
    for s in rows:
        status = "🟢 Aktif" if s.get("active") else "🔒 Kapalı"
        items.append(
            f'<div class="card"><b>{escape(s["title"])}</b> <span class="badge">{status}</span>'
            f'<p>{escape(s.get("description") or "")}</p>'
            f'<a href="/surveys/admin/{s["id"]}">Soruları yönet</a> · '
            f'<a href="/surveys/{s["id"]}/results">Sonuçlar</a> · '
            f'<form method="post" action="/surveys/admin/{s["id"]}/toggle" style="display:inline">'
            f'<button type="submit">{"Kapat" if s.get("active") else "Aktif Et"}</button></form> '
            f'<form method="post" action="/surveys/admin/{s["id"]}/delete" style="display:inline" '
            f'onsubmit="return confirm(\'Bu anket ve tüm cevapları silinecek. Emin misiniz?\')">'
            f'<button type="submit" class="danger">Sil</button></form></div>'
        )
    body = ("<h1>Anket Yönetimi</h1>"
            '<form method="post" action="/surveys/admin/create" class="card">'
            '<label>Başlık<br><input name="title" required></label><br>'
            '<label>Açıklama<br><textarea name="description" rows="2"></textarea></label><br>'
            '<button type="submit">Yeni Anket Oluştur</button></form>'
            + "".join(items))
    return page("Anket Yönetimi", body)


@router.post("/admin/create")
async def admin_create(request: Request, title: str = Form(...), description: str = Form("")):
    u = require_active_user(request.cookies.get("session"))
    if not u or not can_manage(u):
        return HTMLResponse("Yetkisiz.", 403)
    try:
        svc.create_survey(u["id"], title, description)
    except ValueError as e:
        return page("Anket Yönetimi", f'<p class="err">{escape(str(e))}</p><p><a href="/surveys/admin">← Geri</a></p>', 400)
    return RedirectResponse("/surveys/admin", status_code=303)


@router.post("/admin/{survey_id}/toggle")
async def admin_toggle(request: Request, survey_id: str):
    u = require_active_user(request.cookies.get("session"))
    if not u or not can_manage(u):
        return HTMLResponse("Yetkisiz.", 403)
    survey = svc.get_survey(survey_id)
    if survey:
        svc.set_survey_active(survey_id, not survey.get("active"))
    return RedirectResponse("/surveys/admin", status_code=303)


@router.post("/admin/{survey_id}/delete")
async def admin_delete(request: Request, survey_id: str):
    u = require_active_user(request.cookies.get("session"))
    if not u or not can_manage(u):
        return HTMLResponse("Yetkisiz.", 403)
    try:
        svc.delete_survey(survey_id)
    except ValueError:
        pass
    return RedirectResponse("/surveys/admin", status_code=303)


@router.get("/admin/{survey_id}", response_class=HTMLResponse)
async def admin_questions(request: Request, survey_id: str):
    u = require_active_user(request.cookies.get("session"))
    if not u or not can_manage(u):
        return page("Yetkisiz", "<p>Bu sayfayı görüntüleme yetkiniz yok.</p>", 403)
    survey, questions = svc.get_survey_with_questions(survey_id)
    if not survey:
        return page("Anket bulunamadı", "<p>Bu anket bulunamadı.</p>", 404)
    rows = "".join(
        f'<div class="card"><b>{escape(q["question"])}</b> <span class="badge">{KIND_LABELS.get(q["kind"], q["kind"])}</span>'
        + ("<br>" + escape(", ".join(svc.question_options(q))) if q["kind"] == "single_choice" else "")
        + f'<form method="post" action="/surveys/admin/questions/{q["id"]}/delete" style="display:inline" '
          f'onsubmit="return confirm(\'Bu soru ve verilen cevaplar silinecek. Emin misiniz?\')">'
          f'<button type="submit" class="danger">Sil</button></form></div>'
        for q in questions
    ) or "<p><i>Henüz soru eklenmemiş.</i></p>"
    body = (f"<h1>{escape(survey['title'])} — Sorular</h1>"
            f'<form method="post" action="/surveys/admin/{survey_id}/questions/add" class="card">'
            '<label>Soru metni<br><input name="question" required></label><br>'
            '<label>Tip<br><select name="kind">'
            '<option value="text">Serbest metin</option>'
            '<option value="single_choice">Çoktan seçmeli</option>'
            '<option value="rating">Puanlama (1-5)</option>'
            '</select></label><br>'
            '<label>Şıklar (sadece çoktan seçmeli için, virgülle ayırın)<br>'
            '<input name="options" placeholder="Çok memnun, Memnun, Memnun değil"></label><br>'
            '<button type="submit">Soru Ekle</button></form>'
            f'<p><a href="/surveys/admin">← Anket listesine dön</a></p>' + rows)
    return page(f"{survey['title']} — Sorular", body)


@router.post("/admin/{survey_id}/questions/add")
async def admin_add_question(request: Request, survey_id: str, question: str = Form(...),
                              kind: str = Form("text"), options: str = Form("")):
    u = require_active_user(request.cookies.get("session"))
    if not u or not can_manage(u):
        return HTMLResponse("Yetkisiz.", 403)
    opts = [o.strip() for o in options.split(",")] if options else []
    try:
        svc.add_question(survey_id, question, kind, opts)
    except ValueError as e:
        survey, _ = svc.get_survey_with_questions(survey_id)
        title = survey["title"] if survey else "Anket"
        return page(title, f'<p class="err">{escape(str(e))}</p><p><a href="/surveys/admin/{survey_id}">← Geri</a></p>', 400)
    return RedirectResponse(f"/surveys/admin/{survey_id}", status_code=303)


@router.post("/admin/questions/{question_id}/delete")
async def admin_delete_question(request: Request, question_id: str):
    u = require_active_user(request.cookies.get("session"))
    if not u or not can_manage(u):
        return HTMLResponse("Yetkisiz.", 403)
    row = repos.survey_questions.get(question_id)
    survey_id = row["survey_id"] if row else None
    try:
        svc.delete_question(question_id)
    except ValueError:
        pass
    return RedirectResponse(f"/surveys/admin/{survey_id}" if survey_id else "/surveys/admin", status_code=303)


# --- Kullanıcı: anket detayı / cevaplama / sonuçlar -------------------------
# NOT: Bu route'lar sabit "/admin" ve "/{survey_id}/..." alt-yollarından
# SONRA tanımlanır ki FastAPI "admin" kelimesini bir survey_id sanıp yanlış
# handler'a yönlendirmesin (yol eşleştirme tanım sırasına göre çalışır).

@router.get("/{survey_id}", response_class=HTMLResponse)
async def survey_detail(request: Request, survey_id: str):
    u = require_active_user(request.cookies.get("session"))
    if not u:
        return HTMLResponse("Giriş yapmalısınız.", 401)
    survey, questions = svc.get_survey_with_questions(survey_id)
    if not survey:
        return page("Anket bulunamadı", "<p>Bu anket bulunamadı.</p>", 404)
    answered = svc.has_answered(survey_id, u["id"])
    results_link = f'<p><a href="/surveys/{survey_id}/results">📊 Sonuçları gör</a></p>' if can_view_results(u, survey_id) else ""
    if answered:
        body = (f"<h1>{escape(survey['title'])}</h1><p>{escape(survey.get('description') or '')}</p>"
                f"<p>✅ Bu anketi zaten cevapladınız.</p>{results_link}")
        return page(survey["title"], body)
    if not survey.get("active"):
        body = f"<h1>{escape(survey['title'])}</h1><p>Bu anket artık kapalı; yeni cevap kabul edilmiyor.</p>{results_link}"
        return page(survey["title"], body)
    if not questions:
        body = f"<h1>{escape(survey['title'])}</h1><p>Bu ankette henüz soru eklenmemiş.</p>"
        return page(survey["title"], body)
    fields = []
    for q in questions:
        label = f'<label><b>{escape(q["question"])}</b>'
        if q["kind"] == "text":
            fields.append(f'{label}<br><textarea name="q_{q["id"]}" rows="3"></textarea></label>')
        elif q["kind"] == "single_choice":
            opts = "".join(
                f'<label class="opt"><input type="radio" name="q_{q["id"]}" value="{escape(o)}"> {escape(o)}</label>'
                for o in svc.question_options(q))
            fields.append(f'{label}<div class="opts">{opts}</div></label>')
        elif q["kind"] == "rating":
            opts = "".join(
                f'<label class="opt"><input type="radio" name="q_{q["id"]}" value="{n}"> {n}</label>'
                for n in range(svc.RATING_MIN, svc.RATING_MAX + 1))
            fields.append(f'{label}<div class="opts">{opts}</div></label>')
    body = (f"<h1>{escape(survey['title'])}</h1><p>{escape(survey.get('description') or '')}</p>"
            f'<form method="post" action="/surveys/{survey_id}/answer" class="survey-form">'
            + "".join(fields) +
            '<button type="submit">Gönder</button></form>')
    return page(survey["title"], body)


@router.post("/{survey_id}/answer", response_class=HTMLResponse)
async def survey_answer(request: Request, survey_id: str):
    u = require_active_user(request.cookies.get("session"))
    if not u:
        return HTMLResponse("Giriş yapmalısınız.", 401)
    form = await request.form()
    answers = {k[2:]: v for k, v in form.items() if k.startswith("q_")}
    try:
        svc.submit_answers(survey_id, u["id"], answers)
    except ValueError as e:
        survey, _ = svc.get_survey_with_questions(survey_id)
        title = survey["title"] if survey else "Anket"
        return page(title, f'<h1>{escape(title)}</h1><p class="err">{escape(str(e))}</p>'
                            f'<p><a href="/surveys/{survey_id}">← Geri dön</a></p>', 400)
    return RedirectResponse(f"/surveys/{survey_id}", status_code=303)


@router.get("/{survey_id}/results", response_class=HTMLResponse)
async def survey_results(request: Request, survey_id: str):
    u = require_active_user(request.cookies.get("session"))
    if not u:
        return HTMLResponse("Giriş yapmalısınız.", 401)
    survey = svc.get_survey(survey_id)
    if not survey:
        return page("Anket bulunamadı", "<p>Bu anket bulunamadı.</p>", 404)
    if not can_view_results(u, survey_id):
        return page(survey["title"], "<p>Sonuçları görebilmek için önce bu anketi cevaplamış olmanız gerekir.</p>", 403)
    results = svc.compute_aggregate_results(survey_id)
    blocks = []
    for r in results:
        if r["kind"] == "text":
            answers_html = "".join(f"<li>{escape(a)}</li>" for a in r["answers"]) or "<li><i>Henüz cevap yok.</i></li>"
            blocks.append(f'<div class="card"><b>{escape(r["question"])}</b><ul>{answers_html}</ul></div>')
        elif r["kind"] == "single_choice":
            rows = "".join(f"<li>{escape(o)}: {c}</li>" for o, c in r["counts"].items())
            blocks.append(f'<div class="card"><b>{escape(r["question"])}</b> ({r["total"]} cevap)<ul>{rows}</ul></div>')
        else:  # rating
            rows = "".join(f"<li>{n} puan: {c}</li>" for n, c in r["counts"].items())
            avg = f' — Ortalama: {r["average"]}' if r["average"] is not None else ""
            blocks.append(f'<div class="card"><b>{escape(r["question"])}</b> ({r["total"]} cevap{avg})<ul>{rows}</ul></div>')
    individual_link = (f'<p><a href="/surveys/{survey_id}/individual">👤 İsimli cevapları gör (yetkili)</a></p>'
                        if can_view_individual(u) else "")
    body = (f"<h1>{escape(survey['title'])} — Sonuçlar</h1>"
            f"<p><i>Bu özet anonimdir; kimin ne yazdığı gösterilmez.</i></p>{individual_link}"
            + "".join(blocks))
    return page(f"{survey['title']} — Sonuçlar", body)


@router.get("/{survey_id}/individual", response_class=HTMLResponse)
async def survey_individual(request: Request, survey_id: str):
    u = require_active_user(request.cookies.get("session"))
    if not u:
        return HTMLResponse("Giriş yapmalısınız.", 401)
    if not can_view_individual(u):
        return page("Yetkisiz", "<p>Bu sayfayı görüntüleme yetkiniz yok.</p>", 403)
    survey = svc.get_survey(survey_id)
    if not survey:
        return page("Anket bulunamadı", "<p>Bu anket bulunamadı.</p>", 404)
    rows = svc.compute_individual_answers(survey_id)
    items = "".join(
        f'<tr><td>{escape(r["user_name"])}</td><td>{escape(r["question"])}</td><td>{escape(r["answer"])}</td>'
        f'<td>{escape(r["updated_at"])[:16]}</td></tr>' for r in rows
    ) or '<tr><td colspan="4"><i>Henüz cevap yok.</i></td></tr>'
    body = (f"<h1>{escape(survey['title'])} — İsimli Cevaplar</h1>"
            f'<table class="tbl"><thead><tr><th>Kullanıcı</th><th>Soru</th><th>Cevap</th><th>Tarih</th></tr></thead>'
            f'<tbody>{items}</tbody></table>')
    return page(f"{survey['title']} — İsimli Cevaplar", body)
