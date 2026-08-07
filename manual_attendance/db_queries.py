"""Database queries for Manual Attendance (programs, learners, present inserts)."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Iterable, Sequence

from db import get_connection, insert_attendance

logger = logging.getLogger(__name__)

OFFLINE_ZOOM_ACCOUNT_ID = "offline session"

PROGRAMS_SQL = """
    SELECT DISTINCT
        l.id,
        l.text
    FROM labels l
    JOIN deployment_labels dl
        ON dl.label_id = l.id
    JOIN deployments d
        ON d.id = dl.deployment_id
    WHERE d.start_timestamp >= CURRENT_DATE - INTERVAL '3 months'
    ORDER BY l.text
"""

LEARNERS_SQL = """
    SELECT DISTINCT
        u.id,
        COALESCE(NULLIF(TRIM(u.name), ''), u.email, u.id) AS display_name
    FROM deployments d
    JOIN deployment_labels dl
        ON dl.deployment_id = d.id
    JOIN deployment_users du
        ON du.deployment_id = d.id
    JOIN users u
        ON u.id = du.user_id
    WHERE dl.label_id = %s
      AND d.start_timestamp >= CURRENT_DATE - INTERVAL '3 months'
    ORDER BY display_name
"""


def fetch_programs() -> list[dict[str, str]]:
    """Return active programs (labels) tied to deployments in the last 3 months."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(PROGRAMS_SQL)
            rows = cur.fetchall()
            programs = [{"id": str(row[0]), "text": str(row[1])} for row in rows]
            logger.info("Fetched %d programs for manual attendance", len(programs))
            return programs
    finally:
        conn.close()


def fetch_learners_for_program(program_id: str) -> list[dict[str, str]]:
    """Return enrolled learners for deployments of the selected program."""
    if not program_id:
        raise ValueError("program_id is required")

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(LEARNERS_SQL, (program_id,))
            rows = cur.fetchall()
            learners = [
                {"id": str(row[0]), "display_name": str(row[1])} for row in rows
            ]
            logger.info(
                "Fetched %d learners for program_id=%s",
                len(learners),
                program_id,
            )
            return learners
    finally:
        conn.close()


def build_meeting_id(program_id: str, session_start: datetime) -> str:
    """Build a deterministic manual meeting id."""
    return (
        f"MANUAL-{program_id}-"
        f"{session_start.strftime('%Y%m%d')}-"
        f"{session_start.strftime('%H%M')}"
    )


def submit_present_attendance(
    *,
    program_id: str,
    program_name: str,
    session_date: str,
    meeting_topic: str,
    session_start: datetime,
    session_end: datetime,
    all_learner_ids: Sequence[str],
    absent_learner_ids: Iterable[str],
) -> dict[str, Any]:
    """
    Insert attendance only for PRESENT learners.

    Present = all_learner_ids - absent_learner_ids.
    Absent learners are never written to public.attendance.
    """
    if session_end <= session_start:
        raise ValueError("End time must be after start time")

    absent_set = {str(x) for x in absent_learner_ids}
    present_ids = [str(uid) for uid in all_learner_ids if str(uid) not in absent_set]

    topic = (meeting_topic or "").strip() or session_date
    meeting_id = build_meeting_id(program_id, session_start)

    logger.info(
        "Submitting manual attendance program=%s (%s) date=%s "
        "present=%d absent=%d meeting_id=%s",
        program_name,
        program_id,
        session_date,
        len(present_ids),
        len(absent_set),
        meeting_id,
    )

    inserted = 0
    skipped = 0

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            for user_id in present_ids:
                was_inserted = insert_attendance(
                    cur,
                    user_id=user_id,
                    meeting_id=meeting_id,
                    joined_at=session_start,
                    left_at=session_end,
                    meeting_topic=topic,
                    scheduled_from=session_start,
                    scheduled_to=session_end,
                    zoom_account_id=OFFLINE_ZOOM_ACCOUNT_ID,
                )
                if was_inserted:
                    inserted += 1
                else:
                    skipped += 1
        conn.commit()
    except Exception:
        conn.rollback()
        logger.exception("Failed to insert manual attendance rows")
        raise
    finally:
        conn.close()

    return {
        "meeting_id": meeting_id,
        "meeting_topic": topic,
        "present_count": len(present_ids),
        "inserted_count": inserted,
        "skipped_duplicates": skipped,
        "absent_count": len(absent_set),
        "total_learners": len(all_learner_ids),
        "program_name": program_name,
        "session_date": session_date,
    }
