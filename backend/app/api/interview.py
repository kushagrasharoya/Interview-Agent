"""
interview.py (api)

This file defines the one and only HTTP endpoint the hackathon
technical spec requires: POST /api/interview.

Why this file exists:
This is the "front door" of the backend. It is the only place that
knows about HTTP requests and responses. It does not know *how* to
run an interview (that's Part 2/3's job) — it only knows how to:
  1. read the incoming JSON,
  2. figure out whether this is a "start" or "continue" request,
  3. call the right service(s),
  4. send back JSON in the exact shape the spec requires.

For Part 1, "continuing" an interview returns a placeholder
reply. The real AI interviewer is built in later parts and will plug
in here without changing this file's request/response shape.
"""

from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.models.candidate import Candidate
from app.models.session import InterviewSession, ConversationTurn, Speaker
from app.services import session_service

router = APIRouter()


class InterviewRequest(BaseModel):
    """
    The shape of every incoming POST /api/interview request.

    Per the technical spec, a request is EITHER:
      - a "start" request:    {sessionId, candidate}
      - a "continue" request: {sessionId, message}

    Both "candidate" and "message" are optional here because a single
    request will only ever contain one of them. We check which one
    showed up inside the endpoint function below.
    """

    sessionId: str
    candidate: Optional[Candidate] = None
    message: Optional[str] = None


class InterviewFeedback(BaseModel):
    """Structured feedback shape, matching the technical spec exactly."""

    summary: str
    strengths: list[str]
    gaps: list[str]
    next: list[str]


class InterviewResponse(BaseModel):
    """
    The shape of every outgoing POST /api/interview response.

    'feedback' is optional because it is only included on the final
    response of the interview (when done=True).
    """

    reply: str
    done: bool
    feedback: Optional[InterviewFeedback] = None


@router.post("/api/interview", response_model=InterviewResponse)
def interview(request: InterviewRequest) -> InterviewResponse:
    """
    Handle one turn of the interview conversation.

    MODE 1 - START: request includes "candidate" -> create a new
    session for this candidate and greet them.

    MODE 2 - CONTINUE: request includes "message" -> look up the
    existing session and (for now, in Part 1) return a placeholder
    reply. Part 2 will replace the placeholder with a real AI-driven
    response.
    """

    # ---- MODE 1: START INTERVIEW ----
    if request.candidate is not None:
        session = InterviewSession(
            session_id=request.sessionId,
            candidate=request.candidate,
        )

        # Record the interviewer's opening line in the transcript so
        # conversation history starts from the very first message.
        opening_reply = "Welcome. Let's begin your interview."
        session.conversation_history.append(
            ConversationTurn(speaker=Speaker.INTERVIEWER, text=opening_reply)
        )

        session_service.create_session(session)

        return InterviewResponse(reply=opening_reply, done=False)

    # ---- MODE 2: CONTINUE INTERVIEW ----
    if request.message is not None:
        session = session_service.get_session(request.sessionId)

        if session is None:
            # Handled cleanly rather than crashing: a client sent a
            # sessionId we've never seen (or the server restarted and
            # lost its in-memory sessions).
            raise HTTPException(
                status_code=404,
                detail=f"No interview session found for sessionId '{request.sessionId}'. "
                "Start an interview first by sending a 'candidate' object.",
            )

        # Record the candidate's answer in the transcript.
        session.conversation_history.append(
            ConversationTurn(speaker=Speaker.CANDIDATE, text=request.message)
        )

        # Part 1 placeholder reply. Part 2 (the AI Interview Brain)
        # will replace this with a real generated question/follow-up.
        placeholder_reply = (
            "Interview session received. AI interviewer will be added in Part 2."
        )
        session.conversation_history.append(
            ConversationTurn(speaker=Speaker.INTERVIEWER, text=placeholder_reply)
        )

        session_service.update_session(session)

        return InterviewResponse(reply=placeholder_reply, done=False)

    # Neither "candidate" nor "message" was provided - request doesn't
    # match either mode defined in the technical spec.
    raise HTTPException(
        status_code=400,
        detail="Request must include either 'candidate' (to start an interview) "
        "or 'message' (to continue one).",
    )
