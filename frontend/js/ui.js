/**
 * ui.js
 *
 * This file handles all direct DOM manipulations, UI rendering,
 * and view transitions for the 3 main screens.
 */

const UI = {
  elements: {
    screens: {
      roster: document.getElementById("screen-roster"),
      interview: document.getElementById("screen-interview"),
      feedback: document.getElementById("screen-feedback"),
    },
    rosterGrid: document.getElementById("roster-grid"),
    rosterStatus: document.getElementById("roster-status"),
    ticketSession: document.getElementById("ticket-session"),
    ticketCandidate: document.getElementById("ticket-candidate"),
    tapeCount: document.getElementById("tape-count"),
    tapeTicks: document.getElementById("tape-ticks"),
    transcript: document.getElementById("transcript"),
    answerForm: document.getElementById("answer-form"),
    answerInput: document.getElementById("answer-input"),
    answerSend: document.getElementById("answer-send"),
    interviewError: document.getElementById("interview-error"),
    feedbackCandidateLine: document.getElementById("feedback-candidate-line"),
    feedbackSummary: document.getElementById("feedback-summary"),
    feedbackStrengths: document.getElementById("feedback-strengths"),
    feedbackGaps: document.getElementById("feedback-gaps"),
    feedbackNext: document.getElementById("feedback-next"),
    btnRestart: document.getElementById("btn-restart"),
  },

  showScreen(name) {
    Object.entries(this.elements.screens).forEach(([key, el]) => {
      if (el) el.classList.toggle("screen--active", key === name);
    });
  },

  escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  },

  renderRoster(candidates, onSelectCandidate) {
    const grid = this.elements.rosterGrid;
    grid.innerHTML = "";

    candidates.forEach((candidate) => {
      const passedCount = candidate.missions.filter((m) => m.passed === true).length;
      const totalCount = candidate.missions.length;
      const isFullyComplete = candidate.member.status === "COMPLETED";

      const card = document.createElement("button");
      card.type = "button";
      card.className = "candidate-card";
      card.setAttribute("data-candidate-id", candidate.member.id);

      card.innerHTML = `
        <div class="candidate-card__top">
          <div>
            <p class="candidate-card__name">${this.escapeHtml(candidate.member.name)}</p>
            <p class="candidate-card__role">${this.escapeHtml(candidate.member.jobRole)}</p>
          </div>
          <span class="candidate-card__badge ${isFullyComplete ? "" : "candidate-card__badge--partial"}">
            ${this.escapeHtml(candidate.member.status.replace(/_/g, " "))}
          </span>
        </div>
        <div class="candidate-card__meta">
          <span><strong>${candidate.member.yearsExperience}</strong> yrs experience</span>
          <span>${this.escapeHtml(candidate.member.education)}</span>
          <span><strong>${passedCount}</strong>/${totalCount} missions passed</span>
        </div>
      `;

      card.addEventListener("click", () => onSelectCandidate(candidate));
      grid.appendChild(card);
    });
  },

  setRosterStatus(text, isVisible = true) {
    const el = this.elements.rosterStatus;
    if (!el) return;
    el.hidden = !isVisible;
    el.textContent = text;
  },

  renderTranscriptMessage(speaker, text) {
    const transcript = this.elements.transcript;
    const bubble = document.createElement("div");

    if (speaker === "interviewer") {
      bubble.className = "bubble bubble--interviewer";
      bubble.innerHTML = `<span class="bubble__label">interviewer</span>${this.escapeHtml(text)}`;
    } else if (speaker === "candidate") {
      bubble.className = "bubble bubble--candidate";
      bubble.innerHTML = `<span class="bubble__label">you</span>${this.escapeHtml(text)}`;
    } else {
      bubble.className = "bubble bubble--system";
      bubble.textContent = text;
    }

    transcript.appendChild(bubble);
    transcript.scrollTop = transcript.scrollHeight;
  },

  showTypingIndicator() {
    this.hideTypingIndicator();
    const transcript = this.elements.transcript;
    const bubble = document.createElement("div");
    bubble.className = "bubble bubble--interviewer bubble--typing";
    bubble.id = "typing-indicator";
    bubble.innerHTML = "<span></span><span></span><span></span>";
    transcript.appendChild(bubble);
    transcript.scrollTop = transcript.scrollHeight;
  },

  hideTypingIndicator() {
    const el = document.getElementById("typing-indicator");
    if (el) el.remove();
  },

  renderTape(questionCount, targetCount = 10) {
    this.elements.tapeCount.textContent = `question ${questionCount}`;
    const ticksContainer = this.elements.tapeTicks;
    ticksContainer.innerHTML = "";

    const total = Math.max(targetCount, questionCount);
    for (let i = 1; i <= total; i++) {
      const tick = document.createElement("span");
      tick.className = "tape__tick";
      if (i <= questionCount) {
        tick.classList.add(i > targetCount ? "tape__tick--over" : "tape__tick--filled");
      }
      ticksContainer.appendChild(tick);
    }
  },

  setLoading(isLoading, isDone = false) {
    const { answerInput, answerSend } = this.elements;
    answerInput.disabled = isLoading || isDone;
    answerSend.disabled = isLoading || isDone;

    if (isLoading) {
      this.showTypingIndicator();
    } else {
      this.hideTypingIndicator();
    }
  },

  renderFeedbackList(el, items) {
    el.innerHTML = "";
    if (!items || items.length === 0) {
      el.classList.add("scorecard__list--empty");
      const li = document.createElement("li");
      li.textContent = "Nothing noted.";
      el.appendChild(li);
      return;
    }

    el.classList.remove("scorecard__list--empty");
    items.forEach((item) => {
      const li = document.createElement("li");
      li.textContent = item;
      el.appendChild(li);
    });
  },

  renderScorecard(candidate, feedback) {
    const { feedbackCandidateLine, feedbackSummary, feedbackStrengths, feedbackGaps, feedbackNext } = this.elements;
    feedbackCandidateLine.textContent = candidate
      ? `${candidate.member.name} \u2014 ${candidate.member.jobRole}`
      : "";

    if (feedback) {
      feedbackSummary.textContent = feedback.summary || "No summary provided.";
      this.renderFeedbackList(feedbackStrengths, feedback.strengths);
      this.renderFeedbackList(feedbackGaps, feedback.gaps);
      this.renderFeedbackList(feedbackNext, feedback.next);
    } else {
      feedbackSummary.textContent = "Interview finished with no feedback report.";
      this.renderFeedbackList(feedbackStrengths, []);
      this.renderFeedbackList(feedbackGaps, []);
      this.renderFeedbackList(feedbackNext, []);
    }
  },
};
