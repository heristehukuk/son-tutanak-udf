
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, Response
from app.auth.service import get_user_by_session
from app.database_layer import repos
from app.web import page
from app.modules.tasks.storage import document_checklist
from app.storage import storage
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
        chk_items=[]
        for c in checklist:
            if c["created"] and c.get("document"):
                chk_items.append(f'<a class="chk on" href="/files/document/{c["document"]["id"]}">☑ {c["title"]} ⬇</a>')
            else:
                chk_items.append(f'<span class="chk">☐ {c["title"]}</span>')
        check_html="".join(chk_items)
        rows.append(f'''<div class="card">
            <h3>{r["title"] or "Dosya"} <span class="status">{STATUS_LABELS.get(r.get("status"),r.get("status") or "")}</span></h3>
            <p>Kayıt No: <b>{r.get("registry_no") or "—"}</b></p>
            <p>Sistem ID: {r["id"]}</p><p>Dosya No: {r["file_no"] or "-"}</p>
            <p>Başvuru No: {r["application_no"] or "-"}</p>
            <p>Dosya Türü: {r.get("file_type") or "-"}</p>
            <div class="checklist">{check_html}</div>
            <p class="links">
                <a href="/tasks/?case_id={r["id"]}">📋 Görevler</a> ·
                <a href="/calendar">📅 Takvim</a> ·
                <a href="/messages/?case_id={r["id"]}">💬 Dosya Mesajları</a>
            </p></div>''')
    style='''<style>.status{font-size:13px;font-weight:normal}.checklist{display:flex;flex-wrap:wrap;gap:8px;margin:8px 0}
    .chk{font-size:12px;padding:4px 8px;border-radius:999px;background:#f1f4f7;color:#66717c;text-decoration:none}
    .chk.on{background:#dcfce7;color:#166534}.links a{margin-right:4px}</style>'''
    return page("Dosyalar", style+"<h1>Dosyalarım</h1>"+("".join(rows) or "<p>Henüz dosyanız yok.</p>"))

@router.get("/document/{doc_id}")
async def download_generated(request:Request,doc_id:str):
    u=get_user_by_session(request.cookies.get("session"))
    if not u:return HTMLResponse("Giriş yapmalısınız.",401)
    r=repos.generated_documents.get(doc_id)
    if not r or r.get("owner_id")!=u["id"]:return HTMLResponse("Belge bulunamadı veya erişim yetkiniz yok.",404)
    data=storage.read(r["stored_path"])
    ext=r["stored_path"].rsplit(".",1)[-1] if "." in r["stored_path"] else "udf"
    filename=f'{r.get("original_template") or "belge"}.{ext}'
    return Response(data,media_type="application/octet-stream",
                    headers={"Content-Disposition":f'attachment; filename="{filename}"'})

