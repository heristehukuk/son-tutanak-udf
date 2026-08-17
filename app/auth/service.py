
from datetime import datetime, timedelta, timezone
from uuid import uuid4
import secrets
from app.database_layer import repos
from app.auth.security import hash_password, verify_password

def now():
    return datetime.now(timezone.utc)

PENDING_EXPIRY_HOURS = 48

def cleanup_expired_pending():
    """48 saatten uzun süredir 'pending' (onay bekleyen) kalan üyelikleri
    otomatik olarak 'rejected' durumuna alır. Gerçek bir zamanlayıcı
    (background scheduler) yerine "lazy check" kullanılıyor - yani bu
    fonksiyon bir sayfa yüklendiğinde çağrılır (bkz. app/main.py home(),
    app/admin/routes.py dashboard()). Render gibi platformlarda sürekli
    çalışan bir arka plan görevi garanti olmadığından bu daha güvenilir."""
    cutoff = (now() - timedelta(hours=PENDING_EXPIRY_HOURS)).isoformat()
    expired = []
    for u in repos.users.list_all():
        if u.get("status") == "pending" and (u.get("created_at") or "") < cutoff:
            repos.users.update(u["id"], {"status": "rejected"})
            repos.audit.create({
                "actor_id": None, "action": "auto_reject_expired_pending",
                "target_id": u["id"], "details": "48 saat içinde onaylanmadığı için otomatik reddedildi.",
                "created_at": now().isoformat(),
            })
            expired.append(u["id"])
    return expired

def create_user(email, display_name, password, ip=""):
    user_id = str(uuid4())
    pw = hash_password(password)
    repos.users.create({
        "id": user_id, "email": email.strip().lower(), "display_name": display_name.strip(),
        "password_hash": pw, "status": "pending", "plan_id": "free",
        "created_at": now().isoformat(), "last_ip": ip,
    })
    return user_id

def authenticate(email, password):
    u = repos.users.get_by_email(email.strip().lower())
    if not u or not verify_password(password, u["password_hash"]):
        return None
    return u

def create_session(user_id, ip=""):
    token = secrets.token_urlsafe(48)
    expires = now() + timedelta(days=7)
    repos.sessions.create({
        "token": token, "user_id": user_id, "created_at": now().isoformat(),
        "expires_at": expires.isoformat(), "ip": ip,
    })
    return token

def get_user_by_session(token):
    if not token:
        return None
    session = repos.sessions.get(token)
    if not session or session["expires_at"] <= now().isoformat():
        return None
    return repos.users.get(session["user_id"])

def delete_session(token):
    if token:
        repos.sessions.delete(token)
