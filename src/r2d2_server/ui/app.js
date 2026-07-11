const keyMap = {
  w: { label: "FORWARD", action: "FWD", short: "W", direction: "forward" },
  s: { label: "BACKWARD", action: "BWD", short: "S", direction: "backward" },
  a: { label: "LEFT", action: "LEFT", short: "A", direction: "left" },
  d: { label: "RIGHT", action: "RIGHT", short: "D", direction: "right" },
  q: { label: "ROTATE CW", action: "ROT CW", short: "Q", direction: "rotate_cw" },
  e: { label: "ROTATE CCW", action: "ROT CCW", short: "E", direction: "rotate_ccw" },
};

const keyState = Object.fromEntries(Object.keys(keyMap).map((key) => [key, false]));
const log = [];
let logId = 0;

const vehicle = document.getElementById("vehicle-visual");
const statusBadge = document.getElementById("status-badge");
const statusText = document.getElementById("status-text");
const commandReadout = document.getElementById("command-readout");
const keyList = document.getElementById("key-list");
const logList = document.getElementById("log-list");
const logCount = document.getElementById("log-count");
const bars = document.getElementById("bars");
const tickSvg = document.getElementById("tick-svg");
const dateElement = document.getElementById("date");
const timeElement = document.getElementById("time");
const carCanvas = document.getElementById("car-canvas");
const connectionRow = document.querySelector(".connection-row");
const connectionState = document.getElementById("connection-state");
const touchButtons = document.querySelectorAll(".touch-button[data-key]");
const stopButton = document.querySelector(".touch-button[data-stop]");
let movementSocket;
let motorAvailable = false;
let motorError = null;

function activeKeys() {
  return Object.keys(keyState).filter((key) => keyState[key]);
}

function activeCommand() {
  const commands = activeKeys().map((key) => keyMap[key].action);
  return commands.length ? commands.join(" + ") : "IDLE";
}

function formatTimeWithMs(date) {
  return `${date.toTimeString().slice(0, 8)}.${String(date.getMilliseconds()).padStart(3, "0")}`;
}

function drawTickRing() {
  const center = 260;
  const radiusOuter = 258;
  const radiusInnerMajor = 246;
  const radiusInnerMinor = 252;

  for (let index = 0; index < 36; index += 1) {
    const angle = (index * 10 * Math.PI) / 180;
    const isMajor = index % 9 === 0;
    const radiusInner = isMajor ? radiusInnerMajor : radiusInnerMinor;
    const line = document.createElementNS("http://www.w3.org/2000/svg", "line");

    line.setAttribute("x1", String(center + Math.cos(angle) * radiusOuter));
    line.setAttribute("y1", String(center + Math.sin(angle) * radiusOuter));
    line.setAttribute("x2", String(center + Math.cos(angle) * radiusInner));
    line.setAttribute("y2", String(center + Math.sin(angle) * radiusInner));
    if (isMajor) {
      line.classList.add("major");
    }
    tickSvg.appendChild(line);
  }

  const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
  circle.setAttribute("cx", "260");
  circle.setAttribute("cy", "260");
  circle.setAttribute("r", "258");
  circle.setAttribute("fill", "none");
  tickSvg.appendChild(circle);
}

function chevronPath(direction, index) {
  const center = 260;
  const spacing = 47;
  const lineWidth = 36;
  const lineHeight = 21;

  if (direction === "forward") {
    const y = center - 140 - index * spacing;
    return `${center - lineWidth},${y + lineHeight} ${center},${y} ${center + lineWidth},${y + lineHeight}`;
  }
  if (direction === "backward") {
    const y = center + 140 + index * spacing;
    return `${center - lineWidth},${y - lineHeight} ${center},${y} ${center + lineWidth},${y - lineHeight}`;
  }
  if (direction === "left") {
    const x = center - 140 - index * spacing;
    return `${x + lineHeight},${center - lineWidth} ${x},${center} ${x + lineHeight},${center + lineWidth}`;
  }

  const x = center + 140 + index * spacing;
  return `${x - lineHeight},${center - lineWidth} ${x},${center} ${x - lineHeight},${center + lineWidth}`;
}

function drawChevrons() {
  for (const direction of ["forward", "backward", "left", "right"]) {
    const group = document.querySelector(`.chevrons-${direction}`);
    for (let index = 0; index < 4; index += 1) {
      const polyline = document.createElementNS("http://www.w3.org/2000/svg", "polyline");
      polyline.setAttribute("points", chevronPath(direction, index));
      polyline.style.animationDelay = `${-index * 0.14}s`;
      group.appendChild(polyline);
    }
  }
}

function renderKeyReference() {
  keyList.replaceChildren();
  bars.replaceChildren();

  Object.entries(keyMap).forEach(([key, meta]) => {
    const row = document.createElement("div");
    row.className = "key-row";
    row.dataset.key = key;
    row.innerHTML = `
      <div class="key-left">
        <span class="key-code">${key.toUpperCase()}</span>
        <span class="key-label">${meta.label}</span>
      </div>
      <span class="key-action">${meta.action}</span>
    `;
    keyList.appendChild(row);

    const bar = document.createElement("div");
    bar.className = "bar";
    bar.dataset.key = key;
    bars.appendChild(bar);
  });
}

function renderLog() {
  logCount.textContent = `${log.length} ${log.length === 1 ? "entry" : "entries"}`;

  if (!log.length) {
    logList.innerHTML = '<div class="empty-log">— awaiting input —</div>';
    return;
  }

  logList.replaceChildren();
  log.forEach((entry) => {
    const row = document.createElement("div");
    row.className = "log-entry";
    row.innerHTML = `
      <span class="log-time">${entry.time}</span>
      <div class="log-detail">
        ${entry.keys.map((key) => `<span class="log-key">${key}</span>`).join("")}
        <span class="log-command">${entry.command}</span>
      </div>
    `;
    logList.appendChild(row);
  });
}

function syncClasses() {
  const keys = activeKeys();
  const moving = keyState.w || keyState.s || keyState.a || keyState.d;
  const rotatingCw = keyState.q;
  const rotatingCcw = keyState.e;
  const rotating = rotatingCw || rotatingCcw;
  const anyActive = keys.length > 0;
  const uiActive = anyActive && motorAvailable && !motorError;

  vehicle.className = "vehicle-visual";
  if (moving && uiActive) vehicle.classList.add("active-move");
  if (rotating && uiActive) vehicle.classList.add("active-rotate");
  if (rotatingCw) vehicle.classList.add("rotate-cw");
  if (rotatingCcw) vehicle.classList.add("rotate-ccw");
  keys.forEach((key) => vehicle.classList.add(`active-${key}`));

  statusBadge.classList.toggle("active", uiActive);
  statusBadge.classList.toggle("inactive", !motorAvailable || Boolean(motorError));
  if (!motorAvailable || motorError) {
    statusText.textContent = "INACTIVE";
  } else {
    statusText.textContent = anyActive ? "ACTIVE" : "STANDBY";
  }
  commandReadout.textContent = activeCommand();
  commandReadout.classList.toggle("active", uiActive);

  document.querySelectorAll(".key-row, .bar").forEach((element) => {
    element.classList.toggle("active", keyState[element.dataset.key]);
  });

  touchButtons.forEach((button) => {
    button.classList.toggle("active", keyState[button.dataset.key]);
  });
}

function pushLog() {
  const keys = activeKeys();
  if (!keys.length) {
    return;
  }

  log.unshift({
    id: ++logId,
    time: formatTimeWithMs(new Date()),
    command: activeCommand(),
    keys: keys.map((key) => keyMap[key].short),
  });
  log.splice(40);
  renderLog();
}

function setConnectionState(state) {
  connectionRow.classList.remove("connected", "error");
  if (state === "CONNECTED") {
    connectionRow.classList.add("connected");
  } else if (state === "ERROR" || state === "DISCONNECTED") {
    connectionRow.classList.add("error");
  }
  connectionState.textContent = state;
}

function applyMotorStatus(motor, status) {
  if (motor) {
    motorAvailable = Boolean(motor.available);
    motorError = motor.error || null;
  }

  if (status === "error" || status === "inactive") {
    motorAvailable = false;
    motorError = motorError || status;
  }

  syncClasses();
}

function movementSocketUrl() {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}/ws/movement`;
}

function connectMovementSocket() {
  movementSocket = new WebSocket(movementSocketUrl());

  movementSocket.addEventListener("open", () => {
    setConnectionState("CONNECTED");
  });

  movementSocket.addEventListener("message", (event) => {
    const payload = JSON.parse(event.data);
    applyMotorStatus(payload.motor, payload.status);
  });

  movementSocket.addEventListener("close", () => {
    setConnectionState("DISCONNECTED");
    window.setTimeout(connectMovementSocket, 1200);
  });

  movementSocket.addEventListener("error", () => {
    setConnectionState("ERROR");
  });
}

function sendMovement(direction) {
  if (!movementSocket || movementSocket.readyState !== WebSocket.OPEN) {
    motorError = "websocket unavailable";
    syncClasses();
    return;
  }

  movementSocket.send(JSON.stringify({ direction }));
}

async function fetchMotorStatus() {
  try {
    const response = await fetch("/motor/status");
    applyMotorStatus(await response.json(), null);
  } catch {
    motorAvailable = false;
    motorError = "motor status unavailable";
    syncClasses();
  }
}

function stopIfNoKeysActive() {
  if (!activeKeys().length) {
    sendMovement("stop");
  }
}

function setKey(key, pressed) {
  if (!(key in keyMap) || keyState[key] === pressed) {
    return;
  }

  keyState[key] = pressed;
  syncClasses();
  if (pressed) {
    sendMovement(keyMap[key].direction);
    pushLog();
  } else {
    stopIfNoKeysActive();
  }
}

function stopAllKeys() {
  let changed = false;
  Object.keys(keyState).forEach((key) => {
    if (keyState[key]) {
      keyState[key] = false;
      changed = true;
    }
  });

  if (changed) {
    syncClasses();
  }
  sendMovement("stop");
}

function bindTouchControls() {
  touchButtons.forEach((button) => {
    const key = button.dataset.key;

    button.addEventListener("pointerdown", (event) => {
      event.preventDefault();
      button.setPointerCapture(event.pointerId);
      setKey(key, true);
    });

    button.addEventListener("pointerup", (event) => {
      event.preventDefault();
      button.releasePointerCapture(event.pointerId);
      setKey(key, false);
    });

    button.addEventListener("pointercancel", () => {
      setKey(key, false);
    });

    button.addEventListener("lostpointercapture", () => {
      setKey(key, false);
    });
  });

  stopButton.addEventListener("pointerdown", (event) => {
    event.preventDefault();
    stopAllKeys();
  });
}

function updateClock() {
  const now = new Date();
  dateElement.textContent = now.toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "2-digit",
  });
  timeElement.textContent = now.toTimeString().slice(0, 8);
}

function loadCarImage() {
  const image = new Image();
  image.src = "/ui/assets/r2d2_car.png";
  image.onload = () => {
    const context = carCanvas.getContext("2d");
    carCanvas.width = image.width;
    carCanvas.height = image.height;
    context.drawImage(image, 0, 0);

    const imageData = context.getImageData(0, 0, carCanvas.width, carCanvas.height);
    const data = imageData.data;
    for (let index = 0; index < data.length; index += 4) {
      const brightness = (data[index] + data[index + 1] + data[index + 2]) / 3;
      if (brightness > 240) {
        data[index + 3] = 0;
      } else if (brightness > 200) {
        data[index + 3] = Math.round(((240 - brightness) / 40) * 255);
      }
    }
    context.putImageData(imageData, 0, 0);
  };
}

window.addEventListener("keydown", (event) => {
  const key = event.key.toLowerCase();
  if (key in keyMap) {
    event.preventDefault();
    setKey(key, true);
  }
});

window.addEventListener("keyup", (event) => {
  const key = event.key.toLowerCase();
  if (key in keyMap) {
    event.preventDefault();
    setKey(key, false);
  }
});

drawTickRing();
drawChevrons();
renderKeyReference();
renderLog();
syncClasses();
updateClock();
loadCarImage();
fetchMotorStatus();
connectMovementSocket();
bindTouchControls();
setInterval(updateClock, 1000);
