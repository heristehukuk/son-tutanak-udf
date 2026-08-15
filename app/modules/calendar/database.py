import sqlite3
from pathlib import Path
from typing import Optional


BASE_DIR = Path(__file__).resolve().parent
CALENDAR_DB = BASE_DIR / "calendar.sqlite"


def get_connection() -> sqlite3.Connection:

    connection = sqlite3.connect(
        str(CALENDAR_DB),
        check_same_thread=False,
    )

    connection.row_factory = sqlite3.Row

    return connection


def init_calendar_database() -> None:

    with get_connection() as connection:

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS calendar_cases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                case_no TEXT NOT NULL,
                applicant_name TEXT NOT NULL,
                file_type TEXT NOT NULL,

                start_date TEXT NOT NULL,
                normal_due_date TEXT NOT NULL,
                extended_due_date TEXT NOT NULL,

                created_at TEXT NOT NULL,

                UNIQUE(case_no, start_date)
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS calendar_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                case_id INTEGER NOT NULL,

                event_type TEXT NOT NULL,
                event_date TEXT NOT NULL,

                title TEXT NOT NULL,
                description TEXT,

                FOREIGN KEY(case_id)
                    REFERENCES calendar_cases(id)
                    ON DELETE CASCADE
            )
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_calendar_events_date
            ON calendar_events(event_date)
            """
        )

        connection.commit()


def insert_case(data: dict) -> int:

    with get_connection() as connection:

        cursor = connection.execute(
            """
            INSERT INTO calendar_cases (
                case_no,
                applicant_name,
                file_type,
                start_date,
                normal_due_date,
                extended_due_date,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["case_no"],
                data["applicant_name"],
                data["file_type"],
                data["start_date"],
                data["normal_due_date"],
                data["extended_due_date"],
                data["created_at"],
            ),
        )

        connection.commit()

        return int(cursor.lastrowid)


def insert_event(data: dict) -> int:

    with get_connection() as connection:

        cursor = connection.execute(
            """
            INSERT INTO calendar_events (
                case_id,
                event_type,
                event_date,
                title,
                description
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                data["case_id"],
                data["event_type"],
                data["event_date"],
                data["title"],
                data["description"],
            ),
        )

        connection.commit()

        return int(cursor.lastrowid)


def get_case(case_id: int) -> Optional[dict]:

    with get_connection() as connection:

        row = connection.execute(
            """
            SELECT *
            FROM calendar_cases
            WHERE id = ?
            """,
            (case_id,),
        ).fetchone()

    return dict(row) if row else None


def list_cases() -> list[dict]:

    with get_connection() as connection:

        rows = connection.execute(
            """
            SELECT *
            FROM calendar_cases
            ORDER BY start_date DESC
            """
        ).fetchall()

    return [dict(row) for row in rows]


def list_events(
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict]:

    query = """
        SELECT
            e.*,
            c.case_no,
            c.applicant_name,
            c.file_type,
            c.start_date
        FROM calendar_events e
        JOIN calendar_cases c
            ON c.id = e.case_id
    """

    conditions = []
    parameters = []

    if start_date:
        conditions.append("e.event_date >= ?")
        parameters.append(start_date)

    if end_date:
        conditions.append("e.event_date <= ?")
        parameters.append(end_date)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY e.event_date ASC"

    with get_connection() as connection:

        rows = connection.execute(
            query,
            parameters,
        ).fetchall()

    return [dict(row) for row in rows]


def delete_case(case_id: int) -> None:

    with get_connection() as connection:

        connection.execute(
            """
            DELETE FROM calendar_events
            WHERE case_id = ?
            """,
            (case_id,),
        )

        connection.execute(
            """
            DELETE FROM calendar_cases
            WHERE id = ?
            """,
            (case_id,),
        )

        connection.commit()


init_calendar_database()
