"""
interview.py (api)

This file defines the one and only HTTP endpoint the hackathon
technical spec requires: POST /api/interview.

Why this file exists:
This is the "front door" of the backend. It is the only place that
knows about HTTP requests and responses. It does not run the interview
itself - that's app/services/interview_engine.py's job (Part 3). This
file's job is only to:
  1. read the incoming JSON,
  2. figure out whether this is a "start" or "continue" request,
  3. call the engine,
  4. translate the engine's result (or any error) into the exact JSON
     shape the technical spec requires.

The InterviewRequest / InterviewResponse / InterviewFeedback classes
below are the API CONTRACT and have not changed since Part 1 - only
the logic inside the `interview()` function has, now that Part 3 has
a real engine to call instead of a placeholder.
"""

from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.models.candidate import Candidate
from app.services import interview_engine

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
    Handle one turn of the interview conversation by delegating to the
    Interview Engine (Part 3).

    MODE 1 - START: request includes "candidate" -> engine analyzes
    the candidate, plans the interview, and generates the first
    question.

    MODE 2 - CONTINUE: request includes "message" -> engine evaluates
    the answer, decides what happens next, and either asks another
    question or ends the interview with final feedback.
    """

    # ---- MODE 1: START INTERVIEW ----
    if request.candidate is not None:
        try:
            result = interview_engine.start_interview(request.sessionId, request.candidate)
        except interview_engine.SessionAlreadyExistsError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except interview_engine.AIBrainError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        return InterviewResponse(reply=result.reply, done=result.done)

    # ---- MODE 2: CONTINUE INTERVIEW ----
    if request.message is not None:
        if not request.message.strip():
            raise HTTPException(status_code=400, detail="'message' cannot be empty.")

        try:
            result = interview_engine.continue_interview(request.sessionId, request.message)
        except interview_engine.SessionNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except interview_engine.AIBrainError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        feedback = InterviewFeedback(**result.feedback.model_dump()) if result.feedback else None
        return InterviewResponse(reply=result.reply, done=result.done, feedback=feedback)

    # Neither "candidate" nor "message" was provided - request doesn't
    # match either mode defined in the technical spec.
    raise HTTPException(
        status_code=400,
        detail="Request must include either 'candidate' (to start an interview) "
        "or 'message' (to continue one).",
    )
