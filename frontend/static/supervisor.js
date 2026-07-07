let map;
let markerLayer;

function statusPill(status) {
  return `<span class="badge ${status}">${status}</span>`;
}

function eventLabel(type) {
  return type === "check_out" ? "Check out" : "Check in";
}

function formatDateTime(value) {
  return new Intl.DateTimeFormat("en-IN", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function renderMetrics(metrics) {
  const grid = document.getElementById("metricGrid");
  const cards = [
    ["Events", metrics.total_events],
    ["Verified", metrics.verified_count],
    ["Review", metrics.review_count],
    ["Flagged", metrics.flagged_count],
  ];

  grid.innerHTML = cards
    .map(
      ([label, value]) => `
        <article class="metric-card">
          <span>${label}</span>
          <strong>${value}</strong>
        </article>
      `
    )
    .join("");
}

function renderAlerts(alerts) {
  const list = document.getElementById("alertsList");
  if (!alerts.length) {
    list.innerHTML = "<p class='empty-copy'>No alerts.</p>";
    return;
  }

  list.innerHTML = alerts
    .map(
      (alert) => `
        <article class="alert-item ${alert.level}">
          <div class="alert-title">
            <strong>${alert.title}</strong>
            <span>${alert.level}</span>
          </div>
          <p>${alert.detail}</p>
          <p>${alert.recommendation}</p>
        </article>
      `
    )
    .join("");
}

function renderTable(records) {
  const table = document.getElementById("checkInTable");
  table.innerHTML = `
    <div class="table-head">
      <span>Worker</span>
      <span>Event</span>
      <span>Time</span>
      <span>AI result</span>
      <span>Status</span>
    </div>
    ${records
      .map(
        (item) => `
          <div class="table-row">
            <span>
              <strong>${item.worker_name}</strong>
              <small>${item.facility_name}</small>
              ${item.note ? `<div class="worker-note">"<i>${item.note}</i>"</div>` : ""}
              ${item.translated_note && item.translated_note !== item.note ? `<div class="worker-note-translation"><small>🌐 English: "${item.translated_note}"</small></div>` : ""}
            </span>
            <span>${eventLabel(item.event_type)}</span>
            <span>${formatDateTime(item.event_time)}</span>
            <span>${item.ai_result}</span>
            <span>${statusPill(item.verification_status)}</span>
          </div>
        `
      )
      .join("")}
  `;
}

function ensureMap() {
  if (map || !window.L) {
    return;
  }
  map = L.map("map", { zoomControl: false }).setView([23.2599, 77.4126], 11);
  L.control.zoom({ position: "bottomright" }).addTo(map);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "&copy; OpenStreetMap contributors",
  }).addTo(map);
  markerLayer = L.layerGroup().addTo(map);
}

function renderMarkers(records) {
  ensureMap();
  if (!markerLayer) {
    return;
  }

  markerLayer.clearLayers();
  records.forEach((item) => {
    if (item.latitude === null || item.longitude === null) {
      return;
    }
    const marker = L.marker([item.latitude, item.longitude]);
    marker.bindPopup(`
      <strong>${item.worker_name}</strong><br />
      ${eventLabel(item.event_type)}<br />
      ${item.verification_status.toUpperCase()} | Risk ${item.risk_score}
    `);
    marker.addTo(markerLayer);
  });
}

async function refreshDashboard() {
  const response = await fetch("/api/dashboard");
  const payload = await response.json();
  renderMetrics(payload.metrics);
  renderAlerts(payload.alerts);
  renderTable(payload.records);
  renderMarkers(payload.records);
}

async function triggerSpoofDemo() {
  await fetch("/api/demo/spoof", { method: "POST" });
  await refreshDashboard();
}

window.addEventListener("DOMContentLoaded", async () => {
  document.getElementById("seedSpoofButton").addEventListener("click", triggerSpoofDemo);
  await refreshDashboard();
  setInterval(refreshDashboard, 5000);
});
