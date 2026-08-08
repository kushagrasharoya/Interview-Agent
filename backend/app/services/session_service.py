"""
session_service.py

This file is the "memory" of the whole application while it is
running.

Why this file exists:
HTTP is stateless: the server does not automatically remember anything
between one request and the next. But an interview needs to remember
the candidate, the questions asked, and the conversation so far. This
file stores that state in a plain Python dictionary, keyed by
sessionId, while the server process is running.

IMPORTANT: this is in-memory only. If the server restarts, all
sessions are lost. That's fine for Part 1 (and fine for a hackathon
demo) but is called out here so future parts don't get confused about
why sessions disappeared after a restart.
"""

from app.models.session import InterviewSession

# The actual in-memory "database" of sessions.
# Key: session_id (str). Value: InterviewSession object.
_sessions: dict[str, InterviewSession] = {}


def create_session(session: InterviewSession) -> InterviewSession:
    """Store a brand new session, keyed by its session_id."""
    _sessions[session.session_id] = session
    return session


def get_session(session_id: str) -> InterviewSession | None:
    """
    Look up a session by id.

    Returns None if no session exists with that id (e.g. the
    sessionId was never started, or the server restarted).
    """
    return _sessions.get(session_id)


def update_session(session: InterviewSession) -> InterviewSession:
    """
    Save changes to a session that already exists.

    Since InterviewSession objects are stored by reference in the
    dictionary, this mainly matters when a caller has been working on
    a *copy* of the session and wants to write it back. Overwriting by
    session_id keeps that intent explicit and easy to read.
    """
    _sessions[session.session_id] = session
    return session


def delete_session(session_id: str) -> bool:
    """
    Remove a session entirely.

    Returns True if a session was found and removed, False if there
    was nothing to delete.
    """
    if session_id in _sessions:
        del _sessions[session_id]
        return True
    return False


def session_exists(session_id: str) -> bool:
    """Convenience check used by the API layer."""
    return session_id in _sessions
