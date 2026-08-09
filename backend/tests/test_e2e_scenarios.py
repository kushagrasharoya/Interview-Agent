"""
test_e2e_scenarios.py

Comprehensive End-to-End Test Suite for "The Interview Agent" (Part 5).
Covers all 18 functional scenarios and diverse candidate profiles.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.agent import candidate_analyzer
from app.models.candidate import Candidate, CandidateMember, CandidateMission, CandidateSignals
from app.models.session import (
    DecisionAction,
    MissionSignalStrength,
    QuestionLevel,
)
from app.services import candidate_service, curriculum_service, session_service
from app.engine import interview_engine

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_in_memory_stores():
    """Clear session stores before each test."""
    interview_engine._engine_sessions.clear()
    session_service._sessions.clear()
    yield


def make_custom_candidate(id_str, name, role, exp, missions):
    return Candidate(
        member=CandidateMember(
            id=id_str,
            name=name,
            jobRole=role,
            yearsExperience=exp,
            education="BS Computer Science",
            status="COMPLETED" if all(m.passed for m in missions) else "PARTIALLY_COMPLETED",
        ),
        missions=missions,
        signals=CandidateSignals(commitDays=15, missionsCompleted=len(missions), missionsFirstTry=1),
    )


def make_mock_llm(eval_sequence=None, feedback_data=None):
    """Configurable mock LLM generator."""
    eval_iter = iter(eval_sequence or [])
    counter = {"n": 0}

    def fake(system_prompt, user_prompt, **kwargs):
        lower = user_prompt.lower()
        if "final interview feedback" in lower:
            return feedback_data or {
                "summary": "Solid demonstration of cohort concepts.",
                "strengths": ["Strong foundational knowledge"],
                "gaps": ["Room to deepen production deployment"],
                "next": ["Review Kubernetes scaling and MCP server design"],
            }
        if "evaluating a candidate" in lower:
            try:
                return next(eval_iter)
            except StopIteration:
                return {
                    "score": 7,
                    "understanding": "strong",
                    "technical_correctness": "correct",
                    "strengths": ["Accurate explanation"],
                    "missing_concepts": [],
                    "follow_up_needed": False,
                    "recommended_action": "NEW_TOPIC",
                }
        counter["n"] += 1
        return {"question": f"Technical question #{counter['n']} on cohort tools?"}

    return fake


# =====================================================================
# Scenario 1: New Interview Start (Mode 1)
# =====================================================================
def test_scenario_01_new_interview_start(monkeypatch):
    monkeypatch.setattr("app.services.llm_service.generate_json", make_mock_llm())
    candidate = candidate_service.get_candidate_by_id("CAND-001")

    res = client.post("/api/interview", json={"sessionId": "scen-01", "candidate": candidate.model_dump()})
    assert res.status_code == 200
    body = res.json()
    assert body["done"] is False
    assert "Sarah Johnson" in body["reply"]
    assert body["feedback"] is None


# =====================================================================
# Scenario 2: Existing Session Continuation (Mode 2)
# =====================================================================
def test_scenario_02_existing_session_continuation(monkeypatch):
    monkeypatch.setattr("app.services.llm_service.generate_json", make_mock_llm())
    candidate = candidate_service.get_candidate_by_id("CAND-001")

    client.post("/api/interview", json={"sessionId": "scen-02", "candidate": candidate.model_dump()})
    res = client.post("/api/interview", json={"sessionId": "scen-02", "message": "I built dense vector search pipelines."})
    assert res.status_code == 200
    assert res.json()["done"] is False
    assert len(interview_engine._engine_sessions["scen-02"].context.conversation_history) == 3


# =====================================================================
# Scenario 3: Strong Candidate Profile
# =====================================================================
def test_scenario_03_strong_candidate_profile(monkeypatch):
    candidate = candidate_service.get_candidate_by_id("CAND-001")
    analysis = candidate_analyzer.analyze_candidate(candidate)
    assert analysis.experience_level == "senior"
    assert len(analysis.strong_days) >= 2
    assert len(analysis.suggested_focus_days) >= 4


# =====================================================================
# Scenario 4: Multiple Attempts Profile
# =====================================================================
def test_scenario_04_multiple_attempts_profile():
    candidate = candidate_service.get_candidate_by_id("CAND-004")
    analysis = candidate_analyzer.analyze_candidate(candidate)
    assert analysis.experience_level == "senior"
    # David Miller had multiple attempts on most missions and skipped day 28
    assert len(analysis.weak_days) >= 5
    assert len(analysis.no_evidence_days) >= 1


# =====================================================================
# Scenario 5: Candidate with Skipped Topics
# =====================================================================
def test_scenario_05_candidate_with_skipped_topics():
    candidate = candidate_service.get_candidate_by_id("CAND-001")
    analysis = candidate_analyzer.analyze_candidate(candidate)
    # Sarah Johnson skipped day 29 (Observability)
    assert 29 in analysis.no_evidence_days
    signal_29 = next(s for s in analysis.mission_signals if s.day == 29)
    assert signal_29.strength == MissionSignalStrength.NONE


# =====================================================================
# Scenario 6: Candidate with Many Attempts (Day 12, 5 Attempts)
# =====================================================================
def test_scenario_06_candidate_with_many_attempts():
    candidate = candidate_service.get_candidate_by_id("CAND-002")
    analysis = candidate_analyzer.analyze_candidate(candidate)
    signal_12 = next(s for s in analysis.mission_signals if s.day == 12)
    assert signal_12.strength == MissionSignalStrength.MODERATE
    assert "5 attempts" in signal_12.reason


# =====================================================================
# Scenario 7: Candidate with Failed Missions
# =====================================================================
def test_scenario_07_candidate_with_failed_missions():
    missions = [
        CandidateMission(day=7, title="Embeddings", passed=True, attempts=1),
        CandidateMission(day=10, title="Retrieval", passed=False, attempts=3),
    ]
    cand = make_custom_candidate("CAND-FAIL", "Bob", "Developer", 3, missions)
    analysis = candidate_analyzer.analyze_candidate(cand)
    signal_10 = next(s for s in analysis.mission_signals if s.day == 10)
    assert signal_10.strength == MissionSignalStrength.WEAK
    assert "did not pass" in signal_10.reason


# =====================================================================
# Scenario 8: Follow-up Behavior on Technical Gap
# =====================================================================
def test_scenario_08_followup_behavior_on_gap(monkeypatch):
    eval_gap = {
        "score": 6,
        "understanding": "moderate",
        "technical_correctness": "partially_correct",
        "strengths": ["Basic definition provided"],
        "missing_concepts": ["HNSW graph construction"],
        "follow_up_needed": True,
        "recommended_action": "FOLLOW_UP",
    }
    monkeypatch.setattr("app.services.llm_service.generate_json", make_mock_llm(eval_sequence=[eval_gap]))

    candidate = candidate_service.get_candidate_by_id("CAND-001")
    client.post("/api/interview", json={"sessionId": "scen-08", "candidate": candidate.model_dump()})
    engine_sess = interview_engine._engine_sessions["scen-08"]
    first_day = engine_sess.current_question.day

    client.post("/api/interview", json={"sessionId": "scen-08", "message": "Vector DBs index embeddings."})
    assert engine_sess.current_question.is_followup is True
    assert engine_sess.current_question.day == first_day


# =====================================================================
# Scenario 9: Dynamic Difficulty Adaptation
# =====================================================================
def test_scenario_09_difficulty_adaptation(monkeypatch):
    strong_eval = {
        "score": 9,
        "understanding": "strong",
        "technical_correctness": "correct",
        "strengths": ["In-depth understanding"],
        "missing_concepts": [],
        "follow_up_needed": False,
        "recommended_action": "GO_DEEPER",
    }
    monkeypatch.setattr("app.services.llm_service.generate_json", make_mock_llm(eval_sequence=[strong_eval]))

    candidate = candidate_service.get_candidate_by_id("CAND-001")
    client.post("/api/interview", json={"sessionId": "scen-09", "candidate": candidate.model_dump()})
    engine_sess = interview_engine._engine_sessions["scen-09"]
    start_level = engine_sess.context.current_difficulty

    client.post("/api/interview", json={"sessionId": "scen-09", "message": "Comprehensive architecture breakdown."})
    assert engine_sess.context.current_difficulty.value >= start_level.value


# =====================================================================
# Scenario 10: Topic Switching Across Curriculum Days
# =====================================================================
def test_scenario_10_topic_switching(monkeypatch):
    monkeypatch.setattr("app.services.llm_service.generate_json", make_mock_llm())
    candidate = candidate_service.get_candidate_by_id("CAND-001")

    client.post("/api/interview", json={"sessionId": "scen-10", "candidate": candidate.model_dump()})
    engine_sess = interview_engine._engine_sessions["scen-10"]
    day_1 = engine_sess.current_question.day

    client.post("/api/interview", json={"sessionId": "scen-10", "message": "Solid explanation of topic 1."})
    day_2 = engine_sess.current_question.day
    assert day_1 != day_2


# =====================================================================
# Scenario 11 & 12: 8-Question and 4-Day Minimums Enforced
# =====================================================================
def test_scenario_11_12_minimums_enforced(monkeypatch):
    early_end = {
        "score": 8,
        "understanding": "strong",
        "technical_correctness": "correct",
        "strengths": [],
        "missing_concepts": [],
        "follow_up_needed": False,
        "recommended_action": "END_INTERVIEW",
    }
    monkeypatch.setattr("app.services.llm_service.generate_json", make_mock_llm(eval_sequence=[early_end, early_end]))

    candidate = candidate_service.get_candidate_by_id("CAND-001")
    client.post("/api/interview", json={"sessionId": "scen-11", "candidate": candidate.model_dump()})

    res = client.post("/api/interview", json={"sessionId": "scen-11", "message": "Answer 1"})
    assert res.json()["done"] is False  # Backend overrides early end


# =====================================================================
# Scenario 13: Final Feedback Generated Correctly
# =====================================================================
def test_scenario_13_final_feedback_schema(monkeypatch):
    expected_feedback = {
        "summary": "Exceptional grasp of AI agent systems.",
        "strengths": ["Vector similarity", "LangChain tool calling"],
        "gaps": ["Model quantization tradeoffs"],
        "next": ["Practice deploying MCP servers on Kubernetes"],
    }
    monkeypatch.setattr("app.services.llm_service.generate_json", make_mock_llm(feedback_data=expected_feedback))

    candidate = candidate_service.get_candidate_by_id("CAND-001")
    client.post("/api/interview", json={"sessionId": "scen-13", "candidate": candidate.model_dump()})

    final_res = None
    for turn in range(12):
        r = client.post("/api/interview", json={"sessionId": "scen-13", "message": f"Answer #{turn+1}"})
        final_res = r.json()
        if final_res["done"]:
            break

    assert final_res["done"] is True
    assert final_res["feedback"] == expected_feedback


# =====================================================================
# Scenario 14: Invalid / Unknown Session (404)
# =====================================================================
def test_scenario_14_unknown_session_returns_404():
    res = client.post("/api/interview", json={"sessionId": "nonexistent-id", "message": "Hello"})
    assert res.status_code == 404
    assert "No interview session found" in res.json()["detail"]


# =====================================================================
# Scenario 15: Invalid Request Body (400)
# =====================================================================
def test_scenario_15_invalid_request_returns_400():
    res1 = client.post("/api/interview", json={"sessionId": "scen-15"})
    assert res1.status_code == 400

    candidate = candidate_service.get_candidate_by_id("CAND-001")
    client.post("/api/interview", json={"sessionId": "scen-15-2", "candidate": candidate.model_dump()})
    res2 = client.post("/api/interview", json={"sessionId": "scen-15-2", "message": "   "})
    assert res2.status_code == 400


# =====================================================================
# Scenario 16: LLM Provider Failure (502, Safe Error)
# =====================================================================
def test_scenario_16_llm_failure_returns_502_without_secrets(monkeypatch):
    from app.services.llm_service import LLMServiceError

    def failing_llm(*args, **kwargs):
        raise LLMServiceError("Secret upstream auth failed with key sk-ant-secret-key-123")

    monkeypatch.setattr("app.services.llm_service.generate_json", failing_llm)

    candidate = candidate_service.get_candidate_by_id("CAND-001")
    res = client.post("/api/interview", json={"sessionId": "scen-16", "candidate": candidate.model_dump()})
    assert res.status_code == 502
    detail = res.json()["detail"]
    assert "sk-ant" not in detail
    assert "could not generate" in detail


# =====================================================================
# Scenario 17: Refresh / Re-Entry After Completion
# =====================================================================
def test_scenario_17_safe_reentry_after_done(monkeypatch):
    monkeypatch.setattr("app.services.llm_service.generate_json", make_mock_llm())
    candidate = candidate_service.get_candidate_by_id("CAND-001")
    client.post("/api/interview", json={"sessionId": "scen-17", "candidate": candidate.model_dump()})

    engine_sess = interview_engine._engine_sessions["scen-17"]
    engine_sess.done = True
    engine_sess.final_feedback = {
        "summary": "Completed",
        "strengths": ["Knowledge"],
        "gaps": [],
        "next": [],
    }

    res = client.post("/api/interview", json={"sessionId": "scen-17", "message": "Late turn"})
    assert res.status_code == 200
    assert res.json()["done"] is True
    assert res.json()["feedback"]["summary"] == "Completed"


# =====================================================================
# Scenario 18: Health Check & Server Alive
# =====================================================================
def test_scenario_18_health_check():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}
