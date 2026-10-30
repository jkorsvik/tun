"use strict";

const form = document.querySelector("#decision-form");
const list = document.querySelector("#decision-list");
const filter = document.querySelector("#status-filter");
const summary = document.querySelector("#summary");
const requestError = document.querySelector("#request-error");
const formError = document.querySelector("#form-error");
const createButton = document.querySelector("#create-button");
let loadVersion = 0;

function node(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined) element.textContent = text;
  return element;
}

async function api(url, options = {}) {
  const response = await fetch(url, options);
  let payload;
  try {
    payload = await response.json();
  } catch (_error) {
    throw new Error(`The local server returned HTTP ${response.status} without JSON.`);
  }
  if (!response.ok) {
    const error = new Error(payload.error?.message || `Request failed with HTTP ${response.status}.`);
    error.fields = payload.error?.fields || {};
    throw error;
  }
  return payload;
}

function detail(term, value, className) {
  const wrapper = node("div");
  wrapper.append(node("dt", "", term));
  wrapper.append(node("dd", className, value));
  return wrapper;
}

function decisionCard(row) {
  const card = node("article", "decision");
  card.dataset.decisionId = String(row.id);
  card.dataset.status = row.status;

  const heading = node("div", "decision-heading");
  heading.append(node("h2", "", row.decision));
  heading.append(node("span", `status status-${row.status}`, row.status === "open" ? "Open" : "Completed"));
  card.append(heading);

  const details = node("dl", "details");
  details.append(detail("Next action", row.action, "field-action"));
  details.append(detail("Owner", row.owner, "field-owner"));
  details.append(detail("Due", row.due_date || "No due date", "field-due"));
  details.append(detail("Created", row.created_at, "field-created"));
  details.append(detail("Completed", row.completed_at || "Not completed", "field-completed"));
  card.append(details);

  if (row.status === "open") {
    const footer = node("div", "decision-footer");
    const button = node("button", "complete-button", "Mark complete");
    button.type = "button";
    button.addEventListener("click", async () => {
      button.disabled = true;
      requestError.hidden = true;
      try {
        await api(`/api/decisions/${row.id}/complete`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: "{}"
        });
        await loadDecisions();
      } catch (error) {
        requestError.textContent = error.message;
        requestError.hidden = false;
        button.disabled = false;
      }
    });
    footer.append(button);
    card.append(footer);
  }
  return card;
}

async function loadDecisions() {
  const version = ++loadVersion;
  list.setAttribute("aria-busy", "true");
  requestError.hidden = true;
  try {
    const payload = await api(`/api/decisions?status=${encodeURIComponent(filter.value)}`);
    if (version !== loadVersion) return;
    list.replaceChildren();
    if (!payload.decisions.length) {
      list.append(node("p", "empty", "No decisions match this filter."));
    } else {
      payload.decisions.forEach(row => list.append(decisionCard(row)));
    }
    summary.textContent = `${payload.count} decision${payload.count === 1 ? "" : "s"} shown`;
  } catch (error) {
    if (version !== loadVersion) return;
    list.replaceChildren();
    summary.textContent = "The decision log is unavailable.";
    requestError.textContent = error.message;
    requestError.hidden = false;
  } finally {
    if (version === loadVersion) list.setAttribute("aria-busy", "false");
  }
}

function clearValidation() {
  formError.hidden = true;
  formError.textContent = "";
  ["decision", "action", "owner", "due_date"].forEach(name => {
    document.querySelector(`#${name}-error`).textContent = "";
    document.querySelector(`#${name}`).removeAttribute("aria-invalid");
  });
}

function showValidation(error) {
  formError.textContent = error.message;
  formError.hidden = false;
  let firstInvalid;
  Object.entries(error.fields || {}).forEach(([name, message]) => {
    const input = document.querySelector(`#${name}`);
    const target = document.querySelector(`#${name}-error`);
    if (input && target) {
      target.textContent = message;
      input.setAttribute("aria-invalid", "true");
      input.setAttribute("aria-describedby", `${name}-error`);
      firstInvalid ||= input;
    }
  });
  if (firstInvalid) firstInvalid.focus();
}

form.addEventListener("submit", async event => {
  event.preventDefault();
  clearValidation();
  createButton.disabled = true;
  const body = {
    decision: document.querySelector("#decision").value,
    action: document.querySelector("#action").value,
    owner: document.querySelector("#owner").value,
    due_date: document.querySelector("#due_date").value || null
  };
  try {
    await api("/api/decisions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });
    form.reset();
    filter.value = "all";
    await loadDecisions();
  } catch (error) {
    showValidation(error);
  } finally {
    createButton.disabled = false;
  }
});

filter.addEventListener("change", loadDecisions);

// Bootstrap last: every const above must exist before the first request starts.
loadDecisions();
