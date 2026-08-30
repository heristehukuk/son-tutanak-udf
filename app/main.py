import os

import io, os, re, json, urllib.parse, zipfile
from uuid import uuid4
import pytesseract
from pathlib import Path
from fastapi import FastAPI, Request, UploadFile, File
from fastapi.responses import HTMLResponse, StreamingResponse, RedirectResponse
from app.database import init_db, connect
from app.database_layer import repos
from app.storage import storage
from app.auth.routes import router as auth_router
from app.files.routes import router as files_router
from app.admin.routes import router as admin_router
from app.messaging.routes import router as messaging_router
from app.surveys.routes import router as surveys_router
from app.plans.routes import router as plans_router
from app.customtemplates.routes import router as templates_router
from app.feepusula.routes import router as feepusula_router
from app.feepusula.service import seed_known_tariffs
from app.auth.service import get_user_by_session, now
from app.auth.security import hash_password
from app.files.pending_service import create_pending, get_pending_for_user, cleanup_expired_pending_merges, serialize_row
from app.plans.service import seed_plans, get_plan, feature_enabled, consume
from app.files.service import save_document, create_case, save_generated
from app.files.case_matcher import detect_identity_conflicts, merge_case_values, case_values, IDENTITY_FIELDS
from app.customtemplates.service import list_visible_templates, get_template, can_use_template, get_template_bytes
from app.documents.engine import (
    read_udf, extract, render_editor, form_state, merge_state, template_bytes, TEMPLATES,
    extract_any_source, standard_result, set_parties_and_signatures, replace_meeting_paragraph,
    build_meeting_sentence, replace_final_legal_paragraph, fill_general, replace_talep_in_narrative,
    update_offsets, rebuild_region_paragraphs, build_udf, scan_custom_template, fill_custom_template,
    fill_custom_template_tracked, update_offsets_exact,
    discover_folder_templates, FIXED_TEMPLATE_DOC_KIND,
)
from app.web import page
from app.supabase_client import supabase_health
from app.modules.calendar.router import router as calendar_router
from app.modules.tasks.router import router as tasks_router
from app.folders.routes import router as folders_router
app=FastAPI(title="Son Tutanak UDF Asistanı v17")
app.include_router(auth_router,prefix="/auth")
app.include_router(files_router,prefix="/files")
app.include_router(admin_router,prefix="/admin")
app.include_router(messaging_router,prefix="/messages")
app.include_router(surveys_router,prefix="/surveys")
app.include_router(plans_router,prefix="/plans")
app.include_router(templates_router,prefix="/templates")
app.include_router(feepusula_router,prefix="/harcama-pusulasi")
app.include_router(calendar_router)
app.include_router(tasks_router)
app.include_router(folders_router)

@app.on_event("startup")
async def startup():
    init_db(); seed_plans(); bootstrap_admin(); seed_known_tariffs()
    from app.registry import assign_missing_mediator_numbers, assign_missing_registry_numbers
    assign_missing_mediator_numbers(); assign_missing_registry_numbers()

def ocr_environment():
    try:
        return {
            "tesseract": str(pytesseract.get_tesseract_version()),
            "cmd": pytesseract.pytesseract.tesseract_cmd
        }
    except Exception as exc:
        return {"error": str(exc), "cmd": getattr(pytesseract.pytesseract, "tesseract_cmd", "tesseract")}

def bootstrap_admin():
    email=os.getenv("ADMIN_EMAIL"); password=os.getenv("ADMIN_PASSWORD")
    if not email or not password:return
    if repos.users.get_by_email(email.lower()):return
    import uuid
    repos.users.create({"id":str(uuid.uuid4()),"email":email.lower(),"display_name":"Super Admin",
        "password_hash":hash_password(password),"status":"active","plan_id":"pro",
        "is_super_admin":1,"created_at":now().isoformat()})

def current_user(request):
    return get_user_by_session(request.cookies.get("session"))

def apply_mediator_profile_defaults(user, values):
    """Profildeki arabulucu bilgilerini Bilgi Havuzu'nda yalnızca boş alanlara varsayılan yapar."""
    mapping={
        "mediator_name":"arabulucuAdi", "mediator_tc":"arabulucuTc",
        "mediator_registry":"arabulucuSicil", "mediator_address":"arabulucuAdres",
        "mediator_phone":"arabulucuTelefon", "mediator_email":"arabulucuEposta",
    }
    out=dict(values)
    for src,dst in mapping.items():
        if not str(out.get(dst) or "").strip() and user.get(src):
            out[dst]=str(user.get(src))
    return out

def require_user(request):
    u=current_user(request)
    if not u or u["status"] in ("banned","rejected"):return None
    return u

@app.get("/health")
async def health():
    return {"status": "ok", "ocr": ocr_environment()}
    
@app.get("/health/supabase")
async def supabase_health_check():
    return supabase_health()

@app.get("/",response_class=HTMLResponse)
async def home(request:Request):
    u=current_user(request)
    if u:
        from app.auth.service import cleanup_expired_pending
        from app.files.trash_service import cleanup_expired_deleted_cases
        from app.folders.service import cleanup_deleted_folders
        cleanup_expired_pending()
        cleanup_expired_pending_merges()
        cleanup_expired_deleted_cases()
        cleanup_deleted_folders()
        u=current_user(request)  # durumu değişmiş olabilir (pending->rejected)
    if not u:
        return page("Son Tutanak UDF Asistanı",
        """<div class="card narrow"><h1>Son Tutanak UDF Asistanı v17</h1>
        <p>Başvuru formu yükleyin; UDF, PDF, JPG, JPEG veya PNG belgelerinden bilgileri çekin.</p>
        <p><a href="/auth/login"><button>Giriş Yap</button></a>
        <a href="/auth/register"><button>Üyelik Başvurusu</button></a></p></div>""")
    if u["status"]=="pending":
        return page("Onay Bekliyor",
        '<div class="card narrow"><h1>Onay bekleniyor</h1><p>Hesabınız yönetici onayından sonra kullanılabilir.</p>'
        '<form action="/auth/logout" method="post"><button>Çıkış</button></form></div>')
    if u["status"]=="suspicious":
        return page("İnceleme",
        '<div class="card narrow"><h1>Hesabınız incelemede</h1><p>Yönetici açıklama istemiş olabilir. Mesajlar bölümünü kontrol edin.</p>'
        '<p><a href="/messages/">Mesajlara Git</a></p></div>')
    return page("Son Tutanak UDF Asistanı",
    f"""<div class="card"><h1>Son Tutanak UDF Asistanı v17</h1><p>Hoş geldiniz, {u["display_name"]}.</p>
    <form action="/edit" method="post" enctype="multipart/form-data">
    <label>Başvuru formu / kaynak belge</label>
    <input type="file" name="file" accept=".udf,.pdf,.jpg,.jpeg,.png" required>
    <button>Belgeyi Analiz Et</button></form>
    <p><a href="/files/">Dosyalarım</a> · <a href="/tasks/">Görevler</a> · <a href="/calendar">Takvim</a> ·
    <a href="/messages/">Mesajlar{f' <span class="badge">{unread}</span>' if (unread:=repos.messages.count_unread(u["id"])) else ''}</a> ·
    <a href="/plans/">Planlar</a>
    {' · <a href="/admin/">Admin</a>' if u["is_super_admin"] else ''}</p></div>""")

@app.post("/edit",response_class=HTMLResponse)
async def edit(request:Request,file:UploadFile=File(...)):
    u=require_user(request)
    if not u:return RedirectResponse("/auth/login",303)
    data=await file.read(); ext=Path(file.filename or "").suffix.lower()
    if ext not in {".udf",".pdf",".jpg",".jpeg",".png"}:
        return HTMLResponse("Desteklenen dosyalar: UDF, PDF, JPG, JPEG, PNG.",400)
    plan=get_plan(u["plan_id"]); max_mb=plan["limits"].get("file.max_mb")
    if max_mb and len(data)>max_mb*1024*1024:return HTMLResponse(f"Tek dosya sınırı {max_mb} MB.",413)
    try:
        text,kind=extract_any_source(file.filename or "",data)
        if kind=="ocr" and not feature_enabled(plan,"documents.ocr"):return HTMLResponse("Planınız OCR desteklemiyor.",403)
        if kind=="ocr" and not consume(u["id"],"ocr",plan["limits"].get("ocr.monthly")):return HTMLResponse("Aylık OCR limitiniz dolmuştur.",429)
        values,respondents=extract(text)
        # Profildeki arabulucu bilgileri yalnızca bilgi havuzunda boş kalan alanlara
        # başlangıç değeri olarak gelir; kaynak belgeden gelen gerçek dosya verileri ezilmez.
        values=apply_mediator_profile_defaults(u, values)
        cid=create_case(u["id"],values.get("dosyaNo"),values.get("basvuruNo"),values.get("basvurucuAdiSoyadi") or "Yeni Dosya",values.get("dosyaTuru"))
        save_document(u["id"],data,file.filename or "kaynak",kind,cid)
        html=render_editor(file.filename or "Kaynak Belge",values,respondents,custom_templates=list_visible_templates(u["id"]))
        html=html.replace('<form id="mainform" action="/build" method="post" enctype="multipart/form-data">',
                           f'<form id="mainform" action="/build" method="post" enctype="multipart/form-data"><input type="hidden" name="case_id" value="{cid}">',1)
        html=html.replace('name="merge_file" accept=".udf"','name="merge_file" accept=".udf,.pdf,.jpg,.jpeg,.png"')
        return HTMLResponse(html)
    except Exception as e:return HTMLResponse(f"Belge okunamadı: {e}",400)

@app.post("/case/schedule")
async def schedule_case(request:Request):
    """Bilgi Havuzu ekranındaki '📅 Takvime Ekle / Görevleri Oluştur' butonu.
    Ayrı bir 'yeni dosya' formu DEĞİL - bu ekrandaki mevcut case_id'yi kullanır,
    böylece aynı dosya için ikinci bir kayıt (mükerrer dosya) OLUŞMAZ."""
    u=require_user(request)
    if not u:return RedirectResponse("/auth/login",303)
    form=await request.form(); values,respondents,locked,locked_resp=form_state(form)
    cid=str(form.get("case_id") or "")
    if not cid:return HTMLResponse("Önce belge yükleyerek bir dosya oluşturun.",400)
    case=repos.cases.get(cid)
    if not case or case["owner_id"]!=u["id"]:return HTMLResponse("Dosya bulunamadı veya erişim yetkiniz yok.",403)
    dosya_no=values.get("dosyaNo") or case.get("file_no") or ""
    basvurucu=values.get("basvurucuAdiSoyadi") or case.get("title") or ""
    if str(basvurucu).strip() in {"Yeni Dosya", "Yeni dosya"}:
        basvurucu=""
    dosya_turu=values.get("dosyaTuru") or case.get("file_type") or ""
    baslangic_raw=values.get("baslangicTarihi") or case.get("start_date") or ""
    from app.modules.tasks.storage import _parse_start
    start=_parse_start(baslangic_raw)
    missing=[]
    if not basvurucu:missing.append("Başvurucu Adı Soyadı")
    if not dosya_turu:missing.append("Dosya Türü")
    if not start:missing.append("Süreç Başlangıç Tarihi (geçerli bir tarih olmalı)")
    if missing:
        html=render_editor("Bilgi Havuzu",values,respondents,locked,locked_resp,
            "Takvime eklemek için şu alanlar eksik/geçersiz: "+", ".join(missing)+". Doldurup tekrar deneyin.",
            custom_templates=list_visible_templates(u["id"]))
        html=html.replace('<form id="mainform" action="/build" method="post" enctype="multipart/form-data">',
                           f'<form id="mainform" action="/build" method="post" enctype="multipart/form-data"><input type="hidden" name="case_id" value="{cid}">',1)
        return HTMLResponse(html,400)
    from app.modules.calendar.service import CalendarService
    result=CalendarService().add_case(u["id"],dosya_no,basvurucu,dosya_turu,start,main_case_id=cid,case_data=values)
    task_result = {"created": int(result.get("tasks_created", 0)), "reason": result.get("tasks_result", "ok")}
    expected_tasks = 6
    if task_result["reason"] not in ("ok", "created") or task_result["created"] + int(result.get("tasks_existing", 0)) < expected_tasks:
        # İkinci güvenlik çağrısı: eski bir dosyada şablonlar yeni seed edilmiş olabilir.
        from app.modules.tasks.storage import create_standard_tasks
        task_result = create_standard_tasks(u["id"], cid)
    current_tasks = repos.tasks.list_for_case(cid)
    standard_count = sum(1 for t in current_tasks if t.get("is_standard"))
    if standard_count < expected_tasks:
        return HTMLResponse(
            "Takvim kayıtları oluşturuldu ancak standart 6 görevin tamamı oluşturulamadı. "
            f"Oluşan standart görev: {standard_count}/6. Görev şablonlarını ve dosya başlangıç tarihini kontrol edin.",
            500,
        )
    return RedirectResponse(f"/tasks?case_id={cid}",303)

@app.post("/merge",response_class=HTMLResponse)
async def merge(request:Request,merge_file:UploadFile=File(...)):
    u=require_user(request)
    if not u:return RedirectResponse("/auth/login",303)
    form=await request.form(); values,respondents,locked,locked_resp=form_state(form); data=await merge_file.read()
    try:
        text,kind=extract_any_source(merge_file.filename or "",data); nv,nr=extract(text); plan=get_plan(u["plan_id"])
        if kind=="ocr" and not feature_enabled(plan,"documents.ocr"):return HTMLResponse("Planınız OCR desteklemiyor.",403)
        if kind=="ocr" and not consume(u["id"],"ocr",plan["limits"].get("ocr.monthly")):return HTMLResponse("Aylık OCR limitiniz dolmuştur.",429)
        base_values=apply_mediator_profile_defaults(u, values)
        cid=str(form.get("case_id") or "")
        notice="Yeni belgeden bilgiler bilgi havuzuna eklendi. Kilitli alanlar korunmuştur."
        if cid:
            case=repos.cases.get(cid)
            if not case or case.get("owner_id")!=u["id"]:
                return HTMLResponse("Dosya bulunamadı veya erişim yetkiniz yok.",403)
            conflicts=detect_identity_conflicts(case,nv)
            if conflicts:
                # Kullanıcı karar verene kadar HİÇBİR veritabanı kaydı oluşturulmaz.
                # Belge geçici olarak storage'a kaydedilir, kararı /merge/resolve uygular.
                ext=Path(merge_file.filename or "ek").suffix.lower() or ".bin"
                pending_key=f"pending/{uuid4()}{ext}"
                storage.save(pending_key,data)
                create_pending(u["id"], cid, pending_key, merge_file.filename or "ek belge", kind, nv, nr, base_values, respondents, locked, locked_resp, conflicts)
                return HTMLResponse(render_conflict_page(
                    case,conflicts,nv,nr,base_values,respondents,locked,locked_resp,
                    pending_key,merge_file.filename or "ek belge",kind))
            values,respondents=merge_state(base_values,respondents,locked,locked_resp,nv,nr)
            save_document(u["id"],data,merge_file.filename or "ek belge",kind,cid)
            merged_case_data=merge_case_values(case,values,respondents)
            repos.cases.update(cid,{
                "file_no":merged_case_data.get("dosyaNo") or case.get("file_no"),
                "application_no":merged_case_data.get("basvuruNo") or case.get("application_no"),
                "title":merged_case_data.get("basvurucuAdiSoyadi") or case.get("title") or "Dosya",
                "file_type":merged_case_data.get("dosyaTuru") or case.get("file_type"),
                "start_date":merged_case_data.get("baslangicTarihi") or case.get("start_date"),
                "case_data_json":json.dumps(merged_case_data,ensure_ascii=False),
                "updated_at":now().isoformat()})
            values=merged_case_data.copy()
            from app.folders.service import update_case_folder_name, ensure_case_folders
            ensure_case_folders(u["id"],cid); update_case_folder_name(u["id"],cid)
        else:
            values,respondents=merge_state(base_values,respondents,locked,locked_resp,nv,nr)
        html=render_editor(merge_file.filename or "Birleştirilmiş Bilgi Havuzu",values,respondents,locked,locked_resp,
                           notice,custom_templates=list_visible_templates(u["id"]))
        html=html.replace('<form id="mainform" action="/build" method="post" enctype="multipart/form-data">',
                          f'<form id="mainform" action="/build" method="post" enctype="multipart/form-data"><input type="hidden" name="case_id" value="{cid}">',1)
        html=html.replace('name="merge_file" accept=".udf"','name="merge_file" accept=".udf,.pdf,.jpg,.jpeg,.png"')
        return HTMLResponse(html)
    except Exception as e:return HTMLResponse(f"Belge bilgi havuzuna eklenemedi: {e}",400)


def render_conflict_page(case,conflicts,nv,nr,base_values,base_respondents,locked,locked_resp,pending_key,filename,kind):
    from html import escape as esc
    rows=[]
    for c in conflicts:
        field=c["field"]; label=c["label"]; old=c["old"]; new=c["new"]
        rows.append(f'''<div class="card"><b>{esc(label)}</b>
        <label><input type="radio" name="choice_{field}" value="old" checked> Mevcut değeri koru: <b>{esc(old)}</b></label>
        <label><input type="radio" name="choice_{field}" value="new"> Yeni değeri kullan: <b>{esc(new)}</b></label>
        <label><input type="radio" name="choice_{field}" value="custom"> Özel değer gir: <input type="text" name="custom_{field}" placeholder="Yeni değer yazın"></label>
        </div>''')
    return f'''<!doctype html><html lang="tr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Çakışan Bilgiler</title>
<style>body{{font-family:Arial,sans-serif;background:#f3f6f9;margin:0;color:#20252b}}.wrap{{max-width:720px;margin:30px auto;padding:0 16px}}.card{{background:#fff;border-radius:14px;padding:18px;margin:12px 0;box-shadow:0 4px 16px #0001}}button{{border:0;border-radius:10px;padding:12px 18px;font-weight:700;cursor:pointer;margin:6px 8px 0 0;font-size:15px}}.primary{{background:#1769e0;color:#fff}}.secondary{{background:#b45309;color:#fff}}label{{display:block;margin:8px 0;font-weight:normal}}input[type=text]{{padding:6px;border:1px solid #ccd4dc;border-radius:6px;margin-left:6px}}.warn{{background:#fff7ed;border:1px solid #fdba74;border-radius:12px;padding:14px;margin:14px 0}}</style></head><body><div class="wrap">
<h1>⚠️ Çakışan Bilgiler Bulundu</h1>
<div class="warn">Yeni yüklediğiniz <b>{esc(filename)}</b> belgesi ile bu dosyanın (<b>{esc(case.get('file_no') or case.get('title') or '')}</b>) bilgileri arasında farklar var. Kararınız verilene kadar belge geçici olarak bekletilir.</div>
{''.join(rows)}
<form method="post" action="/merge/resolve">
<input type="hidden" name="pending_key" value="{esc(pending_key)}">
<button class="primary" type="submit" name="action" value="merge">✓ Seçtiklerimle Mevcut Dosyaya Ekle</button>
<button class="secondary" type="submit" name="action" value="separate">📁 Bunu Ayrı Yeni Dosya Yap</button>
</form></div></body></html>'''


@app.post("/merge/resolve",response_class=HTMLResponse)
async def merge_resolve(request:Request):
    u=require_user(request)
    if not u:return RedirectResponse("/auth/login",303)
    form=await request.form(); action=str(form.get("action") or "merge"); pending_key=str(form.get("pending_key") or "")
    row=get_pending_for_user(pending_key,u)
    if not row:return HTMLResponse("Bekleyen belge bulunamadı, süresi dolmuş veya erişim yetkiniz yok.",403)
    payload=serialize_row(row)
    nv,nr=payload["incoming"],payload["respondents"]
    base_values,base_respondents=payload["base_values"],payload["base_respondents"]
    locked,locked_resp=payload["locked"],payload["locked_resp"]
    filename=row.get("original_filename") or "ek belge"; kind=row.get("kind") or "source"; owner_id=row.get("owner_id"); cid=row.get("case_id") or ""
    try:data=storage.read(pending_key)
    except Exception:return HTMLResponse("Bekleyen belge okunamadı, lütfen tekrar yükleyin.",400)
    case=repos.cases.get(cid) if cid else None
    if action=="separate":
        new_case_id=create_case(owner_id,nv.get("dosyaNo") or None,nv.get("basvuruNo") or None,nv.get("basvurucuAdiSoyadi") or "Yeni Dosya",nv.get("dosyaTuru") or None,nv.get("baslangicTarihi") or None,json.dumps(merge_case_values({},nv,nr),ensure_ascii=False))
        save_document(owner_id,data,filename,kind,new_case_id)
        repos.pending_merges.update(row["id"],{"status":"resolved","resolved_at":now().isoformat(),"resolved_by":u["id"]})
        try:storage.delete(pending_key)
        except Exception:pass
        values,respondents,locked,locked_resp=nv,nr,set(),set(); cid=new_case_id; notice="Belge ayrı bir yeni dosya olarak kaydedildi."
    else:
        if not case:return HTMLResponse("Bağlı dosya bulunamadı.",404)
        current=case_values(case); resolved=dict(nv)
        for field in IDENTITY_FIELDS:
            choice=form.get(f"choice_{field}")
            if choice=="old": resolved[field]=current.get(field) or ""
            elif choice=="custom":
                custom_val=str(form.get(f"custom_{field}") or "").strip()
                if custom_val: resolved[field]=custom_val
        values,respondents=merge_state(base_values,base_respondents,locked,locked_resp,resolved,nr)
        merged_case_data=merge_case_values(case,values,respondents)
        save_document(owner_id,data,filename,kind,cid)
        repos.cases.update(cid,{"file_no":merged_case_data.get("dosyaNo") or case.get("file_no"),"application_no":merged_case_data.get("basvuruNo") or case.get("application_no"),"title":merged_case_data.get("basvurucuAdiSoyadi") or case.get("title") or "Dosya","file_type":merged_case_data.get("dosyaTuru") or case.get("file_type"),"start_date":merged_case_data.get("baslangicTarihi") or case.get("start_date"),"case_data_json":json.dumps(merged_case_data,ensure_ascii=False),"updated_at":now().isoformat()})
        from app.folders.service import update_case_folder_name, ensure_case_folders
        ensure_case_folders(owner_id,cid); update_case_folder_name(owner_id,cid)
        repos.pending_merges.update(row["id"],{"status":"resolved","resolved_at":now().isoformat(),"resolved_by":u["id"]})
        try:storage.delete(pending_key)
        except Exception:pass
        values=merged_case_data.copy(); notice="Seçtiğiniz bilgilerle mevcut dosya güncellendi."
    html=render_editor(filename,values,respondents,locked,locked_resp,notice,custom_templates=list_visible_templates(owner_id))
    html=html.replace('<form id="mainform" action="/build" method="post" enctype="multipart/form-data">',f'<form id="mainform" action="/build" method="post" enctype="multipart/form-data"><input type="hidden" name="case_id" value="{cid}">',1)
    html=html.replace('name="merge_file" accept=".udf"','name="merge_file" accept=".udf,.pdf,.jpg,.jpeg,.png"')
    return HTMLResponse(html)

def _safe_download_name(value, fallback="davet_mektubu"):
    name=re.sub(r'[^A-Za-z0-9ÇĞİÖŞÜçğıöşü _-]', '_', str(value or ''))
    name=re.sub(r'\s+', ' ', name).strip(' ._')
    return name or fallback

def _build_davet_outputs(data, values, respondents, u):
    """Başvurucu + her karşı taraf için ayrı davet UDF'si üretir."""
    xml, old, files = read_udf(data)
    applicant={
        'name': values.get('basvurucuAdiSoyadi',''), 'address': values.get('basvurucuAdres',''),
        'proxy': values.get('basvurucuVekili',''), 'phone': values.get('basvurucuTelefon',''),
        'email': values.get('basvurucuEposta',''), 'tc': values.get('basvurucuTcKimlik',''),
        'tax': values.get('basvurucuVergiNo',''),
    }
    recipients=[('Başvurucu', applicant)]
    for i, r in enumerate(respondents, 1):
        if str(r.get('name') or '').strip():
            recipients.append((f'Karşı Taraf {i}', dict(r)))
    outputs=[]
    for role, recipient in recipients:
        v=dict(values)
        v['_userIban']=u.get('iban') or ''
        v['_recipient']=recipient
        v['_davetRole']='basvurucu' if role=='Başvurucu' else 'karsi_taraf'
        new,edits=fill_custom_template_tracked(old,v,respondents)
        out_xml=update_offsets_exact(xml,edits,len(old),len(new))
        result=build_udf(files,out_xml,old,new)
        label=role
        filename=_safe_download_name(f"Davet Mektubu - {recipient.get('name') or role}")+".udf"
        outputs.append((label,filename,result))
    return outputs

@app.post("/build")
async def build(request:Request):
    u=require_user(request)
    if not u:return RedirectResponse("/auth/login",303)
    try:
        form=await request.form(); values,respondents,locked,locked_resp=form_state(form); choice=str(form.get("template_choice",""))
        plan=get_plan(u["plan_id"])
        if not feature_enabled(plan,"documents.udf"):return HTMLResponse("Planınız UDF oluşturmayı desteklemiyor.",403)
        if not consume(u["id"],"udf",plan["limits"].get("udf.monthly")):return HTMLResponse("Aylık UDF oluşturma limitiniz dolmuştur.",429)
        if not values.get("sonuc"):values["sonuc"]=standard_result(choice)
        is_bracket_template=False
        doc_kind=None
        if choice.startswith("folder__"):
            entry=discover_folder_templates().get(choice)
            if not entry:return HTMLResponse("Seçilen şablon sunucuda bulunamadı (klasörden kaldırılmış olabilir).",400)
            data=entry["path"].read_bytes();source_name=entry["path"].stem
            doc_kind=entry["doc_kind"];is_bracket_template=True
        elif choice.startswith("tpl_"):
            row=get_template(choice[len("tpl_"):])
            if not row or not can_use_template(row,u):return HTMLResponse("Bu şablona erişim yetkiniz yok.",403)
            data=get_template_bytes(row);source_name=re.sub(r'\.udf$','',row["name"],flags=re.I) or "son_tutanak"
            doc_kind=row.get("doc_kind") or "diger"
            is_bracket_template=True
        elif choice=="custom":
            upload=form.get("custom_file")
            if not isinstance(upload,UploadFile):return HTMLResponse("Özel UDF şablonu yükleyin.",400)
            data=await upload.read();source_name=Path(upload.filename or "son_tutanak").stem
        else:
            data=template_bytes(choice);source_name=Path(TEMPLATES[choice][1]).stem
            doc_kind=FIXED_TEMPLATE_DOC_KIND
        xml,old,files=read_udf(data)
        # Davet mektubu özel akışı: tek belge yerine başvurucu ve her karşı taraf için ayrı UDF.
        if doc_kind == "davet_mektubu":
            davet_outputs=_build_davet_outputs(data,values,respondents,u)
            cid=str(form.get("case_id") or "")
            if cid:
                case=repos.cases.get(cid)
                if case and case.get("owner_id")==u["id"]:
                    template_label="Davet Mektubu"
                    for role,filename,davet_result in davet_outputs:
                        save_generated(u["id"],cid,davet_result,f"{template_label} - {role}",doc_kind="davet_mektubu")
                    repos.cases.update(cid,{
                        "file_no":values.get("dosyaNo") or case.get("file_no"),
                        "application_no":values.get("basvuruNo") or case.get("application_no"),
                        "title":values.get("basvurucuAdiSoyadi") or case.get("title") or "Dosya",
                        "file_type":values.get("dosyaTuru") or case.get("file_type"),
                        "start_date":values.get("baslangicTarihi") or case.get("start_date"),
                        "case_data_json":json.dumps(values,ensure_ascii=False),
                        "updated_at":now().isoformat()})
                    from app.folders.service import update_case_folder_name, ensure_case_folders
                    ensure_case_folders(u["id"],cid); update_case_folder_name(u["id"],cid)
            # Çoklu UDF'leri tek indirmede koruyarak gönder.
            archive=io.BytesIO()
            with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as zf:
                used=set()
                for _role,filename,davet_result in davet_outputs:
                    base=filename; n=2
                    while filename in used:
                        filename=f"{Path(base).stem} ({n}).udf"; n+=1
                    used.add(filename)
                    zf.writestr(filename,davet_result)
            archive.seek(0)
            zip_name=_safe_download_name(f"Davet Mektupları - {values.get('basvurucuAdiSoyadi') or values.get('dosyaNo') or 'Dosya'}")+".zip"
            quoted=urllib.parse.quote(zip_name)
            ascii_fallback=re.sub(r'[^A-Za-z0-9_.-]','_',zip_name) or "davet_mektuplari.zip"
            return StreamingResponse(archive,media_type="application/zip",headers={"Content-Disposition":f"attachment; filename=\"{ascii_fallback}\"; filename*=UTF-8''{quoted}"})
        # "custom" (tek seferlik) yüklemede de köşeli parantez varsa yeni motoru kullan.
        if choice=="custom" and not is_bracket_template:
            recognized,_=scan_custom_template(old)
            if recognized:is_bracket_template=True
        if is_bracket_template:
            values["_userIban"]=u["iban"] or ""
            new,edits=fill_custom_template_tracked(old,values,respondents)
            xml=update_offsets_exact(xml,edits,len(old),len(new))
            result=build_udf(files,xml,old,new)
        else:
            applicant={"type":"kurum" if values.get("basvurucuVergiNo") else "kisi",
                       "tax":values.get("basvurucuVergiNo",""),"name":values.get("basvurucuAdiSoyadi",""),
                       "tc":values.get("basvurucuTcKimlik",""),"address":values.get("basvurucuAdres",""),
                       "proxy":values.get("basvurucuVekili",""),"phone":values.get("basvurucuTelefon",""),
                       "email":values.get("basvurucuEposta","")}
            arb={"name":values.get("arabulucuAdi",""),"sicil":values.get("arabulucuSicil","")}
            new=set_parties_and_signatures(old,applicant,respondents,arb)
            new=replace_meeting_paragraph(new,build_meeting_sentence(values,{**applicant,"_arb_name":arb["name"]},respondents))
            new=replace_final_legal_paragraph(new,values); new=fill_general(new,values)
            if values.get("talep"):new=replace_talep_in_narrative(new,values["talep"])
            xml=update_offsets(xml,old,new)
            xml=rebuild_region_paragraphs(xml,old,new,"KARŞI TARAF BİLGİLERİ","Arabuluculuk Konusu Uyuşmazlık")
            xml=rebuild_region_paragraphs(xml,old,new,"İMZALAR",None)
            result=build_udf(files,xml,old,new)
        cid=str(form.get("case_id") or "")
        if cid:
            template_label=TEMPLATES.get(choice,(None,))[0] or (discover_folder_templates().get(choice) or {}).get("label") or "Özel Son Tutanak"
            save_generated(u["id"],cid,result,template_label,doc_kind=doc_kind)
            case=repos.cases.get(cid)
            if case and case["owner_id"]==u["id"]:
                repos.cases.update(cid,{"file_no":values.get("dosyaNo") or case.get("file_no"),"application_no":values.get("basvuruNo") or case.get("application_no"),
                                        "title":values.get("basvurucuAdiSoyadi") or case.get("title") or "Dosya",
                                        "file_type":values.get("dosyaTuru") or case.get("file_type"),
                                        "start_date":values.get("baslangicTarihi") or case.get("start_date"),
                                        "case_data_json":json.dumps(values,ensure_ascii=False),
                                        "updated_at":now().isoformat()})
                from app.folders.service import update_case_folder_name, ensure_case_folders
                ensure_case_folders(u["id"], cid); update_case_folder_name(u["id"], cid)
        name=re.sub(r'[^A-Za-z0-9ÇĞİÖŞÜçğıöşü _-]','_',source_name)+"_hazir.udf"
        ascii_fallback=re.sub(r'[^A-Za-z0-9_.-]','_',name) or "son_tutanak_hazir.udf"
        quoted=urllib.parse.quote(name)
        return StreamingResponse(io.BytesIO(result),media_type="application/octet-stream",
                                 headers={"Content-Disposition":f"attachment; filename=\"{ascii_fallback}\"; filename*=UTF-8''{quoted}"})
    except Exception as e:return HTMLResponse(f"Belge oluşturulurken hata: {e}",500)
