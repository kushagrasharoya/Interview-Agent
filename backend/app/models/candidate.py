"""
candidate.py (models)

This file defines what a "candidate" is allowed to look like.

Why this file exists:
candidates.json is just text on disk. Before we trust that text and use
it inside our app, we want to check it actually has the shape we expect
(a name, a job role, a list of missions, etc). Pydantic does that check
for us automatically.

These classes are "shape descriptions", not logic. They don't calculate
anything. Other files (services, api) import these classes and use them.
"""

from typing import Optional
from pydantic import BaseModel


class CandidateMember(BaseModel):
    """The 'member' block inside a candidate record: who this person is."""

    id: str
    name: str
    jobRole: str
    yearsExperience: int
    education: str
    status: str


class CandidateMission(BaseModel):
    """
    One entry from the candidate's 'missions' list.

    A mission represents one curriculum day the candidate attempted.
    Not every field is present on every mission:
    - a completed mission has "passed" and "attempts"
    - a skipped mission has "skipped": true instead

    That's why "passed", "attempts", and "skipped" are all Optional
    below: Pydantic will accept the field being missing.
    """

    day: int
    title: str
    passed: Optional[bool] = None
    attempts: Optional[int] = None
    skipped: Optional[bool] = None


class CandidateSignals(BaseModel):
    """Summary numbers about the candidate's overall engagement."""

    commitDays: int
    missionsCompleted: int
    missionsFirstTry: int


class Candidate(BaseModel):
    """
    A full candidate record, matching one entry in candidates.json's
    "candidates" list.

    This is the object the frontend/technical-spec calls "candidate" in
    the very first POST /api/interview request.
    """

    member: CandidateMember
    missions: list[CandidateMission]
    signals: CandidateSignals
