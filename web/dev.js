const devButton = document.querySelector("#devButton");
const devOverlay = document.querySelector("#devOverlay");
const devLoginPanel = document.querySelector("#devLoginPanel");
const devDashboard = document.querySelector("#devDashboard");
const devPassword = document.querySelector("#devPassword");
const devError = document.querySelector("#devError");
const devUnlockButton = document.querySelector("#devUnlockButton");
const devTabs = document.querySelector("#devTabs");
const devPanels = document.querySelector("#devPanels");
const devAccessKey = sessionStorage.getItem("strokevision-access-key") || "";
let devLockTimer = null;

function devElement(tag, className = "", text = "") {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== "") element.textContent = text;
  return element;
}

function devPercent(value) {
  return value == null || !Number.isFinite(Number(value)) ? "—" : `${(Number(value) * 100).toFixed(2)}%`;
}

function openDev() {
  devOverlay.classList.remove("hidden");
  devLoginPanel.classList.remove("hidden");
  devDashboard.classList.add("hidden");
  devError.textContent = "";
  devPassword.value = "";
  devPassword.focus();
}

function lockDev(close = false) {
  clearTimeout(devLockTimer);
  devLockTimer = null;
  devTabs.replaceChildren();
  devPanels.replaceChildren();
  devPassword.value = "";
  devLoginPanel.classList.remove("hidden");
  devDashboard.classList.add("hidden");
  if (close) devOverlay.classList.add("hidden");
  else devPassword.focus();
}

function closeDev() {
  lockDev(true);
  devButton.focus();
}

function metricCards(values) {
  const grid = devElement("div", "dev-metrics");
  values.forEach(([label, value]) => {
    const card = devElement("div", "dev-metric");
    card.append(devElement("small", "", label), devElement("strong", "", value));
    grid.append(card);
  });
  return grid;
}

function matrixTable(metrics) {
  const labels = metrics.labels || [];
  const matrix = metrics.confusion_matrix || [];
  const maximum = Math.max(1, ...matrix.flat().map(Number));
  const wrap = devElement("div", "dev-table-wrap");
  const table = devElement("table", "dev-table matrix");
  const head = devElement("thead");
  const headRow = devElement("tr");
  headRow.append(devElement("th", "", "จริง ↓ / ทำนาย →"));
  labels.forEach(label => headRow.append(devElement("th", "", String(label).replaceAll("_", " "))));
  head.append(headRow);
  const body = devElement("tbody");
  matrix.forEach((row, rowIndex) => {
    const tr = devElement("tr");
    tr.append(devElement("th", "", String(labels[rowIndex] ?? rowIndex).replaceAll("_", " ")));
    row.forEach(value => {
      const level = Math.max(0, Math.min(5, Math.ceil(Number(value) / maximum * 5)));
      tr.append(devElement("td", `heat-${level}`, String(value)));
    });
    body.append(tr);
  });
  table.append(head, body);
  wrap.append(table);
  return wrap;
}

function classTable(metrics, detection = false) {
  const wrap = devElement("div", "dev-table-wrap");
  const table = devElement("table", "dev-table");
  const columns = detection
    ? [["label", "Class"], ["precision", "Precision"], ["recall", "Recall"], ["f1", "F1"], ["ap50", "AP50"], ["map50_95", "mAP50–95"], ["support", "Boxes"]]
    : [["label", "Class"], ["precision", "Precision"], ["recall", "Recall"], ["f1", "F1"], ["support", "Support"]];
  const head = devElement("thead");
  const headRow = devElement("tr");
  columns.forEach(([, title]) => headRow.append(devElement("th", "", title)));
  head.append(headRow);
  const body = devElement("tbody");
  (metrics.per_class || []).forEach(row => {
    const tr = devElement("tr");
    columns.forEach(([key]) => {
      const value = key === "label" || key === "support" ? row[key] : devPercent(row[key]);
      tr.append(devElement("td", "", String(value ?? "—").replaceAll("_", " ")));
    });
    body.append(tr);
  });
  table.append(head, body);
  wrap.append(table);
  return wrap;
}

function evaluationPanel(definition) {
  const panel = devElement("section", "dev-panel");
  panel.id = `dev-panel-${definition.id}`;
  panel.setAttribute("role", "tabpanel");
  const header = devElement("div", "dev-panel-header");
  const heading = devElement("div");
  heading.append(devElement("h3", "", definition.title), devElement("p", "", definition.description));
  header.append(heading, devElement("span", "dev-chip", definition.badge));
  panel.append(header);

  const metrics = definition.metrics;
  if (definition.detection) {
    panel.append(metricCards([
      ["mAP@50", devPercent(metrics.map50)], ["mAP@50–95", devPercent(metrics.map50_95)],
      ["Precision", devPercent(metrics.precision)], ["Recall", devPercent(metrics.recall)],
    ]));
  } else {
    panel.append(metricCards([
      ["Accuracy", devPercent(metrics.accuracy)], ["Macro precision", devPercent(metrics.macro_precision)],
      ["Macro recall", devPercent(metrics.macro_recall)], ["Macro F1", devPercent(metrics.macro_f1)],
    ]));
  }
  panel.append(devElement("h4", "dev-section-title", "Confusion matrix · แถวเป็นค่าจริง คอลัมน์เป็นค่าที่โมเดลทำนาย"));
  panel.append(matrixTable(metrics));
  panel.append(devElement("h4", "dev-section-title", "ผลแยกตาม Class"));
  panel.append(classTable(metrics, definition.detection));
  if (definition.note) panel.append(devElement("p", "dev-note", definition.note));
  return panel;
}

function selectDevTab(id) {
  [...devTabs.children].forEach(tab => {
    const active = tab.dataset.panel === id;
    tab.classList.toggle("active", active);
    tab.setAttribute("aria-selected", String(active));
  });
  [...devPanels.children].forEach(panel => panel.classList.toggle("active", panel.id === `dev-panel-${id}`));
}

function renderDevReports(reports) {
  const definitions = [];
  if (reports.roboflow?.test) {
    const split = reports.roboflow.dataset?.splits || {};
    definitions.push({
      id: "roboflow", title: "Roboflow · Test detection", badge: `${split.test ?? "—"} ภาพทดสอบ`,
      description: "YOLOv8n ทดลองตรวจจับกรอบ no stroke / stroke จากภาพ ไม่ใช่คะแนนความเสี่ยงของผู้รับบริการ",
      metrics: reports.roboflow.test, detection: true,
      note: "background หมายถึงกรอบที่โมเดลพลาดหรือทำนายเกิน ชุดข้อมูลนี้ไม่ใช่การทดสอบทางคลินิก",
    });
  }
  if (reports.rehab?.test?.status) {
    definitions.push({
      id: "rehab-status", title: "Test · ทำท่าครบ / ไม่ครบ", badge: `${reports.rehab.test.status.samples} คลิป`,
      description: "ผลทดสอบโมเดลท่ากายภาพบนชุด Test ที่แยกบุคคลออกจาก Train และ Validation",
      metrics: reports.rehab.test.status,
      note: "รายงานนี้วัดการทำท่าครบหรือไม่ครบ ไม่ใช่ความแม่นยำในการตรวจ stroke",
    });
  }
  if (reports.rehab?.test?.exercise) {
    definitions.push({
      id: "rehab-exercise", title: "Test · ประเภทท่ากายภาพ", badge: `${reports.rehab.test.exercise.samples} คลิป`,
      description: "ผลจำแนกชนิดท่ากายภาพบนชุด Test ของโมเดล transfer learning",
      metrics: reports.rehab.test.exercise,
      note: "Class เหล่านี้เป็นชื่อท่ากายภาพ ไม่ใช่ระดับอาการหรือระดับความเสี่ยงโรค",
    });
  }
  if (reports.volunteers?.metrics) {
    definitions.push({
      id: "volunteers", title: "อาสาสมัคร · ท่าทางใบหน้า", badge: `${reports.volunteers.clips?.length ?? 0} คลิป`,
      description: "ผลแยกคนทดสอบสำหรับหน้านิ่ง ยิ้ม และกะพริบตา จากชุดอาสาสมัครขนาดเล็ก",
      metrics: reports.volunteers.metrics,
      note: "ไม่มี label โรคและไม่มีคู่ก่อน–หลังนวด จึงใช้เป็นการทดสอบ pipeline เท่านั้น",
    });
  }

  devTabs.replaceChildren();
  devPanels.replaceChildren();
  if (!definitions.length) {
    devPanels.append(devElement("p", "dev-empty", "ยังไม่พบรายงานการประเมินในเซิร์ฟเวอร์นี้"));
    return;
  }
  definitions.forEach((definition, index) => {
    const tab = devElement("button", `dev-tab${index === 0 ? " active" : ""}`, definition.title);
    tab.type = "button";
    tab.dataset.panel = definition.id;
    tab.setAttribute("role", "tab");
    tab.setAttribute("aria-selected", String(index === 0));
    tab.addEventListener("click", () => selectDevTab(definition.id));
    devTabs.append(tab);
    const panel = evaluationPanel(definition);
    if (index === 0) panel.classList.add("active");
    devPanels.append(panel);
  });
}

async function unlockDev() {
  const password = devPassword.value;
  if (!password) {
    devError.textContent = "กรุณาใส่รหัสผ่าน";
    return;
  }
  devError.textContent = "";
  devUnlockButton.disabled = true;
  devUnlockButton.textContent = "กำลังตรวจสอบ…";
  try {
    const response = await fetch("/api/dev/reports", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Access-Key": devAccessKey },
      body: JSON.stringify({ password }),
    });
    const reports = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(reports.error || `HTTP ${response.status}`);
    devPassword.value = "";
    renderDevReports(reports);
    devLoginPanel.classList.add("hidden");
    devDashboard.classList.remove("hidden");
    clearTimeout(devLockTimer);
    devLockTimer = setTimeout(() => lockDev(false), 300000);
  } catch (error) {
    devPassword.value = "";
    devError.textContent = error.message;
    devPassword.focus();
  } finally {
    devUnlockButton.disabled = false;
    devUnlockButton.textContent = "เข้าสู่หน้า Dev →";
  }
}

devButton.addEventListener("click", openDev);
document.querySelector("#devLoginClose").addEventListener("click", closeDev);
document.querySelector("#devCloseButton").addEventListener("click", closeDev);
document.querySelector("#devLockButton").addEventListener("click", () => lockDev(false));
devUnlockButton.addEventListener("click", unlockDev);
devPassword.addEventListener("keydown", event => { if (event.key === "Enter") unlockDev(); });
devOverlay.addEventListener("click", event => { if (event.target === devOverlay) closeDev(); });
document.addEventListener("keydown", event => {
  if (event.key === "Escape" && !devOverlay.classList.contains("hidden")) closeDev();
});
