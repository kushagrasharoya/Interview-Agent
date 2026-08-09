"""
session.py (models)

This file defines what an "interview session" and its related working
context models look like while an interview is in progress.
"""

from enum import Enum
from typing import Literal, Optional
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


# ---------------------------------------------------------------------
# Candidate analysis models
# ---------------------------------------------------------------------


class MissionSignalStrength(str, Enum):
    """How much evidence a candidate's mission result gives us."""

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
    """Structured result of analyzing one candidate's profile."""

    experience_level: Literal["junior", "mid", "senior"]
    mission_signals: list[MissionSignal]
    strong_days: list[int]
    weak_days: list[int]
    no_evidence_days: list[int]
    suggested_focus_days: list[int]
    notes: str


# ---------------------------------------------------------------------
# Question models
# ---------------------------------------------------------------------


class QuestionType(str, Enum):
    """The pedagogical style/nature of an interview question."""

    CONCEPTUAL = "conceptual"
    EXPLANATION = "explanation"
    APPLICATION = "application"
    DEBUGGING = "debugging"
    TRADEOFF = "tradeoff"
    SYSTEM_DESIGN = "system_design"
    SCENARIO = "scenario"


class QuestionLevel(int, Enum):
    """Five difficulty levels (1 to 5)."""

    CONCEPTUAL = 1
    UNDERSTANDING = 2
    APPLICATION = 3
    ENGINEERING = 4
    ARCHITECTURE = 5


class GeneratedQuestion(BaseModel):
    """One interview question, grounded in a specific curriculum day with full traceability metadata."""

    day: int
    topic: str
    level: QuestionLevel
    question: str
    curriculum_day: Optional[int] = None
    curriculum_topic: Optional[str] = None
    objective: Optional[str] = None
    difficulty: Optional[str] = None
    question_type: Optional[str] = None
    type: Optional[QuestionType] = None
    target_concepts: list[str] = Field(default_factory=list)
    selection_reason: Optional[str] = None
    is_followup: bool = False

    def traceability_metadata(self) -> dict:
        """Internal audit metadata describing why this question was selected."""
        return {
            "question": self.question,
            "curriculum_day": self.curriculum_day or self.day,
            "curriculum_topic": self.curriculum_topic or self.topic,
            "objective": self.objective or f"Understand core concepts and tools for Day {self.day}",
            "difficulty": self.difficulty or self.level.name.lower(),
            "question_type": self.question_type or (self.type.value if self.type else "application"),
            "target_concepts": self.target_concepts,
            "selection_reason": self.selection_reason or f"Assessing {self.topic} at {self.level.name} level",
        }


# ---------------------------------------------------------------------
# Evaluation models
# ---------------------------------------------------------------------


class DecisionAction(str, Enum):
    """Actions the decision engine can choose between."""

    FOLLOW_UP = "FOLLOW_UP"
    NEW_TOPIC = "NEW_TOPIC"
    GO_DEEPER = "GO_DEEPER"
    CLARIFY = "CLARIFY"
    INCREASE_DIFFICULTY = "INCREASE_DIFFICULTY"
    DECREASE_DIFFICULTY = "DECREASE_DIFFICULTY"
    END_INTERVIEW = "END_INTERVIEW"


class AnswerEvaluation(BaseModel):
    """Structured judgement of one candidate answer."""

    score: int = Field(ge=0, le=10)
    understanding: Literal["strong", "moderate", "weak", "none"]
    technical_correctness: Literal[
        "correct", "mostly_correct", "partially_correct", "incorrect"
    ]
    strengths: list[str] = Field(default_factory=list)
    missing_concepts: list[str] = Field(default_factory=list)
    misconceptions: list[str] = Field(default_factory=list)
    follow_up_needed: bool
    recommended_action: DecisionAction


class InterviewDecision(BaseModel):
    """What the decision engine decided to do next, and why."""

    action: DecisionAction
    reason: str
    target_level: Optional[QuestionLevel] = None


class FinalFeedback(BaseModel):
    """Technical spec required feedback schema."""

    summary: str
    strengths: list[str]
    gaps: list[str]
    next: list[str]


# ---------------------------------------------------------------------
# Interview Context & Session State
# ---------------------------------------------------------------------


class InterviewContext(BaseModel):
    """Working memory for the AI Interview Brain."""

    candidate: Candidate
    conversation_history: list[ConversationTurn] = Field(default_factory=list)
    question_count: int = 0
    covered_curriculum_days: list[int] = Field(default_factory=list)
    questions_per_day: dict[int, int] = Field(default_factory=dict)
    asked_questions: list[GeneratedQuestion] = Field(default_factory=list)
    current_topic: Optional[str] = None
    current_difficulty: QuestionLevel = QuestionLevel.UNDERSTANDING
    followups_used_on_current_question: int = 0
    evaluations: list[AnswerEvaluation] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)


class EngineSession(BaseModel):
    """The Interview Engine's working state."""

    session_id: str
    analysis: CandidateAnalysis
    context: InterviewContext
    focus_days: list[int] = Field(default_factory=list)
    focus_day_index: int = 0
    topics_covered: list[str] = Field(default_factory=list)
    current_question: Optional[GeneratedQuestion] = None
    done: bool = False
    final_feedback: Optional[FinalFeedback] = None


class InterviewSession(BaseModel):
    """The full state of one candidate's interview."""

    session_id: str
    candidate: Candidate
    conversation_history: list[ConversationTurn] = Field(default_factory=list)
    question_count: int = 0
    covered_curriculum_days: list[int] = Field(default_factory=list)
    current_topic: Optional[str] = None
    current_difficulty: str = "medium"
    status: InterviewStatus = InterviewStatus.IN_PROGRESS
    evaluations: list[dict] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    questions_per_day: dict[int, int] = Field(default_factory=dict)
    asked_questions: list[dict] = Field(default_factory=list)
    followups_used_on_current_question: int = 0
    feedback: Optional[dict] = None
