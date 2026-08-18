
import json
from html import escape
from datetime import datetime
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, Response, RedirectResponse, JSONResponse
from app.auth.service import get_user_by_session, now, cleanup_expired_pending
from app.files.trash_service import (
    cleanup_expired_deleted_cases, soft_delete_case, restore_case, list_trash,
)
from app.storage import storage
from app.auth.permissions import (
    is_admin, has_permission, require_permission, PERMISSIONS,
    PERMISSION_LABELS, ASSIGNABLE_PERMISSIONS,
)
from app.database_layer import repos
from app.web import page
from app.customtemplates.service import list_all_templates
from app.feepusula.service import list_tariffs, add_tariff, delete_tariff, CATEGORY_LABELS
router=APIRouter()

STATUS_LABELS={"pending":"Onay Bekliyor","active":"Aktif","suspicious":"Şüpheli","rejected":"Reddedildi","banned":"Yasaklı"}


def staff(request):
    """Admin paneline HİÇ girebilecek mi: süper admin ya da en az bir yetkisi olan biri."""
    u=get_user_by_session(request.cookies.get("session"))
    if not u:return None
    if u.get("is_super_admin"):return u
    if repos.permissions.list_for_user(u["id"]):return u
    return None


def admin(request):
    """Geriye dönük uyum: eski kod tabanındaki tam-yetkili kontrol noktaları için.
    Sadece süper admin döner (hassas işlemler - kullanıcı silme, yetki verme -
    bu fonksiyonla korunmaya devam eder)."""
    u=get_user_by_session(request.cookies.get("session"))
    return u if u and u["is_super_admin"] else None


def log(actor_id,action,target_id=None,details=""):
    repos.audit.create({"actor_id":actor_id,"action":action,"target_id":target_id,
                        "details":details,"created_at":now().isoformat()})


@router.get("/",response_class=HTMLResponse)
async def dashboard(request:Request):
    u=staff(request)
    if not u:return HTMLResponse("Yetkisiz.",403)
    cleanup_expired_pending()
    cleanup_expired_deleted_cases()
    can={p:require_permission(u,p) for p in PERMISSIONS}
    users=repos.users.list_all()
    plans=repos.plans.list_all()
    plan_options={p["id"]:p["name"] for p in plans}
    perms_by_user={x["id"]:set(repos.permissions.list_for_user(x["id"])) for x in users} if can["admins.manage"] else {}

    us=[]
    for r in users:
        status_opts="".join(f'<option value="{k}"{" selected" if r["status"]==k else ""}>{v}</option>' for k,v in STATUS_LABELS.items())
        status_form=""
        if can["users.approve"] or can["users.reject"] or can["users.suspend"] or can["users.ban"]:
            status_form=(f'<form method="post" action="/admin/users/{r["id"]}/status">'
                        f'<select name="status">{status_opts}</select><button>Durumu Kaydet</button></form>')
        plan_form=""
        if can["plans.manage"]:
            plan_opts="".join(f'<option value="{pid}"{" selected" if r["plan_id"]==pid else ""}>{name}</option>' for pid,name in plan_options.items())
            plan_form=(f'<form method="post" action="/admin/users/{r["id"]}/plan">'
                      f'<select name="plan_id">{plan_opts}</select><button>Plan Ata</button></form>')
        perm_form=""
        if can["admins.manage"] and not r.get("is_super_admin"):
            checks="".join(
                f'<label class="perm"><input type="checkbox" name="permission" value="{p}"'
                f'{" checked" if p in perms_by_user.get(r["id"],set()) else ""}> {escape(PERMISSION_LABELS.get(p,p))}</label>'
                for p in ASSIGNABLE_PERMISSIONS)
            perm_form=(f'<details><summary>Yetkiler</summary><form method="post" action="/admin/users/{r["id"]}/permissions">'
                      f'{checks}<button>Yetkileri Kaydet</button></form></details>')
        message_link=f'<a href="/messages/thread/{r["id"]}">💬 Mesaj</a>' if can["messages.send"] else ""
        delete_form=""
        if can["users.ban"]:
            delete_form=(f'<form method="post" action="/admin/users/{r["id"]}/delete" '
                        f'onsubmit="return confirm(\'{escape(r["display_name"])} hesabı KALICI olarak silinsin mi?\')">'
                        f'<button class="secondary">Hesabı Sil</button></form>')
        us.append(
            f'<div class="card"><b>{escape(r["display_name"])}</b> — {escape(r["email"])}'
            f'<p>Durum: {STATUS_LABELS.get(r["status"],r["status"])} | Plan: {plan_options.get(r["plan_id"],r["plan_id"])} | IP: {r["last_ip"] or "-"}'
            f' | Arabulucu No: {r.get("mediator_no") or "—"} | Sistem ID: <code class="hint">{r["id"]}</code>'
            f'{" | 👑 Süper Admin" if r.get("is_super_admin") else ""}</p>'
            f'<div class="actions">{status_form}{plan_form}</div>{perm_form}<p class="links">{message_link} {delete_form}</p></div>'
        )
    cs=[]
    if can["files.view"]:
        for r in repos.cases.list_all_with_owner():
            if r.get("status")=="deleted":continue
            del_case_btn=""
            if can["files.delete"]:
                del_case_btn=(f'<form method="post" action="/admin/cases/{r["id"]}/delete" style="display:inline" '
                              f'onsubmit="return confirm(\'Bu dosya silinsin mi? 15 gün içinde çöp kutusundan geri getirilebilir.\')">'
                              f'<button class="secondary">🗑️ Dosyayı Sil</button></form>')
            cs.append(
                f'<div class="card"><b>{escape(r.get("title") or "Dosya")}</b> — {escape(r.get("owner_name"))} ({escape(r.get("owner_email"))})'
                f'<p>Dosya No: {escape(r.get("file_no") or "-")} | Durum: {escape(r.get("status") or "-")} | Sistem ID: <code class="hint">{r["id"]}</code></p>'
                f'<form method="post" action="/admin/cases/{r["id"]}/registry-no">'
                f'<label>Kayıt No</label><input name="registry_no" value="{escape(r.get("registry_no") or "")}" placeholder="ör. 212-2026-001">'
                f'<button>Kaydet</button></form><p class="links">{del_case_btn}</p></div>'
            )
    ds=[]
    if can["files.view"]:
        docs=repos.documents.list_all_with_owner_email()
        for r in docs:
            del_btn=(f'<form method="post" action="/admin/documents/{r["id"]}/delete" style="display:inline" '
                    f'onsubmit="return confirm(\'Belge silinsin mi?\')"><button class="secondary">Sil</button></form>') if can["files.delete"] else ""
            dl=f'<a href="/admin/documents/{r["id"]}">Gör/İndir</a>' if can["files.download"] else ""
            ds.append(f'<div class="card"><b>{escape(r["original_name"])}</b><p>{escape(r["email"])} | {r["size_bytes"]} bytes</p>{dl} {del_btn}</div>')
    ts=[]
    for t in list_all_templates():
        paylasim = "Paylaşılan (ortak)" if t["is_shared"] else "Kişisel"
        ts.append(f'<div class="card"><b>{escape(t["name"])}</b>'
                  f'<p>{escape(t["owner_name"])} — {escape(t["owner_email"])} | {escape(paylasim)}</p>'
                  f'<a href="/admin/templates/{escape(t["id"])}">Şablonu Gör/İndir</a></div>')

    audit_html=""
    if can["audit.view"]:
        audit_html='<h2>İşlem Geçmişi</h2><p><a href="/admin/audit"><button>Tüm Kayıtları Gör</button></a></p>'

    folder_html='<h2>📁 Klasör Yönetimi</h2><p><a href="/folders/admin"><button>Klasörleri Yönet</button></a></p>' if u.get('is_super_admin') else ''

    backup_html='<h2>Tam Yedek</h2><p><a href="/admin/backup"><button>Tüm Sistemi JSON Olarak İndir</button></a></p>' if u.get("is_super_admin") else ""

    trash_html=""
    if can["files.delete"]:
        trash_count=len(list_trash())
        trash_html=f'<h2>🗑️ Çöp Kutusu ({trash_count})</h2><p><a href="/admin/trash"><button>Silinen Dosyaları Gör</button></a></p>'

    body=(STYLE+"<h1>Yönetim</h1><h2>Üyeler</h2>"+"".join(us)+
          (("<h2>Dosyalar (Kayıt No)</h2>"+"".join(cs)) if can["files.view"] else "")+
          (("<h2>Yüklenen Belgeler</h2>"+"".join(ds)) if can["files.view"] else "")+
          "<h2>Kullanıcı Şablonları (Tümü)</h2>"+("".join(ts) or "<p>Henüz özel şablon yok.</p>")+
          "<h2>Arabuluculuk Ücret Tarifesi</h2><p><a href=\"/admin/tariffs\"><button>Tarifeyi Yönet</button></a></p>"+
          audit_html+trash_html+folder_html+backup_html)
    return page("Admin",body)


STYLE='''<style>
.actions{display:flex;gap:10px;flex-wrap:wrap;align-items:flex-end}
.actions form{margin:0}
.perm{display:block;font-weight:normal;font-size:13px;margin:4px 0}
details summary{cursor:pointer;font-weight:700;margin-top:8px}
.links{margin-top:8px}
</style>'''


@router.get("/audit",response_class=HTMLResponse)
async def audit_log(request:Request):
    u=staff(request)
    if not u or not require_permission(u,"audit.view"):return HTMLResponse("Yetkisiz.",403)
    users_by_id={x["id"]:x for x in repos.users.list_all()}
    rows=repos.audit.list_all()
    items=[]
    for r in rows:
        actor=users_by_id.get(r.get("actor_id"))
        actor_label=escape(actor["display_name"]) if actor else "Sistem"
        target=users_by_id.get(r.get("target_id"))
        target_label=f' → {escape(target["display_name"])}' if target else (f' → {escape(r["target_id"])}' if r.get("target_id") else "")
        items.append(f'<div class="card"><b>{escape(r["action"])}</b> <span class="hint">{escape(r["created_at"])}</span>'
                    f'<p>{actor_label}{target_label}</p>{f"<p class=\"hint\">{escape(r['details'])}</p>" if r.get("details") else ""}</div>')
    return page("İşlem Geçmişi","<h1>İşlem Geçmişi</h1><p><a href=\"/admin/\">← Yönetime Dön</a></p>"+("".join(items) or "<p>Kayıt yok.</p>"))


@router.get("/trash",response_class=HTMLResponse)
async def trash_page(request:Request):
    u=staff(request)
    if not u or not require_permission(u,"files.delete"):return HTMLResponse("Yetkisiz.",403)
    rows=list_trash()
    items=[]
    for r in rows:
        days=r["days_remaining"]
        days_label=f"{days} gün kaldı" if days>=0 else "süresi doldu, bir sonraki kontrolde kalıcı silinecek"
        items.append(
            f'<div class="card"><b>{escape(r.get("title") or "Dosya")}</b> — {escape(r.get("owner_name"))} ({escape(r.get("owner_email"))})'
            f'<p>Dosya No: {escape(r.get("file_no") or "-")} | Silme tarihi: {escape(r.get("deleted_at") or "-")} | <b>{days_label}</b></p>'
            f'<form method="post" action="/admin/cases/{r["id"]}/restore"><button>♻️ Geri Getir</button></form></div>'
        )
    body=("<h1>🗑️ Çöp Kutusu</h1><p><a href=\"/admin/\">← Yönetime Dön</a></p>"
          "<p class=\"hint\">Silinen dosyalar 15 gün boyunca burada durur, süre dolunca bir sonraki panel açılışında kalıcı olarak silinir (belgeler dahil).</p>"
          +("".join(items) or "<p>Çöp kutusu boş.</p>"))
    return page("Çöp Kutusu",body)

@router.post("/cases/{case_id}/delete")
async def admin_delete_case(request:Request,case_id:str):
    u=staff(request)
    if not u or not require_permission(u,"files.delete"):return HTMLResponse("Yetkisiz.",403)
    try:
        soft_delete_case(case_id,u["id"],is_admin=True)
    except ValueError as e:
        return HTMLResponse(f"Hata: {escape(str(e))}",400)
    return HTMLResponse('<meta http-equiv="refresh" content="0;url=/admin/">')

@router.post("/cases/{case_id}/restore")
async def admin_restore_case(request:Request,case_id:str):
    u=staff(request)
    if not u or not require_permission(u,"files.delete"):return HTMLResponse("Yetkisiz.",403)
    try:
        restore_case(case_id,u["id"])
    except ValueError as e:
        return HTMLResponse(f"Hata: {escape(str(e))}",400)
    return HTMLResponse('<meta http-equiv="refresh" content="0;url=/admin/trash">')

@router.get("/backup")
async def full_backup(request:Request):
    u=admin(request)
    if not u:return HTMLResponse("Yetkisiz.",403)
    data={
        "exported_at": now().isoformat(),
        "users": repos.users.list_all(),
        "cases": [c for x in repos.users.list_all() for c in repos.cases.list_by_owner(x["id"])],
        "documents": repos.documents.list_all_with_owner_email(),
        "generated_documents": [d for x in repos.users.list_all() for d in repos.generated_documents.list_by_owner(x["id"])],
        "templates": repos.templates.list_all(),
        "messages": [m for x in repos.users.list_all() for m in repos.messages.list_for_user(x["id"])],
        "tariffs": repos.tariffs.list_all(),
        "plans": repos.plans.list_all(),
        "audit_logs": repos.audit.list_all(),
        "tasks": [t for x in repos.users.list_all() for t in repos.tasks.list_for_owner(x["id"])],
        "task_templates": [t for x in repos.users.list_all() for t in repos.task_templates.list_for_owner(x["id"])],
        "calendar_events": [e for x in repos.users.list_all() for e in repos.calendar_events.list_for_owner(x["id"])],
        "user_permissions": {x["id"]: repos.permissions.list_for_user(x["id"]) for x in repos.users.list_all()},
    }
    log(u["id"],"full_backup_export",None,"Tam yedek indirildi.")
    payload=json.dumps(data,ensure_ascii=False,indent=2,default=str)
    filename=f"son-tutanak-tam-yedek-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    return HTMLResponse(payload,media_type="application/json",
        headers={"Content-Disposition":f'attachment; filename="{filename}"'})


@router.get("/tariffs",response_class=HTMLResponse)
async def tariffs_page(request:Request):
    u=staff(request)
    if not u or not require_permission(u,"plans.manage"):return HTMLResponse("Yetkisiz.",403)
    rows=list_tariffs()
    trs=[]
    for r in rows:
        trs.append(f'<tr><td>{r["year"]}</td><td>{r["category_label"]}</td>'
                   f'<td>{r["min_parties"]}{"+" if r["max_parties"] is None else "-"+str(r["max_parties"])}</td>'
                   f'<td>{r["unit_price"]:.2f} ₺</td>'
                   f'<td><form method="post" action="/admin/tariffs/{r["id"]}/delete" '
                   f'onsubmit="return confirm(\'Silinsin mi?\')"><button class="secondary">Sil</button></form></td></tr>')
    table = ('<table style="width:100%"><tr><th>Yıl</th><th>Kategori</th><th>Taraf Sayısı</th>'
             '<th>Birim Fiyat</th><th></th></tr>'+''.join(trs)+'</table>') if trs else "<p>Henüz tarife eklenmedi.</p>"
    cat_options=''.join(f'<option value="{k}">{v}</option>' for k,v in CATEGORY_LABELS.items())
    body=f"""<h1>Arabuluculuk Ücret Tarifesi</h1>
    <p><a href="/admin/">Yönetime Dön</a></p>
    <div class="card"><h2>Yeni Tarife Satırı Ekle</h2>
    <form method="post" action="/admin/tariffs/add">
    <label>Yıl</label><input type="number" name="year" value="2026" required>
    <label>Kategori</label><select name="category">{cat_options}</select>
    <label>Min. Taraf Sayısı</label><input type="number" name="min_parties" value="2" required>
    <label>Maks. Taraf Sayısı (sınırsızsa boş bırakın)</label><input type="number" name="max_parties">
    <label>Birim Fiyat (TL)</label><input type="number" step="0.01" name="unit_price" required>
    <button>Ekle</button></form></div>
    <div class="card">{table}</div>"""
    return page("Ücret Tarifesi",body)

@router.post("/tariffs/add")
async def add_tariff_row(request:Request,year:int=Form(...),category:str=Form(...),
                          min_parties:int=Form(...),max_parties:str=Form(""),unit_price:float=Form(...)):
    u=staff(request)
    if not u or not require_permission(u,"plans.manage"):return HTMLResponse("Yetkisiz.",403)
    add_tariff(category,min_parties,int(max_parties) if max_parties.strip() else None,unit_price,year)
    log(u["id"],"tariff_add",None,f"{category} {year}")
    return RedirectResponse("/admin/tariffs",303)

@router.post("/tariffs/{tariff_id}/delete")
async def remove_tariff_row(request:Request,tariff_id:str):
    u=staff(request)
    if not u or not require_permission(u,"plans.manage"):return HTMLResponse("Yetkisiz.",403)
    delete_tariff(tariff_id)
    log(u["id"],"tariff_delete",tariff_id)
    return RedirectResponse("/admin/tariffs",303)

@router.get("/templates/{template_id}")
async def download_template(request:Request,template_id:str):
    u=staff(request)
    if not u:return HTMLResponse("Yetkisiz.",403)
    r=repos.templates.get(template_id)
    if not r:return HTMLResponse("Şablon bulunamadı.",404)
    data=storage.read(r["stored_path"])
    return Response(data,media_type="application/octet-stream",
                    headers={"Content-Disposition":f'attachment; filename="{r["name"]}.udf"'})

@router.post("/cases/{case_id}/registry-no")
async def set_registry_no(request:Request,case_id:str,registry_no:str=Form(...)):
    u=staff(request)
    if not u or not require_permission(u,"files.view"):return HTMLResponse("Yetkisiz.",403)
    from app.registry import set_registry_no_manual
    try:
        set_registry_no_manual(case_id,registry_no)
    except ValueError as e:
        return HTMLResponse(f"Hata: {escape(str(e))} <a href=\"/admin/\">← Geri dön</a>",400)
    log(u["id"],"registry_no_change",case_id,registry_no)
    return HTMLResponse('<meta http-equiv="refresh" content="0;url=/admin/">')

@router.post("/users/{user_id}/status")
async def status(request:Request,user_id:str,status:str=Form(...)):
    u=staff(request)
    needed={"active":"users.approve","rejected":"users.reject","suspicious":"users.suspend","banned":"users.ban","pending":"users.approve"}
    if not u or not require_permission(u,needed.get(status,"users.approve")):return HTMLResponse("Yetkisiz.",403)
    target=repos.users.get(user_id)
    old_status=target.get("status") if target else None
    repos.users.update(user_id,{"status":status,"approved_at":now().isoformat() if status=="active" else None})
    if status=="active":
        from app.registry import ensure_mediator_no
        ensure_mediator_no(user_id)
    log(u["id"],"status_change",user_id,f"{old_status} -> {status}")
    return HTMLResponse('<meta http-equiv="refresh" content="0;url=/admin/">')

@router.post("/users/{user_id}/plan")
async def assign_plan(request:Request,user_id:str,plan_id:str=Form(...)):
    u=staff(request)
    if not u or not require_permission(u,"plans.manage"):return HTMLResponse("Yetkisiz.",403)
    repos.users.update(user_id,{"plan_id":plan_id})
    log(u["id"],"plan_assign",user_id,plan_id)
    return HTMLResponse('<meta http-equiv="refresh" content="0;url=/admin/">')

@router.post("/users/{user_id}/permissions")
async def set_permissions(request:Request,user_id:str):
    u=admin(request)  # admins.manage sadece süper admin - require_permission değil, kesin admin() kontrolü
    if not u:return HTMLResponse("Yetkisiz. Sadece süper admin yetki atayabilir.",403)
    target=repos.users.get(user_id)
    if not target or target.get("is_super_admin"):return HTMLResponse("Bu kullanıcıya yetki ataması yapılamaz.",400)
    form=await request.form()
    selected=set(form.getlist("permission")) & set(ASSIGNABLE_PERMISSIONS)
    current=set(repos.permissions.list_for_user(user_id))
    for p in current-selected: repos.permissions.revoke(user_id,p)
    for p in selected-current: repos.permissions.grant(user_id,p,u["id"])
    log(u["id"],"permissions_update",user_id,", ".join(sorted(selected)) or "(hiçbiri)")
    return HTMLResponse('<meta http-equiv="refresh" content="0;url=/admin/">')

@router.post("/users/{user_id}/delete")
async def delete_user(request:Request,user_id:str):
    u=staff(request)
    if not u or not require_permission(u,"users.ban"):return HTMLResponse("Yetkisiz.",403)
    target=repos.users.get(user_id)
    if not target:return HTMLResponse("Kullanıcı bulunamadı.",404)
    if target.get("is_super_admin"):return HTMLResponse("Süper admin hesabı silinemez.",400)
    repos.users.delete(user_id)
    log(u["id"],"user_delete",user_id,f"{target.get('email')} silindi.")
    return HTMLResponse('<meta http-equiv="refresh" content="0;url=/admin/">')

@router.get("/documents/{doc_id}")
async def download_document(request:Request,doc_id:str):
    u=staff(request)
    if not u or not require_permission(u,"files.download"):return HTMLResponse("Yetkisiz.",403)
    r=repos.documents.get(doc_id)
    if not r:return HTMLResponse("Belge bulunamadı.",404)
    data=storage.read(r["stored_path"])
    return Response(data,media_type="application/octet-stream",
                    headers={"Content-Disposition":f'attachment; filename="{r["original_name"]}"'})

@router.post("/documents/{doc_id}/delete")
async def remove_document(request:Request,doc_id:str):
    u=staff(request)
    if not u or not require_permission(u,"files.delete"):return HTMLResponse("Yetkisiz.",403)
    r=repos.documents.get(doc_id)
    if not r:return HTMLResponse("Belge bulunamadı.",404)
    repos.documents.delete(doc_id)
    log(u["id"],"document_delete",doc_id,r.get("original_name"))
    return HTMLResponse('<meta http-equiv="refresh" content="0;url=/admin/">')
