"""
curriculum_service.py

This file is responsible for everything related to reading
curriculum.json.

Why this file exists:
Same idea as candidate_service.py: this is the one place that knows
how curriculum.json is structured. Other code just asks "what is day
7 about?" instead of reading and searching the JSON file itself.

We keep curriculum entries as plain Python dictionaries (not Pydantic
models) for Part 1. The data is only ever read, never edited by our
app, and Part 2 mainly needs to read fields like "objectives" and
"tools" out of it rather than validate strict types.
"""

import json
from functools import lru_cache
from typing import Any


@lru_cache(maxsize=1)
def _load_curriculum_raw() -> dict[str, Any]:
    """Read curriculum.json from disk exactly once and cache it."""
    from app.config import CURRICULUM_FILE

    with open(CURRICULUM_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def get_cohort_name() -> str:
    """Return the top-level cohort description string."""
    return _load_curriculum_raw()["cohort"]


def get_modules() -> list[dict[str, Any]]:
    """Return the list of modules (each with a number, title, day range)."""
    return _load_curriculum_raw()["modules"]


def get_all_days() -> list[dict[str, Any]]:
    """Return every curriculum day entry."""
    return _load_curriculum_raw()["days"]


def get_day(day_number: int) -> dict[str, Any] | None:
    """
    Find one curriculum day by its day number (e.g. 7).

    Returns None if the day number doesn't exist in curriculum.json.
    """
    for day in get_all_days():
        if day["day"] == day_number:
            return day
    return None


def get_module_for_day(day_number: int) -> dict[str, Any] | None:
    """
    Find which module a given day belongs to, by checking each
    module's [start_day, end_day] range.
    """
    for module in get_modules():
        start_day, end_day = module["days"]
        if start_day <= day_number <= end_day:
            return module
    return None
