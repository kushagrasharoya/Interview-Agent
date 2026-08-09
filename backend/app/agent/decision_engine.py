"""
decision_engine.py

This file decides what the interviewer should do NEXT, after seeing
how the candidate answered the last question.

Why this is plain Python and NOT left up to the LLM:
The hackathon brief is explicit: "Do not rely solely on the LLM to
enforce these requirements." The LLM's evaluation includes its own
opinion (`recommended_action`), but the final call is made here, by
simple, predictable, testable rules that always consider the full
interview state - not just the last answer in isolation. This is what
keeps the interview from (for example) follow-up-ing the same question
forever, or ending after only 3 questions.

The seven possible actions (from the hackathon brief):
    FOLLOW_UP            - ask a clarifying follow-up on the same question
    NEW_TOPIC            - move on to a different curriculum day
    GO_DEEPER            - ask a harder question on the SAME topic
    CLARIFY              - candidate seems confused; rephrase/simplify
    INCREASE_DIFFICULTY  - raise the difficulty level going forward
    DECREASE_DIFFICULTY  - lower the difficulty level going forward
    END_INTERVIEW        - wrap up the interview
"""

from app.config import MINIMUM_CURRICULUM_DAYS_COVERED, MINIMUM_QUESTIONS
from app.models.session import (
    AnswerEvaluation,
    DecisionAction,
    InterviewContext,
    InterviewDecision,
    QuestionLevel,
)

# Score thresholds (answers are scored 0-10 by the evaluator).
WEAK_SCORE_THRESHOLD = 3       # at or below this = candidate is struggling
STRONG_SCORE_THRESHOLD = 8     # at or above this = candidate is doing very well

# Don't follow up on the same question more than this many times -
# after that, move on rather than grilling the candidate forever.
MAX_FOLLOWUPS_PER_QUESTION = 1

# Don't go deeper on the same curriculum day more than this many times
# in a row - even a strong candidate should get breadth, not just depth
# on one topic.
MAX_QUESTIONS_PER_DAY_BEFORE_MOVING_ON = 3


def _clamp_level(level: QuestionLevel, delta: int) -> QuestionLevel:
    """Move a difficulty level up/down by `delta`, staying within 1-5."""
    new_value = max(QuestionLevel.CONCEPTUAL.value, min(QuestionLevel.ARCHITECTURE.value, level.value + delta))
    return QuestionLevel(new_value)


def decide_next_action(
    context: InterviewContext,
    evaluation: AnswerEvaluation,
) -> InterviewDecision:
    """
    Decide what should happen next, given the current interview state
    and the evaluation of the most recent answer.

    Checks are ordered from "most urgent" to "least urgent" - the
    first matching rule wins.
    """
    days_covered = len(set(context.covered_curriculum_days))
    minimums_met = context.question_count >= MINIMUM_QUESTIONS and days_covered >= MINIMUM_CURRICULUM_DAYS_COVERED

    current_day = context.asked_questions[-1].day if context.asked_questions else None
    questions_on_current_day = context.questions_per_day.get(current_day, 0) if current_day else 0

    # 1. Candidate is clearly struggling.
    if evaluation.score <= WEAK_SCORE_THRESHOLD:
        if context.followups_used_on_current_question < MAX_FOLLOWUPS_PER_QUESTION:
            return InterviewDecision(
                action=DecisionAction.CLARIFY,
                reason=(
                    f"Score {evaluation.score}/10 is at or below the weak threshold "
                    f"({WEAK_SCORE_THRESHOLD}) - rephrase or simplify before moving on."
                ),
            )
        return InterviewDecision(
            action=DecisionAction.DECREASE_DIFFICULTY,
            reason="Candidate still struggling after a clarification - lower the difficulty.",
            target_level=_clamp_level(context.current_difficulty, -1),
        )

    # 2. The evaluator flagged a genuine gap worth following up on
    #    (and we haven't already used our follow-up budget here).
    if evaluation.follow_up_needed and context.followups_used_on_current_question < MAX_FOLLOWUPS_PER_QUESTION:
        return InterviewDecision(
            action=DecisionAction.FOLLOW_UP,
            reason="Answer left a specific gap worth probing before moving on.",
        )

    # 3. Minimum requirements satisfied and answer is solid -> Wrap up
    if minimums_met and evaluation.score >= 6 and not evaluation.follow_up_needed:
        return InterviewDecision(
            action=DecisionAction.END_INTERVIEW,
            reason=(
                f"Minimum requirements met ({context.question_count} questions across "
                f"{days_covered} curriculum days) and the interview has reached a natural "
                "closing point."
            ),
        )

    # 4. Candidate is doing very well (before interview completion).
    if evaluation.score >= STRONG_SCORE_THRESHOLD:
        if questions_on_current_day < MAX_QUESTIONS_PER_DAY_BEFORE_MOVING_ON and context.current_difficulty.value < QuestionLevel.ARCHITECTURE.value:
            return InterviewDecision(
                action=DecisionAction.GO_DEEPER,
                reason=(
                    f"Score {evaluation.score}/10 is at or above the strong threshold "
                    f"({STRONG_SCORE_THRESHOLD}) - ask a harder question on the same topic."
                ),
                target_level=_clamp_level(context.current_difficulty, 1),
            )
        return InterviewDecision(
            action=DecisionAction.INCREASE_DIFFICULTY,
            reason="Candidate has shown strong understanding across this topic - raise the bar and move to a new curriculum day.",
            target_level=_clamp_level(context.current_difficulty, 1),
        )

    # 5. Default: move on to a new topic to keep breadth up.
    return InterviewDecision(
        action=DecisionAction.NEW_TOPIC,
        reason="Solid answer with no specific follow-up needed - move to a new curriculum area.",
    )
