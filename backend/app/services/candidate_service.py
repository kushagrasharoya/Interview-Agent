"""
candidate_service.py

This file is responsible for everything related to reading
candidates.json.

Why this file exists:
We don't want every part of the app to know *how* candidate data is
stored (a JSON file, on disk, at a specific path). Instead, other code
just asks this file simple questions like "load all candidates" or
"find candidate CAND-001". If we ever changed candidates.json to a
database, only this file would need to change.

Nothing here modifies candidates.json. We only ever read it.
"""

import json
from functools import lru_cache

from app.config import CANDIDATES_FILE
from app.models.candidate import Candidate


@lru_cache(maxsize=1)
def load_candidates() -> list[Candidate]:
    """
    Read candidates.json from disk and convert every entry into a
    validated Candidate object.

    @lru_cache means this only actually reads the file once; repeated
    calls reuse the same in-memory result instead of re-reading disk
    every time. This is safe because we never modify the file.
    """
    with open(CANDIDATES_FILE, "r", encoding="utf-8") as f:
        raw = json.load(f)

    candidates_raw = raw["candidates"]
    return [Candidate.model_validate(item) for item in candidates_raw]


def get_candidate_by_id(candidate_id: str) -> Candidate | None:
    """
    Find one candidate by their member.id (e.g. "CAND-001").

    Returns None if no candidate with that id exists, so callers can
    decide how to handle a missing candidate instead of the app
    crashing.
    """
    for candidate in load_candidates():
        if candidate.member.id == candidate_id:
            return candidate
    return None
