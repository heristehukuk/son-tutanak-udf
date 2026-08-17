"""
Takvim modülünün servis katmanı.

ÖNEMLİ TASARIM KARARI: Bu modül artık kendine ait ayrı bir "calendar_cases"
tablosu/veritabanı TUTMAZ. Önceki sürümde takvim, ana `cases` tablosundan
tamamen bağımsız kendi SQLite dosyasında (calendar.sqlite) bir dosya kopyası
tutuyordu - bu hem Supabase'e hiç bağlı değildi hem de "dosya bilgisi bir
kere girilir" ilkesini ihlal ediyordu. Artık takvim doğrudan ana `cases`
tablosu (repos.cases) üzerinde çalışır; kendine ait sadece `calendar_events`
tablosunu (repos.calendar_events) tutar, `case_id` doğrudan `cases.id`'dir.
"""
import json
from datetime import date, datetime
from uuid import uuid4
from app.database_layer import repos
from app.files.service import create_case
from app.modules.tasks.storage import update_case_info, create_standard_tasks
from .calculator import calculate_deadlines, calculate_remaining_days


def _now_iso():
    return datetime.now().isoformat(timespec="seconds")


def _case_to_calendar_dict(case):
    """Takvim ekranının beklediği alan adlarıyla bir dosya kaydını döner
    (case_no/applicant_name gibi eski isimler + gerçek cases.id)."""
    if not case:
        return None
    start = case.get("start_date")
    file_type = case.get("file_type") or ""
    deadlines = None
    if start:
        try:
            deadlines = calculate_deadlines(date.fromisoformat(start), file_type)
        except Exception:
            deadlines = None
    return {
        "id": case["id"],
        "main_case_id": case["id"],
        "owner_id": case.get("owner_id"),
        "case_no": case.get("file_no") or "",
        "applicant_name": case.get("title") or "",
        "file_type": file_type,
        "start_date": start,
        "normal_due_date": deadlines["normal_due_date"].isoformat() if deadlines else None,
        "extended_due_date": deadlines["extended_due_date"].isoformat() if deadlines else None,
        "created_at": case.get("created_at"),
    }


class CalendarService:
    def add_case(self, owner_id, case_no, applicant_name, file_type, start_date, main_case_id=None, case_data=None):
        case_no = (case_no or "").strip(); applicant_name = (applicant_name or "").strip(); file_type = (file_type or "").strip()
        if not case_no: raise ValueError("Dosya No boş bırakılamaz.")
        if not applicant_name: raise ValueError("Başvurucu Adı Soyadı boş bırakılamaz.")
        if not file_type: raise ValueError("Dosya Türü boş bırakılamaz.")
        metadata = dict(case_data or {})
        metadata.setdefault("dosyaNo", case_no); metadata.setdefault("basvurucuAdiSoyadi", applicant_name)
        metadata.setdefault("dosyaTuru", file_type); metadata.setdefault("baslangicTarihi", start_date.isoformat())
        application_no = metadata.get("basvuruNo") or None

        if main_case_id:
            case = repos.cases.get(main_case_id)
            if not case or case.get("owner_id") != owner_id:
                raise ValueError("Dosya bulunamadı veya erişim yetkiniz yok.")
            cid = main_case_id
        else:
            cid = create_case(owner_id, case_no, application_no, applicant_name, file_type)

        update_case_info(owner_id, cid, case_no, applicant_name, file_type, start_date.isoformat(), case_data=metadata)
        create_standard_tasks(owner_id, cid)

        deadlines = calculate_deadlines(start_date, file_type)
        # Bu dosya için önceden oluşturulmuş takvim olaylarını (varsa) temizleyip yeniden kur -
        # tarih/tür değiştiyse eski hatırlatıcılar yanlış kalmasın.
        repos.calendar_events.delete_for_case(cid)
        normal_event = repos.calendar_events.create({
            "case_id": cid, "owner_id": owner_id, "event_type": "normal_deadline",
            "event_date": deadlines["normal_due_date"].isoformat(),
            "title": f"{case_no} – {applicant_name} Normal Süre Sonu",
            "description": f"Dosya: {case_no}\nBaşvurucu: {applicant_name}\nDosya Türü: {file_type}\nNormal süre: {deadlines['normal_weeks']} hafta",
            "created_at": _now_iso(),
        })
        extended_event = repos.calendar_events.create({
            "case_id": cid, "owner_id": owner_id, "event_type": "extended_deadline",
            "event_date": deadlines["extended_due_date"].isoformat(),
            "title": f"{case_no} – {applicant_name} Ek Süre Sonu",
            "description": f"Dosya: {case_no}\nBaşvurucu: {applicant_name}\nDosya Türü: {file_type}\nEk süre: {deadlines['extra_weeks']} hafta",
            "created_at": _now_iso(),
        })
        return {
            "id": cid, "main_case_id": cid, "case_no": case_no, "applicant_name": applicant_name,
            "file_type": file_type, "start_date": start_date.isoformat(),
            "normal_due_date": deadlines["normal_due_date"].isoformat(),
            "extended_due_date": deadlines["extended_due_date"].isoformat(),
            "normal_event_id": normal_event["id"], "extended_event_id": extended_event["id"],
            "is_commercial": deadlines["is_commercial"], "tasks_created": 6,
        }

    def get_case(self, case_id, owner_id=None):
        case = repos.cases.get(case_id)
        if not case or (owner_id is not None and case.get("owner_id") != owner_id):
            return None
        return _case_to_calendar_dict(case)

    def list_cases(self, owner_id=None):
        cases = repos.cases.list_by_owner(owner_id) if owner_id else []
        return [_case_to_calendar_dict(c) for c in cases if c.get("start_date")]

    def delete_case(self, case_id, owner_id=None):
        """Takvim ekranından 'sil' dendiğinde SADECE bu dosyanın takvim
        hatırlatıcıları kaldırılır - dosyanın kendisi (belgeler, görevler,
        mesajlar bağlı olduğu için) silinmez."""
        case = repos.cases.get(case_id)
        if case and (owner_id is None or case.get("owner_id") == owner_id):
            repos.calendar_events.delete_for_case(case_id)

    def get_events(self, start_date=None, end_date=None, owner_id=None):
        events = repos.calendar_events.list_for_owner(owner_id) if owner_id else []
        if start_date:
            events = [e for e in events if e["event_date"] >= start_date.isoformat()]
        if end_date:
            events = [e for e in events if e["event_date"] <= end_date.isoformat()]
        return sorted(events, key=lambda e: e["event_date"])

    def get_upcoming_warnings(self, warning_days=7, owner_id=None):
        today = date.today(); warnings = []
        for event in repos.calendar_events.list_for_owner(owner_id) if owner_id else []:
            event_date = date.fromisoformat(event["event_date"])
            remaining = calculate_remaining_days(event_date, today)
            item = dict(event); item["remaining_days"] = remaining
            if remaining < 0: item["warning_level"] = "expired"; warnings.append(item)
            elif remaining == 0: item["warning_level"] = "today"; warnings.append(item)
            elif remaining <= warning_days: item["warning_level"] = "soon"; warnings.append(item)
        return sorted(warnings, key=lambda x: x["event_date"])
