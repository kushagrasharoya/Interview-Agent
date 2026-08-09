"""
question_generator.py

This file is responsible for producing ONE interview question at a
time - either a brand-new question on a curriculum topic, or a
follow-up question that digs into a gap from the candidate's last
answer.

It never talks to the LLM provider directly - it builds a prompt (see
prompts.py) and hands it to llm_service.generate_json(), then
validates the result into a GeneratedQuestion object.
"""

from app.agent import prompts
from app.models.session import (
    AnswerEvaluation,
    CandidateAnalysis,
    GeneratedQuestion,
    InterviewContext,
    QuestionLevel,
)
from app.models.candidate import Candidate
from app.services import curriculum_service, llm_service


class CurriculumDayNotFoundError(ValueError):
    """Raised when asked to generate a question for a day that doesn't exist."""


def _get_day_or_raise(day_number: int) -> dict:
    day = curriculum_service.get_day(day_number)
    if day is None:
        raise CurriculumDayNotFoundError(
            f"Curriculum day {day_number} does not exist in curriculum.json."
        )
    return day


def _is_repeat(question_text: str, context: InterviewContext) -> bool:
    """
    Lightweight safety check: has this exact question (or something
    identical after trimming/casing) already been asked?

    This is NOT a substitute for the LLM being told the full list of
    prior questions in the prompt (see prompts.py) - it's just a cheap
    extra guard. Part 3 could extend this with a retry loop if it ever
    fires in practice.
    """
    normalized = question_text.strip().lower()
    return any(q.question.strip().lower() == normalized for q in context.asked_questions)


def generate_question(
    candidate: Candidate,
    analysis: CandidateAnalysis,
    context: InterviewContext,
    target_day: int,
    level: QuestionLevel,
) -> GeneratedQuestion:
    """
    Generate a brand-new (non-follow-up) interview question grounded
    in `target_day` of the curriculum, at the given difficulty level.
    """
    curriculum_day = _get_day_or_raise(target_day)

    system_prompt, user_prompt = prompts.question_generation_prompt(
        candidate=candidate,
        analysis=analysis,
        curriculum_day=curriculum_day,
        level=level,
        context=context,
    )

    raw = llm_service.generate_json(system_prompt, user_prompt)
    question = GeneratedQuestion.model_validate(
        {
            "day": raw.get("day", target_day),
            "topic": raw.get("topic", curriculum_day["title"]),
            "level": raw.get("level", level.value),
            "question": raw["question"],
            "is_followup": False,
        }
    )

    if _is_repeat(question.question, context):
        # Prevent repeating identical questions by pulling from curriculum objectives
        objectives = curriculum_day.get("objectives", [])
        alt_q = None
        for obj in objectives:
            candidate_text = f"Regarding {curriculum_day['title']}: {obj} — how did you design and implement this in practice?"
            if not _is_repeat(candidate_text, context):
                alt_q = candidate_text
                break
        if alt_q:
            question = GeneratedQuestion(
                day=target_day,
                topic=curriculum_day["title"],
                level=level,
                question=alt_q,
                is_followup=False,
            )

    return question


def generate_followup_question(
    candidate: Candidate,
    previous_question: GeneratedQuestion,
    answer_text: str,
    evaluation: AnswerEvaluation,
) -> GeneratedQuestion:
    """
    Generate a follow-up question that probes the gaps identified in
    `evaluation`, staying on the same curriculum day/topic as
    `previous_question`.
    """
    curriculum_day = _get_day_or_raise(previous_question.day)

    system_prompt, user_prompt = prompts.follow_up_question_prompt(
        question=previous_question,
        answer_text=answer_text,
        evaluation=evaluation,
        curriculum_day=curriculum_day,
    )

    raw = llm_service.generate_json(system_prompt, user_prompt)
    followup = GeneratedQuestion.model_validate(
        {
            "day": raw.get("day", previous_question.day),
            "topic": raw.get("topic", previous_question.topic),
            "level": raw.get("level", previous_question.level.value),
            "question": raw["question"],
            "is_followup": True,
        }
    )

    if _is_repeat(followup.question, context := InterviewContext(candidate=candidate, asked_questions=context.asked_questions if 'context' in locals() else [])):
        missing = ", ".join(evaluation.missing_concepts) or "this topic"
        alt_followup = f"Could you provide a concrete example of how you implemented {missing} on Day {previous_question.day} ({curriculum_day['title']})?"
        followup = GeneratedQuestion(
            day=previous_question.day,
            topic=previous_question.topic,
            level=previous_question.level,
            question=alt_followup,
            is_followup=True,
        )

    return followup
