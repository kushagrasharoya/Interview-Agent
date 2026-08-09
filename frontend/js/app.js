/**
 * app.js
 *
 * Coordinates AppState (state.js), UI rendering (ui.js), and backend API (api.js).
 */

async function loadRoster() {
  UI.setRosterStatus("loading candidate roster\u2026", true);

  try {
    let data = null;
    try {
      const response = await fetch("assets/candidates.json").catch(() => fetch("data/candidates.json"));
      if (response && response.ok) {
        data = await response.json();
      }
    } catch (fetchErr) {
      // file:// protocol blocks fetch(); will use fallback below
    }

    if (data && data.candidates && data.candidates.length > 0) {
      AppState.candidates = data.candidates;
    } else if (typeof DEFAULT_CANDIDATES !== "undefined" && DEFAULT_CANDIDATES.length > 0) {
      AppState.candidates = DEFAULT_CANDIDATES;
    }

    if (AppState.candidates.length === 0) {
      UI.setRosterStatus("No candidates found.", true);
      return;
    }

    UI.setRosterStatus("", false);
    UI.renderRoster(AppState.candidates, onCandidateSelected);
  } catch (err) {
    if (typeof DEFAULT_CANDIDATES !== "undefined" && DEFAULT_CANDIDATES.length > 0) {
      AppState.candidates = DEFAULT_CANDIDATES;
      UI.setRosterStatus("", false);
      UI.renderRoster(AppState.candidates, onCandidateSelected);
    } else {
      UI.setRosterStatus("Couldn't load candidate roster. Check file and reload.", true);
    }
  }
}

async function onCandidateSelected(candidate) {
  resetInterviewState();
  AppState.selectedCandidate = candidate;
  AppState.sessionId = generateSessionId();

  UI.elements.ticketSession.textContent = AppState.sessionId.slice(0, 8);
  UI.elements.ticketCandidate.textContent = candidate.member.name;

  UI.showScreen("interview");
  UI.elements.transcript.innerHTML = "";
  UI.renderTape(AppState.questionCount, AppState.targetQuestionCount);
  UI.setLoading(true);

  try {
    const result = await startInterview(AppState.sessionId, candidate);
    addMessage("interviewer", result.reply);
  } catch (err) {
    addMessage("system", err.friendlyMessage || "Error starting the interview.");
  } finally {
    UI.setLoading(false);
  }
}

function addMessage(speaker, text) {
  AppState.messages.push({ speaker, text });
  UI.renderTranscriptMessage(speaker, text);
}

function autoGrowTextarea() {
  const input = UI.elements.answerInput;
  input.style.height = "auto";
  input.style.height = Math.min(input.scrollHeight, 160) + "px";
}

UI.elements.answerInput.addEventListener("input", autoGrowTextarea);

UI.elements.answerForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const input = UI.elements.answerInput;
  const message = input.value.trim();
  UI.elements.interviewError.hidden = true;

  if (!message) {
    UI.elements.interviewError.hidden = false;
    UI.elements.interviewError.textContent = "Type an answer before sending.";
    return;
  }
  if (AppState.isLoading || AppState.done) {
    return;
  }

  addMessage("candidate", message);
  input.value = "";
  autoGrowTextarea();

  AppState.questionCount += 1;
  UI.renderTape(AppState.questionCount, AppState.targetQuestionCount);
  UI.setLoading(true);

  try {
    const result = await continueInterview(AppState.sessionId, message);

    if (result.done) {
      AppState.done = true;
      AppState.feedback = result.feedback || null;
      addMessage("interviewer", result.reply);
      UI.setLoading(false, true);

      setTimeout(() => {
        UI.renderScorecard(AppState.selectedCandidate, AppState.feedback);
        UI.showScreen("feedback");
      }, 900);
      return;
    }

    addMessage("interviewer", result.reply);
  } catch (err) {
    if (err.status === 404) {
      addMessage("system", err.friendlyMessage);
      UI.setLoading(false, true);
      return;
    }
    UI.elements.interviewError.hidden = false;
    UI.elements.interviewError.textContent =
      err.friendlyMessage || "Something went wrong sending your answer. Please try again.";
  } finally {
    if (!AppState.done) {
      UI.setLoading(false);
    }
  }
});

UI.elements.btnRestart.addEventListener("click", () => {
  resetInterviewState();
  UI.showScreen("roster");
});

// Start by loading roster
loadRoster();
