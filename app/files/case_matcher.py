from __future__ import annotations
import re
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Bir belgenin mevcut case ile aynı dosya olup olmadığını belirlemede
# kimlik niteliğinde kullandığımız alanlar. Boş alanlar çatışma sayılmaz.
IDENTITY_FIELDS = {
    "dosyaNo": "Dosya No",
    "basvuruNo": "Başvuru No",
    "basvurucuAdiSoyadi": "Başvurucu Adı Soyadı",
}


def _norm(value: Any) -> str:
    value = str(value or "").strip().casefold()
    value = re.sub(r"\s+", " ", value)
    return value


def case_values(case: dict) -> dict:
    data = {}
    raw = case.get("case_data_json")
    if raw:
        try:
            parsed = json.loads(raw) if isinstance(raw, str) else (raw or {})
            if isinstance(parsed, dict):
                data.update(parsed)
        except Exception:
            # NOT: Eskiden burada hata sessizce yutuluyordu (bare except: pass).
            # case_data_json bozuksa bilgi havuzu kullanıcıya hiç uyarı vermeden
            # BOŞ dönüyordu - veri kaybı fark edilmiyordu. Artık en azından loglanıyor.
            logger.warning(
                "case_values: case_data_json ayrıştırılamadı (case_id=%s). "
                "Bilgi havuzu bu dosya için boş dönüyor olabilir.",
                case.get("id"),
                exc_info=True,
            )
    data.setdefault("dosyaNo", case.get("file_no"))
    data.setdefault("basvuruNo", case.get("application_no"))
    data.setdefault("basvurucuAdiSoyadi", case.get("title"))
    return data


def _respondent_name_map(respondents) -> dict:
    """Karşı taraf isimlerini normalize edilmiş anahtar -> orijinal görünen
    ad eşlemesi olarak döndürür. Boş isimler dikkate alınmaz."""
    out = {}
    for r in respondents or []:
        if not isinstance(r, dict):
            continue
        raw = str(r.get("name") or "").strip()
        key = _norm(raw)
        if key and key not in out:
            out[key] = raw
    return out


def detect_identity_conflicts(case: dict, incoming: dict, incoming_respondents=None) -> list[dict]:
    """Return only real, two-sided identity conflicts.

    Empty values never erase an existing value and never cause a conflict.
    """
    current = case_values(case)
    conflicts = []
    for key, label in IDENTITY_FIELDS.items():
        old = _norm(current.get(key))
        new = _norm(incoming.get(key))
        if old and new and old != new:
            conflicts.append({
                "field": key,
                "label": label,
                "old": current.get(key),
                "new": incoming.get(key),
            })
    # Karşı taraf(lar) için de aynı mantık: dosyada zaten isimli karşı taraf(lar)
    # varsa ve yeni belgede de isimli karşı taraf(lar) varsa, ama iki listede
    # ORTAK isim yoksa, bu muhtemelen farklı bir dosyanın belgesidir - kullanıcı
    # onaylamadan sessizce birleştirilmemeli.
    if incoming_respondents is not None:
        current_names = _respondent_name_map(current.get("respondents"))
        incoming_names = _respondent_name_map(incoming_respondents)
        if current_names and incoming_names and set(current_names).isdisjoint(incoming_names):
            conflicts.append({
                "field": "karsiTaraflar",
                "label": "Karşı Taraf(lar)",
                "old": ", ".join(current_names.values()),
                "new": ", ".join(incoming_names.values()),
            })
    return conflicts


def merge_case_values(case: dict, incoming: dict, respondents=None) -> dict:
    """Merge non-empty incoming values without deleting existing values."""
    result = case_values(case)
    for key, value in incoming.items():
        if key.startswith("_"):
            continue
        if str(value or "").strip():
            result[key] = value
    if respondents is not None:
        result["respondents"] = respondents
    return result


def find_duplicate_case(owner_id: str, incoming: dict):
    """İlk belge yüklemesinde (henüz bir case_id yokken) kullanıcının aynı
    dosya no veya başvuru no'ya sahip, silinmemiş bir dosyası olup olmadığını
    arar. Bulunursa /edit akışı otomatik yeni bir case OLUŞTURMAZ; kullanıcıya
    "mevcut dosyaya mı eklensin, ayrı mı kalsın" seçimi sunulur."""
    from app.database_layer import repos
    dosya_no = _norm(incoming.get("dosyaNo"))
    basvuru_no = _norm(incoming.get("basvuruNo"))
    if not dosya_no and not basvuru_no:
        return None
    for case in repos.cases.list_by_owner(owner_id):
        if case.get("status") == "deleted":
            continue
        cur = case_values(case)
        if dosya_no and _norm(cur.get("dosyaNo")) == dosya_no:
            return case
        if basvuru_no and _norm(cur.get("basvuruNo")) == basvuru_no:
            return case
    return None


def get_locked_fields(case: dict) -> set:
    """Bir case için KALICI olarak kilitlenmiş alan adlarını döndürür.

    Eskiden 'kilit' yalnızca tek bir HTTP isteği boyunca form checkbox'larından
    (request.form().getlist('locked')) geliyordu; case'e hiç kaydedilmiyordu.
    Bu yüzden bir arabulucu bir alanı 'sabitle' diye işaretlese bile, bir sonraki
    belge birleştirmesinde bu tercih hatırlanmıyor, kullanıcı her seferinde aynı
    kutucukları yeniden işaretlemek zorunda kalıyordu. Artık `cases.locked_fields`
    sütununda (JSON dize dizisi) kalıcı olarak tutuluyor; bkz. persist_case_update.
    """
    raw = case.get("locked_fields") if case else None
    if not raw:
        return set()
    try:
        parsed = json.loads(raw) if isinstance(raw, str) else (raw or [])
        if isinstance(parsed, list):
            return {str(x) for x in parsed}
    except Exception:
        logger.warning(
            "get_locked_fields: locked_fields ayrıştırılamadı (case_id=%s).",
            case.get("id"),
            exc_info=True,
        )
    return set()


def persist_case_update(cid, case, data, locked=None, actor_id=None):
    """/merge, /merge/resolve, /build, davet mektubu ve bilgi havuzu ekranından
    doğrudan kaydetme (files/routes.py) akışlarında ORTAK olan case güncelleme
    mantığı. `data`, o an geçerli tam bilgi havuzu sözlüğüdür (merge_case_values
    sonucu ya da kullanıcının form üzerinden gönderdiği values sözlüğü).
    Her çağrıda aynı 5 sütun + case_data_json + updated_at, aynı öncelik
    kuralıyla (yeni değer varsa o, yoksa mevcut case değeri) güncellenir.

    `locked` verilirse (bu istekte işaretlenmiş/miras kalan kilit alan
    adları), var olan kalıcı kilitlerle (get_locked_fields) birleştirilip
    cases.locked_fields'a yazılır - böylece bir alanı bir kez 'sabitle' diye
    işaretlemek, sonraki tüm belge birleştirmelerinde de korunur.

    Ayrıca değişen her alan (audit_logs, action='case_data_field_changed')
    ile denetim izine kaydedilir; bilgi havuzunda alan bazlı geçmiş/versiyon
    yoktu, bir birleştirme yanlış veri getirdiğinde eski değere bakılamıyordu."""
    from app.database_layer import repos
    from app.auth.service import now
    update = {
        "file_no": data.get("dosyaNo") or case.get("file_no"),
        "application_no": data.get("basvuruNo") or case.get("application_no"),
        "title": data.get("basvurucuAdiSoyadi") or case.get("title") or "Dosya",
        "file_type": data.get("dosyaTuru") or case.get("file_type"),
        "start_date": data.get("baslangicTarihi") or case.get("start_date"),
        "case_data_json": json.dumps(data, ensure_ascii=False),
        "updated_at": now().isoformat(),
    }
    if locked is not None:
        existing_locked = get_locked_fields(case)
        update["locked_fields"] = json.dumps(sorted(existing_locked | set(locked)), ensure_ascii=False)
    try:
        _record_case_data_history(cid, case, data, actor_id=actor_id)
    except Exception:
        logger.warning("Case veri geçmişi kaydedilemedi (case_id=%s).", cid, exc_info=True)
    repos.cases.update(cid, update)


def _record_case_data_history(cid, case, data, actor_id=None):
    from app.database_layer import repos
    from app.auth.service import now
    old = case_values(case)
    keys = {k for k in old.keys() if k != "respondents" and not str(k).startswith("_")}
    keys |= {k for k in data.keys() if k != "respondents" and not str(k).startswith("_")}
    ts = now().isoformat()
    for key in keys:
        old_v = str(old.get(key) or "")
        new_v = str(data.get(key) or "")
        if old_v != new_v:
            repos.audit.create({
                "actor_id": actor_id,
                "action": "case_data_field_changed",
                "target_id": cid,
                "details": json.dumps({"field": key, "old": old_v, "new": new_v}, ensure_ascii=False),
                "created_at": ts,
            })
