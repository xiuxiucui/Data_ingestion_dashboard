"use strict";

const $ = (id) => document.getElementById(id);

async function checkHealth() {
  const dot = $("health-dot");
  const label = $("health-label");

  try {
    const response = await fetch("/health");
    if (!response.ok) throw new Error("Health check failed");
    dot.className = "status-dot online";
    label.textContent = "API online";
  } catch (error) {
    dot.className = "status-dot offline";
    label.textContent = "API unavailable";
  }
}

function showStatus(statusElement, text, successful) {
  statusElement.textContent = text;
  statusElement.className = `response-status ${successful ? "success" : "error"}`;
}

function setBusy(button, busy) {
  if (!button.dataset.label) button.dataset.label = button.textContent;
  button.disabled = busy;
  button.textContent = busy ? "Sending…" : button.dataset.label;
}

function parsePayload(textarea, responseElement, statusElement) {
  try {
    return JSON.parse(textarea.value);
  } catch (error) {
    showStatus(statusElement, "Invalid JSON", false);
    responseElement.textContent = error.message;
    return null;
  }
}

async function sendJson({ endpoint, textarea, button, responseElement, statusElement }) {
  const payload = parsePayload(textarea, responseElement, statusElement);
  if (payload === null) return null;

  setBusy(button, true);
  try {
    const response = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await readJsonResponse(response);
    responseElement.textContent = JSON.stringify(data, null, 2);
    const requestId = response.headers.get("X-Request-ID");
    const label = `${response.status} ${response.statusText}${requestId ? ` · ${requestId.slice(0, 8)}` : ""}`;
    showStatus(statusElement, label, response.ok);
    return response.ok ? data : null;
  } catch (error) {
    showStatus(statusElement, "Network error", false);
    responseElement.textContent = error.message;
    return null;
  } finally {
    setBusy(button, false);
  }
}

async function readJsonResponse(response) {
  const text = await response.text();
  if (!text) return {};
  try {
    return JSON.parse(text);
  } catch (error) {
    return { rawResponse: text };
  }
}

async function loadDashboard() {
  const name = $("dashboard-name").value.trim();
  const button = $("get-dashboard");
  const statusElement = $("result-status");
  const responseElement = $("result-response");
  const renderTarget = $("dashboard-render");

  if (!name) {
    showStatus(statusElement, "Name required", false);
    renderTarget.className = "dashboard-render empty-state";
    renderTarget.textContent = "Enter a dashboard name first.";
    return;
  }

  setBusy(button, true);
  try {
    const response = await fetch(`/dashboard/${encodeURIComponent(name)}`);
    const data = await readJsonResponse(response);
    responseElement.textContent = JSON.stringify(data, null, 2);
    showStatus(statusElement, `${response.status} ${response.statusText}`, response.ok);

    if (response.ok) {
      renderDashboard(data, renderTarget);
    } else {
      renderTarget.className = "dashboard-render empty-state";
      renderTarget.textContent = data.error?.message || "The dashboard could not be loaded.";
    }
  } catch (error) {
    showStatus(statusElement, "Network error", false);
    responseElement.textContent = error.message;
    renderTarget.className = "dashboard-render empty-state";
    renderTarget.textContent = "The API could not be reached.";
  } finally {
    setBusy(button, false);
  }
}

function renderDashboard(data, target) {
  target.replaceChildren();
  target.className = "dashboard-render";

  for (const view of data.views || []) {
    if (view.type === "summary") {
      target.appendChild(renderSummary(view));
    } else if (view.type === "table") {
      target.appendChild(renderTable(view));
    }
  }

  if (!target.children.length) {
    target.className = "dashboard-render empty-state";
    target.textContent = "This dashboard has no views.";
  }
}

function renderSummary(view) {
  const container = document.createElement("div");
  container.className = "summary-view";

  const label = document.createElement("span");
  label.textContent = `${view.aggregation} of ${view.field}`;

  const value = document.createElement("strong");
  value.textContent = view.value ?? "—";

  container.append(label, value);
  return container;
}

function renderTable(view) {
  const wrapper = document.createElement("div");
  wrapper.className = "table-wrap";
  const table = document.createElement("table");
  const head = document.createElement("thead");
  const headingRow = document.createElement("tr");

  for (const column of view.columns || []) {
    const heading = document.createElement("th");
    heading.scope = "col";
    heading.textContent = column;
    headingRow.appendChild(heading);
  }
  head.appendChild(headingRow);
  table.appendChild(head);

  const body = document.createElement("tbody");
  if (!view.rows?.length) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = Math.max(view.columns?.length || 1, 1);
    cell.className = "no-rows";
    cell.textContent = "No rows ingested yet.";
    row.appendChild(cell);
    body.appendChild(row);
  } else {
    for (const dataRow of view.rows) {
      const row = document.createElement("tr");
      for (const column of view.columns || []) {
        const cell = document.createElement("td");
        const value = dataRow[column];
        cell.textContent = value === null || value === undefined
          ? "—"
          : typeof value === "object"
            ? JSON.stringify(value)
            : String(value);
        row.appendChild(cell);
      }
      body.appendChild(row);
    }
  }
  table.appendChild(body);
  wrapper.appendChild(table);
  return wrapper;
}

$("send-schema").addEventListener("click", () => sendJson({
  endpoint: "/schema",
  textarea: $("schema-payload"),
  button: $("send-schema"),
  responseElement: $("schema-response"),
  statusElement: $("schema-status"),
}));

$("send-ingest").addEventListener("click", () => sendJson({
  endpoint: "/ingest",
  textarea: $("ingest-payload"),
  button: $("send-ingest"),
  responseElement: $("ingest-response"),
  statusElement: $("ingest-status"),
}));

$("send-dashboard").addEventListener("click", () => sendJson({
  endpoint: "/dashboard",
  textarea: $("dashboard-payload"),
  button: $("send-dashboard"),
  responseElement: $("dashboard-response"),
  statusElement: $("dashboard-status"),
}));

$("get-dashboard").addEventListener("click", loadDashboard);
$("dashboard-name").addEventListener("keydown", (event) => {
  if (event.key === "Enter") loadDashboard();
});

checkHealth();
