"""
answer_evaluator.py

This file is responsible for judging ONE candidate answer and turning
it into a structured AnswerEvaluation (score, understanding level,
strengths, missing concepts, etc) instead of free-form text.

Structured output matters here because the decision engine
(decision_engine.py) needs to make reliable if/else decisions based on
this result - it can't safely parse a paragraph of prose every time.
"""

from app.agent import prompts
from app.models.session import AnswerEvaluation, GeneratedQuestion
from app.services import curriculum_service, llm_service


def evaluate_answer(question: GeneratedQuestion, answer_text: str) -> AnswerEvaluation:
    """
    Send the question + candidate's answer to the LLM and return a
    validated AnswerEvaluation.

    Raises pydantic's ValidationError if the LLM's JSON doesn't match
    the required shape (e.g. an out-of-range score, or an
    understanding value outside strong/moderate/weak/none) - this is
    intentional, so a malformed evaluation fails loudly instead of
    silently corrupting the interview's decision-making.
    """
    curriculum_day = curriculum_service.get_day(question.day)
    if curriculum_day is None:
        raise ValueError(f"Curriculum day {question.day} does not exist in curriculum.json.")

    system_prompt, user_prompt = prompts.answer_evaluation_prompt(
        question=question,
        curriculum_day=curriculum_day,
        answer_text=answer_text,
    )

    raw = llm_service.generate_json(system_prompt, user_prompt)
    return AnswerEvaluation.model_validate(raw)
