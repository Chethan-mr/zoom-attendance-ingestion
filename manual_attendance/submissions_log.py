"""Persist who submitted each manual attendance session (by meeting_id)."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_SUBMISSIONS_PATH = Path("data/manual_attendance_submissions.json")


def load_submissions(path: Path | None = None) -> dict[str, Any]:
    file_path = path or DEFAULT_SUBMISSIONS_PATH
    if not file_path.exists():
        return {}
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        logger.exception("Failed reading submissions log %s", file_path)
        return {}


def record_submission(
    *,
    meeting_id: str,
    submitted_by: str,
    meeting_topic: str = "",
    program_name: str = "",
    path: Path | None = None,
) -> dict[str, Any]:
    """Upsert one submission record keyed by meeting_id."""
    file_path = path or DEFAULT_SUBMISSIONS_PATH
    file_path.parent.mkdir(parents=True, exist_ok=True)
    data = load_submissions(file_path)
    email = (submitted_by or "").strip().lower()
    data[meeting_id] = {
        "submitted_by": email,
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "meeting_topic": meeting_topic,
        "program_name": program_name,
    }
    file_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    logger.info("Recorded submission meeting_id=%s by=%s", meeting_id, email or "(unknown)")
    return data[meeting_id]


def merge_submitted_by(
    sessions: list[dict[str, Any]],
    path: Path | None = None,
) -> list[dict[str, Any]]:
    """Attach submitted_by onto recent session dicts when known."""
    submissions = load_submissions(path)
    if not submissions:
        return sessions
    merged: list[dict[str, Any]] = []
    for session in sessions:
        item = dict(session)
        meeting_id = str(item.get("meeting_id") or "")
        meta = submissions.get(meeting_id) or {}
        if meta.get("submitted_by"):
            item["submitted_by"] = meta["submitted_by"]
        merged.append(item)
    return merged
