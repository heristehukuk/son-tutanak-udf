from datetime import date, timedelta


COMMERCIAL_NORMAL_WEEKS = 6
COMMERCIAL_EXTRA_WEEKS = 8

NON_COMMERCIAL_NORMAL_WEEKS = 3
NON_COMMERCIAL_EXTRA_WEEKS = 4


def is_commercial_file(file_type: str) -> bool:
    if not file_type:
        return False

    return "ticari" in file_type.strip().casefold()


def calculate_deadlines(
    start_date: date,
    file_type: str,
) -> dict:

    commercial = is_commercial_file(file_type)

    if commercial:
        normal_weeks = COMMERCIAL_NORMAL_WEEKS
        extra_weeks = COMMERCIAL_EXTRA_WEEKS
    else:
        normal_weeks = NON_COMMERCIAL_NORMAL_WEEKS
        extra_weeks = NON_COMMERCIAL_EXTRA_WEEKS

    normal_due_date = (
        start_date + timedelta(weeks=normal_weeks)
    )

    extended_due_date = (
        start_date + timedelta(weeks=extra_weeks)
    )

    return {
        "is_commercial": commercial,
        "normal_weeks": normal_weeks,
        "extra_weeks": extra_weeks,
        "normal_due_date": normal_due_date,
        "extended_due_date": extended_due_date,
    }


def calculate_remaining_days(
    target_date: date,
    today: date | None = None,
) -> int:

    if today is None:
        today = date.today()

    return (target_date - today).days
