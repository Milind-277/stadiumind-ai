/* global document, window */

(function () {
  "use strict";

  const storage = window.localStorage;
  const root = document.documentElement;

  function getNumber(value, fallback) {
    const parsed = Number.parseFloat(value);
    return Number.isFinite(parsed) ? parsed : fallback;
  }

  function setFontScale(scale) {
    const bounded = Math.max(0.9, Math.min(1.25, scale));
    root.style.setProperty("--font-scale", String(bounded));
    storage.setItem("sm-font-scale", String(bounded));
  }

  function setTheme(enabled) {
    if (enabled) {
      root.dataset.theme = "high-contrast";
      storage.setItem("sm-high-contrast", "true");
    } else {
      delete root.dataset.theme;
      storage.setItem("sm-high-contrast", "false");
    }
  }

  function setMotion(enabled) {
    if (enabled) {
      root.dataset.motion = "reduced";
      storage.setItem("sm-reduced-motion", "true");
    } else {
      delete root.dataset.motion;
      storage.setItem("sm-reduced-motion", "false");
    }
  }

  function applyStoredPreferences() {
    const scale = getNumber(storage.getItem("sm-font-scale"), 1);
    root.style.setProperty("--font-scale", String(scale));
    if (storage.getItem("sm-high-contrast") === "true") {
      root.dataset.theme = "high-contrast";
    }
    if (storage.getItem("sm-reduced-motion") === "true") {
      root.dataset.motion = "reduced";
    }
  }

  function updateAriaPressed(button, active) {
    if (button) {
      button.setAttribute("aria-pressed", active ? "true" : "false");
    }
  }

  function bindAccessibilityToolbar() {
    const contrastButton = document.querySelector("[data-theme-toggle]");
    const motionButton = document.querySelector("[data-motion-toggle]");
    const fontIncrease = document.querySelector("[data-font-increase]");
    const fontDecrease = document.querySelector("[data-font-decrease]");
    const fontReset = document.querySelector("[data-font-reset]");

    updateAriaPressed(contrastButton, root.dataset.theme === "high-contrast");
    updateAriaPressed(motionButton, root.dataset.motion === "reduced");

    contrastButton?.addEventListener("click", () => {
      const active = root.dataset.theme === "high-contrast";
      setTheme(!active);
      updateAriaPressed(contrastButton, !active);
    });

    motionButton?.addEventListener("click", () => {
      const active = root.dataset.motion === "reduced";
      setMotion(!active);
      updateAriaPressed(motionButton, !active);
    });

    fontIncrease?.addEventListener("click", () => {
      setFontScale(getNumber(storage.getItem("sm-font-scale"), 1) + 0.05);
    });

    fontDecrease?.addEventListener("click", () => {
      setFontScale(getNumber(storage.getItem("sm-font-scale"), 1) - 0.05);
    });

    fontReset?.addEventListener("click", () => {
      setFontScale(1);
    });
  }

  function renderList(container, items, fallbackClass) {
    if (!container) {
      return;
    }

    container.innerHTML = "";
    if (!items || !items.length) {
      const empty = document.createElement("div");
      empty.className = fallbackClass || "empty-state";
      empty.textContent = container.dataset.emptyMessage || "No data available.";
      container.appendChild(empty);
      return;
    }

    items.forEach((item) => {
      const node = document.createElement("div");
      node.className = "list-item";
      node.innerHTML = item;
      container.appendChild(node);
    });
  }

  async function requestJson(url, options) {
    const response = await window.fetch(url, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
    const payload = await response.json();
    if (!response.ok || payload.success === false) {
      const message = payload?.errors?.[0]?.message || "Request failed.";
      throw new Error(message);
    }
    return payload.data;
  }

  function appendChatEntry(log, variant, label, content) {
    const entry = document.createElement("article");
    entry.className = `chat-entry ${variant}`;
    entry.setAttribute("role", "article");
    entry.innerHTML = `
      <span class="entry-label">${label}</span>
      <div>${content}</div>
    `;
    log.appendChild(entry);
    log.scrollTop = log.scrollHeight;
  }

  function bindFanChat() {
    const form = document.querySelector("[data-fan-chat-form]");
    const log = document.querySelector("[data-chat-log]");
    const suggestions = document.querySelector("[data-chat-suggestions]");
    if (!form || !log) {
      return;
    }

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const messageInput = form.querySelector("[name='message']");
      const venueIdInput = form.querySelector("[name='venue_id']");
      const submitButton = form.querySelector("button[type='submit']");
      const message = messageInput?.value.trim();
      if (!message) {
        return;
      }

      appendChatEntry(log, "user", "You", message);
      if (submitButton) submitButton.disabled = true;

      try {
        const data = await requestJson("/fan/api/fan/chat", {
          method: "POST",
          body: JSON.stringify({
            message,
            venue_id: venueIdInput?.value || "v001",
          }),
        });
        appendChatEntry(log, "ai", "StadiumMind", data.reply || "No response available.");
        if (suggestions && Array.isArray(data.suggestions)) {
          suggestions.innerHTML = data.suggestions
            .map((item) => `<button type="button" class="chat-suggestion-btn" data-chat-preset>${item}</button>`)
            .join("");
          bindChatSuggestionButtons(form, suggestions);
        }
      } catch (error) {
        appendChatEntry(log, "ai", "StadiumMind", error.message);
      } finally {
        if (submitButton) submitButton.disabled = false;
        if (messageInput) messageInput.value = "";
      }
    });

    bindChatSuggestionButtons(form, suggestions);
  }

  function bindChatSuggestionButtons(form, container) {
    if (!container) {
      return;
    }

    container.querySelectorAll("[data-chat-preset]").forEach((button) => {
      button.addEventListener("click", () => {
        const input = form.querySelector("[name='message']");
        if (input) {
          input.value = button.textContent || "";
          input.focus();
        }
      });
    });
  }

  function bindWayfinding() {
    const form = document.querySelector("[data-wayfinding-form]");
    const target = document.querySelector("[data-wayfinding-result]");
    if (!form || !target) {
      return;
    }

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const venueId = form.querySelector("[name='venue_id']")?.value || "v001";
      const destination = form.querySelector("[name='destination']")?.value.trim();
      if (!destination) {
        return;
      }

      target.dataset.empty = "false";
      target.innerHTML = `<div class="skeleton skeleton-card"></div>`;

      try {
        const data = await requestJson(
          `/fan/api/fan/wayfinding?venue_id=${encodeURIComponent(venueId)}&to=${encodeURIComponent(destination)}`
        );
        target.innerHTML = `
          <div class="detail-list">
            <div class="detail-row"><span class="detail-label">Reply</span><span class="detail-value">${data.ai_guidance.reply || "Ready"}</span></div>
            <div class="detail-row"><span class="detail-label">Best gate</span><span class="detail-value">${data.decision_support.best_gate}</span></div>
            <div class="detail-row"><span class="detail-label">Transportation</span><span class="detail-value">${data.decision_support.transportation_suggestion}</span></div>
          </div>
        `;
      } catch (error) {
        target.innerHTML = `<div class="alert alert-danger">${error.message}</div>`;
      }
    });
  }

  function bindVolunteerTasks() {
    document.querySelectorAll("[data-task-guidance]").forEach((button) => {
      button.addEventListener("click", async () => {
        const taskId = button.getAttribute("data-task-guidance");
        const output = document.querySelector(`[data-task-output="${taskId}"]`);
        if (!taskId || !output) {
          return;
        }

        output.innerHTML = `<div class="spinner spinner-sm" aria-hidden="true"></div>`;
        try {
          const data = await requestJson("/volunteer/api/volunteer/ai-guidance", {
            method: "POST",
            body: JSON.stringify({ task_id: taskId }),
          });
          output.innerHTML = `
            <strong>${data.guidance.guidance || "Guidance ready."}</strong>
            <div class="chips mt-2">${(data.guidance.steps || []).map((item) => `<span class="badge badge-info">${item}</span>`).join("")}</div>
          `;
        } catch (error) {
          output.innerHTML = `<div class="alert alert-danger">${error.message}</div>`;
        }
      });
    });
  }

  function bindSecurityActions() {
    document.querySelectorAll("[data-classify-incident]").forEach((button) => {
      button.addEventListener("click", async () => {
        const incidentId = button.getAttribute("data-classify-incident");
        const output = document.querySelector(`[data-incident-output="${incidentId}"]`);
        if (!incidentId || !output) {
          return;
        }

        output.innerHTML = `<div class="spinner spinner-sm" aria-hidden="true"></div>`;
        try {
          const data = await requestJson(`/security/api/security/incidents/${encodeURIComponent(incidentId)}/classify`, {
            method: "POST",
          });
          output.innerHTML = `
            <strong>${data.classification.type}</strong>
            <div class="detail-row"><span class="detail-label">Severity</span><span class="detail-value">${data.classification.severity}</span></div>
            <div class="detail-row"><span class="detail-label">Recommendation</span><span class="detail-value">${data.classification.recommendation}</span></div>
          `;
        } catch (error) {
          output.innerHTML = `<div class="alert alert-danger">${error.message}</div>`;
        }
      });
    });
  }

  function bindOrganizerCrowd() {
    const form = document.querySelector("[data-organizer-crowd-form]");
    const output = document.querySelector("[data-organizer-crowd-output]");
    if (!form || !output) {
      return;
    }

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const venueId = form.querySelector("[name='venue_id']")?.value || "v001";
      output.innerHTML = `<div class="spinner spinner-sm" aria-hidden="true"></div>`;

      try {
        const data = await requestJson(`/organizer/api/organizer/crowd/live?venue_id=${encodeURIComponent(venueId)}`);
        const venue = data.venues?.[0];
        if (!venue) {
          output.innerHTML = `<div class="empty-state">No live crowd data available for this venue.</div>`;
          return;
        }

        output.innerHTML = `
          <div class="detail-list">
            <div class="detail-row"><span class="detail-label">Occupancy</span><span class="detail-value">${venue.occupancy_pct}%</span></div>
            <div class="detail-row"><span class="detail-label">Attendance</span><span class="detail-value">${venue.total_attendance}</span></div>
            <div class="detail-row"><span class="detail-label">Bottlenecks</span><span class="detail-value">${venue.bottleneck_zones.join(", ") || "None"}</span></div>
          </div>
        `;
      } catch (error) {
        output.innerHTML = `<div class="alert alert-danger">${error.message}</div>`;
      }
    });
  }

  function bindOrganizerReports() {
    const reportForm = document.querySelector("[data-report-form]");
    const reportOutput = document.querySelector("[data-report-output]");
    const alertForm = document.querySelector("[data-alert-form]");
    const alertOutput = document.querySelector("[data-alert-output]");

    reportForm?.addEventListener("submit", async (event) => {
      event.preventDefault();
      const venueId = reportForm.querySelector("[name='venue_id']")?.value || "v001";
      reportOutput.innerHTML = `<div class="spinner spinner-sm" aria-hidden="true"></div>`;

      try {
        const data = await requestJson("/organizer/api/organizer/reports/generate", {
          method: "POST",
          body: JSON.stringify({ venue_id: venueId }),
        });
        reportOutput.innerHTML = `
          <strong>${data.briefing?.title || "Operational briefing"}</strong>
          <p class="mt-2">${data.briefing?.summary || "Briefing generated."}</p>
        `;
      } catch (error) {
        reportOutput.innerHTML = `<div class="alert alert-danger">${error.message}</div>`;
      }
    });

    alertForm?.addEventListener("submit", async (event) => {
      event.preventDefault();
      const title = alertForm.querySelector("[name='title']")?.value.trim();
      const message = alertForm.querySelector("[name='message']")?.value.trim();
      const priority = alertForm.querySelector("[name='priority']")?.value || "medium";
      const venueId = alertForm.querySelector("[name='venue_id']")?.value || "v001";
      if (!title || !message) {
        return;
      }

      alertOutput.innerHTML = `<div class="spinner spinner-sm" aria-hidden="true"></div>`;
      try {
        const data = await requestJson("/organizer/api/organizer/alerts/broadcast", {
          method: "POST",
          body: JSON.stringify({ title, message, priority, venue_id: venueId }),
        });
        alertOutput.innerHTML = `<strong>Alert broadcast</strong><p class="mt-2">${data.alert.title}</p>`;
      } catch (error) {
        alertOutput.innerHTML = `<div class="alert alert-danger">${error.message}</div>`;
      }
    });
  }

  function initThemeHint() {
    const highContrastHint = document.querySelector("[data-high-contrast-hint]");
    if (!highContrastHint) {
      return;
    }

    const prefersHighContrast = window.matchMedia("(prefers-contrast: more)").matches;
    if (prefersHighContrast) {
      highContrastHint.textContent = "High contrast is recommended by your system preferences.";
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    applyStoredPreferences();
    bindAccessibilityToolbar();
    bindFanChat();
    bindWayfinding();
    bindVolunteerTasks();
    bindSecurityActions();
    bindOrganizerCrowd();
    bindOrganizerReports();
    initThemeHint();
  });
})();