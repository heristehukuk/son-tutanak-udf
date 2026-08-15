from datetime import date

from fastapi import APIRouter, HTTPException

from .service import CalendarService


router = APIRouter(
    prefix="/calendar",
    tags=["Calendar"],
)

service = CalendarService()


@router.get("/health")
def calendar_health():

    return {
        "status": "ok",
        "module": "calendar",
    }


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
