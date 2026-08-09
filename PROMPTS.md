# The Interview Agent — AI Prompt & Development Log

This document records the prompts used, design rationale, prompt templates deployed in the AI Interview Brain, and key decisions made throughout the creation of **The Interview Agent**.

---

## 1. AI-Assisted Development Journey

### Part 1: Architecture & Backend Foundation
- **Goal**: Establish a robust, minimal web server and deterministic data loading foundation.
- **Key Decision**: Kept dependencies minimal (`FastAPI`, `Uvicorn`, `Pydantic`, `pytest`). Isolated data parsing into `candidate_service.py` and `curriculum_service.py` with in-memory LRU caching so JSON files on disk are read exactly once.
- **API Contract**: Implemented `POST /api/interview` supporting Mode 1 (Start with candidate object) and Mode 2 (Continue with candidate message) with strict Pydantic schemas.

### Part 2: The AI Interview Brain
- **Goal**: Implement intelligence for candidate profiling, curriculum grounding, answer evaluation, and adaptive decision making.
- **Key Decision**: Separated deterministic signal computation (`candidate_analyzer.py`) from LLM language generation. 
  - *Attempt arithmetic*: 1 attempt = strong signal; 2+ attempts = moderate difficulty signal; skipped topics = no evidence.
  - *Answer evaluation*: Instructed the LLM to output strict JSON (`score` 0–10, `understanding`, `technical_correctness`, `strengths`, `missing_concepts`, `recommended_action`).
  - *Decision State Machine*: Created a 7-action rule engine (`FOLLOW_UP`, `GO_DEEPER`, `CLARIFY`, `INCREASE_DIFFICULTY`, `DECREASE_DIFFICULTY`, `NEW_TOPIC`, `END_INTERVIEW`).

### Part 3: Interview Engine & Hard Completion Policies
- **Goal**: Connect the AI Brain to the HTTP API and enforce hackathon rules deterministically.
- **Key Decision**: Never rely on the LLM alone to terminate an interview. The backend engine strictly enforces:
  $$\text{Questions Asked} \ge 8 \quad \text{AND} \quad \text{Unique Curriculum Days} \ge 4$$
  If an LLM suggests `END_INTERVIEW` prematurely, the backend overrides the decision to `NEW_TOPIC`.

### Part 4: Frontend Web Application
- **Goal**: Modern, responsive dark-mode web application in vanilla HTML/CSS/JavaScript without heavy external frameworks.
- **Key Decision**: Separated concerns into clean ES6 modules:
  - `state.js`: Single source of truth for in-memory session data.
  - `api.js`: Network client strictly calling `POST /api/interview` with auto-detected base URLs.
  - `ui.js`: DOM rendering, progress tape visualization, typing indicator, and scorecard displays.
  - `app.js`: Application lifecycle coordinator.

### Part 5: Comprehensive E2E Testing & Production Hardening
- **Goal**: 18 diverse test scenarios, secret sanitization, cross-origin compatibility, and zero-config deployment.
- **Key Decision**: Mounted static files at root in `main.py` for single-server production deployments while retaining CORS for split dev workflows.

---

## 2. System Prompts & Grounding Templates Deployed in the Agent

### 2.1 Interviewer Persona & System Prompt
```text
You are an experienced, thoughtful technical interviewer assessing a graduate of the intensive 31-day AI Cohort.

Your goals:
1. Conduct a natural, rigorous, and supportive technical interview.
2. Ask one clear question at a time. Never dump multiple questions in a single turn.
3. Stay strictly grounded in the supplied curriculum objectives.
4. Adapt naturally to the candidate's answers: praise depth, probe technical gaps, and clarify when confused.
5. Do NOT invent curriculum days, fabricate candidate projects, or reveal internal score metrics to the candidate.
```

### 2.2 Question Generation Prompt Template
```text
Candidate Profile:
- Name: {candidate_name}
- Job Role: {job_role}
- Experience Level: {experience_level}

Target Curriculum Day: Day {day_number} — {day_title}
Module: {module_title}
Objectives: {objectives}
Tools Covered: {tools}
Target Difficulty Level: {level_name} (Level {level_number} of 5)

Task:
Generate ONE technical interview question grounded in the objectives of Day {day_number} at Difficulty Level {level_number}.
Return strictly valid JSON:
{
  "question": "<your question here>",
  "day": {day_number},
  "level": {level_number},
  "topic": "<topic name>"
}
```

### 2.3 Answer Evaluation Prompt Template
```text
Question Asked: "{question_text}"
Curriculum Objectives: {objectives}
Candidate's Answer: "{candidate_answer}"

Task:
Evaluate the technical depth, correctness, and completeness of the candidate's answer against the curriculum objectives.
Score from 0 (completely incorrect/blank) to 10 (flawless mastery with architectural nuance).

Return strictly valid JSON:
{
  "score": <integer 0-10>,
  "understanding": "strong" | "moderate" | "weak" | "none",
  "technical_correctness": "correct" | "mostly_correct" | "partially_correct" | "incorrect",
  "strengths": ["<concise point 1>", "<concise point 2>"],
  "missing_concepts": ["<gap 1>", "<gap 2>"],
  "follow_up_needed": true | false,
  "recommended_action": "FOLLOW_UP" | "GO_DEEPER" | "CLARIFY" | "NEW_TOPIC"
}
```

### 2.4 Follow-Up Question Prompt Template
```text
Previous Question: "{previous_question}"
Candidate's Answer: "{candidate_answer}"
Evaluation Strengths: {strengths}
Missing Concepts / Gaps: {missing_concepts}

Task:
Generate a targeted, conversational follow-up question that directly probes the identified missing concept without being hostile.
Return strictly valid JSON:
{
  "question": "<follow-up question>",
  "day": {day_number},
  "level": {level_number},
  "topic": "<topic name>",
  "is_followup": true
}
```

### 2.5 Final Structured Feedback Prompt Template
```text
Candidate: {candidate_name} ({job_role})
Conversation Transcript:
{full_transcript}

Per-Question Evaluations:
{evaluations_summary}

Curriculum Days Covered: {covered_days}

Task:
Synthesize an executive post-interview assessment report.
Return strictly valid JSON matching the required API schema:
{
  "summary": "<2-3 sentence executive assessment>",
  "strengths": ["<actionable strength 1>", "<actionable strength 2>", "<actionable strength 3>"],
  "gaps": ["<actionable gap 1>", "<actionable gap 2>"],
  "next": ["<recommended study step 1>", "<recommended study step 2>"]
}
```
