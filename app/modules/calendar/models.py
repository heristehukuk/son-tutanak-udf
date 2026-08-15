from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass
class CalendarCase:
    case_no: str
    applicant_name: str
    file_type: str
    start_date: date

    id: Optional[int] = None
    normal_due_date: Optional[date] = None
    extended_due_date: Optional[date] = None
    created_at: Optional[str] = None


@dataclass
class CalendarEvent:
    case_id: int
    event_type: str
    event_date: date

    case_no: str
    applicant_name: str

    title: str
    description: str

    is_warning: bool = False
    warning_level: str = "normal"

    id: Optional[int] = None
