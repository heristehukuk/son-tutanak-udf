
import base64, hashlib, hmac, os

def hash_password(password: str) -> str:
    if len(password) < 10:
        raise ValueError("Şifre en az 10 karakter olmalıdır.")
    salt = os.urandom(16)
    key = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return "scrypt$" + base64.urlsafe_b64encode(salt).decode() + "$" + base64.urlsafe_b64encode(key).decode()

def verify_password(password: str, stored: str) -> bool:
    try:
        _, salt_b64, key_b64 = stored.split("$", 2)
        salt = base64.urlsafe_b64decode(salt_b64.encode())
        expected = base64.urlsafe_b64decode(key_b64.encode())
        actual = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False
