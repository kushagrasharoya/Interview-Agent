# The Interview Agent

> **An adaptive AI Technical Interviewer grounded in curriculum objectives, candidate learning signals, and multi-turn conversational reasoning.**

---

## 1. Problem Statement
The 31-day enterprise AI Cohort covers modern applied AI topics:
- Dense Vector Retrieval & Embeddings
- Vector Databases (HNSW Indexing & Metric Spaces)
- Prompt Engineering & Structured Outputs
- Agentic AI & Tool Calling (LangChain / ReAct)
- Model Context Protocol (MCP)
- Production AI Deployment (Docker, Kubernetes, Observability)

After completing the cohort, learners must explain the systems they built and defend their engineering tradeoffs in technical interviews. Preparing for realistic interviews and communicating complex technical concepts remains one of the hardest hurdles for engineers.

---

## 2. What The Project Does
**The Interview Agent** conducts realistic, personalized, multi-turn technical interviews tailored to each candidate's learning journey:
- Reads candidate mission attempts, completions, and skipped topics to identify genuine learning signals.
- Grounds technical questions directly in the 31-day curriculum objectives.
- Evaluates candidate answers in real time, identifying technical strengths and missing concepts.
- Generates contextual follow-ups when gaps are detected or raises difficulty when strong understanding is demonstrated.
- Enforces strict interview completion rules ($\ge 8$ questions across $\ge 4$ unique curriculum days).
- Synthesizes post-interview structured feedback (`summary`, `strengths`, `gaps`, `next`).

---

## 3. Key Features
1. **Curriculum-Grounded Question Generation**: Questions are grounded in real tools and objectives from `curriculum.json`.
2. **Learning Signal Extraction**: Distinguishes between clean 1st-try passes (strong signal), multi-try passes (moderate signal), failures (weak signal), and skipped days (no evidence).
3. **Structured Answer Evaluation**: Evaluates answers with 0–10 scoring, technical correctness checks, and missing concept extraction.
4. **Adaptive 7-Action Decision Engine**: Deterministically chooses `FOLLOW_UP`, `GO_DEEPER`, `CLARIFY`, `INCREASE_DIFFICULTY`, `DECREASE_DIFFICULTY`, `NEW_TOPIC`, or `END_INTERVIEW`.
5. **Hard Completion Enforcer**: Guarantees $\ge 8$ questions and $\ge 4$ unique curriculum days before allowing the interview to finish.
6. **Multi-Provider LLM Service**: Supports Anthropic Claude, Google Gemini, OpenAI, or offline Mock fallback.
7. **Single-Endpoint API Contract**: Exposes `POST /api/interview` with session memory keyed by `sessionId`.
8. **Modern Responsive UI**: Dark-mode web interface with live arena transcript, progress tape, typing indicator, and scorecard.

---

## 4. Architecture & Flow Diagram

```
Frontend Client (Browser)
            │
            ▼  POST /api/interview { sessionId, candidate | message }
   FastAPI Server (backend/app/main.py)
            │
            ▼
   Interview Router (backend/app/api/interview.py)
            │
            ▼
   Interview Engine (backend/app/engine/interview_engine.py)
            │
     ┌──────┴──────────────────────────────────────────────────────┐
     │                                                             │
     ▼                                                             ▼
Data Services (backend/app/services/)                 AI Agent (backend/app/agent/)
├── candidate_service.py (candidates.json)           ├── candidate_analyzer.py (signal analysis)
├── curriculum_service.py (curriculum.json)          ├── question_generator.py (grounded questions)
├── session_service.py (in-memory store)             ├── answer_evaluator.py (structured scoring)
└── llm_service.py (Gemini / Claude / OpenAI)        ├── decision_engine.py (7-action state machine)
                                                     ├── feedback_generator.py (final assessment)
                                                     └── prompts.py (system personas & templates)
```

---

## 5. Tech Stack
- **Backend**: Python 3.10+, FastAPI, Uvicorn, Pydantic v2
- **Testing**: pytest, pytest-asyncio, HTTPX / Starlette TestClient (58 automated tests)
- **AI / LLMs**: Google Gemini (`google-genai`), Anthropic (`anthropic`), OpenAI (`openai`)
- **Frontend**: Vanilla HTML5, CSS3 (custom dark-mode design system), Modern ES6 JavaScript

---

## 6. Project Structure

```
Interview-Agent/
├── README.md                          ← Main project documentation
├── PROMPTS.md                         ← AI development log & system prompts
├── technical-spec.md                  ← API specification
├── .gitignore
│
├── backend/
│   ├── requirements.txt               ← Backend dependencies
│   ├── .env.example                   ← Environment variables template
│   │
│   ├── app/
│   │   ├── main.py                    ← FastAPI entrypoint & static mount
│   │   ├── config.py                  ← Constants & file paths
│   │   │
│   │   ├── api/
│   │   │   └── interview.py           ← POST /api/interview endpoint
│   │   │
│   │   ├── models/
│   │   │   ├── candidate.py           ← Candidate data validation schemas
│   │   │   └── session.py             ← Session, context, and evaluation schemas
│   │   │
│   │   ├── services/
│   │   │   ├── candidate_service.py   ← candidates.json loader
│   │   │   ├── curriculum_service.py  ← curriculum.json loader
│   │   │   ├── session_service.py     ← In-memory session store
│   │   │   └── llm_service.py         ← Central multi-provider LLM caller
│   │   │
│   │   ├── agent/
│   │   │   ├── candidate_analyzer.py  ← Deterministic learning signal extractor
│   │   │   ├── question_generator.py  ← Curriculum-grounded question generator
│   │   │   ├── answer_evaluator.py    ← Structured 0-10 answer evaluator
│   │   │   ├── decision_engine.py     ← 7-action adaptive state machine
│   │   │   ├── feedback_generator.py  ← Final structured feedback synthesizer
│   │   │   └── prompts.py             ← System prompts and formatting templates
│   │   │
│   │   └── engine/
│   │       └── interview_engine.py    ← E2E Interview lifecycle orchestrator
│   │
│   ├── data/
│   │   ├── candidates.json            ← Synthetic AI cohort candidates
│   │   └── curriculum.json            ← 31-day course curriculum
│   │
│   └── tests/
│       ├── test_foundation.py         ← Part 1 tests (8 passed)
│       ├── test_ai_brain.py           ← Part 2 tests (17 passed)
│       ├── test_interview_engine.py   ← Part 3 tests (16 passed)
│       └── test_e2e_scenarios.py      ← Part 5 tests (17 passed)
│
└── frontend/
    ├── index.html                     ← 3-screen interface
    ├── css/
    │   └── style.css                  ← Responsive dark-mode styling
    ├── js/
    │   ├── app.js                     ← UI lifecycle coordinator
    │   ├── api.js                     ← Network fetch client
    │   ├── state.js                   ← Client state manager
    │   └── ui.js                      ← DOM renderer & view transitions
    ├── assets/
    │   └── candidates.json            ← Roster picker dataset
    └── README.md
```

---

## 7. How Candidate Data is Used
Candidate data is loaded from `candidates.json` and validated through `Candidate` models:
- **`jobRole` & `yearsExperience`**: Determines initial difficulty level (Junior $\to$ Conceptual, Mid $\to$ Understanding, Senior $\to$ Application).
- **`missions` & `attempts`**:
  - `1 attempt + passed` $\to$ **Strong Signal** (probe deep into architectural tradeoffs).
  - `2+ attempts + passed` $\to$ **Moderate Signal** (inspect for conceptual gaps).
  - `passed: false` $\to$ **Weak Signal** (probe gently with foundational questions).
  - `skipped: true` $\to$ **No Evidence** (do not assume prior knowledge).

---

## 8. How Curriculum Data is Used
Every question is grounded in `curriculum.json` (31 days across 9 modules):
- `day` & `title`: Topic anchor.
- `objectives`: Specific competencies tested in questions and evaluated in answers.
- `tools`: Real frameworks (e.g. `HNSWLib`, `LangChain`, `FastAPI`, `Docker`, `MCP`).

---

## 9. How Adaptive Interviewing Works

### 5-Level Difficulty Hierarchy
1. **Level 1: Conceptual** — Core definitions and high-level principles.
2. **Level 2: Understanding** — Mechanism explanations and design reasoning.
3. **Level 3: Application** — Practical implementation and parameter selection.
4. **Level 4: Engineering** — Edge cases, error recovery, and troubleshooting.
5. **Level 5: Architecture** — End-to-end distributed system design and tradeoffs.

### 7-Action Decision Machine
- `FOLLOW_UP`: Probes an identified missing concept on the same question.
- `GO_DEEPER`: Asks a higher-difficulty question on the same topic for strong answers.
- `CLARIFY`: Rephrases or simplifies when a candidate struggles.
- `INCREASE_DIFFICULTY`: Advances to higher difficulty on a new topic.
- `DECREASE_DIFFICULTY`: Steps down difficulty when repeated struggle occurs.
- `NEW_TOPIC`: Transitions to a new curriculum module.
- `END_INTERVIEW`: Triggers completion when all minimum constraints are satisfied.

---

## 10. API Specification

### `POST /api/interview`

#### Mode 1: Start Interview
```json
{
  "sessionId": "session-123",
  "candidate": {
    "member": {
      "id": "CAND-001",
      "name": "Sarah Johnson",
      "jobRole": "Senior Data Engineer",
      "yearsExperience": 9,
      "education": "MS Computer Science",
      "status": "COMPLETED"
    },
    "missions": [
      { "day": 7, "title": "Embeddings Explained", "passed": true, "attempts": 1 }
    ],
    "signals": { "commitDays": 28, "missionsCompleted": 30, "missionsFirstTry": 20 }
  }
}
```
**Response:**
```json
{
  "reply": "Welcome, Sarah Johnson! Let's begin your interview.\n\nHow do embedding vector dimensions impact search accuracy versus computational cost in dense retrieval?",
  "done": false
}
```

#### Mode 2: Continue Interview
```json
{
  "sessionId": "session-123",
  "message": "Higher dimensions capture richer semantic nuance, but increase cosine similarity compute and memory footprint."
}
```
**Response (In Progress):**
```json
{
  "reply": "Great answer. In a production vector database, how would you configure HNSW M and ef_construction parameters to balance indexing time against query latency?",
  "done": false
}
```
**Response (Final Turn):**
```json
{
  "reply": "Interview completed.",
  "done": true,
  "feedback": {
    "summary": "Sarah demonstrated strong mastery of embeddings and vector search architectures.",
    "strengths": [
      "Deep understanding of vector quantization and index tuning",
      "Clear explanation of multi-agent orchestration"
    ],
    "gaps": [
      "Could deepen observability and telemetry in distributed MCP setups"
    ],
    "next": [
      "Review OpenTelemetry trace propagation in async agent graphs",
      "Practice Kubernetes horizontal pod autoscaling for embedding services"
    ]
  }
}
```

---

## 11. Local Setup & Installation

```bash
# 1. Clone the repository
git clone https://github.com/kushagrasharoya/Interview-Agent.git
cd Interview-Agent

# 2. Set up Python virtual environment
cd backend
python -m venv .venv

# On Windows (PowerShell):
.venv\Scripts\Activate.ps1

# On macOS/Linux:
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt
```

---

## 12. Environment Variables

Copy the example `.env` file in `backend/`:
```bash
cp .env.example .env
```
Fill in your chosen LLM provider credentials:
```env
LLM_PROVIDER=gemini  # Options: gemini | anthropic | openai | mock
GEMINI_API_KEY=your_gemini_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
```
*(Note: If no API key is provided, the engine defaults to mock mode so tests and local runs work out of the box).*

---

## 13. How to Run the Backend
```bash
cd backend
.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000
```
- API Endpoint: `http://127.0.0.1:8000/api/interview`
- Interactive Swagger Docs: `http://127.0.0.1:8000/docs`

---

## 14. How to Run the Frontend
Option A (Standalone):
```bash
cd frontend
python -m http.server 5500
```
Open `http://127.0.0.1:5500` in your browser.

Option B (Single-Server Mode):
When the backend server runs (`http://127.0.0.1:8000`), opening `http://127.0.0.1:8000` automatically serves the full frontend application.

---

## 15. How to Run Tests
All 58 unit, integration, and E2E tests run offline with zero external network dependencies:
```bash
cd backend
pytest -v
```
**Output:**
```
======================== 58 passed, 1 warning in 0.65s ========================
```

---

## 16. Deployment Guide

### Deploying on Render / Railway
1. **Build Command**: `pip install -r backend/requirements.txt`
2. **Start Command**: `uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT`
3. **Environment Variables**: Add `GEMINI_API_KEY` (or `ANTHROPIC_API_KEY`), and `LLM_PROVIDER`.
4. The application automatically serves both the API and the web frontend from a single URL!

---

## 17. AI-Assisted Development Note
This project was developed through a systematic 5-part architecture using advanced AI pair-programming assistants. Prompts, architectural decisions, and human iterations are documented in detail in [PROMPTS.md](file:///e:/VICODATHON/Interview-Agent/PROMPTS.md).

---

## 18. Limitations
- Evaluator scoring is bounded by prompt token budgets.
- Sessions are maintained in an in-memory store; server restarts clear active session history.

---

## 19. Future Improvements
- Persistent PostgreSQL/Redis session store for multi-server horizontally scalable clusters.
- Real-time WebRTC audio streaming for live voice interview conversations.
- Radar competency charts visualizing score breakdown across cohort curriculum modules.

---

## 20. Hackathon Submission Verification Checklist
- [x] Functional technical interview chatbot meeting all specs
- [x] $\ge 8$ questions enforced
- [x] $\ge 4$ distinct curriculum days covered
- [x] Contextual follow-up generation
- [x] Structured `{ summary, strengths, gaps, next }` feedback
- [x] `POST /api/interview` contract strictly preserved
- [x] In-memory session tracking via `sessionId`
- [x] 0 hardcoded secrets committed
- [x] Comprehensive automated test suite (58 passed)
