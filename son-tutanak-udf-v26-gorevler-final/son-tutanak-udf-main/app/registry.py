"""
Arabulucu Numarası ve Dosya Kayıt No sistemi.

- Arabulucu Numarası: her kullanıcıya admin onayladığında (pending->active)
  bir kez, sıradan (1,2,3...) verilir; bir daha değişmez.
- Dosya Kayıt No: "{arabulucu_no}-{yil}-{sira}" formatında (örn. 212-2026-001).
  Yil, dosyanin OLUŞTURULMA tarihinden alınır. Sıra, o arabulucunun o yıl
  içindeki dosyalarına göre 3 haneli sabit genişlikte verilir.

Sayaçlar (`counters` tablosu + repos.counters.next_value) ATOMİK'tir - iki
dosya/kullanıcı tam aynı anda oluşsa bile aynı numarayı alamaz.

Sistem ID (UUID, cases.id / users.id) bu numaralandırmanın YERİNE değil,
YANINDA çalışır - veritabanı ilişkileri hâlâ UUID üzerinden yürür. Kayıt No
sadece insan tarafından okunabilir, düzenli bir referans numarasıdır.
"""
from datetime import datetime
from app.database_layer import repos


def ensure_mediator_no(user_id):
    """Kullanıcının arabulucu numarası yoksa bir tane atar, varsa dokunmaz."""
    user = repos.users.get(user_id)
    if not user:
        return None
    if user.get("mediator_no"):
        return user["mediator_no"]
    n = repos.counters.next_value("mediator_no")
    repos.users.update(user_id, {"mediator_no": n})
    return n


def assign_missing_mediator_numbers():
    """Uygulama başlarken çağrılır: arabulucu numarası olmayan (ör. bu özellik
    devreye girmeden önce zaten 'active' olmuş) kullanıcılara, kayıt tarihi
    sırasına göre toplu numara verir. Zaten numarası olanlara dokunmaz -
    tekrar tekrar çağrılması güvenlidir (idempotent)."""
    users = [u for u in repos.users.list_all() if u.get("status") == "active" and not u.get("mediator_no")]
    users.sort(key=lambda u: u.get("created_at") or "")
    for u in users:
        ensure_mediator_no(u["id"])


def _case_year(case):
    raw = case.get("created_at") or ""
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).year
    except Exception:
        return datetime.now().year


def ensure_registry_no(case_id):
    """Dosyanın Kayıt No'su yoksa bir tane atar, varsa dokunmaz."""
    case = repos.cases.get(case_id)
    if not case:
        return None
    if case.get("registry_no"):
        return case["registry_no"]
    mediator_no = ensure_mediator_no(case["owner_id"])
    if not mediator_no:
        return None
    year = _case_year(case)
    seq = repos.counters.next_value(f"case_seq:{case['owner_id']}:{year}")
    registry_no = f"{mediator_no}-{year}-{seq:03d}"
    repos.cases.update(case_id, {"registry_no": registry_no})
    return registry_no


def assign_missing_registry_numbers():
    """Uygulama başlarken çağrılır: Kayıt No'su olmayan (bu özellik devreye
    girmeden önce oluşturulmuş) dosyalara, oluşturulma tarihi sırasına göre
    toplu numara verir. İdempotent - tekrar çağrılması güvenlidir."""
    all_cases = repos.cases.list_all_with_owner()
    missing = [c for c in all_cases if not c.get("registry_no")]
    missing.sort(key=lambda c: c.get("created_at") or "")
    for c in missing:
        ensure_registry_no(c["id"])


def set_registry_no_manual(case_id, new_registry_no):
    """Admin panelinden elle düzeltme. Aynı numara başka bir dosyada
    kullanılıyorsa ValueError fırlatır - çakışmaya asla izin verilmez."""
    new_registry_no = (new_registry_no or "").strip()
    if not new_registry_no:
        raise ValueError("Kayıt No boş bırakılamaz.")
    existing = repos.cases.get_by_registry_no(new_registry_no)
    if existing and existing["id"] != case_id:
        raise ValueError(f"'{new_registry_no}' zaten başka bir dosyada kullanılıyor.")
    case = repos.cases.get(case_id)
    if not case:
        raise ValueError("Dosya bulunamadı.")
    return repos.cases.update(case_id, {"registry_no": new_registry_no})
