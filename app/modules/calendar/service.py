import json
from datetime import date, datetime
from .calculator import calculate_deadlines, calculate_remaining_days
from .database import delete_case,get_case,get_case_by_key,get_case_by_main_id,insert_case,insert_event,list_cases,list_events,update_case
from app.files.service import create_case
from app.database import connect
from app.modules.tasks.storage import ensure_schema as ensure_task_schema, update_case_info, create_standard_tasks

class CalendarService:
    def add_case(self, owner_id, case_no, applicant_name, file_type, start_date, main_case_id=None, case_data=None):
        case_no=(case_no or "").strip(); applicant_name=(applicant_name or "").strip(); file_type=(file_type or "").strip()
        if not case_no: raise ValueError("Dosya No boş bırakılamaz.")
        if not applicant_name: raise ValueError("Başvurucu Adı Soyadı boş bırakılamaz.")
        if not file_type: raise ValueError("Dosya Türü boş bırakılamaz.")
        ensure_task_schema()
        metadata=dict(case_data or {})
        metadata.setdefault("dosyaNo",case_no); metadata.setdefault("basvurucuAdiSoyadi",applicant_name); metadata.setdefault("dosyaTuru",file_type); metadata.setdefault("baslangicTarihi",start_date.isoformat())
        application_no=metadata.get("basvuruNo") or None
        if main_case_id:
            with connect() as c:
                row=c.execute("SELECT id FROM cases WHERE id=? AND owner_id=?",(main_case_id,owner_id)).fetchone()
            if not row: raise ValueError("Dosya bulunamadı veya erişim yetkiniz yok.")
            cid=main_case_id
        else:
            cid=create_case(owner_id,case_no,application_no,applicant_name)
        update_case_info(owner_id,cid,case_no,applicant_name,file_type,start_date.isoformat(),case_data=metadata)
        create_standard_tasks(owner_id,cid)
        deadlines=calculate_deadlines(start_date,file_type)
        data={"owner_id":owner_id,"main_case_id":cid,"case_no":case_no,"applicant_name":applicant_name,"file_type":file_type,"start_date":start_date.isoformat(),"normal_due_date":deadlines["normal_due_date"].isoformat(),"extended_due_date":deadlines["extended_due_date"].isoformat(),"created_at":datetime.now().isoformat(timespec="seconds")}
        cal=get_case_by_main_id(cid,owner_id) or get_case_by_key(case_no,start_date.isoformat(),owner_id)
        if cal:
            update_case(cal["id"],data); case_id=cal["id"]
        else:
            try: case_id=insert_case(data)
            except Exception as exc:
                if "UNIQUE constraint failed" in str(exc):
                    cal=get_case_by_key(case_no,start_date.isoformat(),owner_id)
                    if not cal: raise
                    update_case(cal["id"],data); case_id=cal["id"]
                else: raise
        normal_event_id=insert_event({"case_id":case_id,"event_type":"normal_deadline","event_date":deadlines["normal_due_date"].isoformat(),"title":f"{case_no} – {applicant_name} Normal Süre Sonu","description":f"Dosya: {case_no}\nBaşvurucu: {applicant_name}\nDosya Türü: {file_type}\nNormal süre: {deadlines['normal_weeks']} hafta"})
        extended_event_id=insert_event({"case_id":case_id,"event_type":"extended_deadline","event_date":deadlines["extended_due_date"].isoformat(),"title":f"{case_no} – {applicant_name} Ek Süre Sonu","description":f"Dosya: {case_no}\nBaşvurucu: {applicant_name}\nDosya Türü: {file_type}\nEk süre: {deadlines['extra_weeks']} hafta"})
        return {"id":case_id,"main_case_id":cid,"case_no":case_no,"applicant_name":applicant_name,"file_type":file_type,"start_date":start_date.isoformat(),"normal_due_date":deadlines["normal_due_date"].isoformat(),"extended_due_date":deadlines["extended_due_date"].isoformat(),"normal_event_id":normal_event_id,"extended_event_id":extended_event_id,"is_commercial":deadlines["is_commercial"],"tasks_created":6}
    def get_case(self,case_id,owner_id=None): return get_case(case_id,owner_id)
    def list_cases(self,owner_id=None): return list_cases(owner_id)
    def delete_case(self,case_id,owner_id=None): delete_case(case_id,owner_id)
    def get_events(self,start_date=None,end_date=None,owner_id=None):
        return list_events(start_date.isoformat() if start_date else None,end_date.isoformat() if end_date else None,owner_id)
    def get_upcoming_warnings(self,warning_days=7,owner_id=None):
        today=date.today(); warnings=[]
        for event in list_events(owner_id=owner_id):
            event_date=date.fromisoformat(event["event_date"]); remaining=calculate_remaining_days(event_date,today); item=dict(event); item["remaining_days"]=remaining
            if remaining<0: item["warning_level"]="expired"; warnings.append(item)
            elif remaining==0: item["warning_level"]="today"; warnings.append(item)
            elif remaining<=warning_days: item["warning_level"]="soon"; warnings.append(item)
        return sorted(warnings,key=lambda x:x["event_date"])
