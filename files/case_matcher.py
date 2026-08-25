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


def detect_identity_conflicts(case: dict, incoming: dict) -> list[dict]:
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
