"""
main.py

This is the entrypoint of the backend application - the file you
actually run to start the server.

Why this file exists:
FastAPI needs one central "app" object that all routes attach to.
This file creates that object and plugs in the interview router from
api/interview.py. It intentionally contains almost no logic of its
own - it just wires pieces together.

Run this file with:
    uvicorn app.main:app --reload
(see README.md for full setup instructions)
"""

from fastapi import FastAPI

from app.api.interview import router as interview_router

app = FastAPI(
    title="The Interview Agent",
    description="AI technical interview backend for the AI Cohort hackathon.",
    version="0.1.0",
)

# Attach the /api/interview endpoint defined in app/api/interview.py.
app.include_router(interview_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    """
    A tiny, non-spec endpoint used only to confirm the server is
    running (e.g. when checking things during development). This is
    NOT one of the "unnecessary public APIs" the spec warns against -
    it doesn't expose candidate or curriculum data, it just answers
    "are you alive?".
    """
    return {"status": "ok"}
