
from datetime import datetime, timedelta, timezone
from uuid import uuid4
import secrets
from app.database import connect
from app.auth.security import hash_password, verify_password

def now():
    return datetime.now(timezone.utc)

def create_user(email, display_name, password, ip=""):
    user_id = str(uuid4())
    pw = hash_password(password)
    with connect() as c:
        c.execute("""INSERT INTO users
        (id,email,display_name,password_hash,status,plan_id,created_at,last_ip)
        VALUES (?,?,?,?,?,?,?,?)""",
        (user_id,email.strip().lower(),display_name.strip(),pw,"pending","free",now().isoformat(),ip))
    return user_id

def authenticate(email, password):
    with connect() as c:
        u = c.execute("SELECT * FROM users WHERE email=?", (email.strip().lower(),)).fetchone()
    if not u or not verify_password(password, u["password_hash"]):
        return None
    return u

def create_session(user_id, ip=""):
    token = secrets.token_urlsafe(48)
    expires = now() + timedelta(days=7)
    with connect() as c:
        c.execute("INSERT INTO sessions(token,user_id,created_at,expires_at,ip) VALUES(?,?,?,?,?)",
                  (token,user_id,now().isoformat(),expires.isoformat(),ip))
    return token

def get_user_by_session(token):
    if not token:
        return None
    with connect() as c:
        return c.execute("""SELECT u.* FROM users u JOIN sessions s ON s.user_id=u.id
                            WHERE s.token=? AND s.expires_at>?""",
                         (token,now().isoformat())).fetchone()

def delete_session(token):
    if token:
        with connect() as c:
            c.execute("DELETE FROM sessions WHERE token=?", (token,))
