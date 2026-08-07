"""
Google Chat HTTP webhook for Manual Attendance.

Deploy this Flask app as the Chat app HTTPS endpoint.
Uses the same DB env vars as Zoom automation (GitHub environment: DB),
plus optional GOOGLE_WEBHOOKS.
"""

from __future__ import annotations

import logging
import os
import re
from datetime import date, datetime, timezone
from typing import Any, Optional

import requests
from flask import Flask, jsonify, request

from manual_attendance.cards import (
    error_card,
    learner_checklist_card,
    parse_time_hhmm,
    program_selection_card,
    session_details_card,
    success_card,
    text_message,
)
from manual_attendance.db_queries import (
    fetch_learners_for_program,
    fetch_programs,
    submit_present_attendance,
)

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

START_COMMANDS = {"hi", "/attendance", "attendance", "manual attendance"}


def _normalize_text(text: Optional[str]) -> str:
    if not text:
        return ""
    # Strip @mentions like "@Manual Attendance hi"
    cleaned = re.sub(r"@\S+", "", text).strip().lower()
    return cleaned


def _is_start_command(text: Optional[str]) -> bool:
    normalized = _normalize_text(text)
    return normalized in START_COMMANDS or normalized.startswith("/attendance")


def _form_string(form_inputs: dict[str, Any], name: str) -> Optional[str]:
    field = form_inputs.get(name) or {}
    values = (field.get("stringInputs") or {}).get("value") or []
    if not values:
        return None
    return str(values[0])


def _form_strings(form_inputs: dict[str, Any], name: str) -> list[str]:
    field = form_inputs.get(name) or {}
    values = (field.get("stringInputs") or {}).get("value") or []
    return [str(v) for v in values]


def _form_date(form_inputs: dict[str, Any], name: str) -> Optional[date]:
    field = form_inputs.get(name) or {}
    date_input = field.get("dateInput") or {}
    ms = date_input.get("msSinceEpoch")
    if ms is None:
        return None
    try:
        ts = int(ms) / 1000.0
        return datetime.fromtimestamp(ts, tz=timezone.utc).date()
    except (TypeError, ValueError, OSError):
        logger.warning("Invalid date input for %s: %s", name, ms)
        return None


def _action_params(event: dict[str, Any]) -> dict[str, str]:
    params: dict[str, str] = {}
    for item in (event.get("common") or {}).get("parameters") or []:
        if isinstance(item, dict) and "key" in item:
            params[str(item["key"])] = str(item.get("value", ""))
    for item in (event.get("action") or {}).get("parameters") or []:
        if isinstance(item, dict) and "key" in item:
            params[str(item["key"])] = str(item.get("value", ""))
    return params


def _invoke_function(event: dict[str, Any]) -> str:
    common = event.get("common") or {}
    if common.get("invokedFunction"):
        return str(common["invokedFunction"])
    action = event.get("action") or {}
    if action.get("actionMethodName"):
        return str(action["actionMethodName"])
    if action.get("function"):
        return str(action["function"])
    return ""


def _notify_google_webhooks(text: str) -> None:
    """Optionally post a plain-text success notice to configured space webhooks."""
    raw = os.environ.get("GOOGLE_WEBHOOKS", "").strip()
    if not raw:
        return

    urls = [u.strip() for u in raw.split(",") if u.strip()]
    for url in urls:
        try:
            resp = requests.post(url, json={"text": text}, timeout=15)
            resp.raise_for_status()
            logger.info("Posted success notice to GOOGLE_WEBHOOKS endpoint")
        except Exception:
            logger.exception("Failed posting to GOOGLE_WEBHOOKS url=%s", url)


def start_manual_attendance() -> dict[str, Any]:
    try:
        programs = fetch_programs()
    except Exception:
        logger.exception("Failed fetching programs")
        return error_card(
            "Could not load programs from the database. "
            "Check DB environment variables and try again."
        )

    if not programs:
        return error_card(
            "No programs found with deployments in the last 3 months."
        )

    return program_selection_card(programs)


def handle_select_program(event: dict[str, Any]) -> dict[str, Any]:
    form_inputs = (event.get("common") or {}).get("formInputs") or {}
    program_id = _form_string(form_inputs, "program_id")
    if not program_id:
        return error_card("Please select a program before continuing.")

    try:
        programs = fetch_programs()
    except Exception:
        logger.exception("Failed fetching programs after selection")
        return error_card("Could not reload programs. Please try again.")

    program_name = next(
        (p["text"] for p in programs if p["id"] == program_id),
        program_id,
    )
    logger.info("Program selected id=%s name=%s", program_id, program_name)
    return session_details_card(program_id=program_id, program_name=program_name)


def handle_load_learners(event: dict[str, Any]) -> dict[str, Any]:
    form_inputs = (event.get("common") or {}).get("formInputs") or {}
    params = _action_params(event)

    program_id = params.get("program_id") or _form_string(form_inputs, "program_id")
    program_name = params.get("program_name") or program_id or "Program"
    if not program_id:
        return error_card("Missing program. Please restart with `hi` or `/attendance`.")

    session_day = _form_date(form_inputs, "session_date")
    if session_day is None:
        return error_card("Please select an attendance date.")

    start_time = _form_string(form_inputs, "start_time")
    end_time = _form_string(form_inputs, "end_time")
    if not start_time or not end_time:
        return error_card("Please select both start and end times from the dropdowns.")

    try:
        start_t = parse_time_hhmm(start_time)
        end_t = parse_time_hhmm(end_time)
    except Exception:
        return error_card("Invalid time selection. Please use the time dropdowns.")

    if end_t <= start_t:
        return error_card("End time must be after start time.")

    topic = (_form_string(form_inputs, "meeting_topic") or "").strip()
    session_date = session_day.isoformat()
    meeting_topic = topic or session_date

    try:
        learners = fetch_learners_for_program(program_id)
    except Exception:
        logger.exception("Failed fetching learners for program_id=%s", program_id)
        return error_card(
            "Could not load learners for this program. "
            "Verify enrollment tables (deployment_users) and try again."
        )

    if not learners:
        return error_card(
            f"No learners found for program <b>{program_name}</b> "
            "in deployments from the last 3 months."
        )

    return learner_checklist_card(
        program_id=program_id,
        program_name=program_name,
        session_date=session_date,
        meeting_topic=meeting_topic,
        start_time=start_time,
        end_time=end_time,
        learners=learners,
    )


def handle_submit_attendance(event: dict[str, Any]) -> dict[str, Any]:
    form_inputs = (event.get("common") or {}).get("formInputs") or {}
    params = _action_params(event)

    program_id = params.get("program_id")
    program_name = params.get("program_name") or program_id or "Program"
    session_date = params.get("session_date")
    meeting_topic = params.get("meeting_topic") or session_date or ""
    start_time = params.get("start_time")
    end_time = params.get("end_time")
    all_ids_raw = params.get("all_learner_ids") or ""

    if not all([program_id, session_date, start_time, end_time]):
        return error_card(
            "Missing session details. Please restart with `hi` or `/attendance`."
        )

    all_learner_ids = [x for x in all_ids_raw.split(",") if x]
    absent_learner_ids = _form_strings(form_inputs, "absent_learners")

    try:
        session_day = date.fromisoformat(session_date)
        start_t = parse_time_hhmm(start_time)
        end_t = parse_time_hhmm(end_time)
        session_start = datetime(
            session_day.year,
            session_day.month,
            session_day.day,
            start_t.hour,
            start_t.minute,
            tzinfo=timezone.utc,
        )
        session_end = datetime(
            session_day.year,
            session_day.month,
            session_day.day,
            end_t.hour,
            end_t.minute,
            tzinfo=timezone.utc,
        )
    except Exception:
        logger.exception("Invalid session datetime on submit")
        return error_card("Invalid session date/time. Please restart the flow.")

    if session_end <= session_start:
        return error_card("End time must be after start time.")

    if not all_learner_ids:
        return error_card("No learners were available to mark attendance for.")

    try:
        result = submit_present_attendance(
            program_id=program_id,
            program_name=program_name,
            session_date=session_date,
            meeting_topic=meeting_topic,
            session_start=session_start,
            session_end=session_end,
            all_learner_ids=all_learner_ids,
            absent_learner_ids=absent_learner_ids,
        )
    except ValueError as exc:
        return error_card(str(exc))
    except Exception:
        logger.exception("Manual attendance submit failed")
        return error_card(
            "Failed to save attendance. Check database connectivity and try again."
        )

    notice = (
        f"Manual attendance saved for {result['program_name']} on "
        f"{result['session_date']}: {result['present_count']} present, "
        f"{result['absent_count']} absent (not inserted)."
    )
    _notify_google_webhooks(notice)
    logger.info(notice)
    return success_card(result)


def handle_card_click(event: dict[str, Any]) -> dict[str, Any]:
    function_name = _invoke_function(event)
    logger.info("CARD_CLICKED function=%s", function_name)

    if function_name == "select_program":
        return handle_select_program(event)
    if function_name == "load_learners":
        return handle_load_learners(event)
    if function_name == "submit_attendance":
        return handle_submit_attendance(event)

    return error_card(f"Unknown action: {function_name or '(none)'}")


def handle_message(event: dict[str, Any]) -> dict[str, Any]:
    message = event.get("message") or {}
    text = message.get("argumentText") or message.get("text") or ""
    logger.info("MESSAGE received text=%r", text)

    if _is_start_command(text):
        return start_manual_attendance()

    return text_message(
        "Send `hi` or `/attendance` to start Manual Attendance."
    )


@app.route("/", methods=["POST"])
@app.route("/chat", methods=["POST"])
def chat_webhook():
    event = request.get_json(silent=True) or {}
    event_type = event.get("type")
    logger.info("Chat event type=%s", event_type)

    try:
        if event_type == "ADDED_TO_SPACE":
            body = text_message(
                "Manual Attendance ready. Send `hi` or `/attendance` to begin."
            )
        elif event_type == "MESSAGE":
            body = handle_message(event)
        elif event_type == "CARD_CLICKED":
            body = handle_card_click(event)
        else:
            body = {}
    except Exception:
        logger.exception("Unhandled Chat webhook error")
        body = error_card("Unexpected error while processing your request.")

    return jsonify(body)


@app.route("/healthz", methods=["GET"])
def healthz():
    return jsonify({"status": "ok", "service": "manual-attendance-chat"})


def main():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
