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
      AND (d.intent IS NULL OR d.intent = 'Learning')
    ORDER BY l.text
"""

# Enrollment path (from Metabase):
# labels -> deployment_labels -> deployments -> progress -> users
LEARNERS_SQL = """
    SELECT DISTINCT
        u.id,
        COALESCE(
            NULLIF(
                TRIM(
                    CONCAT(
                        COALESCE(u.first_name, ''),
                        ' ',
                        COALESCE(u.last_name, '')
                    )
                ),
                ''
            ),
            NULLIF(TRIM(u.email), ''),
            u.id
        ) AS display_name
    FROM labels l
    JOIN deployment_labels dl
        ON dl.label_id = l.id
    JOIN deployments d
        ON d.id = dl.deployment_id
    JOIN progress p
        ON p.deployment_id = d.id
    JOIN users u
        ON u.id = p.user_id
    WHERE l.id = %s
      AND d.start_timestamp >= CURRENT_DATE - INTERVAL '3 months'
      AND (d.intent IS NULL OR d.intent = 'Learning')
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


RECENT_MANUAL_SESSIONS_SQL = """
    SELECT
        a.meeting_id,
        COALESCE(a.meeting_topic, '') AS meeting_topic,
        MIN(a.scheduled_from) AS session_start,
        MAX(a.scheduled_to) AS session_end,
        COUNT(*) AS present_count
    FROM public.attendance a
    WHERE a.zoom_account_id = %s
       OR a.meeting_id LIKE 'MANUAL-%%'
    GROUP BY a.meeting_id, a.meeting_topic
    ORDER BY MIN(a.scheduled_from) DESC NULLS LAST
    LIMIT %s
"""


def fetch_recent_manual_sessions(limit: int = 30) -> list[dict[str, Any]]:
    """Return recent offline/manual attendance sessions for the web UI."""
    limit = max(1, min(int(limit), 100))
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(RECENT_MANUAL_SESSIONS_SQL, (OFFLINE_ZOOM_ACCOUNT_ID, limit))
            rows = cur.fetchall()
            sessions: list[dict[str, Any]] = []
            for row in rows:
                meeting_id = str(row[0] or "")
                topic = str(row[1] or "")
                start = row[2]
                end = row[3]
                present_count = int(row[4] or 0)
                program_name = ""
                if "-ILT-" in topic:
                    program_name = topic.split("-ILT-", 1)[0]
                sessions.append(
                    {
                        "meeting_id": meeting_id,
                        "meeting_topic": topic,
                        "program_name": program_name,
                        "session_start": start.isoformat() if start else None,
                        "session_end": end.isoformat() if end else None,
                        "present_count": present_count,
                    }
                )
            logger.info("Fetched %d recent manual sessions", len(sessions))
            return sessions
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
