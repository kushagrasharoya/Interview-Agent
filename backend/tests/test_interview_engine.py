"""
test_interview_engine.py

Integration tests for Part 3: the Interview Engine that connects the
AI brain (Part 2) to the required HTTP endpoint (Part 1's
POST /api/interview).

Just like Part 2's tests, NONE of these ever call a real LLM. Every
test that needs an AI response monkeypatches the single shared choke
point, `app.ai.llm_service.generate_json`, with a small fake that
returns a plausible response depending on what kind of prompt was
sent (question / follow-up, evaluation, or final feedback) - this
works because every AI file in app/ai/ calls that same function.

Run these with (from the backend/ folder):
    pytest
"""

import pytest
from fastapi.testclient import TestClient

from app.ai import candidate_analyzer
from app.ai.llm_service import LLMServiceError
from app.config import MINIMUM_CURRICULUM_DAYS_COVERED, MINIMUM_QUESTIONS
from app.main import app
from app.models.ai_models import DecisionAction, InterviewContext, InterviewDecision
from app.models.engine_models import EngineSession
from app.services import candidate_service, interview_engine, session_service

client = TestClient(app)


# ---------------------------------------------------------------------
# Shared fixtures / helpers
# ---------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_in_memory_stores():
    """
    Both the engine's session store and Part 1's session store are
    plain module-level dictionaries, so they persist across tests in
    the same process. Clear them before every test for isolation.
    """
    interview_engine._engine_sessions.clear()
    session_service._sessions.clear()
    yield


DEFAULT_EVALUATION = {
    "score": 7,
    "understanding": "strong",
    "technical_correctness": "correct",
    "strengths": ["Clear explanation"],
    "missing_concepts": [],
    "follow_up_needed": False,
    "recommended_action": "NEW_TOPIC",
}

DEFAULT_FEEDBACK = {
    "summary": "The candidate demonstrated solid understanding across multiple topics.",
    "strengths": ["Clear grasp of embeddings", "Good reasoning about agentic workflows"],
    "gaps": ["Needs more practice with distance metrics"],
    "next": ["Review vector similarity metrics", "Practice MCP tool design"],
}


def make_fake_llm(eval_queue=None, feedback_response=None):
    """
    Build a fake replacement for llm_service.generate_json.

    - Requests for final feedback get `feedback_response` (or a
      default).
    - Requests to evaluate an answer pop the next item off
      `eval_queue` (or fall back to DEFAULT_EVALUATION once the queue
      runs out).
    - Anything else (a fresh question or a follow-up question) gets a
      minimal, always-unique `{"question": "..."}` reply - the real
      code fills in day/level/topic from context when they're missing.
    """
    eval_iter = iter(eval_queue or [])
    counter = {"n": 0}

    def fake(system_prompt, user_prompt, **kwargs):
        lower = user_prompt.lower()
        if "final interview feedback" in lower:
            return feedback_response or DEFAULT_FEEDBACK
        if "evaluating a candidate" in lower:
            try:
                return next(eval_iter)
            except StopIteration:
                return DEFAULT_EVALUATION
        counter["n"] += 1
        return {"question": f"Auto-generated interview question #{counter['n']}?"}

    return fake


def get_candidate():
    return candidate_service.get_candidate_by_id("CAND-001")


def start_session(session_id="test-session", candidate=None):
    cand = candidate or get_candidate()
    return client.post(
        "/api/interview",
        json={"sessionId": session_id, "candidate": cand.model_dump()},
    )


def send_message(session_id="test-session", message="Here is my answer."):
    return client.post(
        "/api/interview",
        json={"sessionId": session_id, "message": message},
    )


# ---------------------------------------------------------------------
# 1. Start interview
# ---------------------------------------------------------------------


def test_start_interview_returns_greeting_and_first_question(monkeypatch):
    monkeypatch.setattr("app.ai.llm_service.generate_json", make_fake_llm())

    response = start_session("start-1")
    assert response.status_code == 200
    body = response.json()

    assert body["done"] is False
    assert body["feedback"] is None
    # Greeting includes candidate name and a real question.
    assert "Sarah Johnson" in body["reply"]
    assert "Auto-generated interview question" in body["reply"]


def test_start_interview_creates_engine_session_and_part1_session(monkeypatch):
    monkeypatch.setattr("app.ai.llm_service.generate_json", make_fake_llm())

    start_session("start-2")

    engine_sess = interview_engine._engine_sessions.get("start-2")
    assert engine_sess is not None
    assert engine_sess.context.question_count == 1
    assert len(engine_sess.context.covered_curriculum_days) == 1
    assert engine_sess.current_question is not None

    part1_sess = session_service.get_session("start-2")
    assert part1_sess is not None
    assert part1_sess.question_count == 1


# ---------------------------------------------------------------------
# 2. Continue interview & session persistence
# ---------------------------------------------------------------------


def test_continue_interview_updates_transcript_and_returns_next_question(monkeypatch):
    monkeypatch.setattr("app.ai.llm_service.generate_json", make_fake_llm())

    start_session("cont-1")
    response = send_message("cont-1", "Embeddings turn text into numbers.")
    assert response.status_code == 200
    body = response.json()

    assert body["done"] is False
    assert body["feedback"] is None
    assert body["reply"].startswith("Auto-generated interview question")

    engine_sess = interview_engine._engine_sessions["cont-1"]
    # 1 interviewer opening + 1 candidate answer + 1 next interviewer question = 3 turns
    assert len(engine_sess.context.conversation_history) == 3
    assert len(engine_sess.context.evaluations) == 1


def test_same_session_id_accumulates_across_multiple_turns(monkeypatch):
    monkeypatch.setattr("app.ai.llm_service.generate_json", make_fake_llm())

    start_session("multi-1")
    send_message("multi-1", "Answer 1")
    send_message("multi-1", "Answer 2")
    send_message("multi-1", "Answer 3")

    engine_sess = interview_engine._engine_sessions["multi-1"]
    # 1 opening + 3 answers + 3 follow-up questions = 7 turns total
    assert len(engine_sess.context.conversation_history) == 7
    assert len(engine_sess.context.evaluations) == 3


# ---------------------------------------------------------------------
# 3. Follow-up generation
# ---------------------------------------------------------------------


def test_evaluator_flagging_gap_triggers_followup_on_same_day(monkeypatch):
    eval_with_gap = {
        "score": 6,
        "understanding": "moderate",
        "technical_correctness": "partially_correct",
        "strengths": ["Knows the high level"],
        "missing_concepts": ["distance metrics"],
        "follow_up_needed": True,
        "recommended_action": "FOLLOW_UP",
    }
    monkeypatch.setattr("app.ai.llm_service.generate_json", make_fake_llm(eval_queue=[eval_with_gap]))

    start_session("followup-1")
    engine_sess = interview_engine._engine_sessions["followup-1"]
    first_day = engine_sess.current_question.day

    send_message("followup-1", "Embeddings are just vectors.")

    # The follow-up question should still be grounded in the same day.
    assert engine_sess.current_question.is_followup is True
    assert engine_sess.current_question.day == first_day
    assert engine_sess.context.followups_used_on_current_question == 1


# ---------------------------------------------------------------------
# 4. Topic switching & curriculum coverage
# ---------------------------------------------------------------------


def test_solid_answer_moves_to_next_curriculum_day(monkeypatch):
    solid_eval = {
        "score": 7,
        "understanding": "strong",
        "technical_correctness": "correct",
        "strengths": ["Clear answer"],
        "missing_concepts": [],
        "follow_up_needed": False,
        "recommended_action": "NEW_TOPIC",
    }
    monkeypatch.setattr("app.ai.llm_service.generate_json", make_fake_llm(eval_queue=[solid_eval]))

    start_session("topic-1")
    engine_sess = interview_engine._engine_sessions["topic-1"]
    day_1 = engine_sess.current_question.day

    send_message("topic-1", "Great detailed explanation of topic 1.")

    day_2 = engine_sess.current_question.day
    assert day_2 != day_1
    assert day_1 in engine_sess.context.covered_curriculum_days
    assert day_2 in engine_sess.context.covered_curriculum_days
    assert len(engine_sess.context.covered_curriculum_days) == 2


# ---------------------------------------------------------------------
# 5. Difficulty adjustment
# ---------------------------------------------------------------------


def test_strong_answer_increases_difficulty_or_goes_deeper(monkeypatch):
    strong_eval = {
        "score": 9,
        "understanding": "strong",
        "technical_correctness": "correct",
        "strengths": ["Mastery demonstrated"],
        "missing_concepts": [],
        "follow_up_needed": False,
        "recommended_action": "GO_DEEPER",
    }
    monkeypatch.setattr("app.ai.llm_service.generate_json", make_fake_llm(eval_queue=[strong_eval]))

    start_session("diff-1")
    engine_sess = interview_engine._engine_sessions["diff-1"]
    initial_difficulty = engine_sess.context.current_difficulty

    send_message("diff-1", "Flawless technical answer.")

    new_difficulty = engine_sess.context.current_difficulty
    assert new_difficulty.value >= initial_difficulty.value


def test_struggling_answer_triggers_clarification(monkeypatch):
    weak_eval = {
        "score": 2,
        "understanding": "weak",
        "technical_correctness": "incorrect",
        "strengths": [],
        "missing_concepts": ["everything"],
        "follow_up_needed": True,
        "recommended_action": "CLARIFY",
    }
    monkeypatch.setattr("app.ai.llm_service.generate_json", make_fake_llm(eval_queue=[weak_eval]))

    start_session("diff-2")
    engine_sess = interview_engine._engine_sessions["diff-2"]
    day_before = engine_sess.current_question.day

    send_message("diff-2", "I don't know what that means.")

    # CLARIFY stays on the same day and uses a follow-up.
    assert engine_sess.current_question.day == day_before
    assert engine_sess.current_question.is_followup is True


# ---------------------------------------------------------------------
# 6. Minimum requirements enforcement (8 questions, 4 days)
# ---------------------------------------------------------------------


def test_interview_does_not_end_early_even_if_decision_engine_says_end(monkeypatch):
    """
    Simulate a decision engine that tries to emit END_INTERVIEW on turn
    2 - the engine's completion policy must override it and keep the
    interview going because minimums (8 questions, 4 days) aren't met.
    """
    eager_end = {
        "score": 8,
        "understanding": "strong",
        "technical_correctness": "correct",
        "strengths": [],
        "missing_concepts": [],
        "follow_up_needed": False,
        "recommended_action": "END_INTERVIEW",
    }
    monkeypatch.setattr("app.ai.llm_service.generate_json", make_fake_llm(eval_queue=[eager_end]))

    start_session("min-1")
    response = send_message("min-1", "Answer to question 1.")

    assert response.status_code == 200
    body = response.json()
    assert body["done"] is False
    assert body["feedback"] is None


def test_full_interview_runs_to_completion_and_returns_feedback(monkeypatch):
    """
    Drive an interview all the way to completion.

    We send 11 solid answers. The candidate analyzer's focus days will
    give us at least 4 distinct days, and 10+ turns satisfies the
    8-question minimum and preferred-question target, so the interview
    must conclude with done=True and structured feedback.
    """
    custom_feedback = {
        "summary": "Outstanding interview across RAG, Agents, and MCP.",
        "strengths": ["Deep embedding knowledge", "Strong architecture reasoning"],
        "gaps": ["Could deepen Kubernetes tuning"],
        "next": ["Build production MCP servers"],
    }
    monkeypatch.setattr(
        "app.ai.llm_service.generate_json",
        make_fake_llm(feedback_response=custom_feedback),
    )

    start_session("full-1")

    last_body = None
    for i in range(12):
        res = send_message("full-1", f"Solid technical answer #{i + 1}")
        last_body = res.json()
        if last_body["done"]:
            break

    assert last_body["done"] is True
    assert last_body["reply"] == "Interview completed."

    fb = last_body["feedback"]
    assert fb is not None
    assert fb["summary"] == custom_feedback["summary"]
    assert fb["strengths"] == custom_feedback["strengths"]
    assert fb["gaps"] == custom_feedback["gaps"]
    assert fb["next"] == custom_feedback["next"]

    # Verify minimum requirements were genuinely satisfied.
    engine_sess = interview_engine._engine_sessions["full-1"]
    assert engine_sess.context.question_count >= MINIMUM_QUESTIONS
    assert len(set(engine_sess.context.covered_curriculum_days)) >= MINIMUM_CURRICULUM_DAYS_COVERED


def test_repeated_continue_after_interview_ended_is_safe(monkeypatch):
    """
    If a client sends another message after the interview already
    completed, return the completion response again rather than
    crashing.
    """
    monkeypatch.setattr("app.ai.llm_service.generate_json", make_fake_llm())

    start_session("repeat-end")
    engine_sess = interview_engine._engine_sessions["repeat-end"]

    # Force the session into the completed state manually.
    engine_sess.done = True
    engine_sess.final_feedback = DEFAULT_FEEDBACK

    response = send_message("repeat-end", "Late message after done.")
    assert response.status_code == 200
    body = response.json()
    assert body["done"] is True
    assert body["reply"] == "Interview completed."
    assert body["feedback"] is not None


# ---------------------------------------------------------------------
# 7. Error handling
# ---------------------------------------------------------------------


def test_start_with_existing_session_id_returns_409(monkeypatch):
    monkeypatch.setattr("app.ai.llm_service.generate_json", make_fake_llm())

    start_session("dup-1")
    dup_res = start_session("dup-1")
    assert dup_res.status_code == 409
    assert "already exists" in dup_res.json()["detail"]


def test_continue_with_unknown_session_id_returns_404():
    response = send_message("ghost-session", "Hello?")
    assert response.status_code == 404
    assert "No interview session found" in response.json()["detail"]


def test_continue_with_empty_message_returns_400(monkeypatch):
    monkeypatch.setattr("app.ai.llm_service.generate_json", make_fake_llm())

    start_session("empty-1")
    res = send_message("empty-1", "   ")
    assert res.status_code == 400
    assert "cannot be empty" in res.json()["detail"]


def test_request_missing_both_candidate_and_message_returns_400():
    response = client.post("/api/interview", json={"sessionId": "bad-payload"})
    assert response.status_code == 400


def test_ai_failure_returns_502_with_safe_message(monkeypatch):
    """
    When the LLM provider fails (e.g. timeout / bad key / malformed
    JSON), return 502 with a generic message - NEVER leak provider
    details, keys, or stack traces to the API response.
    """
    def broken_llm(*args, **kwargs):
        raise LLMServiceError("Secret Anthropic internal error with key sk-ant-12345")

    monkeypatch.setattr("app.ai.llm_service.generate_json", broken_llm)

    response = start_session("fail-1")
    assert response.status_code == 502
    detail = response.json()["detail"]
    assert "could not generate" in detail
    assert "sk-ant" not in detail
    assert "Anthropic" not in detail
