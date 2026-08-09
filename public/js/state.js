/**
 * state.js
 *
 * This file holds everything the frontend needs to remember while one
 * interview is in progress: who the candidate is, what sessionId this
 * conversation is using, the messages exchanged so far, how many
 * questions have been asked, whether the interview is finished, and
 * (once it's finished) the feedback the backend generated.
 *
 * Why this file exists:
 * app.js reacts to clicks and API responses; api.js only knows how to
 * talk to the backend. Neither of them should be the "source of truth"
 * for what's currently on screen - that's this file's job. Keeping
 * state in one plain object (instead of scattered across DOM elements
 * or global variables in app.js) makes it easy to reset between
 * interviews and easy to reason about.
 *
 * Nothing in this file touches the DOM or the network. It only stores
 * and updates plain data.
 */

const AppState = {
  /** The full candidate roster loaded from data/candidates.json. */
  candidates: [],

  /** The candidate object currently being interviewed (or null). */
  selectedCandidate: null,

  /** The sessionId this browser generated for the current interview. */
  sessionId: null,

  /**
   * The conversation so far, in order. Each entry looks like:
   *   { speaker: "interviewer" | "candidate" | "system", text: "..." }
   * "system" is used for local status messages (e.g. connection errors)
   * that never get sent to the backend.
   */
  messages: [],

  /**
   * How many candidate answers have been submitted so far in this
   * interview. This is a frontend-only counter used purely to show
   * "question N of ~10" - the backend's response contract
   * (reply/done/feedback) does not include a question count, so this
   * is the best truthful approximation the UI can show.
   */
  questionCount: 0,

  /** The backend's preferred question count, used only to size the
   * progress tape. Matches PREFERRED_QUESTIONS in the backend engine. */
  targetQuestionCount: 10,

  /** True once the backend has returned done: true. */
  done: false,

  /** The structured feedback object once the interview has ended. */
  feedback: null,

  /** True while a request to the backend is in flight (used to disable input). */
  isLoading: false,
};

/**
 * Reset everything back to a fresh state, ready to start a brand-new
 * interview with a different candidate. The candidate roster itself
 * is left alone since it doesn't change between interviews.
 */
function resetInterviewState() {
  AppState.selectedCandidate = null;
  AppState.sessionId = null;
  AppState.messages = [];
  AppState.questionCount = 0;
  AppState.done = false;
  AppState.feedback = null;
  AppState.isLoading = false;
}

/**
 * Generate a sessionId for a new interview. Uses the browser's built-in
 * crypto.randomUUID() when available (all modern browsers), with a
 * simple fallback so the app still works in older environments.
 */
function generateSessionId() {
  if (window.crypto && typeof window.crypto.randomUUID === "function") {
    return window.crypto.randomUUID();
  }
  return "session-" + Date.now() + "-" + Math.random().toString(16).slice(2);
}
