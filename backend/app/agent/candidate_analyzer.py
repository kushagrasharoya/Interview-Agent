"""
candidate_analyzer.py

This file turns a candidate's raw mission history into a structured
CandidateAnalysis: a verdict, per curriculum day, on how much real
evidence we actually have of their understanding.

Why this is plain Python and NOT an LLM call:
Deciding "1 attempt + passed = strong signal" is arithmetic and rule
matching, not something that benefits from a language model - and
getting it wrong would quietly bias the whole interview. Keeping this
deterministic makes it fast, free, and (importantly) unit-testable
without ever needing to mock an API. The LLM is used later for the
parts that actually need language understanding: writing questions,
judging free-text answers, and writing feedback prose.
"""

from app.models.session import CandidateAnalysis, MissionSignal, MissionSignalStrength
from app.models.candidate import Candidate, CandidateMission
from app.services import curriculum_service
from app.config import MINIMUM_CURRICULUM_DAYS_COVERED

# Attempts at or above this count still count as "passed", but are
# treated as a softer signal than a clean first-attempt pass.
MULTIPLE_ATTEMPTS_THRESHOLD = 2


def _score_mission(mission: CandidateMission) -> MissionSignal:
    """
    Decide how much evidence ONE mission result gives us about the
    candidate's real understanding of that day's topic.

    Rules (straight from the hackathon brief):
    - skipped                    -> NONE  (no evidence of mastery)
    - passed, 1 attempt          -> STRONG (strong positive signal)
    - passed, 2+ attempts        -> MODERATE (possible difficulty signal)
    - passed, attempts unknown   -> MODERATE (can't confirm it was easy)
    - failed (passed is False)   -> WEAK (weak evidence, they tried and struggled)
    - no data at all             -> NONE
    """
    if mission.skipped or (mission.passed is None and (mission.attempts is None or mission.attempts == 0)):
        return MissionSignal(
            day=mission.day,
            title=mission.title,
            strength=MissionSignalStrength.NONE,
            reason="Skipped / unattempted - no evidence the candidate ever studied this topic.",
        )

    if mission.passed is True:
        if mission.attempts is not None and mission.attempts >= MULTIPLE_ATTEMPTS_THRESHOLD:
            return MissionSignal(
                day=mission.day,
                title=mission.title,
                strength=MissionSignalStrength.MODERATE,
                reason=(
                    f"Passed, but took {mission.attempts} attempts - "
                    "may indicate some difficulty with this topic."
                ),
            )
        if mission.attempts == 1:
            return MissionSignal(
                day=mission.day,
                title=mission.title,
                strength=MissionSignalStrength.STRONG,
                reason="Passed on the first attempt - strong positive signal.",
            )
        # Passed, but we don't know how many attempts it took.
        return MissionSignal(
            day=mission.day,
            title=mission.title,
            strength=MissionSignalStrength.MODERATE,
            reason="Passed, but attempt count is unknown - treat as moderate evidence only.",
        )

    if mission.passed is False:
        return MissionSignal(
            day=mission.day,
            title=mission.title,
            strength=MissionSignalStrength.WEAK,
            reason="Attempted but did not pass - weak evidence, worth probing gently.",
        )

    return MissionSignal(
        day=mission.day,
        title=mission.title,
        strength=MissionSignalStrength.NONE,
        reason="Skipped / no completion data available for this mission.",
    )


def _experience_level(years_experience: int) -> str:
    """Bucket raw years of experience into a simple label used to frame questions."""
    if years_experience <= 2:
        return "junior"
    if years_experience <= 6:
        return "mid"
    return "senior"


def _select_focus_days(
    mission_signals: list[MissionSignal],
    min_days: int = MINIMUM_CURRICULUM_DAYS_COVERED,
) -> list[int]:
    """
    Choose which curriculum days the interview should prioritize.

    Strategy:
    1. Prefer a MIX of signal strengths (both strong days worth
       validating in depth, and weak/no-evidence days worth probing)
       rather than only the easiest or only the hardest.
    2. Prefer spreading across different curriculum MODULES, so the
       interview doesn't just ask 4 questions about 4 days that are
       all part of the same mini-topic.
    3. Always return at least `min_days` days when the candidate has
       that many missions at all (guarantees the hackathon's "cover at
       least 4 curriculum days" requirement is achievable).
    """
    # Interleave strengths so we don't accidentally pick 4 STRONG days
    # in a row: order = STRONG, WEAK, MODERATE, NONE, then repeat.
    priority = {
        MissionSignalStrength.STRONG: 0,
        MissionSignalStrength.WEAK: 1,
        MissionSignalStrength.MODERATE: 2,
        MissionSignalStrength.NONE: 3,
    }
    ordered = sorted(mission_signals, key=lambda s: priority[s.strength])

    chosen: list[int] = []
    used_modules: set[int | None] = set()

    # First pass: pick one day per module, in priority order.
    for signal in ordered:
        module = curriculum_service.get_module_for_day(signal.day)
        module_n = module["n"] if module else None
        if module_n in used_modules:
            continue
        chosen.append(signal.day)
        used_modules.add(module_n)
        if len(chosen) >= min_days:
            return chosen

    # Second pass: still short (candidate's missions cluster in very
    # few modules) - fill remaining slots with any not-yet-chosen
    # mission day, in the same priority order.
    for signal in ordered:
        if signal.day in chosen:
            continue
        chosen.append(signal.day)
        if len(chosen) >= min_days:
            break

    return chosen


def analyze_candidate(candidate: Candidate) -> CandidateAnalysis:
    """
    The main entry point: turn a full Candidate record into a
    CandidateAnalysis the rest of the AI brain can use.
    """
    mission_signals = [_score_mission(m) for m in candidate.missions]

    strong_days = [s.day for s in mission_signals if s.strength == MissionSignalStrength.STRONG]
    weak_days = [s.day for s in mission_signals if s.strength in (MissionSignalStrength.WEAK, MissionSignalStrength.MODERATE)]
    no_evidence_days = [s.day for s in mission_signals if s.strength == MissionSignalStrength.NONE]

    focus_days = _select_focus_days(mission_signals)

    notes = (
        f"{len(strong_days)} strong signal(s), {len(weak_days)} weak signal(s), "
        f"{len(no_evidence_days)} day(s) with no evidence "
        f"(including skipped topics), out of {len(mission_signals)} missions total."
    )

    return CandidateAnalysis(
        experience_level=_experience_level(candidate.member.yearsExperience),
        mission_signals=mission_signals,
        strong_days=strong_days,
        weak_days=weak_days,
        no_evidence_days=no_evidence_days,
        suggested_focus_days=focus_days,
        notes=notes,
    )
