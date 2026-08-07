"""Shared database helpers for Zoom and Manual attendance flows."""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime
from typing import Any, Optional

import psycopg2
from psycopg2.extensions import connection as PgConnection
from psycopg2.extensions import cursor as PgCursor

logger = logging.getLogger(__name__)

CHECK_ATTENDANCE_SQL = """
    SELECT 1
    FROM public.attendance
    WHERE user_id=%s
      AND meeting_id=%s
      AND joined_at=%s
      AND left_at=%s
    LIMIT 1;
"""

INSERT_ATTENDANCE_SQL = """
    INSERT INTO public.attendance
    (
        id,
        user_id,
        meeting_id,
        joined_at,
        left_at,
        meeting_topic,
        scheduled_from,
        scheduled_to,
        zoom_account_id
    )
    VALUES
    (
        %s,%s,%s,%s,%s,%s,%s,%s,%s
    );
"""


def get_db_config() -> dict[str, Any]:
    """Load DB config from environment (same vars as Zoom automation)."""
    return {
        "host": os.environ["HOST"],
        "port": int(os.environ.get("PORT", 5432)),
        "dbname": os.environ["DBNAME"],
        "user": os.environ["USER"],
        "password": os.environ["PASSWORD"],
    }


def get_connection() -> PgConnection:
    """Open a new Postgres connection."""
    config = get_db_config()
    logger.info(
        "Connecting to database host=%s dbname=%s",
        config["host"],
        config["dbname"],
    )
    return psycopg2.connect(**config)


def get_internal_user_id(cur: PgCursor, email: Optional[str]) -> Optional[str]:
    """Resolve an email to an internal users.id."""
    if not email:
        return None

    cur.execute(
        """
        SELECT id
        FROM public.users
        WHERE LOWER(email)=LOWER(%s)
        LIMIT 1
        """,
        (email,),
    )
    row = cur.fetchone()
    return row[0] if row else None


def attendance_exists(
    cur: PgCursor,
    *,
    user_id: str,
    meeting_id: str,
    joined_at: datetime,
    left_at: datetime,
) -> bool:
    """Return True if an identical attendance row already exists."""
    cur.execute(
        CHECK_ATTENDANCE_SQL,
        (user_id, meeting_id, joined_at, left_at),
    )
    return cur.fetchone() is not None


def insert_attendance(
    cur: PgCursor,
    *,
    user_id: str,
    meeting_id: str,
    joined_at: datetime,
    left_at: datetime,
    meeting_topic: str,
    scheduled_from: datetime,
    scheduled_to: datetime,
    zoom_account_id: str,
    attendance_id: Optional[str] = None,
    skip_if_exists: bool = True,
) -> bool:
    """
    Insert one attendance row.

    When skip_if_exists is True (default), duplicates matching
    (user_id, meeting_id, joined_at, left_at) are skipped.

    Returns True if a row was inserted, False if skipped.
    """
    if skip_if_exists and attendance_exists(
        cur,
        user_id=user_id,
        meeting_id=meeting_id,
        joined_at=joined_at,
        left_at=left_at,
    ):
        return False

    cur.execute(
        INSERT_ATTENDANCE_SQL,
        (
            attendance_id or str(uuid.uuid4()),
            user_id,
            meeting_id,
            joined_at,
            left_at,
            meeting_topic,
            scheduled_from,
            scheduled_to,
            zoom_account_id,
        ),
    )
    return True
