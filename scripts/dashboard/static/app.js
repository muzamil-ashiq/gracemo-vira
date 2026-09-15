// GRaCEmo ViRa — Observability Dashboard Client
let ws = null;

function connectWebSocket() {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = `${protocol}//${window.location.host}/ws`;

  ws = new WebSocket(wsUrl);

  ws.onopen = () => {
    document.getElementById("wsDot").style.backgroundColor = "#10b981";
    document.getElementById("wsDot").style.boxShadow = "0 0 10px #10b981";
    document.getElementById("wsStatus").innerText = "Connected";
    document.getElementById("wsStatus").style.color = "#10b981";
  };

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      if (data.type === "state_update") {
        updateTelemetry(data.telemetry);
        updateAdapters(data.adapters);
        updateTimeline(data.recent_events);
      }
    } catch (e) {
      console.error("Error parsing WebSocket packet", e);
    }
  };

  ws.onclose = () => {
    document.getElementById("wsDot").style.backgroundColor = "#ef4444";
    document.getElementById("wsDot").style.boxShadow = "0 0 10px #ef4444";
    document.getElementById("wsStatus").innerText = "Reconnecting...";
    document.getElementById("wsStatus").style.color = "#ef4444";
    setTimeout(connectWebSocket, 2000);
  };

  ws.onerror = () => {
    ws.close();
  };
}

function updateTelemetry(t) {
  if (!t) return;
  document.getElementById("valX").innerHTML = `${t.x.toFixed(3)} <small>m</small>`;
  document.getElementById("valY").innerHTML = `${t.y.toFixed(3)} <small>m</small>`;
  document.getElementById("valYaw").innerHTML = `${t.yaw_deg.toFixed(1)} <small>°</small>`;
  document.getElementById("valVx").innerHTML = `${t.vx.toFixed(2)} <small>m/s</small>`;
  document.getElementById("valWz").innerHTML = `${t.wz.toFixed(2)} <small>rad/s</small>`;

  const d = t.min_obstacle_dist;
  const obsEl = document.getElementById("valObstacle");
  const fillEl = document.getElementById("cushionFill");
  const cushionText = document.getElementById("cushionText");

  if (d > 10.0) {
    obsEl.innerHTML = `> 10.0 <small>m</small>`;
    fillEl.style.width = "100%";
    fillEl.style.background = "linear-gradient(90deg, #10b981, #06b6d4)";
    cushionText.innerText = "Clearance Safe";
  } else {
    obsEl.innerHTML = `${d.toFixed(2)} <small>m</small>`;
    const pct = Math.min(100, Math.max(0, (d / 2.0) * 100));
    fillEl.style.width = `${pct}%`;

    if (d < 0.45) {
      fillEl.style.background = "#ef4444";
      cushionText.innerText = "CUSHION ACTIVE (Close Obstacle)";
      cushionText.style.color = "#ef4444";
    } else if (d < 0.80) {
      fillEl.style.background = "#f59e0b";
      cushionText.innerText = "Obstacle Approaching";
      cushionText.style.color = "#f59e0b";
    } else {
      fillEl.style.background = "linear-gradient(90deg, #10b981, #06b6d4)";
      cushionText.innerText = "Clearance Safe";
      cushionText.style.color = "#94a3b8";
    }
  }

  document.getElementById("robotState").innerText = t.status || "READY";
  document.getElementById("targetRoom").innerText = t.target_room || "None";
  document.getElementById("missionStep").innerText = t.mission_step || "Stationary";
}

function updateAdapters(a) {
  if (!a) return;
  if (a.vision) {
    document.getElementById("visLatency").innerText = a.vision.latency_ms;
    document.getElementById("visFps").innerText = a.vision.fps;
    document.getElementById("visConf").innerText = `${Math.round(a.vision.confidence_avg * 100)}%`;
  }
  if (a.voice) {
    document.getElementById("voiceLatency").innerText = a.voice.stt_latency_ms;
    document.getElementById("voiceStatus").innerText = a.voice.status;
  }
  if (a.brain) {
    document.getElementById("brainLatency").innerText = a.brain.planning_latency_ms;
  }
  if (a.bridge) {
    document.getElementById("bridgeRate").innerText = a.bridge.msg_rate_hz;
  }
}

function updateTimeline(events) {
  if (!events) return;
  document.getElementById("timelineCount").innerText = `${events.length} Events`;

  const container = document.getElementById("timelineList");
  container.innerHTML = "";

  events.forEach((evt) => {
    const item = document.createElement("div");
    item.className = "timeline-item";

    // Border color based on source
    let borderColor = "#06b6d4";
    if (evt.source.includes("VOICE")) borderColor = "#8b5cf6";
    else if (evt.source.includes("KERNEL")) borderColor = "#06b6d4";
    else if (evt.source.includes("BRAIN")) borderColor = "#3b82f6";
    else if (evt.source.includes("BRIDGE")) borderColor = "#10b981";
    item.style.borderLeftColor = borderColor;

    item.innerHTML = `
      <div class="timeline-left">
        <span class="timeline-time">${evt.timestamp}</span>
        <span class="timeline-source" style="color: ${borderColor}">${evt.source}</span>
        <span class="timeline-payload">${evt.payload}</span>
      </div>
      <div class="timeline-latency">${evt.latency_ms > 0 ? evt.latency_ms + " ms" : ""}</div>
    `;
    container.appendChild(item);
  });
}

async function dispatchRoom(room) {
  try {
    const res = await fetch("/api/command", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ command: `Navigate to the ${room}`, target_room: room }),
    });
    const data = await res.json();
    console.log("Dispatched:", data);
  } catch (e) {
    console.error("Failed to dispatch command", e);
  }
}

async function dispatchCustom() {
  const input = document.getElementById("cmdInput");
  const val = input.value.trim();
  if (!val) return;

  try {
    const res = await fetch("/api/command", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ command: val, target_room: "Custom Destination" }),
    });
    input.value = "";
  } catch (e) {
    console.error("Failed to dispatch custom intent", e);
  }
}

// Connect on load
window.addEventListener("DOMContentLoaded", connectWebSocket);
