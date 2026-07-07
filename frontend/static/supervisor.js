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
  // Only auto-refresh if dashboard feed tab is active
  const dashboardTab = document.getElementById("dashboardTab");
  if (!dashboardTab.classList.contains("active")) {
    return;
  }
  try {
    const response = await fetch("/api/dashboard");
    const payload = await response.json();
    renderMetrics(payload.metrics);
    renderAlerts(payload.alerts);
    renderTable(payload.records);
    renderMarkers(payload.records);
  } catch (err) {
    console.error("Dashboard refresh error:", err);
  }
}

async function triggerSpoofDemo() {
  await fetch("/api/demo/spoof", { method: "POST" });
  await refreshDashboard();
}

async function loadEmployees() {
  try {
    const response = await fetch("/api/employees");
    const payload = await response.json();
    const grid = document.getElementById("employeesGrid");
    
    if (!payload.employees.length) {
      grid.innerHTML = "<p class='empty-copy'>No registered workers found.</p>";
      return;
    }
    
    grid.innerHTML = payload.employees
      .map(emp => {
        const initials = emp.name.split(" ").map(n => n[0]).join("").slice(0, 2);
        const photoHtml = emp.photo_url 
          ? `<img class="employee-photo" src="${emp.photo_url}" alt="${emp.name}" onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';" />`
          : '';
          
        return `
          <div class="employee-card">
            <div class="employee-avatar-container">
              ${photoHtml}
              <div class="employee-avatar-placeholder" style="${emp.photo_url ? 'display:none;' : 'display:flex;'}">${initials}</div>
            </div>
            <div class="employee-details">
              <h3>${emp.name}</h3>
              <div class="employee-meta-info">
                <span class="label">Location:</span> ${emp.facility_name}
              </div>
              <div class="employee-meta-info">
                <span class="label">Hours:</span> ${emp.work_hours}
              </div>
            </div>
          </div>
        `;
      })
      .join("");
  } catch (err) {
    console.error("Error loading employees:", err);
  }
}

function initTabs() {
  const tabs = document.querySelectorAll(".tab-btn");
  tabs.forEach(btn => {
    btn.addEventListener("click", () => {
      tabs.forEach(t => t.classList.remove("active"));
      btn.classList.add("active");
      
      const target = btn.dataset.tab;
      document.querySelectorAll(".tab-content").forEach(tc => tc.classList.remove("active"));
      document.getElementById(`${target}Tab`).classList.add("active");
      
      if (target === "employees") {
        loadEmployees();
      } else {
        refreshDashboard();
      }
    });
  });
}

function initModal() {
  const modal = document.getElementById("employeeModal");
  const openBtn = document.getElementById("addEmployeeBtn");
  const closeBtn = document.getElementById("closeModalBtn");
  const cancelBtn = document.getElementById("cancelBtn");
  const fileInput = document.getElementById("empPhoto");
  const previewText = document.getElementById("photoPreviewText");
  const form = document.getElementById("employeeForm");
  
  if (!modal || !openBtn) return;

  openBtn.addEventListener("click", () => {
    modal.classList.add("active");
  });
  
  const closeModal = () => {
    modal.classList.remove("active");
    form.reset();
    previewText.textContent = "Click to select photo...";
  };
  
  closeBtn.addEventListener("click", closeModal);
  cancelBtn.addEventListener("click", closeModal);
  
  fileInput.addEventListener("change", (e) => {
    if (e.target.files.length) {
      previewText.textContent = e.target.files[0].name;
    } else {
      previewText.textContent = "Click to select photo...";
    }
  });
  
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const formData = new FormData(form);
    
    const submitBtn = form.querySelector("button[type='submit']");
    const originalText = submitBtn.textContent;
    submitBtn.textContent = "Registering...";
    submitBtn.disabled = true;
    
    try {
      const response = await fetch("/api/employees", {
        method: "POST",
        body: formData
      });
      if (response.ok) {
        closeModal();
        loadEmployees();
      } else {
        alert("Failed to register employee.");
      }
    } catch (err) {
      console.error(err);
      alert("Error submitting registration.");
    } finally {
      submitBtn.textContent = originalText;
      submitBtn.disabled = false;
    }
  });
}

window.addEventListener("DOMContentLoaded", async () => {
  document.getElementById("seedSpoofButton").addEventListener("click", triggerSpoofDemo);
  initTabs();
  initModal();
  await refreshDashboard();
  setInterval(refreshDashboard, 5000);
});
