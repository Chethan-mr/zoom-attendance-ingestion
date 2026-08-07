"""Google Chat Cards V2 builders for Manual Attendance."""

from __future__ import annotations

from datetime import time
from typing import Any, Sequence


def _time_slots(step_minutes: int = 15) -> list[dict[str, str]]:
    """Build HH:MM dropdown items from 06:00 through 22:00."""
    items: list[dict[str, str]] = []
    minutes = 6 * 60
    end = 22 * 60
    while minutes <= end:
        hh, mm = divmod(minutes, 60)
        value = f"{hh:02d}:{mm:02d}"
        items.append({"text": value, "value": value})
        minutes += step_minutes
    return items


TIME_SLOT_ITEMS = _time_slots()


def text_message(text: str) -> dict[str, Any]:
    return {"text": text}


def error_card(message: str) -> dict[str, Any]:
    return {
        "cardsV2": [
            {
                "cardId": "manualAttendanceError",
                "card": {
                    "header": {
                        "title": "Manual Attendance",
                        "subtitle": "Something went wrong",
                    },
                    "sections": [
                        {
                            "widgets": [
                                {"textParagraph": {"text": message}},
                            ]
                        }
                    ],
                },
            }
        ]
    }


def program_selection_card(programs: Sequence[dict[str, str]]) -> dict[str, Any]:
    items = [
        {"text": p["text"], "value": p["id"], "selected": i == 0}
        for i, p in enumerate(programs)
    ]
    return {
        "cardsV2": [
            {
                "cardId": "manualAttendanceProgram",
                "card": {
                    "header": {
                        "title": "Manual Attendance",
                        "subtitle": "Step 1 of 3 — Select program",
                    },
                    "sections": [
                        {
                            "widgets": [
                                {
                                    "textParagraph": {
                                        "text": (
                                            "Select the program for this offline session. "
                                            "Only programs with deployments in the last "
                                            "3 months are listed."
                                        )
                                    }
                                },
                                {
                                    "selectionInput": {
                                        "name": "program_id",
                                        "label": "Program",
                                        "type": "DROP_DOWN",
                                        "items": items,
                                    }
                                },
                                {
                                    "buttonList": {
                                        "buttons": [
                                            {
                                                "text": "Continue",
                                                "onClick": {
                                                    "action": {
                                                        "function": "select_program",
                                                    }
                                                },
                                            }
                                        ]
                                    }
                                },
                            ]
                        }
                    ],
                },
            }
        ]
    }


def session_details_card(
    *,
    program_id: str,
    program_name: str,
) -> dict[str, Any]:
    start_items = [
        {**item, "selected": item["value"] == "09:00"} for item in TIME_SLOT_ITEMS
    ]
    end_items = [
        {**item, "selected": item["value"] == "11:00"} for item in TIME_SLOT_ITEMS
    ]
    return {
        "cardsV2": [
            {
                "cardId": "manualAttendanceSession",
                "card": {
                    "header": {
                        "title": "Manual Attendance",
                        "subtitle": "Step 2 of 3 — Session details",
                    },
                    "sections": [
                        {
                            "widgets": [
                                {
                                    "textParagraph": {
                                        "text": f"<b>Program:</b> {program_name}"
                                    }
                                },
                                {
                                    "dateTimePicker": {
                                        "name": "session_date",
                                        "label": "Attendance date",
                                        "type": "DATE_ONLY",
                                    }
                                },
                                {
                                    "textInput": {
                                        "name": "meeting_topic",
                                        "label": "Meeting topic (optional)",
                                        "type": "SINGLE_LINE",
                                        "hintText": "Leave blank to use the date",
                                    }
                                },
                                {
                                    "selectionInput": {
                                        "name": "start_time",
                                        "label": "Session start time",
                                        "type": "DROP_DOWN",
                                        "items": start_items,
                                    }
                                },
                                {
                                    "selectionInput": {
                                        "name": "end_time",
                                        "label": "Session end time",
                                        "type": "DROP_DOWN",
                                        "items": end_items,
                                    }
                                },
                                {
                                    "buttonList": {
                                        "buttons": [
                                            {
                                                "text": "Load learners",
                                                "onClick": {
                                                    "action": {
                                                        "function": "load_learners",
                                                        "parameters": [
                                                            {
                                                                "key": "program_id",
                                                                "value": program_id,
                                                            },
                                                            {
                                                                "key": "program_name",
                                                                "value": program_name,
                                                            },
                                                        ],
                                                    }
                                                },
                                            }
                                        ]
                                    }
                                },
                            ]
                        }
                    ],
                },
            }
        ]
    }


def learner_checklist_card(
    *,
    program_id: str,
    program_name: str,
    session_date: str,
    meeting_topic: str,
    start_time: str,
    end_time: str,
    learners: Sequence[dict[str, str]],
) -> dict[str, Any]:
    items = [
        {
            "text": learner["display_name"],
            "value": learner["id"],
            "selected": False,
        }
        for learner in learners
    ]
    all_ids = ",".join(learner["id"] for learner in learners)
    return {
        "cardsV2": [
            {
                "cardId": "manualAttendanceLearners",
                "card": {
                    "header": {
                        "title": "Manual Attendance",
                        "subtitle": "Step 3 of 3 — Mark absents",
                    },
                    "sections": [
                        {
                            "widgets": [
                                {
                                    "textParagraph": {
                                        "text": (
                                            f"<b>Program:</b> {program_name}<br>"
                                            f"<b>Date:</b> {session_date}<br>"
                                            f"<b>Topic:</b> {meeting_topic}<br>"
                                            f"<b>Time:</b> {start_time} – {end_time}<br><br>"
                                            "Check learners who were <b>ABSENT</b>. "
                                            "Everyone else will be marked present."
                                        )
                                    }
                                },
                                {
                                    "selectionInput": {
                                        "name": "absent_learners",
                                        "label": "Absent learners",
                                        "type": "CHECK_BOX",
                                        "items": items,
                                    }
                                },
                                {
                                    "buttonList": {
                                        "buttons": [
                                            {
                                                "text": "Submit attendance",
                                                "onClick": {
                                                    "action": {
                                                        "function": "submit_attendance",
                                                        "parameters": [
                                                            {
                                                                "key": "program_id",
                                                                "value": program_id,
                                                            },
                                                            {
                                                                "key": "program_name",
                                                                "value": program_name,
                                                            },
                                                            {
                                                                "key": "session_date",
                                                                "value": session_date,
                                                            },
                                                            {
                                                                "key": "meeting_topic",
                                                                "value": meeting_topic,
                                                            },
                                                            {
                                                                "key": "start_time",
                                                                "value": start_time,
                                                            },
                                                            {
                                                                "key": "end_time",
                                                                "value": end_time,
                                                            },
                                                            {
                                                                "key": "all_learner_ids",
                                                                "value": all_ids,
                                                            },
                                                        ],
                                                    }
                                                },
                                            }
                                        ]
                                    }
                                },
                            ]
                        }
                    ],
                },
            }
        ]
    }


def success_card(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "cardsV2": [
            {
                "cardId": "manualAttendanceSuccess",
                "card": {
                    "header": {
                        "title": "Manual Attendance recorded",
                        "subtitle": result.get("program_name", ""),
                    },
                    "sections": [
                        {
                            "widgets": [
                                {
                                    "textParagraph": {
                                        "text": (
                                            f"<b>Date:</b> {result.get('session_date')}<br>"
                                            f"<b>Topic:</b> {result.get('meeting_topic')}<br>"
                                            f"<b>Meeting ID:</b> {result.get('meeting_id')}<br>"
                                            f"<b>Present:</b> {result.get('present_count')}<br>"
                                            f"<b>Inserted:</b> {result.get('inserted_count')}<br>"
                                            f"<b>Duplicates skipped:</b> "
                                            f"{result.get('skipped_duplicates')}<br>"
                                            f"<b>Absent (not inserted):</b> "
                                            f"{result.get('absent_count')}<br>"
                                            f"<b>Total learners:</b> "
                                            f"{result.get('total_learners')}<br>"
                                            f"<b>Account:</b> offline session"
                                        )
                                    }
                                }
                            ]
                        }
                    ],
                },
            }
        ]
    }


def parse_time_hhmm(value: str) -> time:
    """Parse HH:MM into a time object."""
    hour_str, minute_str = value.split(":")
    return time(hour=int(hour_str), minute=int(minute_str))
