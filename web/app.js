const video = document.querySelector("#camera");
const canvas = document.querySelector("#capture");
const ctx = canvas.getContext("2d", { alpha: false });
const connectButton = document.querySelector("#connectButton");
const startButton = document.querySelector("#startButton");
const stopButton = document.querySelector("#stopButton");
const retryButton = document.querySelector("#retryButton");
const connectionPill = document.querySelector("#connectionPill");
const cameraEmpty = document.querySelector("#cameraEmpty");
const modeButtons = [...document.querySelectorAll(".mode")];
const userId = document.querySelector("#userId");
const visitId = document.querySelector("#visitId");
const confirmed = document.querySelector("#confirmed");
const symptoms = document.querySelector("#symptoms");
const symptomRow = document.querySelector("#symptomRow");
const stageList = document.querySelector("#stageList");
const instruction = document.querySelector("#instruction");
const stageDetail = document.querySelector("#stageDetail");
const stageBadge = document.querySelector("#stageBadge");
const progressBar = document.querySelector("#progressBar");
const timerText = document.querySelector("#timerText");
const resultCard = document.querySelector("#resultCard");
const resultTitle = document.querySelector("#resultTitle");
const resultBody = document.querySelector("#resultBody");
const toast = document.querySelector("#toast");

const state = { mode: "baseline", stream: null, connected: false, running: false, loop: 0 };
const queryKey = new URLSearchParams(location.search).get("key");
if (queryKey) {
  sessionStorage.setItem("strokevision-access-key", queryKey);
  history.replaceState(null, "", location.pathname);
}
const accessKey = sessionStorage.getItem("strokevision-access-key") || "";
let clientId = localStorage.getItem("strokevision-browser-station");
if (!clientId) {
  clientId = crypto.randomUUID();
  localStorage.setItem("strokevision-browser-station", clientId);
}

function notify(message) {
  toast.textContent = message;
  toast.hidden = false;
  clearTimeout(notify.timer);
  notify.timer = setTimeout(() => { toast.hidden = true; }, 5000);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { "X-Access-Key": accessKey, ...(options.headers || {}) },
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
  return data;
}

function setLocked(locked) {
  modeButtons.forEach(button => { button.disabled = locked; });
  userId.disabled = locked;
  visitId.disabled = locked;
  confirmed.disabled = locked;
  symptoms.disabled = locked;
}

function setMode(mode) {
  if (state.running) return;
  state.mode = mode;
  modeButtons.forEach(button => button.classList.toggle("active", button.dataset.mode === mode));
  symptomRow.classList.toggle("hidden", mode !== "recheck");
  startButton.textContent = mode === "baseline" ? "เริ่มบันทึกก่อนนวด" : "เริ่มตรวจหลังนวด";
  stageBadge.textContent = mode === "baseline" ? "ก่อนนวด · เตรียมเริ่มตรวจ" : "หลังนวด · เตรียมเริ่มตรวจ";
}

function drawCover() {
  const vw = video.videoWidth;
  const vh = video.videoHeight;
  if (!vw || !vh) return false;
  const scale = Math.max(canvas.width / vw, canvas.height / vh);
  const sw = canvas.width / scale;
  const sh = canvas.height / scale;
  ctx.drawImage(video, (vw - sw) / 2, (vh - sh) / 2, sw, sh, 0, 0, canvas.width, canvas.height);
  return true;
}

function renderStages(stages = []) {
  stageList.replaceChildren(...stages.map((stage, index) => {
    const item = document.createElement("li");
    item.dataset.index = String(index + 1).padStart(2, "0");
    item.className = stage.status;
    item.textContent = stage.label;
    return item;
  }));
}

function renderSnapshot(data) {
  renderStages(data.stages);
  const active = data.stage_index == null ? null : data.stages[data.stage_index];
  const modeName = (data.visit_mode || state.mode) === "recheck" ? "หลังนวด" : "ก่อนนวด";
  stageBadge.textContent = active ? `${modeName} · ขั้นตอนที่ ${data.stage_index + 1} / ${data.stages.length} · ${active.label}` : `${modeName} · กำลังตรวจ`;
  instruction.textContent = data.instruction || "ทำตามคำแนะนำบนหน้าจอ";
  stageDetail.textContent = active?.instruction || "ระบบกำลังประมวลผลข้อมูลจากกล้อง";
  progressBar.style.width = `${Math.round((data.progress || 0) * 100)}%`;
  timerText.textContent = data.duration ? `${Math.min(data.elapsed, data.duration).toFixed(1)} / ${data.duration.toFixed(0)} วินาที` : "";

  if (data.result) {
    resultTitle.textContent = data.result.title;
    resultBody.textContent = data.result.body;
    const status = data.result.status || "";
    resultCard.className = `card result-card ${status.includes("alert") || status === "delta_alert" ? "risk" : status.includes("incomplete") || status.includes("failed") || status.includes("inconclusive") ? "retry" : "safe"}`;
    retryButton.classList.toggle("hidden", !(status.includes("incomplete") || status.includes("failed") || status.includes("inconclusive")));
  }
  if (data.state === "summary" || data.state === "identity_rejected") {
    state.running = false;
    stopButton.disabled = true;
    startButton.disabled = false;
    setLocked(false);
  }
}

async function frameLoop(token) {
  if (!state.running || token !== state.loop) return;
  try {
    if (!drawCover()) throw new Error("กล้องยังไม่พร้อมส่งภาพ");
    const blob = await new Promise(resolve => canvas.toBlob(resolve, "image/jpeg", .72));
    const data = await api("/api/frame", { method: "POST", headers: { "Content-Type": "image/jpeg" }, body: blob });
    renderSnapshot(data);
  } catch (error) {
    state.running = false;
    setLocked(false);
    stopButton.disabled = true;
    startButton.disabled = false;
    notify(error.message);
    return;
  }
  if (state.running && token === state.loop) setTimeout(() => frameLoop(token), 40);
}

async function connectCamera() {
  if (!accessKey) return notify("ลิงก์นี้ไม่มี access key กรุณาเปิดลิงก์ที่แสดงใน Terminal");
  connectButton.disabled = true;
  try {
    if (state.stream) state.stream.getTracks().forEach(track => track.stop());
    state.stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: "user", width: { ideal: 1280 }, height: { ideal: 720 } }, audio: false,
    });
    video.srcObject = state.stream;
    await video.play();
    await api("/api/connect", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ width: canvas.width, height: canvas.height, client_id: clientId }),
    });
    state.connected = true;
    cameraEmpty.classList.add("hidden");
    connectionPill.textContent = "เชื่อมต่อกล้องแล้ว";
    connectionPill.classList.remove("offline");
    connectButton.textContent = "เชื่อมต่อใหม่";
    startButton.disabled = false;
  } catch (error) {
    state.connected = false;
    notify(error.name === "NotAllowedError" ? "ไม่ได้รับอนุญาตใช้กล้อง กรุณาอนุญาตกล้องในเบราว์เซอร์" : error.message);
  } finally {
    connectButton.disabled = false;
  }
}

async function startScreening() {
  if (!state.connected) return notify("กรุณาเชื่อมต่อกล้องก่อน");
  if (!userId.value.trim() || !visitId.value.trim()) return notify("กรุณากรอกรหัสผู้รับบริการและรหัสครั้งรับบริการ");
  if (!confirmed.checked) return notify("กรุณายืนยันกล้อง จุดตรวจ และท่าทางก่อนเริ่ม");
  startButton.disabled = true;
  try {
    await api("/api/start", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        mode: state.mode, user_id: userId.value.trim(), visit_id: visitId.value.trim(),
        setup_confirmed: true, symptoms_reported: state.mode === "recheck" && symptoms.checked,
      }),
    });
    resultCard.className = "card result-card neutral";
    resultTitle.textContent = "กำลังเก็บข้อมูล";
    resultBody.textContent = "ทำตามคำแนะนำทีละขั้นตอน";
    retryButton.classList.add("hidden");
    state.running = true;
    state.loop += 1;
    setLocked(true);
    stopButton.disabled = false;
    frameLoop(state.loop);
  } catch (error) {
    startButton.disabled = false;
    notify(error.message);
  }
}

async function stopScreening() {
  state.running = false;
  state.loop += 1;
  try { await api("/api/stop", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" }); }
  catch (error) { notify(error.message); }
  setLocked(false);
  startButton.disabled = !state.connected;
  stopButton.disabled = true;
  instruction.textContent = "หยุดการตรวจแล้ว สามารถเริ่มขั้นตอนใหม่ได้";
}

modeButtons.forEach(button => button.addEventListener("click", () => setMode(button.dataset.mode)));
connectButton.addEventListener("click", connectCamera);
startButton.addEventListener("click", startScreening);
stopButton.addEventListener("click", stopScreening);
retryButton.addEventListener("click", startScreening);
window.addEventListener("pagehide", () => {
  state.running = false;
  state.stream?.getTracks().forEach(track => track.stop());
  if (accessKey) fetch("/api/disconnect", {
    method: "POST", keepalive: true, body: "{}",
    headers: { "Content-Type": "application/json", "X-Access-Key": accessKey },
  }).catch(() => {});
});

setMode("baseline");
renderStages([
  "ตรวจสอบกล้อง", "ใบหน้าผ่อนคลาย", "ยิ้ม", "หลับตา", "กะพริบตา", "ยกแขน", "สรุปผล",
].map((label, index) => ({ label, status: index === 0 ? "active" : "waiting" })));
if (!window.isSecureContext) {
  notify("กล้องมือถือจำเป็นต้องเปิดผ่าน HTTPS ส่วนบนคอมสามารถใช้ localhost ได้");
}
