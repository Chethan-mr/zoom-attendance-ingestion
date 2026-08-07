"""Build a JSON cache of programs + learners for the Apps Script Chat app."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from manual_attendance.db_queries import fetch_learners_for_program, fetch_programs

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)

DEFAULT_OUTPUT = Path("data/manual_attendance_cache.json")


def build_cache() -> dict:
    programs = fetch_programs()
    learners_by_program: dict[str, list[dict[str, str]]] = {}

    for program in programs:
        program_id = program["id"]
        try:
            learners_by_program[program_id] = fetch_learners_for_program(program_id)
        except Exception:
            logger.exception("Failed fetching learners for program_id=%s", program_id)
            learners_by_program[program_id] = []

    return {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "programs": programs,
        "learners_by_program": learners_by_program,
    }


def main() -> None:
    output = Path(os.environ.get("CACHE_OUTPUT", str(DEFAULT_OUTPUT)))
    output.parent.mkdir(parents=True, exist_ok=True)

    cache = build_cache()
    output.write_text(json.dumps(cache, indent=2), encoding="utf-8")

    logger.info(
        "Wrote cache to %s (%d programs)",
        output,
        len(cache["programs"]),
    )
    print(f"✅ Cache written: {output} ({len(cache['programs'])} programs)")


if __name__ == "__main__":
    main()
