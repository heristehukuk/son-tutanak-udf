from datetime import date
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from .service import CalendarService


router = APIRouter(
    prefix="/calendar",
    tags=["Calendar"],
)


service = CalendarService()


TEMPLATE_PATH = (
    Path(__file__).resolve().parent
    / "templates"
    / "calendar.html"
)


@router.get("/health")
def calendar_health():

    return {
        "status": "ok",
        "module": "calendar",
    }


@router.get(
    "",
    response_class=HTMLResponse
)
def calendar_page():

    if not TEMPLATE_PATH.exists():

        return HTMLResponse(
            "Takvim şablonu bulunamadı.",
            status_code=500
        )

    return HTMLResponse(
        TEMPLATE_PATH.read_text(
            encoding="utf-8"
        )
    )


@router.post("/calculate")
def calculate_calendar(
    case_no: str,
    applicant_name: str,
    file_type: str,
    start_date: date,
):

    try:

        return service.add_case(
            case_no=case_no,
            applicant_name=applicant_name,
            file_type=file_type,
            start_date=start_date,
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )


@router.get("/cases")
def get_cases():

    return service.list_cases()


@router.get("/events")
def get_events():

    return service.get_events()


@router.get("/warnings")
def get_warnings():

    return service.get_upcoming_warnings()


@router.delete("/cases/{case_id}")
def delete_case(case_id: int):

    case = service.get_case(case_id)

    if not case:

        raise HTTPException(
            status_code=404,
            detail="Dosya bulunamadı."
        )

    service.delete_case(case_id)

    return {
        "status": "ok",
        "deleted": case_id,
    }
