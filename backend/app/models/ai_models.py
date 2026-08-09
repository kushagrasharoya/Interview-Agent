"""
ai_models.py (models)

This file defines the "shapes" used by the AI Interview Brain (Part 2).

Why this is a SEPARATE file from candidate.py / session.py:
Those two files belong to Part 1 and are left completely untouched.
Everything Part 2 needs that didn't already exist goes here instead,
so we never risk breaking anything Part 1 already relies on.

Just like candidate.py and session.py, this file only describes shapes.
It contains no logic - the actual thinking happens in the files under
app/ai/.
"""

from enum import Enum
from typing import Literal, Optional
from pydantic import BaseModel, Field

from app.models.candidate import Candidate
from app.models.session import ConversationTurn


# ---------------------------------------------------------------------
# Candidate analysis
# ---------------------------------------------------------------------


class MissionSignalStrength(str, Enum):
    """
    How much evidence a candidate's mission result gives us about their
    real understanding of that topic. This is NOT the same as
    "passed/failed" - a pass earned on the 5th attempt is weaker
    evidence than a pass on the 1st attempt, and a skipped mission is
    no evidence at all.
    """

    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"
    NONE = "none"


class MissionSignal(BaseModel):
    """The evidence-strength verdict for one curriculum day/mission."""

    day: int
    title: str
    strength: MissionSignalStrength
    reason: str


class CandidateAnalysis(BaseModel):
    """
    The structured result of analyzing one candidate's profile.

    Built by app/ai/candidate_analyzer.py using plain Python (no LLM
    call) so it is fast, free, and 100% reliable/testable. This object
    is then formatted into text and handed to the LLM as grounding
    context for every other prompt (question generation, evaluation,
    feedback).
    """

    experience_level: Literal["junior", "mid", "senior"]
    mission_signals: list[MissionSignal]
    strong_days: list[int]
    weak_days: list[int]
    no_evidence_days: list[int]
    # Curriculum days the interview should prioritize covering.
    # Guaranteed (by the analyzer) to contain at least
    # MINIMUM_CURRICULUM_DAYS_COVERED entries whenever possible.
    suggested_focus_days: list[int]
    notes: str


# ---------------------------------------------------------------------
# Questions
# ---------------------------------------------------------------------


class QuestionLevel(int, Enum):
    """
    The five difficulty levels the interview can operate at.

    Stored as an int Enum so the decision engine can do simple math on
    it later (e.g. "one level harder" = level + 1), while still being
    readable by name in code (QuestionLevel.APPLICATION).
    """

    CONCEPTUAL = 1
    UNDERSTANDING = 2
    APPLICATION = 3
    ENGINEERING = 4
    ARCHITECTURE = 5


class GeneratedQuestion(BaseModel):
    """One interview question, grounded in a specific curriculum day."""

    day: int
    topic: str
    level: QuestionLevel
    question: str
    is_followup: bool = False


# ---------------------------------------------------------------------
# Answer evaluation
# ---------------------------------------------------------------------


class DecisionAction(str, Enum):
    """Every action the decision engine is allowed to choose between."""

    FOLLOW_UP = "FOLLOW_UP"
    NEW_TOPIC = "NEW_TOPIC"
    GO_DEEPER = "GO_DEEPER"
    CLARIFY = "CLARIFY"
    INCREASE_DIFFICULTY = "INCREASE_DIFFICULTY"
    DECREASE_DIFFICULTY = "DECREASE_DIFFICULTY"
    END_INTERVIEW = "END_INTERVIEW"


class AnswerEvaluation(BaseModel):
    """
    Structured judgement of one candidate answer.

    Matches the exact example shape given in the hackathon brief. Using
    Literal[...] for understanding/technical_correctness means Pydantic
    will reject anything outside the allowed values, so a slightly
    "creative" LLM response gets caught immediately instead of quietly
    corrupting later logic.
    """

    score: int = Field(ge=0, le=10)
    understanding: Literal["strong", "moderate", "weak", "none"]
    technical_correctness: Literal[
        "correct", "mostly_correct", "partially_correct", "incorrect"
    ]
    strengths: list[str] = Field(default_factory=list)
    missing_concepts: list[str] = Field(default_factory=list)
    follow_up_needed: bool
    recommended_action: DecisionAction


# ---------------------------------------------------------------------
# Decision engine
# ---------------------------------------------------------------------


class InterviewDecision(BaseModel):
    """What the decision engine decided to do next, and why."""

    action: DecisionAction
    reason: str
    # Only meaningful for INCREASE_DIFFICULTY / DECREASE_DIFFICULTY /
    # GO_DEEPER - the level the next question should target.
    target_level: Optional[QuestionLevel] = None


# ---------------------------------------------------------------------
# Final feedback
# ---------------------------------------------------------------------


class FinalFeedback(BaseModel):
    """
    Matches the technical spec's required feedback schema exactly:

        {
          "summary": "...",
          "strengths": [],
          "gaps": [],
          "next": []
        }

    Part 3 will place this object directly into the API's final
    response.
    """

    summary: str
    strengths: list[str]
    gaps: list[str]
    next: list[str]


# ---------------------------------------------------------------------
# Interview context (the AI Brain's "working memory")
# ---------------------------------------------------------------------


class InterviewContext(BaseModel):
    """
    Everything the AI Interview Brain needs to decide what to do next.

    This is intentionally a SEPARATE object from Part 1's
    InterviewSession (app/models/session.py). We reuse Part 1's
    Candidate and ConversationTurn classes (imported, not copied) so
    the two stay compatible, but we do not touch InterviewSession
    itself. InterviewContext adds a few extra bookkeeping fields the
    decision engine specifically needs, like how many follow-ups have
    already been used on the current question.

    Part 3's job is to wire this up to the real InterviewSession the
    API stores between requests - that connection is deliberately not
    built yet.
    """

    candidate: Candidate
    conversation_history: list[ConversationTurn] = Field(default_factory=list)

    question_count: int = 0
    covered_curriculum_days: list[int] = Field(default_factory=list)

    # How many questions have been asked per curriculum day so far.
    # Lets the decision engine avoid asking 5 questions about day 7
    # while never touching days 8, 10, 12...
    questions_per_day: dict[int, int] = Field(default_factory=dict)

    # The full history of questions asked, in order.
    asked_questions: list[GeneratedQuestion] = Field(default_factory=list)

    current_topic: Optional[str] = None
    current_difficulty: QuestionLevel = QuestionLevel.UNDERSTANDING

    # Resets to 0 every time a brand-new (non-follow-up) question is
    # asked. Prevents the interview getting stuck follow-up-ing the
    # same question forever.
    followups_used_on_current_question: int = 0

    evaluations: list[AnswerEvaluation] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
