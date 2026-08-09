# Frontend

Plain HTML/CSS/JavaScript client for The Interview Agent. No build
step, no framework - open `index.html` through a local static server
and it talks directly to the backend's `POST /api/interview` endpoint.

## Files

```
frontend/
├── index.html        The three screens (roster / interview / feedback)
├── css/
│   └── styles.css    All styling
├── js/
│   ├── state.js       In-memory app state (sessionId, messages, etc.)
│   ├── api.js         The only file that calls fetch() on the backend
│   └── app.js          DOM rendering + event handling, wires the above together
├── data/
│   └── candidates.json   Same synthetic roster the backend reads from
└── README.md
```

### Why `data/candidates.json` is duplicated here

The technical spec deliberately does not expose a `GET /api/candidates`
endpoint (Part 1 was told not to invent one), so there's no backend
route the frontend can call to list candidates for the selection
screen. Instead the frontend reads the same provided `candidates.json`
directly as a static file. The full candidate object picked here is
what gets sent as `candidate` in the very first `POST /api/interview`
request - so this file must stay in sync with `backend/data/candidates.json`
(same source file, just present in both places).

## Running it locally

The frontend must be served over HTTP (not opened as a `file://` URL),
because loading `data/candidates.json` uses `fetch()`, which browsers
block on the `file://` protocol.

1. Start the backend first (from `backend/`):
   ```
   uvicorn app.main:app --reload
   ```
   It listens on `http://127.0.0.1:8000` by default.

2. In a second terminal, serve the frontend folder with any static
   file server, for example:
   ```
   cd frontend
   python -m http.server 5500
   ```
   Then open `http://127.0.0.1:5500` in a browser.

3. If you serve the frontend from a different host/port, update
   `API_BASE_URL` at the top of `js/api.js` to match wherever the
   backend is actually running.

The backend's `app/main.py` enables CORS so requests from a different
origin (like the static server above) are allowed to reach
`POST /api/interview`.

## How each file communicates with the backend

- **`js/api.js`** is the single point of contact with the backend. It
  exposes two functions, `startInterview(sessionId, candidate)` and
  `continueInterview(sessionId, message)`, both of which POST to
  `/api/interview` and return the parsed `{ reply, done, feedback? }`
  response, or throw an `ApiError` with a message that's already safe
  to show in the UI.
- **`js/state.js`** never touches the network. It just stores the
  current sessionId, the selected candidate, the running transcript,
  and the feedback object once the interview ends.
- **`js/app.js`** is the only file that touches the DOM. It calls
  `api.js` when the candidate submits an answer, updates `state.js`
  with the result, and re-renders whichever screen is active.

## What Part 5 will add

Deployment instructions and any final polish to `PROMPTS.md`,
documenting the prompts used to build this app and the prompts the
app itself sends to the LLM.
