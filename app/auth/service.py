
from datetime import datetime, timedelta, timezone
from uuid import uuid4
import secrets
from app.database_layer import repos
from app.auth.security import hash_password, verify_password

def now():
    return datetime.now(timezone.utc)

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
