"""
test_foundation.py

These tests check that the Part 1 foundation actually works:
the server starts, data loads correctly, and the /api/interview
endpoint behaves the way the technical spec says it should.

Run these with (from the backend/ folder):
    pytest
"""

from fastapi.testclient import TestClient

from app.main import app
from app.services import candidate_service, curriculum_service

client = TestClient(app)


# ---------------------------------------------------------------------
# 1. The FastAPI application starts and responds.
# ---------------------------------------------------------------------
def test_app_starts_and_health_check_works():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# ---------------------------------------------------------------------
# 2. POST /api/interview can start a session.
# ---------------------------------------------------------------------
def test_start_interview_creates_session():
    candidate = candidate_service.get_candidate_by_id("CAND-001")
    assert candidate is not None  # sanity check the data loaded

    response = client.post(
        "/api/interview",
        json={
            "sessionId": "test-session-1",
            "candidate": candidate.model_dump(),
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["reply"] == "Welcome. Let's begin your interview."
    assert body["done"] is False


# ---------------------------------------------------------------------
# 3. POST /api/interview can continue an existing session.
# ---------------------------------------------------------------------
def test_continue_interview_returns_placeholder_reply():
    candidate = candidate_service.get_candidate_by_id("CAND-002")

    # Start the session first.
    client.post(
        "/api/interview",
        json={"sessionId": "test-session-2", "candidate": candidate.model_dump()},
    )

    # Now continue it.
    response = client.post(
        "/api/interview",
        json={"sessionId": "test-session-2", "message": "My answer is..."},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["done"] is False
    assert "Part 2" in body["reply"]


# ---------------------------------------------------------------------
# 4. The same sessionId retrieves the same session
#    (conversation history accumulates across requests).
# ---------------------------------------------------------------------
def test_same_session_id_keeps_conversation_history():
    from app.services import session_service

    candidate = candidate_service.get_candidate_by_id("CAND-003")

    client.post(
        "/api/interview",
        json={"sessionId": "test-session-3", "candidate": candidate.model_dump()},
    )
    client.post(
        "/api/interview",
        json={"sessionId": "test-session-3", "message": "first answer"},
    )
    client.post(
        "/api/interview",
        json={"sessionId": "test-session-3", "message": "second answer"},
    )

    session = session_service.get_session("test-session-3")
    assert session is not None
    assert session.candidate.member.id == "CAND-003"
    # 1 opening line + (candidate + interviewer) x2 continue calls = 5
    assert len(session.conversation_history) == 5


# ---------------------------------------------------------------------
# 5. An unknown sessionId is handled cleanly (no crash, clear error).
# ---------------------------------------------------------------------
def test_unknown_session_id_returns_404():
    response = client.post(
        "/api/interview",
        json={"sessionId": "does-not-exist", "message": "hello?"},
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------
# 6. Candidate data can be loaded.
# ---------------------------------------------------------------------
def test_candidate_data_loads():
    candidates = candidate_service.load_candidates()
    assert len(candidates) > 0
    assert candidates[0].member.id.startswith("CAND-")


# ---------------------------------------------------------------------
# 7. Curriculum data can be loaded.
# ---------------------------------------------------------------------
def test_curriculum_data_loads():
    days = curriculum_service.get_all_days()
    assert len(days) == 31


# ---------------------------------------------------------------------
# 8. Curriculum day lookup works.
# ---------------------------------------------------------------------
def test_curriculum_day_lookup():
    day_7 = curriculum_service.get_day(7)
    assert day_7 is not None
    assert day_7["day"] == 7
    assert "objectives" in day_7

    missing_day = curriculum_service.get_day(999)
    assert missing_day is None
