import os

import io, os, re, json, urllib.parse
import pytesseract
from pathlib import Path
from fastapi import FastAPI, Request, UploadFile, File
from fastapi.responses import HTMLResponse, StreamingResponse, RedirectResponse
from app.database import init_db, connect
from app.database_layer import repos
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
from app.plans.service import seed_plans, get_plan, feature_enabled, consume
from app.files.service import save_document, create_case, save_generated
from app.customtemplates.service import list_visible_templates, get_template, can_use_template, get_template_bytes
from app.documents.engine import (
    read_udf, extract, render_editor, form_state, merge_state, template_bytes, TEMPLATES,
    extract_any_source, standard_result, set_parties_and_signatures, replace_meeting_paragraph,
    build_meeting_sentence, replace_final_legal_paragraph, fill_general, replace_talep_in_narrative,
    update_offsets, rebuild_region_paragraphs, build_udf, scan_custom_template, fill_custom_template,
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
    return RedirectResponse(f"/tasks/?case_id={cid}",303)

@app.post("/merge",response_class=HTMLResponse)
async def merge(request:Request,merge_file:UploadFile=File(...)):
    u=require_user(request)
    if not u:return RedirectResponse("/auth/login",303)
    form=await request.form(); values,respondents,locked,locked_resp=form_state(form); data=await merge_file.read()
    try:
        text,kind=extract_any_source(merge_file.filename or "",data); nv,nr=extract(text); plan=get_plan(u["plan_id"])
        if kind=="ocr" and not feature_enabled(plan,"documents.ocr"):return HTMLResponse("Planınız OCR desteklemiyor.",403)
        if kind=="ocr" and not consume(u["id"],"ocr",plan["limits"].get("ocr.monthly")):return HTMLResponse("Aylık OCR limitiniz dolmuştur.",429)
        values,respondents=merge_state(values,respondents,locked,locked_resp,nv,nr)
        cid=str(form.get("case_id") or "")
        if cid:
            save_document(u["id"],data,merge_file.filename or "ek belge",kind,cid)
            case=repos.cases.get(cid)
            if case and case.get("owner_id")==u["id"]:
                repos.cases.update(cid,{"file_no":values.get("dosyaNo") or case.get("file_no"),"application_no":values.get("basvuruNo") or case.get("application_no"),
                    "title":values.get("basvurucuAdiSoyadi") or case.get("title") or "Dosya",
                    "file_type":values.get("dosyaTuru") or case.get("file_type"),
                    "start_date":values.get("baslangicTarihi") or case.get("start_date"),
                    "case_data_json":json.dumps(values,ensure_ascii=False),"updated_at":now().isoformat()})
                from app.folders.service import update_case_folder_name, ensure_case_folders
                ensure_case_folders(u["id"], cid); update_case_folder_name(u["id"], cid)
        html=render_editor(merge_file.filename or "Birleştirilmiş Bilgi Havuzu",values,respondents,locked,locked_resp,
                           "Yeni belgeden bilgiler bilgi havuzuna eklendi. Kilitli alanlar korunmuştur.",
                           custom_templates=list_visible_templates(u["id"]))
        if cid:html=html.replace('<form id="mainform" action="/build" method="post" enctype="multipart/form-data">',
                                  f'<form id="mainform" action="/build" method="post" enctype="multipart/form-data"><input type="hidden" name="case_id" value="{cid}">',1)
        html=html.replace('name="merge_file" accept=".udf"','name="merge_file" accept=".udf,.pdf,.jpg,.jpeg,.png"')
        return HTMLResponse(html)
    except Exception as e:return HTMLResponse(f"Belge bilgi havuzuna eklenemedi: {e}",400)

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
            is_bracket_template=True
        elif choice=="custom":
            upload=form.get("custom_file")
            if not isinstance(upload,UploadFile):return HTMLResponse("Özel UDF şablonu yükleyin.",400)
            data=await upload.read();source_name=Path(upload.filename or "son_tutanak").stem
        else:
            data=template_bytes(choice);source_name=Path(TEMPLATES[choice][1]).stem
            doc_kind=FIXED_TEMPLATE_DOC_KIND
        xml,old,files=read_udf(data)
        # "custom" (tek seferlik) yüklemede de köşeli parantez varsa yeni motoru kullan.
        if choice=="custom" and not is_bracket_template:
            recognized,_=scan_custom_template(old)
            if recognized:is_bracket_template=True
        if is_bracket_template:
            # Kendi şablonu / köşeli parantez sistemi: sabit etiket motoru yerine [alan] değişimi kullanılır.
            # [iban] belgeyi oluşturan kullanıcının kendi profilinden (Profilim ekranı) otomatik gelir.
            values["_userIban"]=u["iban"] or ""
            new=fill_custom_template(old,values,respondents)
            xml=update_offsets(xml,old,new)
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
