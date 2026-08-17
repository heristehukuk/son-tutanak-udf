import json
from datetime import date
from pathlib import Path
from fastapi import APIRouter, HTTPException, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from app.auth.service import get_user_by_session
from .service import CalendarService
router=APIRouter(prefix="/calendar",tags=["Calendar"])
service=CalendarService()
TEMPLATE_PATH=Path(__file__).resolve().parent/"templates"/"calendar.html"

def user(request):
    u=get_user_by_session(request.cookies.get("session")); return u if u and u["status"] not in ("banned","rejected") else None

@router.get("/health")
def calendar_health(): return {"status":"ok","module":"calendar"}

@router.get("",response_class=HTMLResponse)
def calendar_page(request:Request):
    if not user(request): return RedirectResponse("/auth/login",303)
    if not TEMPLATE_PATH.exists(): return HTMLResponse("Takvim şablonu bulunamadı.",500)
    return HTMLResponse(TEMPLATE_PATH.read_text(encoding="utf-8"))

@router.post("/calculate")
def calculate_calendar(request:Request, case_no:str=Form(...), applicant_name:str=Form(...), file_type:str=Form(...), start_date:date=Form(...), case_id:str=Form(""), case_data:str=Form("")):
    u=user(request)
    if not u: raise HTTPException(status_code=401,detail="Giriş gerekli.")
    try: metadata=json.loads(case_data) if case_data else {}
    except Exception: metadata={}
    try: return service.add_case(u["id"],case_no,applicant_name,file_type,start_date,main_case_id=case_id or None,case_data=metadata)
    except ValueError as exc: raise HTTPException(status_code=400,detail=str(exc))

@router.get("/cases")
def get_cases(request:Request):
    u=user(request)
    if not u: raise HTTPException(status_code=401,detail="Giriş gerekli.")
    return service.list_cases(u["id"])

@router.get("/events")
def get_events(request:Request):
    u=user(request)
    if not u: raise HTTPException(status_code=401,detail="Giriş gerekli.")
    return service.get_events(owner_id=u["id"])

@router.get("/warnings")
def get_warnings(request:Request):
    u=user(request)
    if not u: raise HTTPException(status_code=401,detail="Giriş gerekli.")
    return service.get_upcoming_warnings(owner_id=u["id"])

@router.delete("/cases/{case_id}")
def delete_case_route(request:Request,case_id:str):
    u=user(request)
    if not u: raise HTTPException(status_code=401,detail="Giriş gerekli.")
    case=service.get_case(case_id,u["id"])
    if not case: raise HTTPException(status_code=404,detail="Dosya bulunamadı.")
    service.delete_case(case_id,u["id"]); return {"status":"ok","deleted":case_id}
