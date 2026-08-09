"""
feedback_generator.py

This file produces the final structured feedback at the end of an
interview - the object that gets placed directly into the
POST /api/interview response's "feedback" field once done=true.

It reviews the whole transcript and all per-question evaluations
gathered during the interview, and asks the LLM to synthesize them
into a short, honest, actionable summary. The output shape is
validated against FinalFeedback, which matches the technical spec's
required schema exactly.
"""

from app.agent import prompts
from app.models.session import CandidateAnalysis, FinalFeedback, InterviewContext
from app.models.candidate import Candidate
from app.services import llm_service


def generate_feedback(
    candidate: Candidate,
    analysis: CandidateAnalysis,
    context: InterviewContext,
) -> FinalFeedback:
    """
    Generate the final feedback object for a completed interview.
    """
    system_prompt, user_prompt = prompts.final_feedback_prompt(
        candidate=candidate,
        analysis=analysis,
        context=context,
    )

    raw = llm_service.generate_json(system_prompt, user_prompt)
    return FinalFeedback.model_validate(raw)
