"""Insert present-only manual attendance from a GitHub repository_dispatch payload."""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from manual_attendance.cards import parse_time_hhmm
from manual_attendance.db_queries import submit_present_attendance
from manual_attendance.submissions_log import record_submission

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)


def _load_payload() -> dict:
    raw = os.environ.get("CLIENT_PAYLOAD", "").strip()
    if raw:
        return json.loads(raw)

    if len(sys.argv) > 1:
        path = Path(sys.argv[1])
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            raise SystemExit(
                f"Payload file is empty: {path}. "
                "Check the workflow Write payload step / repository_dispatch client_payload."
            )
        return json.loads(text)

    raise SystemExit("CLIENT_PAYLOAD env var (or JSON file arg) is required")


def main() -> None:
    payload = _load_payload()
    logger.info("Received manual attendance payload keys=%s", sorted(payload.keys()))

    program_id = payload["program_id"]
    program_name = payload.get("program_name") or program_id
    session_date = payload["session_date"]
    meeting_topic = payload.get("meeting_topic") or session_date
    start_time = payload["start_time"]
    end_time = payload["end_time"]
    all_learner_ids = payload.get("all_learner_ids") or []
    absent_learner_ids = payload.get("absent_learner_ids") or []
    submitted_by = str(payload.get("submitted_by") or "").strip()

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

    if result.get("meeting_id"):
        record_submission(
            meeting_id=str(result["meeting_id"]),
            submitted_by=submitted_by,
            meeting_topic=meeting_topic,
            program_name=program_name,
        )
        result["submitted_by"] = submitted_by or None

    print("✅ Manual attendance saved")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
