"""
test_ai_brain.py

Tests for Part 2's AI Interview Brain.

IMPORTANT: these tests never call a real LLM / never need an API key.
Anywhere we need an LLM response, we monkeypatch
`app.ai.llm_service.generate_json` to return a fixed dictionary
instead of actually contacting Anthropic. This keeps the test suite
fast, free, and runnable offline / in CI.

Run these with (from the backend/ folder):
    pytest
"""

import pytest

from app.ai import candidate_analyzer, decision_engine
from app.ai import question_generator, answer_evaluator, feedback_generator
from app.models.ai_models import (
    AnswerEvaluation,
    DecisionAction,
    GeneratedQuestion,
    InterviewContext,
    MissionSignalStrength,
    QuestionLevel,
)
from app.models.candidate import Candidate, CandidateMember, CandidateMission, CandidateSignals
from app.services import candidate_service


def make_candidate(missions: list[CandidateMission], years_experience: int = 5) -> Candidate:
    """Small helper to build a throwaway Candidate for tests without touching candidates.json."""
    return Candidate(
        member=CandidateMember(
            id="TEST-001",
            name="Test Candidate",
            jobRole="Software Engineer",
            yearsExperience=years_experience,
            education="B.Tech Computer Science",
            status="COMPLETED",
        ),
        missions=missions,
        signals=CandidateSignals(commitDays=20, missionsCompleted=len(missions), missionsFirstTry=1),
    )


# ---------------------------------------------------------------------
# 1. Candidate analysis
# ---------------------------------------------------------------------


def test_candidate_analysis_classifies_signals_correctly():
    candidate = make_candidate(
        [
            CandidateMission(day=7, title="Embeddings Explained", passed=True, attempts=1),
            CandidateMission(day=8, title="Vector Databases Overview", passed=True, attempts=4),
            CandidateMission(day=12, title="Prompt Engineering Fundamentals", passed=False, attempts=2),
            CandidateMission(day=29, title="Monitoring, Logging & Observability", skipped=True),
        ]
    )

    analysis = candidate_analyzer.analyze_candidate(candidate)

    signals_by_day = {s.day: s for s in analysis.mission_signals}
    assert signals_by_day[7].strength == MissionSignalStrength.STRONG   # 1 attempt + passed
    assert signals_by_day[8].strength == MissionSignalStrength.MODERATE  # many attempts + passed
    assert signals_by_day[12].strength == MissionSignalStrength.WEAK     # failed
    assert signals_by_day[29].strength == MissionSignalStrength.NONE     # skipped

    assert 7 in analysis.strong_days
    assert 12 in analysis.weak_days
    assert 29 in analysis.no_evidence_days


def test_candidate_analysis_real_candidate_data_loads_and_analyzes():
    """Sanity check against the real provided candidates.json (from Part 1)."""
    candidate = candidate_service.get_candidate_by_id("CAND-001")
    assert candidate is not None

    analysis = candidate_analyzer.analyze_candidate(candidate)
    assert len(analysis.mission_signals) == len(candidate.missions)
    assert analysis.experience_level in ("junior", "mid", "senior")


# ---------------------------------------------------------------------
# 6. Skipped topic handling
# ---------------------------------------------------------------------


def test_skipped_topic_gets_no_evidence_signal_and_cautious_reason():
    candidate = make_candidate(
        [CandidateMission(day=29, title="Monitoring, Logging & Observability", skipped=True)]
    )
    analysis = candidate_analyzer.analyze_candidate(candidate)

    signal = analysis.mission_signals[0]
    assert signal.strength == MissionSignalStrength.NONE
    assert "skip" in signal.reason.lower()
    assert "no evidence" in signal.reason.lower()


# ---------------------------------------------------------------------
# 7. Repeated attempts handling
# ---------------------------------------------------------------------


def test_repeated_attempts_downgrades_to_moderate_even_though_passed():
    candidate = make_candidate(
        [CandidateMission(day=12, title="Prompt Engineering Fundamentals", passed=True, attempts=5)]
    )
    analysis = candidate_analyzer.analyze_candidate(candidate)

    signal = analysis.mission_signals[0]
    assert signal.strength == MissionSignalStrength.MODERATE
    assert "5 attempts" in signal.reason


# ---------------------------------------------------------------------
# Focus day selection guarantees >= 4 days when possible
# ---------------------------------------------------------------------


def test_suggested_focus_days_covers_at_least_four_when_available():
    candidate = candidate_service.get_candidate_by_id("CAND-002")
    analysis = candidate_analyzer.analyze_candidate(candidate)
    assert len(analysis.suggested_focus_days) >= 4


# ---------------------------------------------------------------------
# 2. Question generation (mocked LLM)
# ---------------------------------------------------------------------


def test_generate_question_returns_valid_question(monkeypatch):
    candidate = candidate_service.get_candidate_by_id("CAND-001")
    analysis = candidate_analyzer.analyze_candidate(candidate)
    context = InterviewContext(candidate=candidate)

    fake_response = {
        "question": "Can you explain what an embedding is and why we use one?",
        "day": 7,
        "level": 1,
        "topic": "Embeddings",
    }
    monkeypatch.setattr(
        "app.ai.question_generator.llm_service.generate_json",
        lambda system_prompt, user_prompt, **kwargs: fake_response,
    )

    question = question_generator.generate_question(
        candidate=candidate,
        analysis=analysis,
        context=context,
        target_day=7,
        level=QuestionLevel.CONCEPTUAL,
    )

    assert isinstance(question, GeneratedQuestion)
    assert question.day == 7
    assert question.level == QuestionLevel.CONCEPTUAL
    assert question.is_followup is False
    assert "embedding" in question.question.lower()


def test_generate_question_unknown_day_raises():
    candidate = candidate_service.get_candidate_by_id("CAND-001")
    analysis = candidate_analyzer.analyze_candidate(candidate)
    context = InterviewContext(candidate=candidate)

    with pytest.raises(question_generator.CurriculumDayNotFoundError):
        question_generator.generate_question(
            candidate=candidate,
            analysis=analysis,
            context=context,
            target_day=999,
            level=QuestionLevel.CONCEPTUAL,
        )


def test_generate_followup_question_marks_is_followup_true(monkeypatch):
    candidate = candidate_service.get_candidate_by_id("CAND-001")
    previous_question = GeneratedQuestion(
        day=7, topic="Embeddings", level=QuestionLevel.CONCEPTUAL,
        question="What is an embedding?",
    )
    evaluation = AnswerEvaluation(
        score=6,
        understanding="moderate",
        technical_correctness="mostly_correct",
        strengths=["Understands the basic idea"],
        missing_concepts=["distance metrics"],
        follow_up_needed=True,
        recommended_action=DecisionAction.FOLLOW_UP,
    )

    fake_response = {
        "question": "How would you compare two embeddings to see how similar they are?",
        "day": 7,
        "level": 1,
        "topic": "Embeddings",
    }
    monkeypatch.setattr(
        "app.ai.question_generator.llm_service.generate_json",
        lambda system_prompt, user_prompt, **kwargs: fake_response,
    )

    followup = question_generator.generate_followup_question(
        candidate=candidate,
        previous_question=previous_question,
        answer_text="An embedding is a vector representation of data.",
        evaluation=evaluation,
    )

    assert followup.is_followup is True
    assert followup.day == 7


# ---------------------------------------------------------------------
# 3. Answer evaluation (mocked LLM)
# ---------------------------------------------------------------------


def test_evaluate_answer_returns_structured_evaluation(monkeypatch):
    question = GeneratedQuestion(
        day=7, topic="Embeddings", level=QuestionLevel.CONCEPTUAL,
        question="What is an embedding?",
    )

    fake_response = {
        "score": 7,
        "understanding": "moderate",
        "technical_correctness": "mostly_correct",
        "strengths": ["Understands semantic search"],
        "missing_concepts": ["distance metrics"],
        "follow_up_needed": True,
        "recommended_action": "FOLLOW_UP",
    }
    monkeypatch.setattr(
        "app.ai.answer_evaluator.llm_service.generate_json",
        lambda system_prompt, user_prompt, **kwargs: fake_response,
    )

    evaluation = answer_evaluator.evaluate_answer(
        question=question,
        answer_text="An embedding is a vector that captures meaning.",
    )

    assert isinstance(evaluation, AnswerEvaluation)
    assert evaluation.score == 7
    assert evaluation.recommended_action == DecisionAction.FOLLOW_UP
    assert evaluation.follow_up_needed is True


# ---------------------------------------------------------------------
# 4. Decision engine (pure Python, no mocking needed)
# ---------------------------------------------------------------------


def _base_context(candidate: Candidate, **overrides) -> InterviewContext:
    defaults = dict(candidate=candidate)
    defaults.update(overrides)
    return InterviewContext(**defaults)


def test_decision_strong_answer_leads_to_harder_question():
    candidate = candidate_service.get_candidate_by_id("CAND-001")
    context = _base_context(
        candidate,
        asked_questions=[GeneratedQuestion(day=7, topic="Embeddings", level=QuestionLevel.CONCEPTUAL, question="Q1")],
        questions_per_day={7: 1},
    )
    evaluation = AnswerEvaluation(
        score=9,
        understanding="strong",
        technical_correctness="correct",
        strengths=["Excellent explanation"],
        missing_concepts=[],
        follow_up_needed=False,
        recommended_action=DecisionAction.GO_DEEPER,
    )

    decision = decision_engine.decide_next_action(context, evaluation)
    assert decision.action in (DecisionAction.GO_DEEPER, DecisionAction.INCREASE_DIFFICULTY)
    assert decision.target_level is not None
    assert decision.target_level.value >= QuestionLevel.UNDERSTANDING.value


def test_decision_weak_answer_leads_to_clarify_or_decrease():
    candidate = candidate_service.get_candidate_by_id("CAND-001")
    context = _base_context(candidate)
    evaluation = AnswerEvaluation(
        score=2,
        understanding="weak",
        technical_correctness="incorrect",
        strengths=[],
        missing_concepts=["core concept"],
        follow_up_needed=True,
        recommended_action=DecisionAction.CLARIFY,
    )

    decision = decision_engine.decide_next_action(context, evaluation)
    assert decision.action in (DecisionAction.CLARIFY, DecisionAction.DECREASE_DIFFICULTY)


def test_decision_follow_up_needed_triggers_follow_up_action():
    candidate = candidate_service.get_candidate_by_id("CAND-001")
    context = _base_context(candidate, followups_used_on_current_question=0)
    evaluation = AnswerEvaluation(
        score=6,
        understanding="moderate",
        technical_correctness="mostly_correct",
        strengths=["Got the basics"],
        missing_concepts=["distance metrics"],
        follow_up_needed=True,
        recommended_action=DecisionAction.FOLLOW_UP,
    )

    decision = decision_engine.decide_next_action(context, evaluation)
    assert decision.action == DecisionAction.FOLLOW_UP


def test_decision_ends_interview_when_minimums_met_and_answer_solid():
    candidate = candidate_service.get_candidate_by_id("CAND-001")
    context = _base_context(
        candidate,
        question_count=8,
        covered_curriculum_days=[7, 8, 12, 22],
    )
    evaluation = AnswerEvaluation(
        score=7,
        understanding="strong",
        technical_correctness="correct",
        strengths=["Solid closing answer"],
        missing_concepts=[],
        follow_up_needed=False,
        recommended_action=DecisionAction.END_INTERVIEW,
    )

    decision = decision_engine.decide_next_action(context, evaluation)
    assert decision.action == DecisionAction.END_INTERVIEW


def test_decision_does_not_end_interview_before_minimums_met():
    candidate = candidate_service.get_candidate_by_id("CAND-001")
    context = _base_context(
        candidate,
        question_count=3,          # below MINIMUM_QUESTIONS
        covered_curriculum_days=[7],
    )
    evaluation = AnswerEvaluation(
        score=7,
        understanding="strong",
        technical_correctness="correct",
        strengths=["Good answer"],
        missing_concepts=[],
        follow_up_needed=False,
        recommended_action=DecisionAction.NEW_TOPIC,
    )

    decision = decision_engine.decide_next_action(context, evaluation)
    assert decision.action != DecisionAction.END_INTERVIEW


# ---------------------------------------------------------------------
# 5. Final structured feedback (mocked LLM)
# ---------------------------------------------------------------------


def test_generate_feedback_matches_required_schema(monkeypatch):
    candidate = candidate_service.get_candidate_by_id("CAND-001")
    analysis = candidate_analyzer.analyze_candidate(candidate)
    context = InterviewContext(candidate=candidate, covered_curriculum_days=[7, 8, 12, 22])

    fake_response = {
        "summary": "The candidate showed solid understanding of embeddings and agentic workflows.",
        "strengths": ["Clear grasp of vector search", "Good MCP explanation"],
        "gaps": ["Distance metrics were unclear"],
        "next": ["Review cosine similarity vs. Euclidean distance"],
    }
    monkeypatch.setattr(
        "app.ai.feedback_generator.llm_service.generate_json",
        lambda system_prompt, user_prompt, **kwargs: fake_response,
    )

    feedback = feedback_generator.generate_feedback(candidate, analysis, context)

    assert feedback.summary
    assert isinstance(feedback.strengths, list)
    assert isinstance(feedback.gaps, list)
    assert isinstance(feedback.next, list)
    assert feedback.gaps == ["Distance metrics were unclear"]


# ---------------------------------------------------------------------
# LLM service: JSON parsing helper handles messy model output
# ---------------------------------------------------------------------


def test_llm_service_strips_markdown_fences_before_parsing():
    from app.ai.llm_service import _parse_json_response

    messy = '```json\n{"score": 5, "ok": true}\n```'
    parsed = _parse_json_response(messy)
    assert parsed == {"score": 5, "ok": True}


def test_llm_service_raises_clear_error_on_invalid_json():
    from app.ai.llm_service import _parse_json_response, LLMServiceError

    with pytest.raises(LLMServiceError):
        _parse_json_response("this is not json at all")
