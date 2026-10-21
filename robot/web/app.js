const $ = (s) => document.querySelector(s),
  buttons = [...document.querySelectorAll(".drive")];
let mapBusy = false,
  mapMessage = "",
  mapMessageUntil = 0,
  knownSavedMap = "",
  savedMapRequest = false,
  speedBusy = false,
  speedInitialized = false;

let armed = false,
  connected = false,
  holding = new Set(),
  busy = false,
  lastFrame = 0,
  generation = 0,
  state = null;
let exploreRequested = false,
  exploreDeadline = 0,
  mappingSelectionInitialized = false;
let navMission = null,
  navView = null,
  navBusy = false,
  navError = "",
  navErrorUntil = 0,
  mapImage = null,
  mapImageMeta = null,
  mapImageRevision = -1,
  mapLoadingRevision = -1,
  mapLayout = null,
  targetOverlay = null;
const keyDirs = {
  w: "forward",
  ArrowUp: "forward",
  s: "back",
  ArrowDown: "back",
  a: "left",
  ArrowLeft: "left",
  d: "right",
  ArrowRight: "right",
};
async function api(path, data, keepalive = false) {
  const options = {
    cache: "no-store",
    signal: keepalive
      ? undefined
      : AbortSignal.timeout(
          path.startsWith("/local/")
            ? 30000
            : ["/maps", "/manual/speed"].includes(path)
              ? 5000
              : 700,
        ),
    keepalive,
  };
  if (data !== undefined)
    Object.assign(options, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Limo-Control": "1" },
      body: JSON.stringify(data),
    });
  const r = await fetch(path, options);
  if (!r.ok) {
    let message = t("Cannot connect to the robot");
    try {
      message = (await r.json()).error || message;
    } catch (_) {}
    throw Error(t(message));
  }
  return r.json();
}
function clearHold() {
  holding.clear();
  buttons.forEach((b) => b.classList.remove("active"));
}
function stopped(message) {
  armed = false;
  clearHold();
  $("#arm").textContent = t("Enable manual drive");
  buttons.forEach((b) => (b.disabled = true));
  $("#mode").textContent = t("Stopped");
  if (message) $("#status").textContent = t(message);
}
function stop() {
  exploreRequested = false;
  navMission = null;
  generation++;
  stopped(t("Stopped. Enable manual drive when ready."));
  api("/stop", {}, true).catch(() => {});
}
function render(s) {
  state = s;
  connected = true;
  $("#demoBanner").hidden = !s.demo;
  renderLidarState(s);
  if (window.renderRecording && (s.demo || s.recording?.saved_directory || !window.localRecordingAvailable))
    window.renderRecording(s.recording, s.demo);
  renderMapping(s);
  renderManualSpeed(s);
  if (navMission && (!s.navigation || s.navigation.mission_id !== navMission))
    navMission = null;
  $("#dot").classList.add("live");
  $("#connection").textContent = t("Robot connected");
  if (s.mode !== "manual" && armed) stopped(s.reason);
  $("#arm").textContent = t(
    armed ? "Manual drive enabled" : "Enable manual drive",
  );
  $("#arm").disabled =
    speedBusy ||
    mapBusy ||
    s.stationary_mode ||
    !!(s.navigation && s.navigation.preparing) ||
    exploreRequested ||
    !!navMission ||
    armed ||
    !s.chassis_online ||
    s.chassis.error_code !== 0 ||
    s.chassis.vehicle_state !== 0 ||
    s.chassis.control_mode !== 1;
  buttons.forEach(
    (b) =>
      (b.disabled =
        !armed ||
        speedBusy ||
        mapBusy ||
        s.stationary_mode),
  );
  $("#battery").textContent = Number(s.chassis.battery_voltage || 0).toFixed(1);
  $("#speed").textContent = Number(s.odometry.linear || 0).toFixed(2);
  $("#turn").textContent = Number(s.odometry.angular || 0).toFixed(2);
  $("#mode").textContent = navMission
    ? s.navigation.exploration && s.navigation.exploration.obstacle_paused
      ? t("Obstacle pause")
      : t("Navigating")
    : armed
      ? t("Manual drive enabled")
      : s.mode !== "stopped"
        ? t("Controlled by another tab")
        : s.chassis.vehicle_state === 1
          ? t("Chassis paused")
          : t("Stopped");
  $("#status").classList.remove("error");
  $("#status").textContent =
    s.navigation && (s.navigation.mission_id || s.navigation.phase === "failed")
      ? t(s.navigation.message)
      : armed || s.reason !== "Stopped"
        ? t(s.reason)
        : s.mode !== "stopped"
          ? t("Another tab is controlling the robot. Stop to end movement.")
          : t("Stopped. Enable manual drive to use the direction controls.");
  $("#sensors").textContent = t("Camera {0} · Chassis {1} · Lidar {2}", [
    s.camera_online ? t("online") : t("offline"),
    s.chassis_online ? t("online") : t("offline"),
    s.lidar_online ? t("Scanning") : t("offline"),
  ]);
}
$("#arm").onclick = async () => {
  const g = ++generation;
  $("#arm").disabled = true;
  try {
    await api("/arm", { mode: "manual" });
    if (g !== generation) {
      api("/stop", {}, true).catch(() => {});
      return;
    }
    armed = true;
    $("#arm").textContent = t("Manual drive enabled");
    clearHold();
  } catch (e) {
    stopped(e.message);
    $("#status").classList.add("error");
  }
};
$("#stop").onclick = stop;
$("#quickStop").onclick = stop;
$("#desktop").href =
  "http://" +
  location.hostname +
  ":16080/vnc.html?autoconnect=true&resize=scale";
$("#desktop").onclick = () => {
  stop();
  fetch("/desktop", {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Limo-Control": "1" },
    body: "{}",
  }).catch(() => {});
};
function press(dir) {
  if (!armed) return;
  holding.add(dir);
  buttons
    .filter((b) => b.dataset.dir === dir)
    .forEach((b) => b.classList.add("active"));
}
function release(dir) {
  holding.delete(dir);
  buttons
    .filter((b) => b.dataset.dir === dir)
    .forEach((b) => b.classList.remove("active"));
  if (armed) api("/drive", { x: 0, z: 0 }).catch(stop);
}
buttons.forEach((b) => {
  b.onpointerdown = (e) => {
    e.preventDefault();
    b.setPointerCapture(e.pointerId);
    press(b.dataset.dir);
    api("/events", {
      type: "pointer",
      direction: b.dataset.dir,
      phase: "down",
    }).catch(() => {});
  };
  b.onpointerup = () => release(b.dataset.dir);
  b.onpointercancel = () => release(b.dataset.dir);
  b.onlostpointercapture = () => release(b.dataset.dir);
});
document.onkeydown = (e) => {
  if (e.code === "Space") {
    e.preventDefault();
    stop();
    return;
  }
  if (e.target.closest("input,select,textarea,[contenteditable=true]")) return;
  if (e.key.toLowerCase() === "n" && !e.repeat) {
    e.preventDefault();
    window.nextRecordingInstance?.();
    return;
  }
  const d = keyDirs[e.key] || keyDirs[e.key.toLowerCase()];
  if (d) {
    e.preventDefault();
    press(d);
    if (!e.repeat)
      api("/events", { type: "keyboard", direction: d, phase: "down" }).catch(
        () => {},
      );
  }
};
document.onkeyup = (e) => {
  if (e.key.toLowerCase() === "n" && !e.repeat) {
    e.preventDefault();
    window.nextRecordingInstance?.();
    return;
  }
  const d = keyDirs[e.key] || keyDirs[e.key.toLowerCase()];
  if (d) {
    e.preventDefault();
    release(d);
  }
};
window.addEventListener("blur", stop);
document.addEventListener("visibilitychange", () => {
  if (document.hidden) stop();
});
window.addEventListener("pagehide", stop);
async function tick() {
  if (busy) return;
  busy = true;
  const g = generation;
  try {
    const x = holding.has("forward")
      ? (state?.manual_speed?.forward ?? 0.1)
      : holding.has("back")
        ? -(state?.manual_speed?.reverse ?? 0.05)
        : 0;
    const turn = state?.manual_speed?.angular ?? 0.3;
    const z =
      (holding.has("left") ? turn : 0) - (holding.has("right") ? turn : 0);
    const response = navMission
      ? await api("/heartbeat", { mission_id: navMission })
      : armed
        ? await api("/drive", { x, z })
        : await api("/status");
    if (g === generation) render(response);
  } catch (e) {
    connected = false;
    stopped(e.message);
    $("#dot").classList.remove("live");
    $("#connection").textContent = t("Disconnected");

    $("#lidarState").textContent = t("Connection lost");
    $("#driveReadiness").textContent = t("Check the robot connection");
    $("#arm").disabled = true;
    $("#status").classList.add("error");
    api("/stop", {}, true).catch(() => {});
  } finally {
    busy = false;
  }
}
const camera = $("#camera");
camera.onload = () => {
  lastFrame = performance.now();
  if (camera.naturalWidth) {
    $(".feed").style.setProperty(
      "--camera-aspect",
      camera.naturalWidth + " / " + camera.naturalHeight,
    );
    $("#cameraResolution").textContent =
      "RGB · " + camera.naturalWidth + " × " + camera.naturalHeight;
  }
  $("#cameraOffline").hidden = true;
  setTimeout(loadFrame, 150);
};
camera.onerror = () => {
  $("#cameraOffline").hidden = false;
  $("#cameraOffline").textContent = t("Camera unavailable. Preview only is affected.");
  setTimeout(loadFrame, 500);
};
function loadFrame() {
  camera.src = "/camera.jpg?t=" + Date.now();
}
loadFrame();
tick();
setInterval(tick, 100);
function drawLidar(scan) {
  const c = $("#lidar"),
    g = c.getContext("2d"),
    w = c.width,
    h = c.height,
    cx = w / 2,
    cy = h / 2,
    scale = 76;
  g.clearRect(0, 0, w, h);
  g.strokeStyle = "#dce9e5";
  g.lineWidth = 1;
  g.font = "18px -apple-system,sans-serif";
  g.textAlign = "left";
  for (let r = 1; r <= 3; r++) {
    g.beginPath();
    g.arc(cx, cy, r * scale, 0, Math.PI * 2);
    g.stroke();
    g.fillStyle = "#9fb8b0";
    g.fillText(r + " m", cx + 6, cy - r * scale - 5);
  }
  g.beginPath();
  g.moveTo(cx, 50);
  g.lineTo(cx, h - 50);
  g.moveTo(45, cy);
  g.lineTo(w - 45, cy);
  g.stroke();
  g.fillStyle = scan.online ? "#168f7d" : "#a4b6b1";
  for (const [x, y] of scan.points || []) {
    if (Math.hypot(x, y) > 3.3) continue;
    g.beginPath();
    g.arc(cx - y * scale, cy - x * scale, 3, 0, Math.PI * 2);
    g.fill();
  }
  g.fillStyle = "#13a38d";
  g.fillRect(cx - 9, cy - 13, 18, 26);
  g.beginPath();
  g.moveTo(cx, cy - 27);
  g.lineTo(cx - 8, cy - 16);
  g.lineTo(cx + 8, cy - 16);
  g.fill();
  g.textAlign = "center";
  g.fillStyle = "#8ca49e";
  g.fillText(t("FORWARD"), cx, 32);
  $("#lidarInfo").textContent = scan.online
    ? t("{0} points · 1 m rings · 3 m range", [scan.points.length])
    : t("No scan data");
}
async function lidarLoop() {
  try {
    drawLidar(await api("/scan"));
  } catch (e) {
    drawLidar({ online: false, points: [] });
  }
  setTimeout(lidarLoop, 250);
}
lidarLoop();
const activePhases = ["starting", "navigating", "returning", "exploring"];
function navFailure(e) {
  navError = e.message || String(e);
  navErrorUntil = performance.now() + 6000;
  $("#navStatus").textContent = navError;
  $("#navStatus").classList.add("error");
}
function mapPoint(x, y) {
  if (!mapLayout) return null;
  const m = mapLayout,
    dx = x - m.meta.origin[0],
    dy = y - m.meta.origin[1],
    a = m.meta.origin[2],
    c = Math.cos(a),
    s = Math.sin(a);
  return [
    m.left + ((c * dx + s * dy) / m.meta.resolution) * m.scale,
    m.top + (m.meta.height - (-s * dx + c * dy) / m.meta.resolution) * m.scale,
  ];
}
function buildTargetOverlay(img, meta) {
  const c = document.createElement("canvas");
  c.width = meta.width;
  c.height = meta.height;
  const ctx = c.getContext("2d");
  ctx.drawImage(img, 0, 0);
  const pixels = ctx.getImageData(0, 0, c.width, c.height),
    out = ctx.createImageData(c.width, c.height),
    radius = 0.23 / meta.resolution + 0.71,
    extent = Math.floor(radius),
    offsets = [];
  for (let dy = -extent; dy <= extent; dy++)
    for (let dx = -extent; dx <= extent; dx++)
      if (Math.hypot(dx, dy) <= radius) offsets.push([dx, dy]);
  for (let y = extent; y < c.height - extent; y++)
    for (let x = extent; x < c.width - extent; x++)
      if (
        offsets.every(
          ([dx, dy]) => pixels.data[((y + dy) * c.width + x + dx) * 4] === 230,
        )
      ) {
        const i = (y * c.width + x) * 4;
        out.data.set([64, 173, 145, 95], i);
      }
  ctx.putImageData(out, 0, 0);
  return c;
}
function paintMap() {
  const canvas = $("#navMap"),
    g = canvas.getContext("2d");
  g.fillStyle = "#f0f5f4";
  g.fillRect(0, 0, canvas.width, canvas.height);
  if (!mapImage || !mapImageMeta) {
    mapLayout = null;
    return;
  }
  const meta = mapImageMeta,
    scale = Math.min(
      (canvas.width - 48) / meta.width,
      (canvas.height - 48) / meta.height,
    ),
    left = (canvas.width - meta.width * scale) / 2,
    top = (canvas.height - meta.height * scale) / 2;
  mapLayout = { meta, scale, left, top };
  g.imageSmoothingEnabled = false;
  g.drawImage(mapImage, left, top, meta.width * scale, meta.height * scale);
  if (targetOverlay)
    g.drawImage(
      targetOverlay,
      left,
      top,
      meta.width * scale,
      meta.height * scale,
    );
  function line(points, color, width) {
    if (!points || points.length < 2) return;
    g.strokeStyle = color;
    g.lineWidth = width;
    g.beginPath();
    points.forEach((p, i) => {
      const q = mapPoint(p[0], p[1]);
      if (i) g.lineTo(...q);
      else g.moveTo(...q);
    });
    g.stroke();
  }
  if (!navView) return;
  line(navView.plan, "#249ee8", 4);
  line(navView.trail, "#12a18b", 3);
  if (navView.home) {
    const p = mapPoint(...navView.home);
    g.fillStyle = "#125c3b";
    g.beginPath();
    g.arc(...p, 11, 0, Math.PI * 2);
    g.fill();
    g.fillStyle = "white";
    g.font = "bold 14px sans-serif";
    g.textAlign = "center";
    g.fillText("H", p[0], p[1] + 5);
  }
  if (navView.target) {
    const p = mapPoint(...navView.target);
    g.strokeStyle = "#ff8c53";
    g.lineWidth = 3;
    g.beginPath();
    g.arc(...p, 10, 0, Math.PI * 2);
    g.moveTo(p[0] - 16, p[1]);
    g.lineTo(p[0] + 16, p[1]);
    g.moveTo(p[0], p[1] - 16);
    g.lineTo(p[0], p[1] + 16);
    g.stroke();
  }
  if (navView.pose) {
    const p = mapPoint(navView.pose[0], navView.pose[1]),
      a = navView.pose[2] - meta.origin[2];
    g.save();
    g.translate(...p);
    g.rotate(-a);
    g.fillStyle = "#13a38d";
    g.strokeStyle = "#1a2918";
    g.lineWidth = 2;
    g.beginPath();
    g.moveTo(17, 0);
    g.lineTo(-10, -10);
    g.lineTo(-6, 0);
    g.lineTo(-10, 10);
    g.closePath();
    g.fill();
    g.stroke();
    g.restore();
  }
}
function renderNav(n) {
  if (!mappingSelectionInitialized && n.mapping_backend) {
    $("#mappingEngine").value = n.mapping_backend;
    mappingSelectionInitialized = true;
  }
  if (exploreRequested && performance.now() > exploreDeadline) {
    exploreRequested = false;
    navFailure(Error(t("Mapping startup timed out. Please retry.")));
  }
  if (exploreRequested && n.ready && !navBusy) {
    exploreRequested = false;
    startMission("/navigation/explore", {});
  }
  navView = n;
  const active = activePhases.includes(n.phase),
    hardwareReady =
      state &&
      !state.stationary_mode &&
      state.chassis_online &&
      state.chassis.vehicle_state === 0 &&
      state.chassis.control_mode === 1 &&
      !state.chassis.error_code;
  const lidarReady = state?.lidar_online;
  $("#applyMapping").disabled =
    !lidarReady ||
    navBusy ||
    n.preparing ||
    active ||
    armed ||
    exploreRequested;
  $("#mappingEngine").disabled =
    $("#applyMapping").disabled ||
    !!state?.mapping?.active ||
    !!state?.mapping?.waiting;
  $("#mappingEngineStatus").textContent =
    t("Current engine: ") +
    (n.mapping_backend === "cartographer" ? "Cartographer" : "SLAM Toolbox");
  $("#prepareNav").disabled =
    !lidarReady || navBusy || n.preparing || active || n.ready;
  $("#prepareNav").textContent = n.ready
    ? t("Navigation ready")
    : n.preparing
      ? t("Starting…")
      : t("Enable navigation");
  $("#exploreNav").disabled =
    !lidarReady ||
    navBusy ||
    n.preparing ||
    active ||
    armed ||
    exploreRequested ||
    !hardwareReady ||
    !state.lidar_online;
  $("#exploreNav").textContent =
    n.exploration && n.exploration.active
      ? t("Exploration running…")
      : exploreRequested
        ? t("Starting mapping…")
        : t("Explore automatically");
  const tour = n.exploration;
  $("#exploreInfo").textContent = tour
    ? tour.active
      ? t("{0} targets · {1} retries · {2} m · {3} s", [
          tour.reached,
          tour.retries || 0,
          tour.distance.toFixed(2),
          Math.round(tour.elapsed),
        ])
      : t(tour.save_message) || ""
    : "";
  $("#returnHome").disabled =
    !lidarReady ||
    navBusy ||
    active ||
    armed ||
    !n.ready ||
    !n.return_available ||
    !hardwareReady;
  $("#returnMode").disabled = active;
  const names = {
    idle: t("Awaiting a goal"),
    exploring: t("Exploring"),
    complete: t("Exploration complete"),
    starting: t("Planning"),
    navigating: t("Driving to goal"),
    returning: t("Following route home"),
    arrived: t("Arrived"),
    home: t("Returned home"),
    cancelled: t("Stopped"),
    failed: t("Route incomplete"),
  };
  $("#navPhase").textContent = n.ready
    ? n.exploration && n.exploration.active
      ? t("Exploration · ") +
        (n.exploration.obstacle_paused
          ? t("Obstacle pause")
          : names[n.phase] || n.phase)
      : names[n.phase] || n.phase
    : n.map
      ? t("Navigation not started")
      : t("Waiting for map and localization");
  if (performance.now() > navErrorUntil) {
    $("#navStatus").textContent = !hardwareReady
      ? t("Chassis not ready. Check the pause button and connection.")
      : t(n.message);
    $("#navStatus").classList.remove("error");
  }
  $("#returnInfo").textContent = n.reverse_available
    ? t("Rear scan available. Slow reverse return is supported.")
    : t(
        "No valid rear scan. Auto return turns and drives forward; reverse-only return is unavailable.",
      );
  $("#targetInfo").textContent = n.target
    ? t("Goal ({0}, {1}) m", [n.target[0].toFixed(2), n.target[1].toFixed(2)]) +
      (n.distance_remaining !== null
        ? t(" · {0} m remaining", [n.distance_remaining.toFixed(2)])
        : "")
    : "";
  $("#mapEmpty").hidden = !!n.map;
  if (
    n.map &&
    n.revision !== mapImageRevision &&
    n.revision !== mapLoadingRevision
  ) {
    const rev = n.revision,
      meta = n.map,
      img = new Image();
    mapLoadingRevision = rev;
    img.onload = () => {
      if (rev < mapImageRevision) return;
      mapImage = img;
      mapImageMeta = meta;
      mapImageRevision = rev;
      targetOverlay = $("#enableMapGoals").checked
        ? buildTargetOverlay(img, meta)
        : null;
      paintMap();
    };
    img.onerror = () => {
      mapLoadingRevision = -1;
    };
    img.src = "/map.png?v=" + rev;
  }
  paintMap();
}
async function startMission(path, data) {
  if (navBusy) return;
  navBusy = true;
  const g = ++generation;
  clearHold();
  try {
    const s = await api(path, data);
    if (g !== generation) {
      api("/stop", {}, true).catch(() => {});
      return;
    }
    navMission = s.navigation.mission_id;
    armed = false;
    render(s);
  } catch (e) {
    navFailure(e);
  } finally {
    navBusy = false;
  }
}
$("#applyMapping").onclick = async () => {
  if (navBusy) return;
  navBusy = true;
  exploreRequested = false;
  try {
    await api("/navigation/prepare", { backend: $("#mappingEngine").value });
    navErrorUntil = 0;
  } catch (e) {
    navFailure(e);
  } finally {
    navBusy = false;
  }
};
$("#prepareNav").onclick = async () => {
  if (navBusy) return;
  navBusy = true;
  try {
    await api("/navigation/prepare", {});
    navErrorUntil = 0;
  } catch (e) {
    navFailure(e);
  } finally {
    navBusy = false;
  }
};
$("#exploreNav").onclick = async () => {
  if (navBusy || exploreRequested) return;
  if (navView && navView.ready) {
    startMission("/navigation/explore", {});
    return;
  }
  exploreRequested = true;
  exploreDeadline = performance.now() + 45000;
  navBusy = true;
  const g = ++generation;
  try {
    await api("/navigation/prepare", {});
    if (g !== generation) exploreRequested = false;
    navErrorUntil = 0;
  } catch (e) {
    exploreRequested = false;
    navFailure(e);
  } finally {
    navBusy = false;
  }
};
$("#returnHome").onclick = () =>
  startMission("/navigation/return", { mode: $("#returnMode").value });
$("#navStop").onclick = stop;
$("#navMap").onclick = (e) => {
  if (!$("#enableMapGoals").checked) return;
  if (!state?.lidar_online) {
    navFailure(Error(t("Fresh lidar scans are required")));
    return;
  }
  if (!navView || !navView.ready || !mapLayout) {
    navFailure(
      Error(t("Start mapping and navigation, then wait for the map.")),
    );
    return;
  }
  if (armed || navMission || activePhases.includes(navView.phase)) {
    navFailure(Error(t("Stop the current task before choosing another goal.")));
    return;
  }
  const canvas = $("#navMap"),
    r = canvas.getBoundingClientRect(),
    px = ((e.clientX - r.left) * canvas.width) / r.width,
    py = ((e.clientY - r.top) * canvas.height) / r.height,
    m = mapLayout;
  const lx = ((px - m.left) / m.scale) * m.meta.resolution,
    ly = (m.meta.height - (py - m.top) / m.scale) * m.meta.resolution;
  if (
    lx < 0 ||
    ly < 0 ||
    lx > m.meta.width * m.meta.resolution ||
    ly > m.meta.height * m.meta.resolution
  ) {
    navFailure(Error(t("Choose free space inside the map.")));
    return;
  }
  const a = m.meta.origin[2],
    x = m.meta.origin[0] + Math.cos(a) * lx - Math.sin(a) * ly,
    y = m.meta.origin[1] + Math.sin(a) * lx + Math.cos(a) * ly;
  startMission("/navigation/goal", { x, y });
};
async function navigationLoop() {
  try {
    renderNav(await api("/navigation"));
  } catch (e) {
    $("#navPhase").textContent = t("Connection lost");
    $("#prepareNav").disabled = true;
    $("#exploreNav").disabled = true;
    $("#returnHome").disabled = true;
  }
  setTimeout(navigationLoop, 750);
}
navigationLoop();

function renderLidarState(s) {
  const online = !!s.lidar_online;
  $("#lidarState").textContent = t(online ? "Scanning" : "offline");
  $("#lidarDetail").textContent = t(
    online ? "Lidar is scanning" : "No scan data",
  );
  $("#driveReadiness").textContent = s.stationary_mode
    ? t("Stationary maintenance mode; driving is locked")
    : !s.chassis_online ? t("Chassis offline. Check the connection.")
    : s.chassis.vehicle_state !== 0 ? t("Chassis paused. Release the robot's physical pause button.")
    : t("Chassis ready. Camera and recording are optional.");
}

function renderManualSpeed(s) {
  const limits = s.manual_speed;
  if (!limits) return;
  if (!speedInitialized) {
    for (const key of ["forward", "reverse", "angular"]) {
      $("#" + key + "Speed").value = Number(limits[key]).toFixed(2);
      $("#" + key + "SpeedRange").value = limits[key];
    }
    speedInitialized = true;
  }
  $("#speedApplied").textContent = t(
    "Applied: forward {0} / reverse {1} m/s · turn {2} rad/s (about {3}°/s)",
    [
      limits.forward.toFixed(2),
      limits.reverse.toFixed(2),
      limits.angular.toFixed(2),
      ((limits.angular * 180) / Math.PI).toFixed(0),
    ],
  );
  $("#driveSpeedHint").textContent = t(
    "Forward {0} m/s · Reverse {1} m/s · Turn {2} rad/s",
    [
      limits.forward.toFixed(2),
      limits.reverse.toFixed(2),
      limits.angular.toFixed(2),
    ],
  );
  $("#saveManualSpeed").disabled = speedBusy || !connected;
}
for (const key of ["forward", "reverse", "angular"]) {
  $("#" + key + "SpeedRange").oninput = (e) => {
    $("#" + key + "Speed").value = Number(e.target.value).toFixed(2);
  };
  $("#" + key + "Speed").oninput = (e) => {
    if (e.target.validity.valid)
      $("#" + key + "SpeedRange").value = e.target.value;
  };
}
$("#manualSpeedForm").onsubmit = async (e) => {
  e.preventDefault();
  if (speedBusy) return;
  const forward = Number($("#forwardSpeed").value),
    reverse = Number($("#reverseSpeed").value),
    angular = Number($("#angularSpeed").value);
  if (
    ![forward, reverse].every((v) => Number.isFinite(v) && v >= 0 && v <= 1)
  ) {
    $("#speedFeedback").textContent = t(
      "Enter a speed between 0 and 1.00 m/s.",
    );
    return;
  }
  if (!Number.isFinite(angular) || angular < 0 || angular > 2) {
    $("#speedFeedback").textContent = t(
      "Enter a turning speed between 0 and 2.00 rad/s.",
    );
    return;
  }
  speedBusy = true;
  generation++;
  navMission = null;
  exploreRequested = false;
  stopped(t("Stopped. Saving speed limits."));
  $("#saveManualSpeed").disabled = true;
  try {
    const s = await api("/manual/speed", { forward, reverse, angular });
    speedInitialized = false;
    render(s);
    $("#speedFeedback").textContent = t(
      "Saved. Re-enable driving to use these limits.",
    );
  } catch (e) {
    $("#speedFeedback").textContent = e.message;
  } finally {
    speedBusy = false;
    tick();
  }
};
function renderMapping(s) {
  const m = s.mapping || {},
    working = mapBusy || m.busy || s.navigation?.preparing;
  $("#mappingPhase").textContent = m.busy
    ? { start: t("Starting"), save: t("Saving"), stop: t("Finishing") }[
        m.operation
      ] || t("Working")
    : m.waiting
      ? t("Waiting for map")
      : m.active
        ? t("Mapping")
        : m.error
          ? t("Retry needed")
          : t("Not mapping");
  $("#mappingPhase").className = "device-tag" + (m.error ? " error" : "");
  $("#mappingStatus").textContent =
    performance.now() < mapMessageUntil
      ? t(mapMessage)
      : t(m.message) ||
        t("Start mapping, then drive manually to expand the map.");
  $("#mappingStatus").classList.toggle("error", !!m.error);
  $("#mapHealth").textContent = m.active
    ? t("Known free area {0} m² · Localization {1} · Route accuracy needs a driving test", [
        Number(m.statistics?.free_area_m2 || 0).toFixed(2),
        t(m.localization_available ? "online" : "offline"),
      ]) : "";
  $("#startMapping").disabled =
    working || m.active || m.waiting || !s.lidar_online || !s.chassis_online;
  $("#saveMapping").disabled = working || !m.active;
  $("#stopMapping").disabled = working || !(m.active || m.waiting || m.error);
  $("#loadSavedMap").disabled = working || m.active || m.waiting || !$("#savedMaps").value;
  $("#mappingEngine").disabled = working || m.active || m.waiting;
  if (m.map) {
    const g = m.map;
    $("#mappingDimensions").textContent = t(
      "{0} × {1} m · {2} cm/cell · Arrow: robot",
      [
        (g.width * g.resolution).toFixed(2),
        (g.height * g.resolution).toFixed(2),
        (g.resolution * 100).toFixed(0),
      ],
    );
  }
  if (m.last_saved && m.last_saved !== knownSavedMap) {
    knownSavedMap = m.last_saved;
    $("#mapSaveResult").textContent = t("Saved: ") + m.last_saved;
    $("#mapName").value = "";
    refreshSavedMaps(m.last_saved);
  }
}
async function mapAction(action) {
  if (mapBusy) return;
  mapBusy = true;
  generation++;
  armed = false;
  navMission = null;
  exploreRequested = false;
  clearHold();
  stopped(t("Mapping operations stop the robot first."));
  const data =
    action === "start"
      ? { backend: $("#mappingEngine").value }
      : action === "save"
        ? { name: $("#mapName").value.trim() || null }
        : action === "load"
          ? {name: $("#savedMaps").value, pose: [$("#localizeX").value, $("#localizeY").value, $("#localizeYaw").value].map((v, i) => v.trim() === "" ? null : Number(v) * (i === 2 ? Math.PI / 180 : 1))}
          : {};
  try {
    const s = await api("/mapping/" + action, data);
    mapMessage = t("Operation requested. Waiting for completion…");
    mapMessageUntil = performance.now() + 1800;
    render(s);
  } catch (e) {
    mapMessage = e.message;
    mapMessageUntil = performance.now() + 7000;
    $("#mappingStatus").textContent = e.message;
  } finally {
    mapBusy = false;
    tick();
  }
}
$("#startMapping").onclick = () => mapAction("start");
$("#saveMapping").onclick = () => mapAction("save");
$("#stopMapping").onclick = () => mapAction("stop");
$("#loadSavedMap").onclick = () => mapAction("load");
function updateMapDownload() {
  const name = $("#savedMaps").value;
  $("#downloadMap").hidden = !name;
  if (name)
    $("#downloadMap").href = "/maps/download?name=" + encodeURIComponent(name);
}
$("#savedMaps").onchange = updateMapDownload;
async function refreshSavedMaps(preferred) {
  if (savedMapRequest) return;
  savedMapRequest = true;
  try {
    const result = await api("/maps"),
      select = $("#savedMaps"),
      chosen = preferred || select.value;
    select.replaceChildren();
    if (!knownSavedMap) $("#mapSaveResult").textContent = "";
    if (!result.maps.length) {
      const option = document.createElement("option");
      option.value = "";
      option.textContent = t("No saved maps");
      select.append(option);
    }
    for (const item of result.maps) {
      const option = document.createElement("option");
      option.value = item.name;
      option.textContent = item.name;
      select.append(option);
    }
    if (result.maps.some((item) => item.name === chosen)) select.value = chosen;
    updateMapDownload();
  } catch (e) {
    $("#mapSaveResult").textContent = t(
      "Saved maps are temporarily unavailable.",
    );
  } finally {
    savedMapRequest = false;
  }
}
refreshSavedMaps();
setInterval(() => refreshSavedMaps(), 10000);

$("#enableMapGoals").onchange = () => {
  targetOverlay =
    $("#enableMapGoals").checked && mapImage && mapImageMeta
      ? buildTargetOverlay(mapImage, mapImageMeta)
      : null;
  paintMap();
};
window.addEventListener("languagechange", () => {
  if (state) render(state);
  if (navView) renderNav(navView);
  $("#mapSaveResult").textContent = knownSavedMap
    ? t("Saved: ") + knownSavedMap
    : t($("#mapSaveResult").textContent);
  $("#speedFeedback").textContent = "";
  refreshSavedMaps();
});
const sections = [...document.querySelectorAll("main [id]")].filter((el) =>
  ["live", "mapping", "devices"].includes(el.id),
);
const sectionObserver = new IntersectionObserver(
  (entries) => {
    for (const entry of entries) {
      if (entry.isIntersecting) {
        document
          .querySelectorAll(".nav-link")
          .forEach((link) =>
            link.classList.toggle(
              "active",
              link.getAttribute("href") === "#" + entry.target.id,
            ),
          );
      }
    }
  },
  { rootMargin: "-90px 0px -55% 0px" },
);
sections.forEach((section) => sectionObserver.observe(section));
