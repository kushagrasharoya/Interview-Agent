"""
engine_models.py (models)

This file defines the "shape" of the Interview Engine's internal
state (Part 3).

Why this is a SEPARATE file from session.py and ai_models.py:
Part 1's InterviewSession (session.py) and Part 2's InterviewContext
(ai_models.py) are both left completely untouched in Part 3 - same
rule we followed in Part 2. EngineSession below WRAPS an
InterviewContext and adds the few extra pieces the engine specifically
needs to run a full interview end-to-end: the plan of which curriculum
days to visit, a pointer into that plan, the question currently
awaiting an answer, and the final feedback once the interview ends.

Nothing here contains logic - the actual orchestration lives in
app/services/interview_engine.py.
"""

from typing import Optional
from pydantic import BaseModel, Field

from app.models.ai_models import CandidateAnalysis, FinalFeedback, GeneratedQuestion, InterviewContext


class EngineSession(BaseModel):
    """
    The Interview Engine's full working state for one interview,
    keyed by sessionId (same id used everywhere else in the project).
    """

    session_id: str

    # Computed once at interview start (see app/ai/candidate_analyzer.py).
    analysis: CandidateAnalysis

    # Part 2's "brain memory": conversation history, questions asked,
    # covered days, evaluations, etc. The engine reads and updates this
    # on every turn.
    context: InterviewContext

    # The ordered list of curriculum days the interview plans to visit,
    # chosen by the candidate analyzer to guarantee good topic
    # diversity. `focus_day_index` points at the next unused entry.
    focus_days: list[int] = Field(default_factory=list)
    focus_day_index: int = 0

    # Topic labels (not day numbers) covered so far, for readability /
    # matching the "topicsCovered" field the spec describes.
    topics_covered: list[str] = Field(default_factory=list)

    # The question the candidate is currently expected to answer.
    # None only before the first question has been generated.
    current_question: Optional[GeneratedQuestion] = None

    # Whether the interview has concluded.
    done: bool = False

    # Set once, when the interview ends.
    final_feedback: Optional[FinalFeedback] = None
