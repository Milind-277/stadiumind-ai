/* global document, window */

(function () {
  "use strict";

  const storage = window.localStorage;
  const root = document.documentElement;

  const TRANSLATIONS = {
    en: {
      toolbar: { contrast: "Contrast", motion: "Motion", switchRole: "Switch role" },
      widgets: {
        weather: "Mock Weather",
        weather_sub: "Influences route advice and confidence.",
        weather_choice: "Condition",
        sustainability: "Sustainability",
        sustainability_sub: "Low-impact travel guidance for match day.",
        why: "Why this recommendation?",
      },
    },
    es: {
      toolbar: { contrast: "Contraste", motion: "Movimiento", switchRole: "Cambiar rol" },
      widgets: {
        weather: "Clima simulado",
        weather_sub: "Influye en las rutas y la confianza.",
        weather_choice: "Condición",
        sustainability: "Sostenibilidad",
        sustainability_sub: "Guía de viaje de bajo impacto.",
        why: "¿Por qué esta recomendación?",
      },
    },
    fr: {
      toolbar: { contrast: "Contraste", motion: "Mouvement", switchRole: "Changer de rôle" },
      widgets: {
        weather: "Météo simulée",
        weather_sub: "Influence les conseils et la confiance.",
        weather_choice: "Condition",
        sustainability: "Durabilité",
        sustainability_sub: "Conseils de déplacement à faible impact.",
        why: "Pourquoi cette recommandation ?",
      },
    },
    hi: {
      toolbar: { contrast: "कॉन्ट्रास्ट", motion: "गति", switchRole: "भूमिका बदलें" },
      widgets: {
        weather: "मॉक मौसम",
        weather_sub: "मार्ग और भरोसे को प्रभावित करता है।",
        weather_choice: "स्थिति",
        sustainability: "स्थिरता",
        sustainability_sub: "कम-प्रभाव वाली यात्रा मार्गदर्शिका।",
        why: "यह अनुशंसा क्यों?",
      },
    },
  };

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
    root.lang = getLanguage();
  }

  function getLanguage() {
    return storage.getItem("sm-language") || "en";
  }

  function setLanguage(language) {
    const supported = ["en", "es", "fr", "hi"];
    const value = supported.includes(language) ? language : "en";
    storage.setItem("sm-language", value);
    root.lang = value;
    applyTranslations();
  }

  function getWeather() {
    return storage.getItem("sm-weather") || "clear";
  }

  function setWeather(weather) {
    const supported = ["clear", "cloudy", "rain", "wind", "heat"];
    const value = supported.includes(weather) ? weather : "clear";
    storage.setItem("sm-weather", value);
    updateWeatherWidgets();
    updateIntelligencePanels();
  }

  function translate(path, fallback) {
    const locale = TRANSLATIONS[getLanguage()] || TRANSLATIONS.en;
    return path.split(".").reduce((value, key) => (value && value[key] !== undefined ? value[key] : undefined), locale) || fallback;
  }

  function applyTranslations() {
    document.querySelectorAll("[data-i18n]").forEach((element) => {
      const key = element.getAttribute("data-i18n") || "";
      const translated = translate(key, element.textContent || "");
      if (translated) {
        element.textContent = translated;
      }
    });

    const themeButton = document.querySelector("[data-theme-toggle]");
    const motionButton = document.querySelector("[data-motion-toggle]");
    const switchButton = document.querySelector("a[href$='switch-role']");
    if (themeButton) themeButton.textContent = translate("toolbar.contrast", themeButton.textContent);
    if (motionButton) motionButton.textContent = translate("toolbar.motion", motionButton.textContent);
    if (switchButton) switchButton.textContent = translate("toolbar.switchRole", switchButton.textContent);
  }

  function updateIntelligencePanels() {
    updateWeatherWidgets();
  }

  function updateAriaPressed(button, active) {
    if (button) {
      button.setAttribute("aria-pressed", active ? "true" : "false");
    }
  }

  function bindAccessibilityToolbar() {
    const languageSelector = document.querySelector("[data-language-select]");
    const weatherSelectors = document.querySelectorAll("[data-weather-select]");
    const contrastButton = document.querySelector("[data-theme-toggle]");
    const motionButton = document.querySelector("[data-motion-toggle]");
    const fontIncrease = document.querySelector("[data-font-increase]");
    const fontDecrease = document.querySelector("[data-font-decrease]");
    const fontReset = document.querySelector("[data-font-reset]");

    updateAriaPressed(contrastButton, root.dataset.theme === "high-contrast");
    updateAriaPressed(motionButton, root.dataset.motion === "reduced");

    if (languageSelector) {
      languageSelector.value = getLanguage();
      languageSelector.addEventListener("change", () => setLanguage(languageSelector.value));
    }

    weatherSelectors.forEach((selector) => {
      selector.value = getWeather();
      selector.addEventListener("change", () => setWeather(selector.value));
    });

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

    applyTranslations();
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

  function getWeatherProfile() {
    const weather = getWeather();
    const profiles = {
      clear: { label: "Clear", detail: "Dry conditions support direct routes.", temperature: "24°C", wind: "8 km/h" },
      cloudy: { label: "Cloudy", detail: "Neutral conditions keep routes steady.", temperature: "21°C", wind: "10 km/h" },
      rain: { label: "Rain", detail: "Indoor routes and shorter walks are preferred.", temperature: "18°C", wind: "12 km/h" },
      wind: { label: "Wind", detail: "Use sheltered entries where possible.", temperature: "20°C", wind: "20 km/h" },
      heat: { label: "Heat", detail: "Hydration and shaded routes are preferred.", temperature: "31°C", wind: "6 km/h" },
    };
    return profiles[weather] || profiles.clear;
  }

  function weatherCarbonSavings(profile) {
    const values = { Clear: 12, Cloudy: 14, Rain: 16, Wind: 13, Heat: 18 };
    return `${values[profile.label] || 12} kg CO2e saved (mock)`;
  }

  function updateWeatherWidgets() {
    const profile = getWeatherProfile();
    document.querySelectorAll("[data-weather-body]").forEach((target) => {
      target.innerHTML = `
        <div class="weather-metric"><span class="weather-metric__label">Condition</span><span class="weather-metric__value">${profile.label}</span></div>
        <div class="weather-metric"><span class="weather-metric__label">Temperature</span><span class="weather-metric__value">${profile.temperature}</span></div>
        <div class="weather-metric"><span class="weather-metric__label">Wind</span><span class="weather-metric__value">${profile.wind}</span></div>
        <div class="weather-metric"><span class="weather-metric__label">Recommendation impact</span><span class="weather-metric__value">${profile.detail}</span></div>
      `;
    });

    document.querySelectorAll("[data-sustainability-body]").forEach((target) => {
      target.innerHTML = `
        <div class="sustainability-item"><span class="sustainability-item__label">Water refill station</span><span class="sustainability-item__value">Use the nearest concourse refill point before the gate.</span></div>
        <div class="sustainability-item"><span class="sustainability-item__label">Walking recommendation</span><span class="sustainability-item__value">${profile.detail}</span></div>
        <div class="sustainability-item"><span class="sustainability-item__label">Waste disposal guidance</span><span class="sustainability-item__value">Use sorted bins and return cups to collection points.</span></div>
        <div class="sustainability-item"><span class="sustainability-item__label">Estimated carbon savings</span><span class="sustainability-item__value">${weatherCarbonSavings(profile)}</span></div>
      `;
    });
  }

  function confidenceMeter(score) {
    return `
      <div class="confidence-meter">
        <div class="confidence-meter__head">
          <span class="confidence-meter__label">AI Confidence</span>
          <span class="confidence-meter__value">${score}%</span>
        </div>
        <div class="confidence-track" aria-hidden="true"><span class="confidence-fill confidence-info" style="width:${score}%"></span></div>
      </div>
    `;
  }

  function statusBadge(label, level) {
    return `<span class="status-badge status-${level}">${label}</span>`;
  }

  function whyPanel(title, reasons) {
    return `
      <article class="intel-card glass-panel tone-info">
        <div class="section-heading">
          <div>
            <h3 class="section-title" data-i18n="widgets.why">${title}</h3>
            <p class="page-subtitle">Current crowd, accessibility, incident, route, and weather context.</p>
          </div>
          <span class="intel-icon" aria-hidden="true">💡</span>
        </div>
        <ul class="why-list">${reasons.map((reason) => `<li>${reason}</li>`).join("")}</ul>
      </article>
    `;
  }

  function sustainabilityPanel() {
    const profile = getWeatherProfile();
    return `
      <article class="intel-card glass-panel tone-success">
        <div class="section-heading">
          <div>
            <h3 class="section-title" data-i18n="widgets.sustainability">Sustainability</h3>
            <p class="page-subtitle" data-i18n="widgets.sustainability_sub">Low-impact travel guidance for match day.</p>
          </div>
          <span class="intel-icon" aria-hidden="true">🌱</span>
        </div>
        <div class="sustainability-list">
          <div class="sustainability-item"><span class="sustainability-item__label">Water refill station</span><span class="sustainability-item__value">Use the nearest accessible refill point.</span></div>
          <div class="sustainability-item"><span class="sustainability-item__label">Walking recommendation</span><span class="sustainability-item__value">${profile.detail}</span></div>
          <div class="sustainability-item"><span class="sustainability-item__label">Waste disposal guidance</span><span class="sustainability-item__value">Use colour-coded recycling and waste bins.</span></div>
          <div class="sustainability-item"><span class="sustainability-item__label">Estimated carbon savings</span><span class="sustainability-item__value">${weatherCarbonSavings(profile)}</span></div>
        </div>
      </article>
    `;
  }

  function weatherPanel() {
    const profile = getWeatherProfile();
    return `
      <article class="intel-card glass-panel tone-warning weather-widget">
        <div class="section-heading">
          <div>
            <h3 class="section-title" data-i18n="widgets.weather">Mock Weather</h3>
            <p class="page-subtitle" data-i18n="widgets.weather_sub">Influences route advice and confidence.</p>
          </div>
          <span class="intel-icon" aria-hidden="true">☁️</span>
        </div>
        <div class="form-group">
          <label class="form-label" for="weather-select" data-i18n="widgets.weather_choice">Condition</label>
          <select id="weather-select" class="form-select" data-weather-select aria-label="Mock weather selector">
            <option value="clear">Clear</option>
            <option value="cloudy">Cloudy</option>
            <option value="rain">Rain</option>
            <option value="wind">Windy</option>
            <option value="heat">Hot</option>
          </select>
        </div>
        <div class="intel-card__body">
          <div class="weather-metric"><span class="weather-metric__label">Condition</span><span class="weather-metric__value">${profile.label}</span></div>
          <div class="weather-metric"><span class="weather-metric__label">Temperature</span><span class="weather-metric__value">${profile.temperature}</span></div>
          <div class="weather-metric"><span class="weather-metric__label">Wind</span><span class="weather-metric__value">${profile.wind}</span></div>
          <div class="weather-metric"><span class="weather-metric__label">Note</span><span class="weather-metric__value">${profile.detail}</span></div>
        </div>
      </article>
    `;
  }

  function statusWidget(title, statusLabel, variant, rows) {
    return `
      <section class="panel glass-panel status-widget">
        <div class="section-heading">
          <div>
            <h2 class="section-title">${title}</h2>
            <p class="page-subtitle">Live operational status</p>
          </div>
          ${statusBadge(statusLabel, variant)}
        </div>
        <div class="detail-list">
          ${rows.map((row) => `<div class="detail-row"><span class="detail-label">${row.label}</span><span class="detail-value">${row.value}</span></div>`).join("")}
        </div>
      </section>
    `;
  }

  function intelligencePanel(container, kind, options) {
    const itemCount = options.items.length;
    const confidence = Math.max(68, Math.min(99, options.confidence || 86));
    const crowdBadge = statusBadge(options.crowdLabel || "Low", options.crowdLevel || "low");
    const incidentBadge = statusBadge(options.incidentLabel || "Info", options.incidentLevel || "info");
    container.innerHTML = `
      <div class="recommendation-card">
        ${confidenceMeter(confidence)}
        <div class="chips">
          ${crowdBadge}
          ${incidentBadge}
          ${statusBadge(`Weather ${getWeatherProfile().label}`, "info")}
          ${statusBadge(getLanguage().toUpperCase(), "info")}
        </div>
        <div class="intel-grid">
          ${whyPanel("Why this recommendation?", options.reasons)}
          ${sustainabilityPanel()}
          ${weatherPanel()}
        </div>
        <div class="recommendation-list">
          ${options.items.map((item, index) => `<div class="list-item recommendation-list__item"><span>${item}</span><span class="status-badge status-info recommendation-list__confidence">${Math.max(68, confidence - index * 3)}%</span></div>`).join("")}
        </div>
      </div>
    `;
    updateWeatherWidgets();
    applyTranslations();
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
        intelligencePanel(log, "fan_chat", {
          items: data.suggestions || [data.reply || "No suggestions"],
          reasons: [
            "The reply uses the current venue context and your selected language.",
            `Weather: ${getWeatherProfile().detail}`,
            "Accessibility-aware suggestions are preserved in the response.",
          ],
          confidence: 88,
          crowdLabel: "Low",
          crowdLevel: "low",
          incidentLabel: data.urgent ? "Warning" : "Info",
          incidentLevel: data.urgent ? "warning" : "info",
        });
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
        const recommendations = [
          data.ai_guidance.reply || `Use ${data.decision_support.best_gate} to continue.`,
          ...(data.decision_support.navigation_advice || []),
          ...(data.decision_support.crowd_avoidance || []),
          ...(data.decision_support.accessibility_recommendations || []),
        ];
        target.innerHTML = `
          <div class="detail-list">
            <div class="detail-row"><span class="detail-label">Reply</span><span class="detail-value">${data.ai_guidance.reply || "Ready"}</span></div>
            <div class="detail-row"><span class="detail-label">Best gate</span><span class="detail-value">${data.decision_support.best_gate}</span></div>
            <div class="detail-row"><span class="detail-label">Transportation</span><span class="detail-value">${data.decision_support.transportation_suggestion}</span></div>
          </div>
        `;
        intelligencePanel(target, "fan_wayfinding", {
          items: recommendations,
          reasons: [
            `The gate selection reduces congestion around ${destination}.`,
            "Accessibility services are prioritised in the route output.",
            `Weather: ${getWeatherProfile().detail}`,
          ],
          confidence: 92,
          crowdLabel: "Low",
          crowdLevel: "low",
          incidentLabel: "Info",
          incidentLevel: "info",
        });
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
            <div class="detail-list">
              <div class="detail-row"><span class="detail-label">Guidance</span><span class="detail-value">${data.guidance.guidance || "Guidance ready."}</span></div>
            </div>
          `;
          intelligencePanel(output, "volunteer_guidance", {
            items: data.guidance.steps || [],
            reasons: [
              "The task is aligned to the assigned zone and priority.",
              "Emergency escalation thresholds are preserved in the guidance.",
              `Weather: ${getWeatherProfile().detail}`,
            ],
            confidence: data.fallback_used ? 81 : 89,
            crowdLabel: "Medium",
            crowdLevel: "medium",
            incidentLabel: "Info",
            incidentLevel: "info",
          });
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
            <div class="detail-list">
              <div class="detail-row"><span class="detail-label">Type</span><span class="detail-value">${data.classification.type}</span></div>
              <div class="detail-row"><span class="detail-label">Severity</span><span class="detail-value">${data.classification.severity}</span></div>
              <div class="detail-row"><span class="detail-label">Recommendation</span><span class="detail-value">${data.classification.recommendation}</span></div>
            </div>
          `;
          intelligencePanel(output, "security_classify", {
            items: data.classification.steps || [data.classification.recommendation],
            reasons: [
              "Incident severity and protocol steps drive the recommendation.",
              "Emergency access routes remain the top priority.",
              `Weather: ${getWeatherProfile().detail}`,
            ],
            confidence: data.classification.severity === "critical" ? 96 : 90,
            crowdLabel: "High",
            crowdLevel: "high",
            incidentLabel: data.classification.severity === "critical" ? "Critical" : "Warning",
            incidentLevel: data.classification.severity === "critical" ? "critical" : "warning",
          });
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

        const crowdLabel = venue.occupancy_pct >= 75 ? "High" : venue.occupancy_pct >= 45 ? "Medium" : "Low";

        output.innerHTML = `
          <div class="detail-list">
            <div class="detail-row"><span class="detail-label">Occupancy</span><span class="detail-value">${venue.occupancy_pct}% ${statusBadge(crowdLabel, crowdLabel.toLowerCase())}</span></div>
            <div class="detail-row"><span class="detail-label">Attendance</span><span class="detail-value">${venue.total_attendance}</span></div>
            <div class="detail-row"><span class="detail-label">Bottlenecks</span><span class="detail-value">${venue.bottleneck_zones.join(", ") || "None"}</span></div>
          </div>
        `;
        intelligencePanel(output, "organizer_crowd", {
          items: (venue.zones || []).slice(0, 4).map((zone) => `${zone.zone_name}: ${zone.occupancy_pct}% (${zone.density_level})`),
          reasons: [
            "Crowd pressure is taken from the latest venue snapshot.",
            "Bottleneck zones and accessibility routes are kept in view.",
            `Weather: ${getWeatherProfile().detail}`,
          ],
          confidence: 90,
          crowdLabel,
          crowdLevel: crowdLabel.toLowerCase(),
          incidentLabel: venue.occupancy_pct >= 75 ? "Warning" : "Info",
          incidentLevel: venue.occupancy_pct >= 75 ? "warning" : "info",
        });
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
        intelligencePanel(reportOutput, "organizer_report", {
          items: data.briefing?.action_items || [],
          reasons: [
            "Briefing uses the current crowd, incident, and volunteer context.",
            "Action items are ranked around immediate operational pressure points.",
            `Weather: ${getWeatherProfile().detail}`,
          ],
          confidence: data.briefing?.overall_status === "red" ? 93 : 87,
          crowdLabel: "Medium",
          crowdLevel: "medium",
          incidentLabel: data.briefing?.overall_status === "red" ? "Critical" : "Info",
          incidentLevel: data.briefing?.overall_status === "red" ? "critical" : "info",
        });
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
    updateWeatherWidgets();
  });
})();