"""
interview_engine.py

This is the "Interview Engine" box from the Part 3 architecture
diagram. It is the ONE place that knows how to run a whole interview
from start to finish - it is the glue between:

    the HTTP layer (app/api/interview.py)
        ↕
    Part 1's data services (candidate_service, curriculum_service, session_service)
        ↕
    Part 2's AI brain (candidate_analyzer, question_generator, answer_evaluator,
                        decision_engine, feedback_generator)

Nothing in Part 1 or Part 2 is modified to build this file. Where Part 1's
InterviewSession model doesn't have a field Part 3 needs (like "which
curriculum days are still left to visit"), this file keeps that extra
bookkeeping in its own EngineSession object (see
app/models/engine_models.py) instead of changing an existing model.

Two public functions do all the work and are called directly by
app/api/interview.py:

    start_interview(session_id, candidate)   -> InterviewTurnResult
    continue_interview(session_id, message)  -> InterviewTurnResult
"""

import logging
from typing import Optional

from pydantic import BaseModel, ValidationError

from app.agent import answer_evaluator, candidate_analyzer, decision_engine, feedback_generator, question_generator
from app.services.llm_service import LLMServiceError
from app.config import MINIMUM_CURRICULUM_DAYS_COVERED, MINIMUM_QUESTIONS
from app.models.candidate import Candidate
from app.models.session import (
    AnswerEvaluation,
    ConversationTurn,
    DecisionAction,
    EngineSession,
    FinalFeedback,
    GeneratedQuestion,
    InterviewContext,
    InterviewDecision,
    InterviewSession,
    InterviewStatus,
    QuestionLevel,
    Speaker,
)
from app.services import curriculum_service, session_service

logger = logging.getLogger(__name__)

# Hard minimums are enforced no matter what the LLM or decision engine
# suggests (imported from config, same constants Part 2 uses).
# "Prefer approximately 10 questions" per the Part 3 brief - once the
# hard minimums are satisfied, the engine still leans toward this many
# questions if there is more curriculum left to explore.
PREFERRED_QUESTIONS = 10

# Starting difficulty is picked from the candidate's experience level,
# then adjusted turn by turn by the decision engine from there.
_STARTING_LEVEL_BY_EXPERIENCE = {
    "junior": QuestionLevel.CONCEPTUAL,
    "mid": QuestionLevel.UNDERSTANDING,
    "senior": QuestionLevel.APPLICATION,
}

# In-memory store for EngineSession objects, keyed by sessionId - the
# same pattern Part 1's session_service.py uses for InterviewSession.
# Kept separate from session_service's store on purpose.
_engine_sessions: dict[str, EngineSession] = {}


# ---------------------------------------------------------------------
# Public result type returned to the API layer
# ---------------------------------------------------------------------


class InterviewTurnResult(BaseModel):
    """Everything app/api/interview.py needs to build its HTTP response."""

    reply: str
    done: bool
    feedback: Optional[FinalFeedback] = None


# ---------------------------------------------------------------------
# Errors - the API layer catches these and turns them into clean HTTP
# responses. None of these ever include raw provider errors, API keys,
# or stack traces in their message.
# ---------------------------------------------------------------------


class SessionAlreadyExistsError(Exception):
    """Raised when a start request reuses a sessionId that's already in use."""


class SessionNotFoundError(Exception):
    """Raised when a continue request references an unknown sessionId."""


class AIBrainError(Exception):
    """
    Raised when the AI brain (LLM call or its structured output)
    fails. The real underlying error is logged server-side; only this
    generic, safe message is ever shown to the API caller.
    """


# ---------------------------------------------------------------------
# START INTERVIEW
# ---------------------------------------------------------------------


def start_interview(session_id: str, candidate: Candidate) -> InterviewTurnResult:
    """
    Create a brand-new interview session for `candidate`, analyze
    them, plan which curriculum days to cover, and generate the first
    question.
    """
    if session_service.session_exists(session_id):
        raise SessionAlreadyExistsError(
            f"A session with id '{session_id}' already exists. "
            "Use a new sessionId to start a new interview."
        )

    # 1. Analyze the candidate (plain Python, no LLM - see Part 2).
    analysis = candidate_analyzer.analyze_candidate(candidate)

    # 2. Build the AI brain's working memory and the engine's own
    #    bookkeeping around it.
    context = InterviewContext(candidate=candidate)
    engine_session = EngineSession(
        session_id=session_id,
        analysis=analysis,
        context=context,
        focus_days=list(analysis.suggested_focus_days),
    )

    # 3. Also create Part 1's InterviewSession, so the project's
    #    original session model/service stay meaningfully in use and
    #    any other code that reads it sees up-to-date data.
    part1_session = InterviewSession(session_id=session_id, candidate=candidate)
    session_service.create_session(part1_session)

    # 4. Pick the first curriculum day + starting difficulty and
    #    generate the opening question.
    first_day = _next_focus_day(engine_session)
    starting_level = _STARTING_LEVEL_BY_EXPERIENCE.get(analysis.experience_level, QuestionLevel.UNDERSTANDING)

    question = _generate_fresh_question(candidate, engine_session, target_day=first_day, level=starting_level)
    engine_session.current_question = question
    engine_session.context.current_difficulty = starting_level
    _record_question(engine_session, question)

    _engine_sessions[session_id] = engine_session

    reply = f"Welcome, {candidate.member.name}! Let's begin your interview.\n\n{question.question}"
    _append_turn(engine_session, part1_session, Speaker.INTERVIEWER, reply)
    _sync_part1_session(engine_session, part1_session)

    return InterviewTurnResult(reply=reply, done=False)


# ---------------------------------------------------------------------
# CONTINUE INTERVIEW
# ---------------------------------------------------------------------


def continue_interview(session_id: str, message: str) -> InterviewTurnResult:
    """
    Take the candidate's latest answer, evaluate it, decide what
    happens next, and either ask another question or end the
    interview with final feedback.
    """
    engine_session = _engine_sessions.get(session_id)
    part1_session = session_service.get_session(session_id)

    if engine_session is None or part1_session is None:
        raise SessionNotFoundError(
            f"No interview session found for sessionId '{session_id}'. "
            "Start an interview first by sending a 'candidate' object."
        )

    if engine_session.done:
        # The interview already ended. Rather than erroring, hand back
        # the same completion response so a duplicate/late request
        # from the frontend doesn't crash anything.
        return InterviewTurnResult(
            reply="Interview completed.",
            done=True,
            feedback=engine_session.final_feedback,
        )

    candidate = engine_session.context.candidate
    _append_turn(engine_session, part1_session, Speaker.CANDIDATE, message)

    # 1. Evaluate the candidate's answer to the question they were
    #    just asked.
    evaluation = _evaluate_answer(engine_session, message)
    engine_session.context.evaluations.append(evaluation)
    _merge_strengths_and_gaps(engine_session, evaluation)

    # 2. Ask the decision engine what should happen next.
    decision = decision_engine.decide_next_action(engine_session.context, evaluation)
    decision = _enforce_completion_policy(decision, engine_session)

    # 3. Act on the decision.
    if decision.action == DecisionAction.END_INTERVIEW:
        return _end_interview(engine_session, part1_session, candidate)

    question = _apply_decision(engine_session, candidate, message, evaluation, decision)
    engine_session.current_question = question

    _append_turn(engine_session, part1_session, Speaker.INTERVIEWER, question.question)
    _sync_part1_session(engine_session, part1_session)

    return InterviewTurnResult(reply=question.question, done=False)


# ---------------------------------------------------------------------
# Internal helpers - AI brain calls
# ---------------------------------------------------------------------


def _evaluate_answer(engine_session: EngineSession, answer_text: str) -> AnswerEvaluation:
    question = engine_session.current_question
    if question is None:
        raise AIBrainError("No active question found for this session.")

    try:
        return answer_evaluator.evaluate_answer(question=question, answer_text=answer_text)
    except (LLMServiceError, ValidationError, KeyError) as exc:
        logger.error("Answer evaluation failed for session %s: %s", engine_session.session_id, exc)
        raise AIBrainError("The AI interview service could not evaluate that answer. Please try again.") from exc


def _generate_fresh_question(
    candidate: Candidate,
    engine_session: EngineSession,
    target_day: int,
    level: QuestionLevel,
) -> GeneratedQuestion:
    try:
        return question_generator.generate_question(
            candidate=candidate,
            analysis=engine_session.analysis,
            context=engine_session.context,
            target_day=target_day,
            level=level,
        )
    except (LLMServiceError, ValidationError, KeyError) as exc:
        logger.error("Question generation failed for session %s: %s", engine_session.session_id, exc)
        raise AIBrainError("The AI interview service could not generate the next question. Please try again.") from exc


def _generate_followup(
    candidate: Candidate,
    engine_session: EngineSession,
    answer_text: str,
    evaluation: AnswerEvaluation,
) -> GeneratedQuestion:
    try:
        return question_generator.generate_followup_question(
            candidate=candidate,
            previous_question=engine_session.current_question,
            answer_text=answer_text,
            evaluation=evaluation,
        )
    except (LLMServiceError, ValidationError, KeyError) as exc:
        logger.error("Follow-up generation failed for session %s: %s", engine_session.session_id, exc)
        raise AIBrainError("The AI interview service could not generate a follow-up. Please try again.") from exc


def _generate_feedback(engine_session: EngineSession, candidate: Candidate) -> FinalFeedback:
    try:
        return feedback_generator.generate_feedback(
            candidate=candidate,
            analysis=engine_session.analysis,
            context=engine_session.context,
        )
    except (LLMServiceError, ValidationError, KeyError) as exc:
        logger.error("Feedback generation failed for session %s: %s", engine_session.session_id, exc)
        raise AIBrainError("The AI interview service could not generate final feedback. Please try again.") from exc


# ---------------------------------------------------------------------
# Internal helpers - decision -> question orchestration
# ---------------------------------------------------------------------


def _apply_decision(
    engine_session: EngineSession,
    candidate: Candidate,
    answer_text: str,
    evaluation: AnswerEvaluation,
    decision: InterviewDecision,
) -> GeneratedQuestion:
    """
    Turn a decision engine action into an actual next question, and
    update the engine's bookkeeping to match.
    """
    context = engine_session.context
    action = decision.action
    current_day = engine_session.current_question.day

    # FOLLOW_UP / CLARIFY: stay on the exact same question/topic and
    # probe the gap the evaluator identified.
    if action in (DecisionAction.FOLLOW_UP, DecisionAction.CLARIFY):
        question = _generate_followup(candidate, engine_session, answer_text, evaluation)
        context.followups_used_on_current_question += 1
        _record_question(engine_session, question, new_day=False)
        return question

    # GO_DEEPER / DECREASE_DIFFICULTY: fresh (non-follow-up) question,
    # same curriculum day, adjusted difficulty.
    if action in (DecisionAction.GO_DEEPER, DecisionAction.DECREASE_DIFFICULTY):
        level = decision.target_level or context.current_difficulty
        question = _generate_fresh_question(candidate, engine_session, target_day=current_day, level=level)
        context.current_difficulty = level
        context.followups_used_on_current_question = 0
        _record_question(engine_session, question, new_day=False)
        return question

    # NEW_TOPIC / INCREASE_DIFFICULTY: move on to a new curriculum day.
    next_day = _next_focus_day(engine_session)
    level = decision.target_level or context.current_difficulty
    question = _generate_fresh_question(candidate, engine_session, target_day=next_day, level=level)
    context.current_difficulty = level
    context.followups_used_on_current_question = 0
    _record_question(engine_session, question, new_day=True)
    return question


def _next_focus_day(engine_session: EngineSession) -> int:
    """
    Pop the next planned curriculum day off the interview's plan.
    """
    while engine_session.focus_day_index < len(engine_session.focus_days):
        day = engine_session.focus_days[engine_session.focus_day_index]
        engine_session.focus_day_index += 1
        if day not in engine_session.context.covered_curriculum_days:
            return day

    all_days = [d["day"] for d in curriculum_service.get_all_days()]
    uncovered = [d for d in all_days if d not in engine_session.context.covered_curriculum_days]
    if uncovered:
        return uncovered[0]

    counts = engine_session.context.questions_per_day
    return min(counts, key=counts.get) if counts else all_days[0]


def _record_question(engine_session: EngineSession, question: GeneratedQuestion, new_day: bool = True) -> None:
    """Update all the bookkeeping that happens whenever a new question is asked."""
    context = engine_session.context
    context.asked_questions.append(question)
    context.question_count += 1
    context.questions_per_day[question.day] = context.questions_per_day.get(question.day, 0) + 1
    context.current_topic = question.topic

    if question.day not in context.covered_curriculum_days:
        context.covered_curriculum_days.append(question.day)
    if question.topic not in engine_session.topics_covered:
        engine_session.topics_covered.append(question.topic)


def _merge_strengths_and_gaps(engine_session: EngineSession, evaluation: AnswerEvaluation) -> None:
    """Fold one evaluation's strengths/missing_concepts into the running totals, without duplicates."""
    context = engine_session.context
    for item in evaluation.strengths:
        if item not in context.strengths:
            context.strengths.append(item)
    for item in evaluation.missing_concepts:
        if item not in context.gaps:
            context.gaps.append(item)


# ---------------------------------------------------------------------
# Internal helpers - completion enforcement
# ---------------------------------------------------------------------


def _enforce_completion_policy(decision: InterviewDecision, engine_session: EngineSession) -> InterviewDecision:
    """
    The backend - not the LLM alone - has the final say on when an interview is allowed to end.

    Rule 1 (hard minimum): never end before
        question_count >= MINIMUM_QUESTIONS
        AND unique curriculum days covered >= MINIMUM_CURRICULUM_DAYS_COVERED

    Rule 2 (soft preference): once the hard minimum is met, still
    prefer to keep going until PREFERRED_QUESTIONS (~10) questions have
    been asked, as long as there is more curriculum left to explore.
    """
    context = engine_session.context
    unique_days = len(set(context.covered_curriculum_days))
    minimums_met = context.question_count >= MINIMUM_QUESTIONS and unique_days >= MINIMUM_CURRICULUM_DAYS_COVERED

    if decision.action != DecisionAction.END_INTERVIEW:
        return decision

    if not minimums_met:
        return InterviewDecision(
            action=DecisionAction.NEW_TOPIC,
            reason=(
                f"Backend override: minimum requirements not yet met "
                f"({context.question_count}/{MINIMUM_QUESTIONS} questions, "
                f"{unique_days}/{MINIMUM_CURRICULUM_DAYS_COVERED} days) - continuing."
            ),
        )

    more_curriculum_available = engine_session.focus_day_index < len(engine_session.focus_days)
    if context.question_count < PREFERRED_QUESTIONS and more_curriculum_available:
        return InterviewDecision(
            action=DecisionAction.NEW_TOPIC,
            reason=(
                f"Backend override: minimums met, but preferring ~{PREFERRED_QUESTIONS} "
                "questions and more curriculum remains."
            ),
        )

    return decision


def _end_interview(engine_session: EngineSession, part1_session: InterviewSession, candidate: Candidate) -> InterviewTurnResult:
    """Generate final feedback, mark the session done, and build the completion response."""
    feedback = _generate_feedback(engine_session, candidate)

    engine_session.done = True
    engine_session.final_feedback = feedback

    closing_reply = "Interview completed."
    _append_turn(engine_session, part1_session, Speaker.INTERVIEWER, closing_reply)

    part1_session.status = InterviewStatus.COMPLETED
    part1_session.strengths = feedback.strengths
    part1_session.gaps = feedback.gaps
    _sync_part1_session(engine_session, part1_session)

    return InterviewTurnResult(reply=closing_reply, done=True, feedback=feedback)


# ---------------------------------------------------------------------
# Internal helpers - keeping Part 1's InterviewSession in sync
# ---------------------------------------------------------------------


def _append_turn(engine_session: EngineSession, part1_session: InterviewSession, speaker: Speaker, text: str) -> None:
    """Record one line of dialogue in BOTH the AI brain's context and Part 1's session."""
    engine_session.context.conversation_history.append(ConversationTurn(speaker=speaker, text=text))
    part1_session.conversation_history.append(ConversationTurn(speaker=speaker, text=text))


def _sync_part1_session(engine_session: EngineSession, part1_session: InterviewSession) -> None:
    """
    Copy the engine's current state onto Part 1's InterviewSession and
    save it via session_service.
    """
    context = engine_session.context
    part1_session.question_count = context.question_count
    part1_session.covered_curriculum_days = list(set(context.covered_curriculum_days))
    part1_session.current_topic = context.current_topic
    part1_session.current_difficulty = context.current_difficulty.name
    part1_session.evaluations = [e.model_dump() for e in context.evaluations]
    part1_session.strengths = context.strengths
    part1_session.gaps = context.gaps

    session_service.update_session(part1_session)
