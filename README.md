# The Interview Agent — Part 1: Foundation

This is **Part 1 of 5** of "The Interview Agent," an AI technical
interviewer built for the AI Cohort hackathon.

Part 1 does **not** run a real AI interview yet. It builds the
foundation everything else will be built on: a working web server, the
required `POST /api/interview` endpoint, and the data/session
plumbing behind it. Where the real AI logic will eventually go, you'll
see a placeholder reply and a comment saying "Part 2 goes here."

---

## 1. Big picture: what is this project?

Imagine a real technical interviewer. They:

- Know the candidate's background (what they studied, what they built).
- Ask questions.
- Listen to the answers and ask smart follow-up questions.
- At the end, summarize how the candidate did.

"The Interview Agent" is a program that does this automatically, using
the candidate's actual progress through the "AI Cohort" course
(`candidates.json`) and the course content itself (`curriculum.json`)
to ask relevant questions.

The **backend** (the part we built in Part 1) is the "brain and
memory" — it runs on a server, keeps track of each interview in
progress, and will (starting in Part 2) generate the interviewer's
questions. The **frontend** (Part 4) will be the chat window a
candidate actually types into.

---

## 2. What each folder does

```
the-interview-agent/
├── README.md              ← you are here
├── PROMPTS.md              ← placeholder; filled in properly in Part 5
├── technical-spec.md       ← the API contract we must not break
├── .gitignore
│
├── backend/                ← everything that runs the server
│   ├── requirements.txt    ← list of Python packages this project needs
│   ├── app/                ← the actual application code
│   │   ├── main.py         ← starts the web server
│   │   ├── config.py       ← file paths & constants, kept in one place
│   │   ├── api/             ← handles HTTP requests/responses
│   │   ├── models/          ← describes the "shape" of our data
│   │   └── services/        ← the logic that reads data & manages sessions
│   ├── data/                ← the provided JSON files live here (unedited)
│   └── tests/                ← automated tests
│
└── frontend/                ← empty for now; built in Part 4
```

Think of it like a restaurant:
- `models/` = the recipe cards (what a valid dish looks like).
- `services/` = the kitchen (does the actual work: fetching
  ingredients, cooking).
- `api/` = the waiter (takes the customer's order, brings back food,
  speaks "HTTP" to the outside world).
- `main.py` = the restaurant's front door / open sign.

---

## 3. What each Python file does

### `app/main.py`
Starts the FastAPI web server and plugs in the interview endpoint.
This is the file you actually run.

### `app/config.py`
Holds file paths (where `candidates.json` and `curriculum.json` live)
and a couple of constants (like "minimum 8 questions"). Having one
place for these means we never have to hunt through multiple files to
change a path or a number later.

### `app/models/candidate.py`
Describes what a valid **candidate** object looks like (using
Pydantic — see below). It does not contain any real candidate data,
just the *shape* that data must follow.

### `app/models/session.py`
Describes what a valid **interview session** looks like while an
interview is happening: which candidate it belongs to, the
conversation so far, how many questions have been asked, which
curriculum days have been covered, and so on.

### `app/services/candidate_service.py`
Reads `data/candidates.json` from disk and turns it into validated
`Candidate` objects. Also has a function to find one candidate by ID.
This is the *only* file in the project that knows candidate data comes
from a JSON file — everyone else just asks it questions.

### `app/services/curriculum_service.py`
Same idea, but for `data/curriculum.json`: reads the file, and lets
other code ask things like "what is day 7 about?" or "which module is
day 12 part of?"

### `app/services/session_service.py`
Keeps interview sessions in memory (a Python dictionary) while the
server is running, keyed by `sessionId`. Supports create / get /
update / delete. This is what lets the interview "remember" the
conversation across multiple separate HTTP requests.

### `app/api/interview.py`
The only HTTP route in this project: `POST /api/interview`. Reads the
incoming JSON, figures out if it's a "start" or "continue" request,
calls the session service, and returns JSON shaped exactly like the
technical spec requires.

### `tests/test_foundation.py`
Automated checks that everything above actually works (server starts,
sessions are created and remembered, data loads correctly, etc).

---

## 4. Key concepts, explained simply

### What is FastAPI?
FastAPI is a Python tool for building web servers — programs that
listen for requests over the internet (or your local network) and
send back responses. We use it because it's beginner-friendly, fast,
and works very well with Pydantic (see next).

### What is Pydantic?
Pydantic lets us describe the "shape" of data as a Python class (e.g.
"a Candidate must have a name, which must be text"). When data comes
in, Pydantic automatically checks it against that shape and gives a
clear error if something's missing or wrong — instead of the program
crashing confusingly later on.

### What is a POST endpoint?
A "POST" request is one of the ways a program on the internet can ask
a server to *do something with data it's sending along* (as opposed to
"GET," which just asks the server to hand back data). Our frontend
(later) will POST a JSON object like `{"sessionId": "...", "message":
"..."}` to `/api/interview`, and the server sends a response back.

### What is JSON?
JSON (JavaScript Object Notation) is a plain-text way of writing
structured data using `{ }` for objects, `[ ]` for lists, and
`"key": value` pairs. It's the format almost all web APIs — including
ours — use to send data back and forth. `candidates.json` and
`curriculum.json` are both just JSON files sitting on disk.

### What does `sessionId` mean?
Since the server can be talking to many candidates' interviews at
once, and HTTP requests don't remember each other automatically, every
request needs to say *which* interview it belongs to. `sessionId` is
that label — a unique ID the frontend makes up once at the start of an
interview and then repeats on every following request, so the server
knows which conversation to continue.

---

## 5. How the data files are used

- **`candidates.json`** is read once (and cached) by
  `candidate_service.py`. When an interview starts, the frontend sends
  a candidate's data in the request; we validate it against our
  `Candidate` model and store it inside that interview's session. In
  Part 2, the AI brain will look at a candidate's `missions` (passed /
  skipped / attempts) to decide which topics to focus on.

- **`curriculum.json`** is read once (and cached) by
  `curriculum_service.py`. It's not used much yet in Part 1 — but
  Part 2 will use `get_day(day_number)` to pull real objectives and
  tools for a given day, so the interviewer's questions are grounded
  in the actual course content instead of made up.

Neither file is ever modified by the app — we only ever read them.

---

## 6. How the frontend will connect later (Part 4)

The frontend doesn't exist yet, but when it's built, it will simply
send `POST` requests to `http://<server-address>/api/interview` — the
exact same endpoint and JSON shapes shown in the example below. Because
we've already built and tested that contract in Part 1, the frontend
work in Part 4 shouldn't require any backend changes.

## 7. How Part 2 will connect to this foundation

Part 2 is the "AI Interview Brain" — the part that actually decides
what to ask. It will plug in inside `app/api/interview.py`, specifically
in the "MODE 2: CONTINUE INTERVIEW" section, replacing the placeholder
reply with a real call to an AI brain module. That module will read:

- `session.candidate` (to know the candidate's background/progress)
- `session.conversation_history` (to know what's been said)
- `curriculum_service.get_day(...)` (to ground questions in real
  course content)

...and return the next question or a final feedback object. Nothing
about the session model, the services, or the API's request/response
shape needs to change for that to happen — that's the point of
building the foundation this way.

Planned overall flow (later parts fill in the middle):

```
Frontend
   ↓
POST /api/interview
   ↓
FastAPI (app/api/interview.py)
   ↓
Interview Engine        ← Part 3
   ↓
Candidate Service   →   Curriculum Service   →   Session Service   (all Part 1, done)
   ↓
AI Interview Brain       ← Part 2
   ↓
Response
```

---

## 8. Running this project locally

All commands below assume you have Python 3.10+ installed, and that
your terminal is open with `the-interview-agent/backend` as the
current folder unless noted otherwise.

### Step 1 — Create a virtual environment

A virtual environment keeps this project's Python packages separate
from everything else on your machine.

```bash
cd backend
python -m venv .venv
```

### Step 2 — Activate it

**On Windows (Command Prompt):**
```bat
.venv\Scripts\activate.bat
```

**On Windows (PowerShell):**
```powershell
.venv\Scripts\Activate.ps1
```

**On macOS / Linux:**
```bash
source .venv/bin/activate
```

You'll know it worked because your terminal prompt will show
`(.venv)` at the start of the line.

### Step 3 — Install dependencies

```bash
pip install -r requirements.txt
```

### Step 4 — Start the FastAPI server

```bash
uvicorn app.main:app --reload
```

The server will start at `http://127.0.0.1:8000`. `--reload` makes it
auto-restart whenever you save a code change, which is handy during
development.

You can open `http://127.0.0.1:8000/docs` in a browser to see an
interactive page (auto-generated by FastAPI) where you can try the
endpoint directly.

### Step 5 — Run the tests

In a **second terminal** (with the same virtual environment activated,
from the `backend` folder):

```bash
pytest
```

You should see all 8 tests pass.

---

## 9. Example request

**Starting an interview:**

```
POST http://127.0.0.1:8000/api/interview
Content-Type: application/json

{
  "sessionId": "demo-1",
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
    "signals": {
      "commitDays": 28,
      "missionsCompleted": 30,
      "missionsFirstTry": 20
    }
  }
}
```

**Expected response:**

```json
{
  "reply": "Welcome. Let's begin your interview.",
  "done": false,
  "feedback": null
}
```

**Continuing the interview** (same `sessionId`):

```
POST http://127.0.0.1:8000/api/interview
Content-Type: application/json

{
  "sessionId": "demo-1",
  "message": "I used FAISS for the vector store."
}
```

**Expected response (Part 1 placeholder):**

```json
{
  "reply": "Interview session received. AI interviewer will be added in Part 2.",
  "done": false,
  "feedback": null
}
```

---

## 10. What's next

- **Part 2:** AI Interview Brain — actually generating questions and
  follow-ups from the candidate's data and curriculum.
- **Part 3:** Full Interview Engine — enforcing the 8-question /
  4-day minimums, tracking difficulty, and generating the final
  structured feedback.
- **Part 4:** Frontend — a simple chat UI.
- **Part 5:** Testing, deployment, GitHub polish, and completing
  `PROMPTS.md`.
