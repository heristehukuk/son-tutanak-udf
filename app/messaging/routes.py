
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from app.auth.service import get_user_by_session, now
from app.auth.permissions import has_permission
from app.database_layer import repos
from app.web import page
router=APIRouter()


def escape(v):
    return (str(v or "")
            .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;"))


def can_manage_messages(u):
    return bool(u and (u.get("is_super_admin") or has_permission(u["id"], "messages.view")))


def default_admin_recipient(exclude_id=None):
    """Normal kullanıcının mesaj göndereceği varsayılan hedef: ilk süper admin
    (veya messages.view yetkisi verilmiş biri)."""
    for candidate in repos.users.list_all():
        if candidate.get("is_super_admin") and candidate["id"] != exclude_id:
            return candidate
    return None


EXPLANATION_TEMPLATES={
    "pending":"Üyeliğinizin onaylanabilmesi için lütfen kısa bir açıklama gönderin (kim olduğunuz, hangi amaçla kullanacağınız).",
    "suspicious":"Hesabınız incelemeye alınmıştır. Lütfen hesap kullanımınızla ilgili açıklama gönderin; açıklamanız değerlendirildikten sonra hesabınız normale döndürülecektir.",
}


def _thread_html(rows, viewer_id):
    body=[]
    for m in rows:
        mine = m["sender_id"] == viewer_id
        cls = "mine" if mine else "theirs"
        who = "Siz" if mine else escape(m.get("display_name") or "Karşı taraf")
        case_tag = f'<a class="case-tag" href="/files/">📁 Dosyaya Git</a>' if m.get("case_id") else ""
        body.append(f'<div class="msg {cls}"><b>{who}</b><span class="time">{escape(m.get("created_at",""))[:16]}</span>'
                    f'<p>{escape(m["body"])}</p>{case_tag}</div>')
    return "".join(body)


STYLE='''<style>
.msg{padding:10px 14px;border-radius:12px;margin:8px 0;max-width:80%;background:#f1f4f7}
.msg.mine{margin-left:auto;background:#dbe8ff}
.msg .time{float:right;font-size:11px;color:#8a95a1}
.msg .case-tag{display:block;font-size:12px;margin-top:6px}
.conv{display:block;padding:12px;border-radius:10px;background:#fff;margin:8px 0;box-shadow:0 2px 10px #0001;text-decoration:none;color:inherit}
.conv .unread{background:#dc2626;color:#fff;border-radius:999px;padding:1px 8px;font-size:12px;margin-left:6px}
.explain-btn{background:#9a3412;margin-left:6px}
</style>'''


@router.get("/",response_class=HTMLResponse)
async def inbox(request:Request,case_id:str=""):
    u=get_user_by_session(request.cookies.get("session"))
    if not u:return HTMLResponse("Giriş yapmalısınız.",401)

    if case_id:
        case=repos.cases.get(case_id)
        if not case or (case["owner_id"]!=u["id"] and not can_manage_messages(u)):
            return HTMLResponse("Bu dosyaya erişim yetkiniz yok.",403)
        rows=repos.messages.list_for_case(case_id)
        html=STYLE+f'<h1>Dosya Mesajları</h1><p class="hint"><a href="/files/">← Dosyalarım</a></p><div class="thread">{_thread_html(rows,u["id"])}</div>'
        recipient = case["owner_id"] if can_manage_messages(u) else (default_admin_recipient(u["id"]) or {}).get("id","")
        html+=f'''<form method="post" action="/messages/"><input type="hidden" name="case_id" value="{escape(case_id)}">
        <input type="hidden" name="recipient_id" value="{escape(recipient)}">
        <textarea name="body" placeholder="Mesajınız..." required></textarea><button>Gönder</button></form>'''
        return page("Dosya Mesajları",html)

    if can_manage_messages(u):
        # Admin görünümü: her kullanıcıyla olan konuşma listesi, okunmamış sayacıyla.
        users_by_id={x["id"]:x for x in repos.users.list_all()}
        rows=repos.messages.list_for_user(u["id"])
        threads={}
        for m in rows:
            other = m["recipient_id"] if m["sender_id"]==u["id"] else m["sender_id"]
            if other==u["id"]:continue
            t=threads.setdefault(other,{"last":m,"unread":0})
            if m["created_at"]>t["last"]["created_at"]:t["last"]=m
            if m["recipient_id"]==u["id"] and not m.get("read_at"):t["unread"]+=1
        items=[]
        for other_id,info in sorted(threads.items(),key=lambda kv:kv[1]["last"]["created_at"],reverse=True):
            ou=users_by_id.get(other_id,{})
            badge=f'<span class="unread">{info["unread"]}</span>' if info["unread"] else ""
            status_tag=f' <span class="hint">({ou.get("status")})</span>' if ou.get("status") in ("pending","suspicious") else ""
            items.append(f'<a class="conv" href="/messages/thread/{other_id}"><b>{escape(ou.get("display_name") or ou.get("email") or other_id)}</b>{status_tag}{badge}'
                        f'<p class="hint">{escape(info["last"]["body"])[:120]}</p></a>')
        # Henüz hiç yazışma olmayan ama onay/inceleme bekleyen kullanıcılar da listelensin.
        pending_or_suspicious=[x for x in users_by_id.values() if x.get("status") in ("pending","suspicious") and x["id"] not in threads]
        for pu in pending_or_suspicious:
            items.append(f'<a class="conv" href="/messages/thread/{pu["id"]}"><b>{escape(pu.get("display_name"))}</b> <span class="hint">({pu.get("status")})</span>'
                        f'<p class="hint">Henüz yazışma yok - açıklama isteyebilirsiniz.</p></a>')
        return page("Mesajlar",STYLE+"<h1>Mesajlar</h1><p class=\"hint\"><a href=\"/admin/\">← Admin Paneli</a></p>"+("".join(items) or "<p>Henüz mesaj yok.</p>"))

    # Normal kullanıcı görünümü: admin ile tek thread.
    admin=default_admin_recipient(u["id"])
    rows=repos.messages.list_for_user(u["id"])
    rows=[m for m in rows if not m.get("case_id")]
    if admin:repos.messages.mark_thread_read(u["id"],admin["id"])
    html=STYLE+"<h1>Mesajlar</h1>"+f'<div class="thread">{_thread_html(rows,u["id"])}</div>'
    if admin:
        html+=f'''<form method="post" action="/messages/"><input type="hidden" name="recipient_id" value="{admin["id"]}">
        <textarea name="body" placeholder="Yöneticiye mesaj yazın..." required></textarea><button>Gönder</button></form>'''
    else:
        html+='<p class="hint">Şu an mesaj gönderebileceğiniz bir yönetici bulunmuyor.</p>'
    return page("Mesajlar",html)


@router.get("/thread/{other_id}",response_class=HTMLResponse)
async def thread(request:Request,other_id:str):
    u=get_user_by_session(request.cookies.get("session"))
    if not u or not can_manage_messages(u):return HTMLResponse("Bu sayfaya erişim yetkiniz yok.",403)
    other=repos.users.get(other_id)
    if not other:return HTMLResponse("Kullanıcı bulunamadı.",404)
    repos.messages.mark_thread_read(u["id"],other_id)
    rows=repos.messages.list_thread(u["id"],other_id)
    html=STYLE+f'<h1>{escape(other.get("display_name"))}</h1><p class="hint"><a href="/messages/">← Mesajlar</a> · Durum: {escape(other.get("status"))}</p>'
    html+=f'<div class="thread">{_thread_html(rows,u["id"])}</div>'
    explain=EXPLANATION_TEMPLATES.get(other.get("status"))
    explain_btn=""
    if explain:
        explain_btn=f'''<form method="post" action="/messages/" style="display:inline">
        <input type="hidden" name="recipient_id" value="{other_id}"><input type="hidden" name="body" value="{escape(explain)}">
        <button class="explain-btn" type="submit">📩 Açıklama İste</button></form>'''
    html+=f'''<form method="post" action="/messages/"><input type="hidden" name="recipient_id" value="{other_id}">
    <textarea name="body" placeholder="Mesajınız..." required></textarea><button>Gönder</button>{explain_btn}</form>'''
    return page(f"Mesajlar - {other.get('display_name')}",html)


@router.post("/")
async def send(request:Request,recipient_id:str=Form(...),body:str=Form(...),case_id:str=Form("")):
    u=get_user_by_session(request.cookies.get("session"))
    if not u:return HTMLResponse("Giriş yapmalısınız.",401)
    if not recipient_id or not body.strip():return HTMLResponse("Alıcı ve mesaj metni zorunludur.",400)
    if case_id:
        case=repos.cases.get(case_id)
        if not case or (case["owner_id"]!=u["id"] and not can_manage_messages(u)):
            return HTMLResponse("Bu dosyaya erişim yetkiniz yok.",403)
    repos.messages.create({"sender_id":u["id"],"recipient_id":recipient_id,"case_id":case_id or None,
                           "body":body.strip(),"created_at":now().isoformat()})
    dest = f"/messages/thread/{recipient_id}" if can_manage_messages(u) else ("/messages/?case_id="+case_id if case_id else "/messages/")
    return HTMLResponse(f'<meta http-equiv="refresh" content="0;url={dest}">')
