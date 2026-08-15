from datetime import date
from .storage import (
    ensure_standard_tasks,
    get_case,
    get_task,
    list_tasks,
    counts,
    history,
    get_templates,
    update_task,
    create_custom_task,
    delete_custom_task,
    update_template,
    parse_date,
)


def task_context(owner_id, case_id):
    case = get_case(owner_id, case_id)
    if not case:
        return None
    tasks = ensure_standard_tasks(owner_id, case_id)
    return case, tasks


def validate_due_date(case, due_date):
    start = parse_date(case["process_start_date"] if "process_start_date" in case.keys() else None)
    d = parse_date(due_date)
    if not d:
        return False, False
    if not start:
        return True, False
    delta = (d - start).days
    return True, delta > 21
