# Frontend

There is no frontend code yet.

This project is being built in 5 parts, and the frontend is
**Part 4**. Right now (Part 1), we've only built the backend
foundation: the FastAPI server, data loading, and the session
skeleton behind the `POST /api/interview` endpoint.

## What will happen in Part 4

A simple web UI (a chat-style interface) will be built here that:

1. Lets the user pick or load a candidate.
2. Sends the first `POST /api/interview` request (with `sessionId` and
   `candidate`) to start the interview.
3. Displays the interviewer's questions and lets the candidate type
   answers.
4. Sends each answer as a `POST /api/interview` request (with
   `sessionId` and `message`).
5. Keeps showing replies until the response has `"done": true`, then
   displays the structured feedback (`summary`, `strengths`, `gaps`,
   `next`).

Because the backend's request/response shape (defined in
`technical-spec.md`) is already fixed and tested in Part 1, the
frontend built in Part 4 will be able to talk to the backend without
requiring any backend changes.
