"""Görev modülünün servis katmanı. Router'dan bağımsız ortak yardımcılar."""
from datetime import datetime, date
from .storage import get_case, create_standard_tasks, list_tasks, global_stats


def parse_date(value):
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d.%m.%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(str(value).strip(), fmt).date()
        except ValueError:
            pass
    return None


def task_context(owner_id, case_id):
    case = get_case(owner_id, case_id)
    if not case:
        return None
    create_standard_tasks(owner_id, case_id)
    return case, list_tasks(owner_id, case_id)


def validate_due_date(case, due_date):
    start = parse_date(case.get("start_date"))
    d = parse_date(due_date)
    if not d:
        return False, False
    if not start:
        return True, False
    return True, (d - start).days > 21
