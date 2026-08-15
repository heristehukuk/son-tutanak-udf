from datetime import date, datetime

from .calculator import (
    calculate_deadlines,
    calculate_remaining_days,
)

from .database import (
    delete_case,
    get_case,
    insert_case,
    insert_event,
    list_cases,
    list_events,
)


class CalendarService:

    def add_case(
        self,
        case_no: str,
        applicant_name: str,
        file_type: str,
        start_date: date,
    ) -> dict:

        case_no = (case_no or "").strip()
        applicant_name = (applicant_name or "").strip()
        file_type = (file_type or "").strip()

        if not case_no:
            raise ValueError("Dosya No boş bırakılamaz.")

        if not applicant_name:
            raise ValueError(
                "Başvurucu Adı Soyadı boş bırakılamaz."
            )

        if not file_type:
            raise ValueError(
                "Dosya Türü boş bırakılamaz."
            )

        deadlines = calculate_deadlines(
            start_date,
            file_type,
        )

        created_at = datetime.now().isoformat(
            timespec="seconds"
        )

        case_data = {
            "case_no": case_no,
            "applicant_name": applicant_name,
            "file_type": file_type,
            "start_date": start_date.isoformat(),

            "normal_due_date":
                deadlines["normal_due_date"].isoformat(),

            "extended_due_date":
                deadlines["extended_due_date"].isoformat(),

            "created_at": created_at,
        }

        try:
            case_id = insert_case(case_data)

        except Exception as exc:

            if "UNIQUE constraint failed" in str(exc):
                raise ValueError(
                    "Bu dosya aynı başlangıç tarihiyle "
                    "zaten takvimde kayıtlı."
                )

            raise

        normal_event_id = insert_event(
            {
                "case_id": case_id,
                "event_type": "normal_deadline",
                "event_date":
                    deadlines["normal_due_date"].isoformat(),

                "title":
                    f"{case_no} – {applicant_name} "
                    "Normal Süre Sonu",

                "description":
                    f"Dosya: {case_no}\n"
                    f"Başvurucu: {applicant_name}\n"
                    f"Dosya Türü: {file_type}\n"
                    f"Normal süre: "
                    f"{deadlines['normal_weeks']} hafta",
            }
        )

        extended_event_id = insert_event(
            {
                "case_id": case_id,
                "event_type": "extended_deadline",

                "event_date":
                    deadlines["extended_due_date"].isoformat(),

                "title":
                    f"{case_no} – {applicant_name} "
                    "Ek Süre Sonu",

                "description":
                    f"Dosya: {case_no}\n"
                    f"Başvurucu: {applicant_name}\n"
                    f"Dosya Türü: {file_type}\n"
                    f"Ek süre: "
                    f"{deadlines['extra_weeks']} hafta",
            }
        )

        return {
            "id": case_id,
            "case_no": case_no,
            "applicant_name": applicant_name,
            "file_type": file_type,
            "start_date": start_date.isoformat(),

            "normal_due_date":
                deadlines["normal_due_date"].isoformat(),

            "extended_due_date":
                deadlines["extended_due_date"].isoformat(),

            "normal_event_id": normal_event_id,
            "extended_event_id": extended_event_id,

            "is_commercial":
                deadlines["is_commercial"],
        }

    def get_case(self, case_id: int):
        return get_case(case_id)

    def list_cases(self):
        return list_cases()

    def delete_case(self, case_id: int):
        delete_case(case_id)

    def get_events(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
    ):

        return list_events(
            start_date=(
                start_date.isoformat()
                if start_date
                else None
            ),
            end_date=(
                end_date.isoformat()
                if end_date
                else None
            ),
        )

    def get_upcoming_warnings(
        self,
        warning_days: int = 7,
    ):

        today = date.today()

        events = list_events()
        warnings = []

        for event in events:

            event_date = date.fromisoformat(
                event["event_date"]
            )

            remaining = calculate_remaining_days(
                event_date,
                today,
            )

            item = dict(event)
            item["remaining_days"] = remaining

            if remaining < 0:
                item["warning_level"] = "expired"
                item["warning"] = True
                warnings.append(item)

            elif remaining == 0:
                item["warning_level"] = "today"
                item["warning"] = True
                warnings.append(item)

            elif remaining <= warning_days:
                item["warning_level"] = "soon"
                item["warning"] = True
                warnings.append(item)

        warnings.sort(
            key=lambda x: x["event_date"]
        )

        return warnings
