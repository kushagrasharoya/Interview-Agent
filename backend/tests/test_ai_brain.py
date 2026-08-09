"""
test_ai_brain.py

Tests for Part 2's AI Interview Brain.

IMPORTANT: these tests never call a real LLM / never need an API key.
Anywhere we need an LLM response, we monkeypatch
`app.services.llm_service.generate_json` to return a fixed dictionary.
This keeps the test suite fast, free, and runnable offline / in CI.

Run these with (from the backend/ folder):
    pytest
"""

import pytest

from app.agent import candidate_analyzer, decision_engine
from app.agent import question_generator, answer_evaluator, feedback_generator
from app.models.session import (
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
    missions = [
        CandidateMission(day=7, title="Embeddings", passed=True, attempts=1),
        CandidateMission(day=8, title="Vector DBs", passed=True, attempts=4),
        CandidateMission(day=10, title="Retrieval", passed=False, attempts=2),
        CandidateMission(day=12, title="Prompting", passed=None, attempts=0),
    ]
    candidate = make_candidate(missions, years_experience=2)
    analysis = candidate_analyzer.analyze_candidate(candidate)

    assert analysis.experience_level == "junior"
    assert 7 in analysis.strong_days
    assert 8 in analysis.weak_days
    assert 10 in analysis.weak_days
    assert 12 in analysis.no_evidence_days


def test_candidate_analysis_real_candidate_data_loads_and_analyzes():
    candidate = candidate_service.get_candidate_by_id("CAND-001")
    assert candidate is not None

    analysis = candidate_analyzer.analyze_candidate(candidate)
    assert analysis.experience_level == "senior"
    assert len(analysis.mission_signals) > 0
    assert len(analysis.suggested_focus_days) >= 4


def test_skipped_topic_gets_no_evidence_signal_and_cautious_reason():
    missions = [
        CandidateMission(day=22, title="Multi-Agent", passed=None, attempts=0),
    ]
    candidate = make_candidate(missions)
    analysis = candidate_analyzer.analyze_candidate(candidate)

    signal = next(s for s in analysis.mission_signals if s.day == 22)
    assert signal.strength == MissionSignalStrength.NONE
    assert "skipped" in signal.reason.lower()


def test_repeated_attempts_downgrades_to_moderate_even_though_passed():
    missions = [
        CandidateMission(day=12, title="Prompting", passed=True, attempts=4),
    ]
    candidate = make_candidate(missions)
    analysis = candidate_analyzer.analyze_candidate(candidate)

    signal = next(s for s in analysis.mission_signals if s.day == 12)
    assert signal.strength == MissionSignalStrength.MODERATE
    assert "4 attempts" in signal.reason


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
        "app.services.llm_service.generate_json",
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
        "app.services.llm_service.generate_json",
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
        "app.services.llm_service.generate_json",
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
        "app.services.llm_service.generate_json",
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
    from app.services.llm_service import _parse_json_response

    messy = '```json\n{"score": 5, "ok": true}\n```'
    parsed = _parse_json_response(messy)
    assert parsed == {"score": 5, "ok": True}


def test_llm_service_raises_clear_error_on_invalid_json():
    from app.services.llm_service import _parse_json_response, LLMServiceError

    with pytest.raises(LLMServiceError):
        _parse_json_response("this is not json at all")
