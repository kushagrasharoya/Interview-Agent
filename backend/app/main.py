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
"""

from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.interview import router as interview_router

app = FastAPI(
    title="The Interview Agent",
    description="AI technical interview backend for the AI Cohort hackathon.",
    version="1.0.0",
)

# Enable CORS so the static frontend served from different ports/origins can call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Attach the /api/interview endpoint defined in app/api/interview.py.
app.include_router(interview_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    """
    A tiny, non-spec endpoint used only to confirm the server is
    running (e.g. when checking things during development).
    """
    return {"status": "ok"}


# Mount static frontend files if present (for single-server deployment)
root_dir = Path(__file__).resolve().parent.parent.parent
frontend_dir = root_dir / "public" if (root_dir / "public" / "index.html").exists() else (root_dir / "frontend")
if frontend_dir.exists() and (frontend_dir / "index.html").exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
