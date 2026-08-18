"""
Dosya silme (çöp kutusu) sistemi.

Kurallar:
  - Silme: hem dosya sahibi (owner) hem admin silebilir. status='deleted'
    yapılır, deleted_at/deleted_by/deleted_from_status kaydedilir.
    Dosya sahibinin listesinden anında kaybolur, GERİ ALINAMAZ (sahip
    tarafından).
  - Geri getirme: SADECE admin yapabilir, 15 gün içinde. status,
    silinmeden önceki gerçek duruma (deleted_from_status) döner.
  - Kalıcı silme (purge): 15 günü dolan silinmiş dosyalar, bir sonraki
    sayfa yüklenişinde (lazy-check, tıpkı 48 saatlik üyelik temizliği
    gibi) otomatik olarak tamamen silinir - belgelerin Storage'daki
    gerçek baytları dahil, geri dönüşü olmayan şekilde.
"""

from datetime import timedelta
from app.database_layer import repos
from app.auth.service import now
from app.storage import storage

PURGE_AFTER_DAYS = 15


def soft_delete_case(case_id: str, actor_id: str, is_admin: bool) -> dict:
    """Bir dosyayı 'silindi' durumuna alır. Sahibi ya da admin çağırabilir."""
    case = repos.cases.get(case_id)
    if not case:
        raise ValueError("Dosya bulunamadı.")
    if not is_admin and case.get("owner_id") != actor_id:
        raise ValueError("Bu dosyayı silme yetkiniz yok.")
    if case.get("status") == "deleted":
        return case
    updated = repos.cases.update(case_id, {
        "status": "deleted",
        "deleted_at": now().isoformat(),
        "deleted_by": actor_id,
        "deleted_from_status": case.get("status") or "open",
        "updated_at": now().isoformat(),
    })
    repos.audit.create({
        "actor_id": actor_id, "action": "case_soft_delete", "target_id": case_id,
        "details": f"Dosya silindi (önceki durum: {case.get('status')}).",
        "created_at": now().isoformat(),
    })
    return updated


def restore_case(case_id: str, actor_id: str) -> dict:
    """Sadece admin çağırabilir - süresi (15 gün) dolmamış silinmiş bir
    dosyayı, silinmeden önceki durumuna geri getirir."""
    case = repos.cases.get(case_id)
    if not case or case.get("status") != "deleted":
        raise ValueError("Dosya çöp kutusunda değil.")
    restored_status = case.get("deleted_from_status") or "open"
    updated = repos.cases.update(case_id, {
        "status": restored_status,
        "deleted_at": None, "deleted_by": None, "deleted_from_status": None,
        "updated_at": now().isoformat(),
    })
    repos.audit.create({
        "actor_id": actor_id, "action": "case_restore", "target_id": case_id,
        "details": f"Dosya çöp kutusundan geri getirildi (durum: {restored_status}).",
        "created_at": now().isoformat(),
    })
    return updated


def days_remaining(case: dict) -> int:
    """Kalıcı silinmeye kaç gün kaldığını döner (negatifse süresi geçmiş demektir)."""
    deleted_at = case.get("deleted_at")
    if not deleted_at:
        return PURGE_AFTER_DAYS
    from datetime import datetime
    try:
        deleted_dt = datetime.fromisoformat(deleted_at)
    except ValueError:
        return PURGE_AFTER_DAYS
    elapsed = now() - deleted_dt
    return PURGE_AFTER_DAYS - elapsed.days


def _purge_case(case: dict) -> None:
    """Bir dosyayı ve bağlı TÜM verilerini (belgeler, üretilen belgeler,
    mesajlar, görevler, takvim olayları) kalıcı olarak siler - Storage'daki
    gerçek dosya baytları dahil. Görevler ve takvim olayları veritabanı
    seviyesinde zaten ON DELETE CASCADE ile bağlı, o yüzden burada elle
    silinmesi gerekmiyor; ama belgeler/üretilen belgeler/mesajlar
    ON DELETE SET NULL ile bağlı olduğu için elle temizlenmesi gerekiyor."""
    case_id = case["id"]

    for doc in repos.documents.list_by_case(case_id):
        try:
            storage.delete(doc["stored_path"])
        except Exception:
            pass
        repos.documents.delete(doc["id"])

    for doc in repos.generated_documents.list_by_case(case_id):
        try:
            storage.delete(doc["stored_path"])
        except Exception:
            pass
        repos.generated_documents.delete(doc["id"])

    repos.messages.delete_for_case(case_id)

    # tasks/calendar_events, cases satırı silinince ON DELETE CASCADE ile
    # otomatik gider - burada ayrıca silmeye gerek yok.
    repos.cases.delete(case_id)

    repos.audit.create({
        "actor_id": None, "action": "case_purge", "target_id": case_id,
        "details": f"15 gün dolduğu için dosya kalıcı olarak silindi (belgeler dahil).",
        "created_at": now().isoformat(),
    })


def cleanup_expired_deleted_cases() -> list[str]:
    """48 saatlik üyelik temizliğiyle AYNI 'lazy check' deseni: bu fonksiyon
    bir sayfa yüklendiğinde çağrılır (bkz. app/main.py home(),
    app/admin/routes.py dashboard()). 15 günü dolmuş 'deleted' durumundaki
    dosyaları bulur ve kalıcı olarak siler."""
    cutoff = (now() - timedelta(days=PURGE_AFTER_DAYS)).isoformat()
    purged = []
    for case in repos.cases.list_all_with_owner():
        if case.get("status") == "deleted" and (case.get("deleted_at") or "") < cutoff:
            _purge_case(case)
            purged.append(case["id"])
    return purged


def list_trash() -> list[dict]:
    """Admin çöp kutusu ekranı için: silinmiş tüm dosyalar, kalan gün
    sayısıyla birlikte."""
    rows = [c for c in repos.cases.list_all_with_owner() if c.get("status") == "deleted"]
    for r in rows:
        r["days_remaining"] = days_remaining(r)
    rows.sort(key=lambda r: r.get("deleted_at") or "", reverse=True)
    return rows
