const state = {
  eventType: "check_in",
  stream: null,
  photoBlob: null,
  latitude: null,
  longitude: null,
  eventTime: null,
  mediaRecorder: null,
  audioChunks: [],
  isRecording: false,
  recordTimer: null,
  recordSeconds: 0,
  gpsError: false,
};

const $ = (id) => document.getElementById(id);

function formatDateTime(value) {
  return new Intl.DateTimeFormat("en-IN", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function setEventType(type) {
  if (state.eventType === type) return;

  state.eventType = type;
  document.querySelectorAll(".segment").forEach((button) => {
    button.classList.toggle("active", button.dataset.type === type);
  });

  // Reset photo & timing data when toggling event type
  state.photoBlob = null;
  state.eventTime = null;

  // Reset UI elements
  const preview = $("photoPreview");
  preview.classList.add("hidden");
  preview.src = "";
  $("submitCheckIn").disabled = true;
  $("snapPhoto").textContent = "Capture photo";
  $("eventTimeLabel").textContent = "Not captured";

  // Hide any previous AI result card
  $("resultCard").classList.add("hidden");
  $("resultCard").innerHTML = "";
}

function updateOnlineStatus() {
  if (state.gpsError) {
    $("connectionStatus").textContent = "No GPS";
    $("connectionStatus").className = "status-chip no-gps";
  } else {
    $("connectionStatus").textContent = navigator.onLine ? "Online" : "Offline";
    $("connectionStatus").className = navigator.onLine ? "status-chip" : "status-chip offline";
  }
}

async function requestPermissions() {
  try {
    state.stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: "environment" },
      audio: false,
    });
    $("cameraPreview").srcObject = state.stream;
    $("requestPermissions").textContent = "Camera ready";
    $("requestPermissions").disabled = true;
    $("snapPhoto").disabled = false;
    await updateLocation();
  } catch (error) {
    $("requestPermissions").textContent = "Camera blocked";
  }
}

async function updateLocation() {
  const badge = $("locationBadge");
  const label = $("locationLabel");

  if (!("geolocation" in navigator)) {
    badge.textContent = "No GPS";
    label.textContent = "Unavailable";
    state.gpsError = true;
    updateOnlineStatus();
    return;
  }

  return new Promise((resolve) => {
    navigator.geolocation.getCurrentPosition(
      (position) => {
        state.latitude = position.coords.latitude;
        state.longitude = position.coords.longitude;
        const coords = `${state.latitude.toFixed(4)}, ${state.longitude.toFixed(4)}`;
        badge.textContent = "Location locked";
        badge.classList.remove("muted");
        label.textContent = coords;
        state.gpsError = false;
        updateOnlineStatus();
        resolve();
      },
      () => {
        badge.textContent = "GPS blocked";
        label.textContent = "Not shared";
        state.gpsError = true;
        updateOnlineStatus();
        resolve();
      },
      { enableHighAccuracy: true, timeout: 10000 }
    );
  });
}

function snapPhoto() {
  const video = $("cameraPreview");
  const canvas = $("photoCanvas");
  const preview = $("photoPreview");

  state.eventTime = new Date().toISOString();
  $("eventTimeLabel").textContent = formatDateTime(state.eventTime);

  canvas.width = video.videoWidth || 960;
  canvas.height = video.videoHeight || 720;
  const context = canvas.getContext("2d");
  context.drawImage(video, 0, 0, canvas.width, canvas.height);

  canvas.toBlob(
    (blob) => {
      state.photoBlob = blob;
      preview.src = URL.createObjectURL(blob);
      preview.classList.remove("hidden");
      $("submitCheckIn").disabled = false;
      $("snapPhoto").textContent = "Retake photo";
    },
    "image/jpeg",
    0.9
  );
}

function renderResult(record) {
  const resultCard = $("resultCard");
  resultCard.innerHTML = `
    <div class="panel-header">
      <h2>AI result</h2>
      <span class="badge ${record.verification_status}">${record.verification_status}</span>
    </div>
    <div class="result-metrics">
      <span>${Math.round(record.confidence * 100)}% confidence</span>
      <span>${record.risk_score}/100 risk</span>
    </div>
    <p>${record.ai_result}</p>
    <p><strong>Action:</strong> ${record.roster_suggestion}</p>
  `;
  resultCard.classList.remove("hidden");
}

async function submitAttendance() {
  if (!state.photoBlob) {
    return;
  }

  const formData = new FormData();
  formData.append("worker_name", $("workerName").value.trim());
  formData.append("facility_name", $("facilityName").value.trim());
  formData.append("event_type", state.eventType);
  formData.append("event_time", state.eventTime || new Date().toISOString());
  formData.append("note", $("noteInput").value.trim());
  formData.append("photo", state.photoBlob, `${state.eventType}.jpg`);

  if (state.latitude !== null && state.longitude !== null) {
    formData.append("latitude", String(state.latitude));
    formData.append("longitude", String(state.longitude));
  }

  $("submitCheckIn").disabled = true;
  $("submitCheckIn").textContent = "Analyzing...";

  try {
    const response = await fetch("/api/check-in", { method: "POST", body: formData });
    const payload = await response.json();
    renderResult(payload.record);
  } catch (error) {
    $("resultCard").innerHTML = "<p>Upload failed. Reconnect and try again.</p>";
    $("resultCard").classList.remove("hidden");
  } finally {
    $("submitCheckIn").textContent = "Submit attendance";
    $("submitCheckIn").disabled = false;
  }
}

async function toggleRecording() {
  const micBtn = $("micBtn");
  const noteInput = $("noteInput");

  if (!state.isRecording) {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          sampleRate: 16000,
          noiseSuppression: true,
          echoCancellation: true
        }
      });
      state.audioChunks = [];
      state.mediaRecorder = new MediaRecorder(stream, {
        audioBitsPerSecond: 16000
      });

      state.mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          state.audioChunks.push(event.data);
        }
      };

      state.mediaRecorder.onstop = async () => {
        stream.getTracks().forEach((track) => track.stop());
        const audioBlob = new Blob(state.audioChunks, { type: "audio/webm" });
        if (audioBlob.size === 0) return;
        await transcribeAudio(audioBlob);
      };

      state.mediaRecorder.start();
      state.isRecording = true;
      micBtn.classList.add("recording");
      micBtn.textContent = "🛑 Stop (0s)";
      noteInput.placeholder = "Listening... Speak now (max 10 seconds).";
      
      state.recordSeconds = 0;
      state.recordTimer = setInterval(() => {
        state.recordSeconds++;
        if (state.recordSeconds >= 10) {
          toggleRecording(); // auto-stop at 10s
        } else {
          micBtn.textContent = `🛑 Stop (${state.recordSeconds}s)`;
        }
      }, 1000);
      
    } catch (err) {
      console.error("Microphone access denied or error:", err);
      alert("Could not access microphone. Please check permissions.");
    }
  } else {
    if (state.recordTimer) {
      clearInterval(state.recordTimer);
      state.recordTimer = null;
    }
    
    if (state.mediaRecorder && state.mediaRecorder.state !== "inactive") {
      state.mediaRecorder.stop();
    }
    state.isRecording = false;
    micBtn.classList.remove("recording");
    micBtn.textContent = "🎙️ Record note";
    noteInput.placeholder = "Optional note (type or tap Record to speak)";
  }
}

async function transcribeAudio(audioBlob) {
  const micBtn = $("micBtn");
  const noteInput = $("noteInput");

  micBtn.disabled = true;
  micBtn.textContent = "⌛ Transcribing...";

  const formData = new FormData();
  formData.append("audio", audioBlob, "voice_note.webm");

  try {
    const response = await fetch("/api/transcribe", {
      method: "POST",
      body: formData,
    });
    
    if (!response.ok) {
      throw new Error("Server error during transcription");
    }

    const result = await response.json();
    
    if (result.transcription) {
      const currentVal = noteInput.value.trim();
      const transcribed = result.transcription.trim();
      noteInput.value = currentVal ? currentVal + " " + transcribed : transcribed;
    }
  } catch (err) {
    console.error("Transcription error:", err);
    alert("Could not transcribe audio. You can still type your note.");
  } finally {
    micBtn.disabled = false;
    micBtn.textContent = "🎙️ Record note";
  }
}

window.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".segment").forEach((button) => {
    button.addEventListener("click", () => setEventType(button.dataset.type));
  });

  $("requestPermissions").addEventListener("click", requestPermissions);
  $("snapPhoto").addEventListener("click", snapPhoto);
  $("submitCheckIn").addEventListener("click", submitAttendance);
  $("micBtn").addEventListener("click", toggleRecording);

  updateOnlineStatus();
  updateLocation();
  window.addEventListener("online", updateOnlineStatus);
  window.addEventListener("offline", updateOnlineStatus);
});
