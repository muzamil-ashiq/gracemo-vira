import './gazebo3d.js';

// GraceEMO — LPU Digital Twin Command Center Client

let ws = null;
let rosLive = false;
let robotState = {
  x: 0, y: 0, yaw: 0, linear_v: 0, angular_w: 0, battery: 98.5,
  status: 'READY', task: 'IDLE', neck_yaw: 0, neck_pitch: 0,
  left_hand: 0, right_hand: 0, speech: '',
};

let buildings = [];
let dynamicAgents = [];
let scanRanges = [];
let currentMission = null;
let lastTwin = null;
const sessionStart = Date.now();

function applyTwinState(data) {
  if (!data) return;
  lastTwin = data;

  // 1. Robot Pose & Joints
  if (data.robot) {
    robotState = Object.assign(robotState, data.robot);
    if (window.GraceGazebo) {
      window.GraceGazebo.setRobot(robotState);
      window.GraceGazebo.setScan(data.scan || scanRanges, robotState);
    }
    const el = (id) => document.getElementById(id);
    if (el('val-x')) el('val-x').textContent = robotState.x.toFixed(2) + ' m';
    if (el('val-y')) el('val-y').textContent = robotState.y.toFixed(2) + ' m';
    if (el('val-yaw')) el('val-yaw').textContent = ((robotState.yaw * 180) / Math.PI).toFixed(1) + '°';
    if (el('val-speed')) el('val-speed').textContent = Math.abs(robotState.linear_v || 0).toFixed(2) + ' m/s';
    const sns = data.sensors || {};
    if (el('val-prox') && sns.front_range_m != null) el('val-prox').textContent = Number(sns.front_range_m).toFixed(2) + ' m';
    if (el('val-bump')) {
      el('val-bump').textContent = sns.bumper ? 'HIT' : 'OPEN';
      el('val-bump').style.color = sns.bumper ? '#dc2626' : '';
    }
    if (el('batt-val')) el('batt-val').textContent = Math.round(robotState.battery || 0) + '%';
    if (el('mode-text')) el('mode-text').textContent = (robotState.task && robotState.task !== 'IDLE')
      ? robotState.task.toUpperCase() : 'AUTONOMOUS';

    // 4-Wheel HUD
    if (robotState.wheels) {
      const w = robotState.wheels;
      if (el('wheel-fl-val') && w.fl) el('wheel-fl-val').textContent = (w.fl.rpm || 0).toFixed(1) + ' RPM';
      if (el('wheel-fr-val') && w.fr) el('wheel-fr-val').textContent = (w.fr.rpm || 0).toFixed(1) + ' RPM';
      if (el('wheel-rl-val') && w.rl) el('wheel-rl-val').textContent = (w.rl.rpm || 0).toFixed(1) + ' RPM';
      if (el('wheel-rr-val') && w.rr) el('wheel-rr-val').textContent = (w.rr.rpm || 0).toFixed(1) + ' RPM';

      const hasFault = (w.fl && w.fl.status === 'FAULT') || (w.fr && w.fr.status === 'FAULT');
      if (el('wheels-overall-status')) {
        el('wheels-overall-status').textContent = hasFault ? '⚠️ WHEEL FAULT' : '● ALL WHEELS NOMINAL';
        el('wheels-overall-status').style.color = hasFault ? '#ef4444' : '#22c55e';
      }
    }
  }
  if (data.scan && data.scan.length) {
    scanRanges = data.scan;
  }

  // 2. 3D Scene Updates (Buildings, Dynamic Pedestrians & Vehicles)
  if (data.buildings && data.buildings.length && data.buildings.length !== buildings.length) {
    buildings = data.buildings;
    if (window.GraceGazebo) window.GraceGazebo.setBuildings(buildings);
  }
  if (data.dynamic_agents) {
    dynamicAgents = data.dynamic_agents;
    if (window.GraceGazebo) window.GraceGazebo.setDynamicAgents(dynamicAgents);
  }

  paintAllFeeds();

  // 4. Scenario & Weather
  if (data.scenario) {
    const w = data.scenario.weather || 'clear_day';
    const hudW = document.getElementById('hud-weather');
    if (hudW) hudW.textContent = w.toUpperCase().replace('_', ' ');
    if (window.GraceGazebo) window.GraceGazebo.setWeather(w);
  }

  // 5. Central Server & Network Status
  if (data.server) {
    const gpuEl = document.getElementById('gpu-val');
    if (gpuEl) gpuEl.textContent = 'SIM ' + (data.server.gpu_utilization || 55) + '%';
  }
  if (data.network) {
    const netEl = document.getElementById('net-mode-val');
    if (netEl) {
      const lat = data.network.actual_latency_ms || data.network.latency_ms || 12;
      netEl.textContent = `${lat}ms`;
    }
  }

  // 6. Mission State
  if (data.mission && data.mission.active_mission) {
    currentMission = data.mission.active_mission;
    const badge = document.getElementById('mission-status-badge');
    const desc = document.getElementById('tracker-desc');
    const pct = document.getElementById('tracker-pct');
    const bar = document.getElementById('tracker-bar');

    if (badge) {
      const t = (currentMission.type || 'escort').toUpperCase();
      badge.textContent = 'MODE: ' + t;
      badge.className = 'tag orange';
    }
    if (desc) desc.textContent = currentMission.description || 'Active Mission';
    const progress = Math.round((currentMission.progress || 0) * 100);
    if (pct) pct.textContent = progress + '%';
    if (bar) bar.style.width = progress + '%';
    const stepsEl = document.getElementById('mission-steps');
    if (stepsEl) {
      stepsEl.innerHTML = '';
      const steps = currentMission.steps || [];
      steps.forEach((s, idx) => {
        const li = document.createElement('li');
        const isDone = Boolean(s.done);
        const isCurrent = !isDone && (idx === 0 || steps[idx - 1].done);
        const icon = isDone ? '✓' : (isCurrent ? '▶' : '○');
        li.innerHTML = `<span style="display:inline-block; width:16px; font-weight:700; color:${isDone ? '#22c55e' : (isCurrent ? '#38bdf8' : '#64748b')}">${icon}</span> <span>${s.label || ('Step ' + (idx + 1))}</span>`;
        li.className = isDone ? 'done' : (isCurrent ? 'current' : '');
        stepsEl.appendChild(li);
      });
    }
  } else {
    currentMission = null;
    const badge = document.getElementById('mission-status-badge');
    if (badge) {
      badge.textContent = 'MODE: IDLE';
      badge.className = 'tag orange';
    }
    const stepsEl = document.getElementById('mission-steps');
    if (stepsEl) stepsEl.innerHTML = '';
  }

  // 7. Structured Event Logs
  if (data.recent_logs && data.recent_logs.length) {
    const feed = document.getElementById('log-feed');
    if (feed) {
      feed.innerHTML = '';
      for (const l of data.recent_logs) {
        const row = document.createElement('div');
        row.className = 'log-entry ' + (l.severity ? l.severity.toLowerCase() : 'info');
        row.textContent = `[${l.time_str || ''} ${l.module || 'SYS'}] ${l.message || ''}`;
        feed.appendChild(row);
      }
      feed.scrollTop = feed.scrollHeight;
    }
  }

  updateHealthBar(data);
  fillLivePanels(data);
}

// WebSocket Connection
function connectWebSocket() {
  const host = window.location.host || 'localhost:8888';
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = protocol + '//' + host + '/ws';

  try {
    ws = new WebSocket(wsUrl);
  } catch (e) {
    return;
  }

  ws.onopen = () => {
    rosLive = true;
    const badge = document.getElementById('conn-badge');
    const text = document.getElementById('conn-text');
    if (badge) badge.classList.add('connected');
    if (text) text.textContent = 'DIGITAL TWIN LIVE';
    const online = document.getElementById('robot-online');
    if (online) { online.textContent = 'ONLINE'; online.style.color = ''; }
  };

  ws.onclose = () => {
    rosLive = false;
    const badge = document.getElementById('conn-badge');
    const text = document.getElementById('conn-text');
    if (badge) badge.classList.remove('connected');
    if (text) text.textContent = 'CONNECTING…';
    const online = document.getElementById('robot-online');
    if (online) { online.textContent = 'OFFLINE'; online.style.color = '#dc2626'; }
    setTimeout(connectWebSocket, 2000);
  };

  ws.onerror = () => {};

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      if (data.type === 'digital_twin_state' || data.type === 'state') {
        applyTwinState(data);
      }
    } catch (e) {
      console.error('WS Parse Error:', e);
    }
  };
}

// Command Dispatchers
function sendWs(payload) {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(payload));
  }
}

function sendTeleop(v, w) {
  sendWs({ action: 'teleop', v, w });
}

function dispatchNlMission(text) {
  if (!text) return;
  sendWs({ action: 'create_mission_nl', text });
  const logFeed = document.getElementById('log-feed');
  if (logFeed) {
    const row = document.createElement('div');
    row.className = 'log-entry info';
    row.textContent = `[USER] Dispatched Mission: "${text}"`;
    logFeed.appendChild(row);
  }
}

function sizeCanvas(c) {
  const w = Math.max(1, c.clientWidth || 160);
  const h = Math.max(1, c.clientHeight || 84);
  if (c.width !== w || c.height !== h) {
    c.width = w;
    c.height = h;
  }
  return { w, h, ctx: c.getContext('2d') };
}

const jpegLast = {};

function markEmpty(c, msg) {
  const { w, h, ctx } = sizeCanvas(c);
  ctx.fillStyle = '#071018';
  ctx.fillRect(0, 0, w, h);
  ctx.fillStyle = '#94a3b8';
  ctx.font = '11px Inter, sans-serif';
  ctx.fillText(msg, 8, Math.max(16, h / 2));
}

function blitJpeg(canvasId, b64) {
  const c = document.getElementById(canvasId);
  if (!c) return false;
  if (!b64) {
    markEmpty(c, 'NO TWIN JPEG');
    return false;
  }
  if (jpegLast[canvasId] === b64) return true;
  jpegLast[canvasId] = b64;
  const img = new Image();
  img.onload = () => {
    const { w, h, ctx } = sizeCanvas(c);
    ctx.drawImage(img, 0, 0, w, h);
  };
  img.src = 'data:image/jpeg;base64,' + b64;
  return true;
}

function drawLidar(ranges) {
  const c = document.getElementById('lidarCanvas');
  if (!c) return;
  if (!ranges || !ranges.length) {
    markEmpty(c, 'NO /scan');
    return;
  }
  const { w, h, ctx } = sizeCanvas(c);
  ctx.fillStyle = '#071018';
  ctx.fillRect(0, 0, w, h);
  const cx = w / 2;
  const cy = h / 2 + 4;
  const R = Math.min(w, h) * 0.42;
  ctx.strokeStyle = '#1e3a5f';
  ctx.lineWidth = 1;
  for (const r of [0.33, 0.66, 1]) {
    ctx.beginPath();
    ctx.arc(cx, cy, R * r, 0, Math.PI * 2);
    ctx.stroke();
  }
  const n = ranges.length;
  ctx.lineWidth = 1.4;
  for (let i = 0; i < n; i++) {
    const d = ranges[i];
    if (!(d < 28)) continue;
    const angRel = -Math.PI + (i * 2 * Math.PI / n);
    const ang = -Math.PI / 2 + angRel;
    const t = Math.min(1, d / 12);
    ctx.strokeStyle = `hsl(${Math.min(240, (d / 12) * 240)}, 90%, 55%)`;
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.lineTo(cx + Math.cos(ang) * R * t, cy + Math.sin(ang) * R * t);
    ctx.stroke();
  }
  ctx.fillStyle = '#ea580c';
  ctx.beginPath();
  ctx.arc(cx, cy, 3, 0, Math.PI * 2);
  ctx.fill();
}

function paintAllFeeds() {
  const t = lastTwin || {};
  const camOk = blitJpeg('cameraFeed', t.camera_jpeg);
  blitJpeg('cam-front', t.camera_jpeg);
  blitJpeg('cam-left', t.camera_left_jpeg);
  blitJpeg('cam-right', t.camera_right_jpeg);
  if (t.camera_det_jpeg) blitJpeg('detFeed', t.camera_det_jpeg);
  else if (document.getElementById('detFeed')) markEmpty(document.getElementById('detFeed'), 'NO DETECTIONS JPEG');
  if (t.camera_depth_jpeg) blitJpeg('depthFeed', t.camera_depth_jpeg);
  else drawDepth(scanRanges);
  if (t.sensors && t.sensors.lidar_failed) {
    markEmpty(document.getElementById('lidarCanvas'), 'LIDAR FAULT');
  } else {
    drawLidar(scanRanges);
  }
  drawLocalMap(scanRanges, robotState);
  const tag = document.getElementById('cam-live-tag');
  if (tag) tag.textContent = camOk ? 'TWIN CAM' : 'NO CAM';
}

function drawDepth(ranges) {
  const c = document.getElementById('depthFeed');
  if (!c) return;
  if (!ranges || !ranges.length) {
    markEmpty(c, 'NO /scan');
    return;
  }
  const { w, h, ctx } = sizeCanvas(c);
  const n = ranges.length;
  const img = ctx.createImageData(w, h);
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const i = Math.floor((x / w) * n);
      const d = Math.min(20, ranges[i] || 20);
      const g = Math.max(28, Math.floor(245 - (d / 20) * 210));
      const p = (y * w + x) * 4;
      img.data[p] = g;
      img.data[p + 1] = g;
      img.data[p + 2] = g + 8;
      img.data[p + 3] = 255;
    }
  }
  ctx.putImageData(img, 0, 0);
}

function drawLocalMap(ranges, robot) {
  const c = document.getElementById('localMap');
  if (!c) return;
  const { w, h, ctx } = sizeCanvas(c);
  ctx.fillStyle = '#0b1220';
  ctx.fillRect(0, 0, w, h);
  const scale = 4.2;
  const cx = w / 2;
  const cy = h / 2;
  ctx.strokeStyle = '#1e293b';
  ctx.lineWidth = 1;
  for (let g = -40; g <= 40; g += 5) {
    ctx.beginPath();
    ctx.moveTo(cx + g * scale, 0);
    ctx.lineTo(cx + g * scale, h);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(0, cy + g * scale);
    ctx.lineTo(w, cy + g * scale);
    ctx.stroke();
  }
  if (ranges && ranges.length) {
    ctx.fillStyle = '#38bdf8';
    const n = ranges.length;
    const yaw = robot.yaw || 0;
    for (let i = 0; i < n; i += 1) {
      const d = ranges[i];
      if (!(d < 20)) continue;
      const ang = yaw - Math.PI + (i * 2 * Math.PI / n);
      const x = cx + d * Math.cos(ang) * scale;
      const y = cy - d * Math.sin(ang) * scale;
      ctx.fillRect(x, y, 2, 2);
    }
  }
  ctx.fillStyle = '#ea580c';
  ctx.beginPath();
  ctx.moveTo(cx + 7, cy);
  ctx.lineTo(cx - 5, cy - 5);
  ctx.lineTo(cx - 5, cy + 5);
  ctx.closePath();
  ctx.fill();
  if (dynamicAgents && dynamicAgents.length) {
    ctx.fillStyle = '#22c55e';
    for (const a of dynamicAgents) {
      const x = cx + ((a.x || 0) - (robot.x || 0)) * scale;
      const y = cy - ((a.y || 0) - (robot.y || 0)) * scale;
      ctx.fillRect(x - 2, y - 2, 4, 4);
    }
  }
}

function tickHud() {
  const clock = document.getElementById('clock');
  if (clock) {
    clock.textContent = new Date().toLocaleString('en-US', {
      weekday: 'short', day: '2-digit', month: 'short', year: 'numeric',
      hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true,
    });
  }
  const up = document.getElementById('uptime-val');
  if (up) {
    const s = Math.floor((Date.now() - sessionStart) / 1000);
    const hh = String(Math.floor(s / 3600)).padStart(2, '0');
    const mm = String(Math.floor((s % 3600) / 60)).padStart(2, '0');
    const ss = String(s % 60).padStart(2, '0');
    up.textContent = `${hh}:${mm}:${ss}`;
  }
}

function showView(name) {
  document.querySelectorAll('.nav-item').forEach((b) => {
    b.classList.toggle('active', b.getAttribute('data-view') === name);
  });
  const overlay = document.getElementById('view-overlay');
  const body = document.getElementById('overlay-body');
  const title = document.getElementById('overlay-title');
  const dash = ['dashboard', 'map', 'missions'];
  const templates = document.getElementById('overlay-templates');
  if (body && templates) {
    while (body.firstChild) templates.appendChild(body.firstChild);
  }
  if (dash.includes(name)) {
    if (overlay) {
      overlay.hidden = true;
      overlay.classList.remove('is-open');
    }
    return;
  }
  const titles = {
    robots: 'Robots',
    server: 'Server & Cloud',
    scenarios: 'Scenarios',
    analytics: 'Analytics',
    logs: 'Logs',
    sensors: 'Sensors',
    ai: 'AI & Perception',
    settings: 'Settings',
  };
  const tpl = document.getElementById('tpl-' + name) || document.getElementById('tpl-settings');
  if (overlay && body && tpl) {
    if (title) title.textContent = titles[name] || 'Panel';
    body.appendChild(tpl);
    overlay.hidden = false;
    overlay.classList.add('is-open');
    const gridChk = document.getElementById('chk-debug-grid');
    if (gridChk && window.GraceGazebo) {
      gridChk.onchange = () => window.GraceGazebo.setDebugGrid(gridChk.checked);
    }
  }
}

function bindScenarioControls() {
  const selScen = document.getElementById('sel-scenario');
  if (selScen) selScen.onchange = () => sendWs({ action: 'set_scenario', scenario: selScen.value });
  const selWeath = document.getElementById('sel-weather');
  if (selWeath) selWeath.onchange = () => sendWs({ action: 'set_weather', weather: selWeath.value });
  document.querySelectorAll('[data-crowd]').forEach((btn) => {
    btn.onclick = () => {
      document.querySelectorAll('[data-crowd]').forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');
      sendWs({ action: 'set_crowd', crowd: btn.getAttribute('data-crowd') });
    };
  });
  bindClick('btn-fault-lidar', () => sendWs({ action: 'inject_fault', fault: { type: 'lidar_failure', severity: 'critical', duration: 15 } }));
  bindClick('btn-fault-cam', () => sendWs({ action: 'inject_fault', fault: { type: 'camera_failure', severity: 'critical', duration: 15 } }));
  bindClick('btn-fault-net', () => sendWs({ action: 'set_server', available: false }));
  bindClick('btn-fault-batt', () => sendWs({ action: 'inject_fault', fault: { type: 'low_battery', severity: 'warning', duration: 20 } }));
  bindClick('btn-fault-clear', () => {
    sendWs({ action: 'clear_fault', target: 'all' });
    sendWs({ action: 'set_server', available: true });
  });
}

function setTxt(id, v) {
  const el = document.getElementById(id);
  if (el) el.textContent = v;
}

function updateHealthBar(data) {
  const cpu = (data.server && data.server.cpu_utilization) || 45;
  const gpu = (data.server && data.server.gpu_utilization) || 55;
  const batt = robotState.battery || 98;
  const lat = (data.network && (data.network.actual_latency_ms || data.network.latency_ms)) || 12;
  const faults = (data.faults && data.faults.active_count) || 0;
  const hours = (batt / 100) * 6.8;
  const h = Math.floor(hours);
  const m = Math.round((hours - h) * 60);
  const clk = (1.6 + (cpu / 100) * 3.1).toFixed(1);
  const memUsed = (4.8 + cpu * 0.03).toFixed(1);
  const memPct = Math.round((memUsed / 16) * 100);
  const temp = Math.round(38 + cpu * 0.12);
  setTxt('h-sys', faults ? `${faults} fault(s) active` : 'All systems nominal');
  const sys = document.getElementById('h-sys');
  if (sys) sys.style.color = faults ? '#dc2626' : '';
  setTxt('h-batt', Math.round(batt) + '%');
  setTxt('h-batt-eta', `SIMULATED · Est. ${h}h ${String(m).padStart(2, '0')}m`);
  setTxt('h-cpu', Math.round(cpu) + '%');
  setTxt('h-cpu-clk', `SIMULATED · ${clk} GHz`);
  setTxt('h-mem', `${memUsed} / 16 GB`);
  setTxt('h-mem-pct', `SIMULATED · ${memPct}%`);
  setTxt('h-temp', temp + '°C');
  setTxt('h-temp-st', temp > 70 ? 'SIMULATED · Hot' : 'SIMULATED · Normal');
  setTxt('h-net', lat + 'ms');
  setTxt('h-safe', faults ? 'DEGRADED' : 'ACTIVE');
  const safe = document.getElementById('h-safe');
  if (safe) safe.style.color = faults ? '#dc2626' : '';
  setTxt('gpu-val', 'SIM ' + (Math.round(gpu * 10) / 10) + '%');
}

function fillLivePanels(data) {
  setTxt('ov-pose', `${robotState.x.toFixed(1)}, ${robotState.y.toFixed(1)} m`);
  setTxt('ov-task', robotState.task || 'IDLE');
  setTxt('ov-batt', Math.round(robotState.battery || 0) + '%');
  if (data.server) {
    setTxt('ov-srv', data.server.status || 'online');
    setTxt('ov-gpu', 'SIM ' + (data.server.gpu_utilization || 0) + '%');
    setTxt('ov-cpu', (data.server.cpu_utilization || 0) + '%');
  }
  if (data.network) setTxt('ov-lat', (data.network.actual_latency_ms || data.network.latency_ms || 12) + 'ms');
  const a = data.analytics || {};
  setTxt('an-ok', a.missions_completed || 0);
  setTxt('an-fail', a.missions_failed || 0);
  setTxt('an-rate', Math.round(a.mission_success_rate || 100) + '%');
  setTxt('an-col', a.collision_count || 0);
  setTxt('an-dist', Math.round(a.total_distance_traveled || 0) + ' m');
  const sns = data.sensors || {};
  setTxt('ov-sns-src', sns.source || 'virtual_space_raycast');
  if (sns.front_range_m != null) setTxt('ov-sns-front', Number(sns.front_range_m).toFixed(2) + ' m');
  if (sns.lidar_min_m != null) setTxt('ov-sns-lmin', Number(sns.lidar_min_m).toFixed(2) + ' m');
  if (sns.imu) setTxt('ov-sns-imu', `${sns.imu.yaw.toFixed(2)} / ${sns.imu.wz.toFixed(2)} / ${sns.imu.ax.toFixed(2)}`);
  setTxt('ov-sns-bump', sns.bumper ? 'HIT' : 'OPEN');
  if (sns.heard_nodes) setTxt('ov-sns-nodes', sns.heard_nodes.join(', '));
  if (sns.ros_topics) setTxt('ov-sns-topics', sns.ros_topics.join(' '));
  const pc = data.perception || {};
  setTxt('ov-ai-person', pc.person || 0);
  setTxt('ov-ai-veh', pc.vehicle || 0);
  setTxt('ov-ai-bldg', pc.building || 0);
  setTxt('ov-ai-obs', pc.obstacle || 0);
  const met = data.ai_metrics || {};
  if (met.inference_ms != null) setTxt('ov-ai-ms', met.inference_ms + ' ms · ' + (met.fps || 0) + ' Hz');
  const intent = data.intent || {};
  setTxt('ov-ai-intent', intent.intent ? `${intent.intent} → ${intent.target || '—'} (${intent.status || ''})` : '—');
  const dets = data.detections || [];
  const person = dets.find((d) => d.label === 'person');
  if (person) setTxt('ov-ai-near', `#${person.track_id} ${person.distance_m}m ${person.pose} ${person.velocity_mps}m/s`);
  else setTxt('ov-ai-near', '—');
  setTxt('ov-ai-speech', robotState.speech || '—');
  const obs = data.obstacles || {};
  if (obs.front != null) {
    setTxt('obs-f', obs.front + ' m');
    setTxt('obs-l', obs.left + ' m');
    setTxt('obs-r', obs.right + ' m');
    setTxt('obs-b', obs.rear + ' m');
    if (document.getElementById('val-prox')) document.getElementById('val-prox').textContent = obs.front + ' m';
  }
  const cg = data.cg || (data.robot && data.robot.cg) || {};
  if (cg.z != null) setTxt('cg-xyz', `${cg.z} m  x${cg.x} y${cg.y}`);
  if (cg.stability) setTxt('cg-st', cg.stability);
  if (cg.tip_margin_m != null) setTxt('cg-tip', cg.tip_margin_m + ' m');
  const js = data.joints || {};
  if (js.neck_yaw_deg != null) setTxt('j-neck', `${js.neck_yaw_deg}° / ${js.neck_pitch_deg}°`);
  if (js.left) setTxt('j-left', `${js.left.shoulder_pitch_deg}° / ${js.left.elbow_deg}°`);
  if (js.right) setTxt('j-right', `${js.right.shoulder_pitch_deg}° / ${js.right.elbow_deg}°`);
  const wh = data.wheels || {};
  ['fl', 'fr', 'rl', 'rr'].forEach((id) => {
    const w = wh[id];
    if (w) setTxt('w-' + id, `${w.fault}  ${w.rpm} rpm`);
  });
  const estop = !!data.estop;
  setTxt('safe-estop', estop ? 'ACTIVE' : 'CLEAR');
  const he = document.getElementById('hud-estop');
  if (he) {
    he.textContent = estop ? 'E-STOP' : 'SAFE';
    he.style.color = estop ? '#dc2626' : '';
  }
  setTxt('safe-chg', data.charging ? 'DOCKED' : 'NO');
  if (data.speed_limit) setTxt('safe-lim', data.speed_limit + ' m/s');
}

function bindClick(id, fn) {
  const el = document.getElementById(id);
  if (el) el.onclick = fn;
}

function initUi() {
  bindClick('btn-quick-lib', () => {
    if (window.GraceGazebo) window.GraceGazebo.lookAtRos(-40, 50, 42);
    dispatchNlMission('Navigate to Block 37 Central Library');
  });
  bindClick('btn-quick-mall', () => {
    if (window.GraceGazebo) window.GraceGazebo.lookAtRos(0, 60, 42);
    dispatchNlMission('Navigate to Uni-Mall entrance');
  });
  bindClick('btn-quick-gate', () => {
    if (window.GraceGazebo) window.GraceGazebo.lookAtRos(0, -95, 48);
    dispatchNlMission('Navigate to Main Gate 1');
  });
  bindClick('btn-reset-view', () => window.GraceGazebo && window.GraceGazebo.resetView());
  bindClick('btn-focus-robot', () => window.GraceGazebo && window.GraceGazebo.focusRobot());
  bindClick('btn-estop', () => {
    sendWs({ action: 'estop' });
    sendWs({ action: 'teleop', v: 0, w: 0 });
    const estopBadge = document.getElementById('hud-estop');
    if (estopBadge) {
      estopBadge.textContent = 'E-STOP TRIGGERED';
      estopBadge.className = 'tag red';
    }
    const safeEstop = document.getElementById('safe-estop');
    if (safeEstop) {
      safeEstop.textContent = 'ACTIVE (HALTED)';
      safeEstop.style.color = '#ef4444';
    }
  });
  bindClick('btn-estop-clear', () => {
    sendWs({ action: 'estop_clear' });
    const estopBadge = document.getElementById('hud-estop');
    if (estopBadge) {
      estopBadge.textContent = 'SAFE';
      estopBadge.className = 'tag green';
    }
    const safeEstop = document.getElementById('safe-estop');
    if (safeEstop) {
      safeEstop.textContent = 'CLEAR';
      safeEstop.style.color = '#22c55e';
    }
  });
  document.querySelectorAll('[data-hud]').forEach((btn) => {
    btn.onclick = () => {
      document.querySelectorAll('[data-hud]').forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');
      const id = btn.getAttribute('data-hud');
      ['sensors', 'robot', 'safety'].forEach((n) => {
        const p = document.getElementById('hud-' + n);
        if (p) p.hidden = n !== id;
      });
    };
  });
  document.querySelectorAll('[data-spd]').forEach((btn) => {
    btn.onclick = () => {
      document.querySelectorAll('[data-spd]').forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');
      sendWs({ action: 'set_speed_limit', limit: Number(btn.getAttribute('data-spd')) });
    };
  });
  bindClick('tool-zoom-in', () => window.GraceGazebo && window.GraceGazebo.zoom(-8));
  bindClick('tool-zoom-out', () => window.GraceGazebo && window.GraceGazebo.zoom(8));
  bindClick('tool-home', () => window.GraceGazebo && window.GraceGazebo.resetView());

  bindClick('btn-dispatch-mission', () => {
    const inp = document.getElementById('nl-mission-input');
    if (inp && inp.value.trim()) {
      dispatchNlMission(inp.value.trim());
      inp.value = '';
    }
  });
  const inp = document.getElementById('nl-mission-input');
  if (inp) {
    inp.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        dispatchNlMission(inp.value.trim());
        inp.value = '';
      }
    });
  }

  document.querySelectorAll('.chip[data-cmd]').forEach((chip) => {
    chip.onclick = () => dispatchNlMission(chip.getAttribute('data-cmd'));
  });

  bindClick('btn-m-pause', () => sendWs({ action: 'mission_control', command: 'pause' }));
  bindClick('btn-m-resume', () => sendWs({ action: 'mission_control', command: 'resume' }));
  bindClick('btn-m-abort', () => sendWs({ action: 'mission_control', command: 'abort' }));

  bindScenarioControls();

  document.querySelectorAll('.nav-item').forEach((btn) => {
    btn.onclick = () => {
      showView(btn.getAttribute('data-view'));
      bindScenarioControls();
    };
  });
  bindClick('overlay-close', () => showView('dashboard'));
  bindClick('btn-header-settings', () => showView('settings'));

  const speed = 0.5;
  const turn = 1.0;
  bindClick('btn-fwd', () => sendTeleop(speed, 0));
  bindClick('btn-bwd', () => sendTeleop(-speed, 0));
  bindClick('btn-left', () => sendTeleop(0, turn));
  bindClick('btn-right', () => sendTeleop(0, -turn));
  bindClick('btn-stop', () => sendTeleop(0, 0));

  const keys = {};
  window.addEventListener('keydown', (e) => {
    if (['INPUT', 'TEXTAREA'].includes(e.target.tagName)) return;
    keys[e.key.toLowerCase()] = true;
    let v = 0, w = 0;
    if (keys['w'] || keys['arrowup']) v += speed;
    if (keys['s'] || keys['arrowdown']) v -= speed;
    if (keys['a'] || keys['arrowleft']) w += turn;
    if (keys['d'] || keys['arrowright']) w -= turn;
    sendTeleop(v, w);
  });
  window.addEventListener('keyup', (e) => {
    delete keys[e.key.toLowerCase()];
    if (Object.keys(keys).length === 0) sendTeleop(0, 0);
  });

  tickHud();
  setInterval(tickHud, 1000);
  paintAllFeeds();
  connectWebSocket();
}

initUi();
