"""
session.py (models)

This file defines what an "interview session" looks like while it is
in progress.

Why this file exists:
A single POST /api/interview request only carries one message. But an
interview is a *conversation* that spans many requests. Something has
to remember "who is this candidate", "what have we asked so far", and
"how is the interview going" between one request and the next. That
"memory" is the InterviewSession object defined here.

This file only describes the shape of that memory. The actual storing
and retrieving of sessions happens in services/session_service.py.
"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field

from app.models.candidate import Candidate


class Speaker(str, Enum):
    """Who said a given line in the conversation."""

    INTERVIEWER = "interviewer"
    CANDIDATE = "candidate"


class ConversationTurn(BaseModel):
    """One line of dialogue in the interview transcript."""

    speaker: Speaker
    text: str


class InterviewStatus(str, Enum):
    """The lifecycle stage of an interview session."""

    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class InterviewSession(BaseModel):
    """
    The full state of one candidate's interview.

    Part 1 only creates and stores this object. Part 2 (the AI
    Interview Brain) will be the piece that actually reads and updates
    fields like current_topic, evaluations, strengths, and gaps based
    on the candidate's answers.
    """

    session_id: str

    # The candidate this session belongs to. Set once, at session start.
    candidate: Candidate

    # Every line said so far, in order. This is how "conversation
    # context" is maintained across multiple HTTP requests.
    conversation_history: list[ConversationTurn] = Field(default_factory=list)

    # How many interview questions have been asked so far.
    # The hackathon spec requires at least 8 by the end of the interview.
    question_count: int = 0

    # Which curriculum days (by day number) have already been asked
    # about. The hackathon spec requires at least 4 distinct days.
    covered_curriculum_days: list[int] = Field(default_factory=list)

    # What topic/day the interviewer is currently focused on.
    # None until Part 2 picks the first topic.
    current_topic: Optional[str] = None

    # A simple difficulty label the AI brain can adjust over time.
    # Kept as a plain string for now; Part 2 decides the real values
    # (e.g. "easy", "medium", "hard").
    current_difficulty: str = "medium"

    # Whether the interview is still going or has finished.
    status: InterviewStatus = InterviewStatus.IN_PROGRESS

    # Placeholders for Part 2/3 to fill in as answers are evaluated.
    # Part 1 leaves these empty; no AI evaluation happens yet.
    evaluations: list[dict] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
