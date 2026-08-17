
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from app.auth.service import get_user_by_session
from app.database_layer import repos
from app.web import page
from app.modules.tasks.storage import document_checklist
router=APIRouter()

STATUS_LABELS={"open":"🟡 Açık","completed":"🟢 Tamamlandı"}

@router.get("/",response_class=HTMLResponse)
async def files(request:Request):
    u=get_user_by_session(request.cookies.get("session"))
    if not u:return HTMLResponse("Giriş yapmalısınız.",401)
    cases=repos.cases.list_by_owner(u["id"])
    rows=[]
    for r in cases:
        checklist=document_checklist(u["id"],r["id"])
        check_html="".join(
            f'<span class="chk {"on" if c["created"] else ""}">{"☑" if c["created"] else "☐"} {c["title"]}</span>'
            for c in checklist)
        rows.append(f'''<div class="card">
            <h3>{r["title"] or "Dosya"} <span class="status">{STATUS_LABELS.get(r.get("status"),r.get("status") or "")}</span></h3>
            <p>Sistem ID: {r["id"]}</p><p>Dosya No: {r["file_no"] or "-"}</p>
            <p>Başvuru No: {r["application_no"] or "-"}</p>
            <p>Dosya Türü: {r.get("file_type") or "-"}</p>
            <div class="checklist">{check_html}</div>
            <p class="links">
                <a href="/folders?case_id={r["id"]}">📁 Klasörler</a> ·
                <a href="/tasks/?case_id={r["id"]}">📋 Görevler</a> ·
                <a href="/calendar">📅 Takvim</a> ·
                <a href="/messages/?case_id={r["id"]}">💬 Dosya Mesajları</a>
            </p></div>''')
    style='''<style>.status{font-size:13px;font-weight:normal}.checklist{display:flex;flex-wrap:wrap;gap:8px;margin:8px 0}
    .chk{font-size:12px;padding:4px 8px;border-radius:999px;background:#f1f4f7;color:#66717c}
    .chk.on{background:#dcfce7;color:#166534}.links a{margin-right:4px}</style>'''
    return page("Dosyalar", style+"<h1>Dosyalarım</h1>"+("".join(rows) or "<p>Henüz dosyanız yok.</p>"))
