from __future__ import annotations
import re
from typing import Any

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
            import json
            parsed = json.loads(raw) if isinstance(raw, str) else (raw or {})
            if isinstance(parsed, dict):
                data.update(parsed)
        except Exception:
            pass
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
