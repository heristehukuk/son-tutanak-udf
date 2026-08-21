import json
from datetime import date
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from app.auth.service import get_user_by_session
from .storage import ensure_schema, seed_user_templates, get_case, update_case_info, create_standard_tasks, list_tasks, create_custom_task, update_task, templates, history, global_stats, update_template, set_case_status, document_checklist

router = APIRouter(prefix="/tasks", tags=["tasks"])


def esc(value):
    import html
    return html.escape(str(value or ''), quote=True)


def current_user(request):
    return get_user_by_session(request.cookies.get("session"))


def require_user(request):
    u=current_user(request)
    if not u or u["status"] in ("banned","rejected"):
        return None
    return u


def rowdict(row):
    return dict(row) if row else None


def task_json(row):
    d=rowdict(row)
    if not d:return None
    due=d.get("due_date","")
    today=date.today().isoformat()
    d["is_overdue"]=d.get("status") not in ("completed","cancelled") and due < today
    d["is_today"]=d.get("status") not in ("completed","cancelled") and due == today
    return d


def _safe_json(obj):
    """json.dumps + <script> içine güvenli gömme. json.dumps varsayılan olarak
    '/' karakterini kaçışlamaz; veri içinde '</script>' geçerse (örn. bir dosya
    başlığında) tarayıcı script etiketini erken kapatır ve geri kalanı HTML
    olarak yorumlar - bu XSS'e yol açar. '</' dizisini kaçışlayarak önlüyoruz."""
    return json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")


def page_html(user, case, tasks, stats, tmpls, checklist, notice=None):
    case_id=case["id"] if case else ""
    case_dict=rowdict(case) if case else {}
    case_json=_safe_json(case_dict)
    tasks_json=_safe_json([task_json(t) for t in tasks])
    templates_json=_safe_json([rowdict(t) for t in tmpls])
    stats_json=_safe_json(stats)
    checklist_json=_safe_json(checklist)
    return f'''<!doctype html><html lang="tr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Görevler</title><style>
*{{box-sizing:border-box}}body{{font-family:Arial,sans-serif;background:#f3f6f9;margin:0;color:#20252b}}.wrap{{max-width:1180px;margin:25px auto;padding:0 16px}}.top{{display:flex;justify-content:space-between;gap:15px;align-items:center;flex-wrap:wrap}}.card{{background:#fff;border-radius:16px;padding:20px;margin:15px 0;box-shadow:0 4px 20px #0001}}.grid{{display:grid;grid-template-columns:2fr 1fr;gap:18px}}.stats{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}}.stat{{padding:14px;border-radius:10px;background:#f8fafc;border:1px solid #e5e7eb}}.stat b{{display:block;font-size:24px;margin-top:4px}}.task{{border:1px solid #e1e6eb;border-radius:12px;padding:14px;margin:10px 0;background:#fff}}.task.overdue{{border-left:5px solid #dc2626}}.task.today{{border-left:5px solid #f59e0b}}.task.completed{{opacity:.65}}.row{{display:flex;gap:10px;align-items:center;justify-content:space-between;flex-wrap:wrap}}.title{{font-weight:700;font-size:16px}}.meta{{font-size:13px;color:#66717c;margin-top:6px}}.badge{{padding:4px 8px;border-radius:999px;font-size:12px;font-weight:700}}.high{{background:#fee2e2;color:#991b1b}}.normal{{background:#fef3c7;color:#92400e}}.low{{background:#dcfce7;color:#166534}}button{{background:#1769e0;color:#fff;border:0;border-radius:8px;padding:9px 13px;font-weight:700;cursor:pointer}}button.secondary{{background:#44515f}}button.green{{background:#15803d}}button.red{{background:#b91c1c}}input,textarea,select{{width:100%;padding:9px;border:1px solid #ccd4dc;border-radius:8px;font:inherit;margin-top:5px}}textarea{{min-height:70px}}label{{display:block;font-weight:700;margin-top:10px}}.actions{{display:flex;gap:7px;flex-wrap:wrap;margin-top:10px}}.notice{{padding:12px;border-radius:9px;background:#eff6ff;color:#1d4ed8;margin:10px 0}}.warning{{padding:12px;border-radius:9px;background:#fff7ed;color:#9a3412;margin:10px 0}}.error{{padding:12px;border-radius:9px;background:#fee2e2;color:#991b1b;margin:10px 0}}.success{{padding:12px;border-radius:9px;background:#dcfce7;color:#166534;margin:10px 0}}.modal{{position:fixed;inset:0;background:#0008;display:none;align-items:center;justify-content:center;padding:20px;z-index:5}}.modal.show{{display:flex}}.modal-box{{background:#fff;border-radius:14px;padding:22px;max-width:560px;width:100%;max-height:90vh;overflow:auto}}a{{color:#1769e0;text-decoration:none}}@media(max-width:850px){{.grid{{grid-template-columns:1fr}}.stats{{grid-template-columns:repeat(2,1fr)}}}}
</style></head><body><div class="wrap">
<div class="top"><div><h1>📋 Görevler ve Hatırlatıcılar</h1><div class="meta">Dosya: <b>{case_dict.get('file_no','')}</b></div></div><a href="/">← Ana Sayfa</a></div>
<div id="message"></div>{f"<div class=\"warning\">⚠️ {esc(notice)}</div>" if notice else ""}<div class="card"><div class="stats"><div class="stat">🔴 Geciken<b id="sOverdue">0</b></div><div class="stat">🟠 Bugün<b id="sToday">0</b></div><div class="stat">🟡 Yaklaşan<b id="sUpcoming">0</b></div><div class="stat">🟢 Tamamlanan<b id="sCompleted">0</b></div></div></div>
<div class="grid"><div class="card"><div class="row"><h2>Dosya Görevleri</h2><button onclick="openCreate()">+ Yeni Görev</button></div><div class="notice">6 standart görev dosyanın 3 haftalık normal iş akışına göre otomatik oluşturulur. Tarihleri istediğiniz zaman değiştirebilirsiniz.</div><div id="tasks"></div></div>
<div><div class="card"><h2>Dosya Bilgileri</h2><div id="caseInfo"></div><div class="card"><h2>📄 Belge Kontrolü</h2><div id="checklist"></div><p class="meta">Bir belge henüz uygulamaya eklenmemişse kutu boş kalır.</p></div><div class="actions"><button class="green" onclick="completeCase()">✓ Dosyayı Tamamlandı Olarak İşaretle</button><button class="secondary" onclick="reopenCase()">↩ Dosyayı Yeniden Aç</button></div></div><div class="card"><h2>⚙️ Görev Varsayılanları</h2><p class="meta">Standart görevlerin varsayılan günlerini 0–21 arasında değiştirebilirsiniz. Bu ayarlar sonraki dosyalara uygulanır; mevcut görevlerin tarihini otomatik değiştirmez.</p><div id="templates"></div></div></div></div></div>
<div class="modal" id="modal"><div class="modal-box"><div class="row"><h2 id="modalTitle">Yeni Görev</h2><button class="secondary" onclick="closeModal()">✕</button></div><input type="hidden" id="taskId"><label>Görev</label><input id="taskTitle"><label>Son tarih</label><input id="taskDate" type="date"><label>Öncelik</label><select id="taskPriority"><option value="high">Yüksek</option><option value="normal" selected>Normal</option><option value="low">Düşük</option></select><label>Not</label><textarea id="taskDescription"></textarea><div id="dateWarning"></div><div class="actions"><button onclick="saveTask()">Kaydet</button><button class="secondary" onclick="closeModal()">Vazgeç</button></div></div></div>
<script>
const CASE={case_json};let TASKS={tasks_json};let TMPLS={templates_json};let STATS={stats_json};let CHECKLIST={checklist_json};
function esc(v){{return String(v??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#039;')}}
function msg(t,type='success'){{const x=document.getElementById('message');x.className=type;x.textContent=t;setTimeout(()=>{{x.textContent='';x.className=''}},5000)}}
function render(){{
 const root=document.getElementById('tasks');
 if(!TASKS.length){{root.innerHTML='<p class="meta">Bu dosya için henüz görev bulunmuyor.</p>';return}}
 root.innerHTML=TASKS.map(t=>{{const cls=t.is_overdue?'overdue':(t.is_today?'today':'')+(t.status==='completed'?' completed':'');const p=t.priority||'normal';const status={{pending:'Bekliyor',in_progress:'Devam ediyor',completed:'Tamamlandı',cancelled:'İptal edildi'}}[t.status]||t.status;return `<div class="task ${{cls}}"><div class="row"><div><div class="title">${{t.is_standard?'':'✳️ '}}${{esc(t.title)}}</div><div class="meta">📅 ${{esc(t.due_date)}} · ${{esc(status)}}</div></div><span class="badge ${{p}}">${{p==='high'?'🔴 Yüksek':p==='low'?'🟢 Düşük':'🟡 Normal'}}</span></div>${{t.description?`<div class="meta">📝 ${{esc(t.description)}}</div>`:''}}<div class="actions">${{t.status!=='completed'&&t.status!=='cancelled'?`<button class="green" onclick="setStatus('${{t.id}}','completed')">✓ Tamamlandı</button>`:''}}${{t.status==='pending'?`<button class="secondary" onclick="setStatus('${{t.id}}','in_progress')">▶ Başlat</button>`:''}}${{t.status==='completed'?`<button class="secondary" onclick="setStatus('${{t.id}}','pending')">↩ Yeniden Aç</button>`:''}}${{t.status!=='cancelled'?`<button onclick="editTask('${{t.id}}')">✎ Düzenle</button>`:''}}${{t.status!=='cancelled'&&t.status!=='completed'?`<button class="red" onclick="setStatus('${{t.id}}','cancelled')">İptal</button>`:''}}<button class="secondary" onclick="showHistory('${{t.id}}')">Geçmiş</button></div></div>`}}).join('')
}}
function renderStats(){{document.getElementById('sOverdue').textContent=STATS.overdue;document.getElementById('sToday').textContent=STATS.today;document.getElementById('sUpcoming').textContent=STATS.upcoming;document.getElementById('sCompleted').textContent=STATS.completed}}
function renderCase(){{document.getElementById('caseInfo').innerHTML=`<p><b>Dosya No</b><br>${{esc(CASE.file_no||'-')}}</p><p><b>Başvurucu</b><br>${{esc(CASE.title||'-')}}</p><p><b>Dosya Türü</b><br>${{esc(CASE.file_type||'-')}}</p><p><b>Süreç Başlangıcı</b><br>${{esc(CASE.start_date||'-')}}</p><p><b>Dosya Durumu</b><br>${{CASE.status==='completed'?'🟢 Tamamlandı':'🟡 Açık'}}</p>`}}
function renderChecklist(){{document.getElementById("checklist").innerHTML=CHECKLIST.map(x=>`<div class="task"><label style="display:flex;gap:10px;align-items:center"><input type="checkbox" disabled ${{x.created?"checked":""}}> <span><b>${{esc(x.title)}}</b><br><span class="meta">${{x.created?"✓ Oluşturulmuş belge bulundu":"Henüz oluşturulmuş belge bulunmuyor"}}</span></span></label></div>`).join("")}}
function renderTemplates(){{document.getElementById('templates').innerHTML=TMPLS.map(t=>`<div class="task"><b>${{esc(t.title)}}</b><div class="meta">Varsayılan gün: <input style="width:80px;display:inline-block" type="number" min="0" max="21" id="off_${{t.id}}" value="${{t.offset_days}}"> Öncelik: <select style="width:120px;display:inline-block" id="pri_${{t.id}}"><option value="high" ${{t.priority==='high'?'selected':''}}>Yüksek</option><option value="normal" ${{t.priority==='normal'?'selected':''}}>Normal</option><option value="low" ${{t.priority==='low'?'selected':''}}>Düşük</option></select></div><button style="margin-top:8px" onclick="saveTemplate('${{t.id}}')">Kaydet</button></div>`).join('')}}
function openCreate(){{document.getElementById('modalTitle').textContent='Yeni Özel Görev';document.getElementById('taskId').value='';document.getElementById('taskTitle').value='';document.getElementById('taskDate').value=CASE.start_date||new Date().toISOString().slice(0,10);document.getElementById('taskPriority').value='normal';document.getElementById('taskDescription').value='';document.getElementById('dateWarning').innerHTML='';document.getElementById('modal').classList.add('show')}}
function editTask(id){{const t=TASKS.find(x=>x.id===id);if(!t)return;document.getElementById('modalTitle').textContent='Görevi Düzenle';document.getElementById('taskId').value=t.id;document.getElementById('taskTitle').value=t.title;document.getElementById('taskDate').value=t.due_date;document.getElementById('taskPriority').value=t.priority;document.getElementById('taskDescription').value=t.description||'';checkDate();document.getElementById('modal').classList.add('show')}}
function closeModal(){{document.getElementById('modal').classList.remove('show')}}
function checkDate(){{const d=document.getElementById('taskDate').value;if(CASE.start_date&&d){{const a=new Date(CASE.start_date+'T00:00:00'),b=new Date(d+'T00:00:00'),days=Math.round((b-a)/86400000);document.getElementById('dateWarning').innerHTML=days>21?'<div class="warning">⚠️ Bu görev 3 haftalık normal iş akışının dışına taşınıyor. Yine de kaydedebilirsiniz.</div>':''}}}}
document.getElementById('taskDate').addEventListener('change',checkDate);
async function saveTask(){{const id=document.getElementById('taskId').value;const payload={{case_id:CASE.id,title:document.getElementById('taskTitle').value,due_date:document.getElementById('taskDate').value,priority:document.getElementById('taskPriority').value,description:document.getElementById('taskDescription').value}};const url=id?'/tasks/api/'+id:'/tasks/api';const r=await fetch(url,{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(payload)}});const d=await r.json();if(!r.ok){{msg(d.detail||'İşlem başarısız.','error');return}}TASKS=d.tasks;STATS=d.stats;render();renderStats();closeModal();msg(id?'Görev güncellendi.':'Özel görev oluşturuldu.')}}
async function setStatus(id,status){{const r=await fetch('/tasks/api/'+id,{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{status}})}});const d=await r.json();if(!r.ok){{msg(d.detail||'İşlem başarısız.','error');return}}TASKS=d.tasks;STATS=d.stats;render();renderStats();msg('Görev durumu güncellendi.')}}
async function showHistory(id){{const r=await fetch('/tasks/api/'+id+'/history');const d=await r.json();if(!r.ok){{msg(d.detail||'Geçmiş alınamadı.','error');return}}alert(d.history.map(x=>x.created_at+' — '+x.action).join('\\n')||'Geçmiş kaydı yok.')}}
async function completeCase(){{if(!confirm('Dosyayı tamamlandı olarak işaretlemek istediğinizden emin misiniz?'))return;const r=await fetch('/tasks/case-status', {{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{case_id:CASE.id,status:'completed'}})}});const d=await r.json();if(!r.ok){{msg(d.detail||'Dosya kapatılamadı.','error');return}}CASE.status='completed';renderCase();msg('Dosya tamamlandı olarak işaretlendi.')}}
async function reopenCase(){{const r=await fetch('/tasks/case-status', {{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{case_id:CASE.id,status:'open'}})}});const d=await r.json();if(!r.ok){{msg(d.detail||'Dosya yeniden açılamadı.','error');return}}CASE.status='open';renderCase();msg('Dosya yeniden açıldı.')}}

async function saveTemplate(id){{const payload={{title:TMPLS.find(x=>x.id===id).title,offset_days:document.getElementById('off_'+id).value,priority:document.getElementById('pri_'+id).value}};const r=await fetch('/tasks/templates/'+id,{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(payload)}});const d=await r.json();if(!r.ok){{msg(d.detail||'Şablon kaydedilemedi.','error');return}}msg('Varsayılan görev ayarı kaydedildi.')}}
render();renderStats();renderCase();renderChecklist();renderTemplates();
</script></body></html>'''
    return HTMLResponse(page_html.replace("{case_json}",case_json).replace("{tasks_json}",tasks_json).replace("{templates_json}",templates_json).replace("{stats_json}",stats_json).replace("{checklist_json}",checklist_json))


@router.get("", response_class=HTMLResponse)
async def tasks_page(request: Request, case_id: str = "", case_no: str = "", applicant_name: str = "", file_type: str = "", start_date: str = ""):
    ensure_schema()
    u=require_user(request)
    if not u:return RedirectResponse("/auth/login",303)
    if not case_id:
        return HTMLResponse("Görev modülü için bir dosya seçilmelidir.",400)
    case=get_case(u["id"],case_id)
    if not case:return HTMLResponse("Dosya bulunamadı veya erişim yetkiniz yok.",404)
    if any([case_no,applicant_name,file_type,start_date]):
        update_case_info(u["id"],case_id,case_no or None,applicant_name or None,file_type or None,start_date or None)
        case=get_case(u["id"],case_id)
    task_result=create_standard_tasks(u["id"],case_id)
    notice=None
    if task_result.get("reason") == "applicant_missing":
        notice="Takvim ve görevleri oluşturmak için Başvurucu Adı Soyadı bilgisini tamamlayın."
    elif task_result.get("reason") == "start_date_missing":
        notice="Görevleri oluşturmak için Süreç Başlangıç Tarihi bulunamadı. Bilgi Havuzundaki tarihi tamamlayın."
    elif task_result.get("reason") not in ("ok", "created") and task_result.get("created", 0) == 0:
        notice=f"Standart görevler oluşturulamadı: {task_result.get('reason', 'bilinmeyen hata')}"
    elif task_result.get("reason") == "case_deleted":
        return HTMLResponse("Bu dosya silinmiş durumda; görevleri görüntüleyemezsiniz.",410)
    return page_html(u,case,list_tasks(u["id"],case_id),global_stats(u["id"]),templates(u["id"]),document_checklist(u["id"],case_id),notice)


@router.get("/api")
async def tasks_api(request: Request, case_id: str):
    ensure_schema(); u=require_user(request)
    if not u:return JSONResponse({"detail":"Giriş gerekli."},401)
    case=get_case(u["id"],case_id)
    if not case:return JSONResponse({"detail":"Dosya bulunamadı."},404)
    create_standard_tasks(u["id"],case_id)
    return {"case":rowdict(case),"tasks":[task_json(x) for x in list_tasks(u["id"],case_id)],"stats":global_stats(u["id"]),"checklist":document_checklist(u["id"],case_id)}


@router.post("/api")
async def create_task(request: Request):
    ensure_schema(); u=require_user(request)
    if not u:return JSONResponse({"detail":"Giriş gerekli."},401)
    data=await request.json()
    try:
        t=create_custom_task(u["id"],str(data.get("case_id","")),str(data.get("title","")),str(data.get("due_date","")),str(data.get("priority","normal")),str(data.get("description","")))
        cid=t["case_id"]
        return {"task":task_json(t),"tasks":[task_json(x) for x in list_tasks(u["id"],cid)],"stats":global_stats(u["id"])}
    except Exception as e:return JSONResponse({"detail":str(e)},400)


@router.post("/api/{task_id}")
async def update_task_api(request: Request, task_id: str):
    ensure_schema(); u=require_user(request)
    if not u:return JSONResponse({"detail":"Giriş gerekli."},401)
    data=await request.json()
    try:
        t=update_task(u["id"],task_id,**data)
        return {"task":task_json(t),"tasks":[task_json(x) for x in list_tasks(u["id"],t["case_id"])],"stats":global_stats(u["id"])}
    except Exception as e:return JSONResponse({"detail":str(e)},400)


@router.get("/api/{task_id}/history")
async def task_history(request: Request, task_id: str):
    ensure_schema(); u=require_user(request)
    if not u:return JSONResponse({"detail":"Giriş gerekli."},401)
    return {"history":[rowdict(x) for x in history(u["id"],task_id)]}


@router.post("/case-status")
async def case_status_api(request: Request):
    ensure_schema(); u=require_user(request)
    if not u:return JSONResponse({"detail":"Giriş gerekli."},401)
    data=await request.json()
    try:
        case=set_case_status(u["id"],str(data.get("case_id","")),str(data.get("status","open")))
        return {"ok":True,"case":rowdict(case)}
    except Exception as e:return JSONResponse({"detail":str(e)},400)


@router.post("/templates/{template_id}")
async def update_template_api(request: Request, template_id: str):
    ensure_schema(); u=require_user(request)
    if not u:return JSONResponse({"detail":"Giriş gerekli."},401)
    data=await request.json()
    try:
        update_template(u["id"],template_id,str(data.get("title","")),data.get("offset_days",0),str(data.get("priority","normal")))
        return {"ok":True}
    except Exception as e:return JSONResponse({"detail":str(e)},400)
