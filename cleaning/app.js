/* Nightly Cleaning Schedule — date-driven, runs forever off a 28-day rotation */

const STORAGE_KEYS = {
  names: "clean_names_v1",
  progress: "clean_progress_v1",
};

let DATA = null;

function fmtDateKey(d) {
  return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0");
}

function monthKey(d) {
  return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0");
}

function daysBetween(a, b) {
  const MS = 24 * 60 * 60 * 1000;
  const da = new Date(a.getFullYear(), a.getMonth(), a.getDate());
  const db = new Date(b.getFullYear(), b.getMonth(), b.getDate());
  return Math.round((db - da) / MS);
}

function mod(n, m) {
  return ((n % m) + m) % m;
}

function getRotationForDate(date) {
  const anchor = new Date(DATA.meta.anchorDate + "T00:00:00");
  const diff = daysBetween(anchor, date);
  const idx = mod(diff, DATA.meta.cycleLengthDays);
  return DATA.nightlyRotation[idx];
}

function getSeasonalForDate(date) {
  const idx = mod(date.getMonth(), DATA.seasonalTasks.length);
  return DATA.seasonalTasks[idx];
}

function getNames() {
  try {
    const raw = localStorage.getItem(STORAGE_KEYS.names);
    if (raw) return JSON.parse(raw);
  } catch (e) {}
  return { a: DATA.meta.personA, b: DATA.meta.personB };
}

function saveNames(a, b) {
  localStorage.setItem(STORAGE_KEYS.names, JSON.stringify({ a, b }));
}

function getProgress() {
  try {
    const raw = localStorage.getItem(STORAGE_KEYS.progress);
    if (raw) return JSON.parse(raw);
  } catch (e) {}
  return {};
}

function setProgress(dateKey, field, value) {
  const p = getProgress();
  if (!p[dateKey]) p[dateKey] = {};
  p[dateKey][field] = value;
  localStorage.setItem(STORAGE_KEYS.progress, JSON.stringify(p));
}

function getSeasonalProgress() {
  try {
    const raw = localStorage.getItem(STORAGE_KEYS.progress);
    const p = raw ? JSON.parse(raw) : {};
    return p.__seasonal || {};
  } catch (e) {
    return {};
  }
}

function setSeasonalDone(mKey, value) {
  const p = getProgress();
  if (!p.__seasonal) p.__seasonal = {};
  p.__seasonal[mKey] = value;
  localStorage.setItem(STORAGE_KEYS.progress, JSON.stringify(p));
}

function toolLabel(toolKey) {
  const label = DATA.meta.tools[toolKey];
  return label ? `🧰 ${label}` : "";
}

/* ---------- Rendering: Today ---------- */

function renderToday() {
  const el = document.getElementById("view-today");
  const now = new Date();
  const dateKey = fmtDateKey(now);
  const mKey = monthKey(now);
  const rotation = getRotationForDate(now);
  const seasonal = getSeasonalForDate(now);
  const names = getNames();
  const progress = getProgress();
  const dayProgress = progress[dateKey] || {};
  const seasonalDone = !!(progress.__seasonal && progress.__seasonal[mKey]);

  const dateStr = now.toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric", year: "numeric" });

  let html = `<div class="date-heading">${dateStr}</div>`;

  html += `<div class="room-banner">
    <div class="label">Tonight's Room Focus</div>
    <div class="room-name">${rotation.room}</div>
  </div>`;

  html += taskCard("A", names.a, rotation.taskA, dayProgress.taskA, dateKey);
  html += taskCard("B", names.b, rotation.taskB, dayProgress.taskB, dateKey);

  html += `<div class="section-title">Every Night</div>`;
  DATA.dailyTasks.forEach((t, i) => {
    const key = "daily" + i;
    html += taskCard(null, null, t, dayProgress[key], dateKey, key);
  });

  html += `<div class="section-title">This Month's Seasonal Project</div>`;
  html += `<div class="card ${seasonalDone ? "done" : ""}">
    <p class="task-title">${seasonal.title}</p>
    ${toolLabel(seasonal.tool) ? `<span class="tool-chip">${toolLabel(seasonal.tool)}</span>` : ""}
    <div class="check-row">
      <input type="checkbox" id="seasonal-check" ${seasonalDone ? "checked" : ""} />
      <label for="seasonal-check">Done for this month</label>
    </div>
  </div>`;

  el.innerHTML = html;

  ["taskA", "taskB", ...DATA.dailyTasks.map((_, i) => "daily" + i)].forEach((field) => {
    const cb = document.getElementById("check-" + field);
    if (cb) {
      cb.addEventListener("change", () => {
        setProgress(dateKey, field, cb.checked);
        renderToday();
      });
    }
  });

  const seasonalCb = document.getElementById("seasonal-check");
  if (seasonalCb) {
    seasonalCb.addEventListener("change", () => {
      setSeasonalDone(mKey, seasonalCb.checked);
      renderToday();
    });
  }
}

function taskCard(personLetter, personName, task, isDone, dateKey, fieldOverride) {
  const field = fieldOverride || "task" + personLetter;
  const chip = toolLabel(task.tool);
  return `<div class="card ${isDone ? "done" : ""}">
    <div class="card-header">
      ${personName ? `<span class="person-name">${personName}</span>` : `<span class="person-name">Daily reminder</span>`}
    </div>
    <p class="task-title">${task.title}</p>
    ${chip ? `<span class="tool-chip">${chip}</span>` : ""}
    <div class="check-row">
      <input type="checkbox" id="check-${field}" ${isDone ? "checked" : ""} />
      <label for="check-${field}">Mark done</label>
    </div>
  </div>`;
}

/* ---------- Rendering: Week ---------- */

function renderWeek() {
  const el = document.getElementById("view-week");
  const now = new Date();
  const startOfWeek = new Date(now);
  startOfWeek.setDate(now.getDate() - now.getDay()); // Sunday start

  const names = getNames();
  let html = `<div class="date-heading">Week of ${startOfWeek.toLocaleDateString(undefined, { month: "long", day: "numeric" })}</div>`;
  html += `<div class="week-strip">`;

  for (let i = 0; i < 7; i++) {
    const d = new Date(startOfWeek);
    d.setDate(startOfWeek.getDate() + i);
    const rotation = getRotationForDate(d);
    const isToday = fmtDateKey(d) === fmtDateKey(now);
    const weekdayStr = d.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });

    html += `<div class="week-day ${isToday ? "today" : ""}">
      <div class="week-day-head"><span>${weekdayStr}</span>${isToday ? "<span>Today</span>" : ""}</div>
      <div class="week-day-room">${rotation.room}</div>
      <div class="week-day-tasks">${names.a}: ${rotation.taskA.title}</div>
      <div class="week-day-tasks">${names.b}: ${rotation.taskB.title}</div>
    </div>`;
  }

  html += `</div>`;
  el.innerHTML = html;
}

/* ---------- Rendering: Month ---------- */

let monthCursor = new Date();
monthCursor.setDate(1);

function renderMonth() {
  const el = document.getElementById("view-month");
  const now = new Date();
  const year = monthCursor.getFullYear();
  const month = monthCursor.getMonth();
  const firstDay = new Date(year, month, 1);
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const startWeekday = firstDay.getDay();

  const monthLabel = firstDay.toLocaleDateString(undefined, { month: "long", year: "numeric" });

  let html = `<div class="month-header">
    <button id="prevMonth">‹</button>
    <div class="date-heading" style="margin:0;">${monthLabel}</div>
    <button id="nextMonth">›</button>
  </div>`;

  html += `<div class="month-grid">`;
  ["S","M","T","W","T","F","S"].forEach(w => html += `<div class="month-weekday">${w}</div>`);

  for (let i = 0; i < startWeekday; i++) {
    html += `<div class="month-cell empty"></div>`;
  }

  for (let day = 1; day <= daysInMonth; day++) {
    const d = new Date(year, month, day);
    const rotation = getRotationForDate(d);
    const isToday = fmtDateKey(d) === fmtDateKey(now);
    html += `<div class="month-cell ${isToday ? "today" : ""}">
      <div class="day-num">${day}</div>
      <div class="room-tag">${rotation.room}</div>
    </div>`;
  }

  html += `</div>`;
  el.innerHTML = html;

  document.getElementById("prevMonth").addEventListener("click", () => {
    monthCursor.setMonth(monthCursor.getMonth() - 1);
    renderMonth();
  });
  document.getElementById("nextMonth").addEventListener("click", () => {
    monthCursor.setMonth(monthCursor.getMonth() + 1);
    renderMonth();
  });
}

/* ---------- Tabs ---------- */

function switchView(view) {
  document.querySelectorAll(".view").forEach(v => v.classList.remove("active"));
  document.getElementById("view-" + view).classList.add("active");
  document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
  document.querySelector(`.tab-btn[data-view="${view}"]`).classList.add("active");

  if (view === "today") renderToday();
  if (view === "week") renderWeek();
  if (view === "month") renderMonth();
}

/* ---------- Names Modal ---------- */

function setupNamesModal() {
  const modal = document.getElementById("namesModal");
  const btn = document.getElementById("namesBtn");
  const cancel = document.getElementById("namesCancel");
  const save = document.getElementById("namesSave");
  const inputA = document.getElementById("input-personA");
  const inputB = document.getElementById("input-personB");

  btn.addEventListener("click", () => {
    const names = getNames();
    inputA.value = names.a;
    inputB.value = names.b;
    modal.classList.remove("hidden");
  });

  cancel.addEventListener("click", () => modal.classList.add("hidden"));

  save.addEventListener("click", () => {
    const a = inputA.value.trim() || DATA.meta.personA;
    const b = inputB.value.trim() || DATA.meta.personB;
    saveNames(a, b);
    modal.classList.add("hidden");
    renderToday();
    renderWeek();
  });
}

/* ---------- Init ---------- */

function init() {
  document.querySelectorAll(".tab-btn").forEach(b => {
    b.addEventListener("click", () => switchView(b.dataset.view));
  });
  setupNamesModal();
  renderToday();
}

fetch("tasks.json")
  .then(r => r.json())
  .then(json => {
    DATA = json;
    init();
  })
  .catch(err => {
    document.getElementById("view-today").innerHTML =
      `<div class="card"><p class="task-title">Could not load tasks.json. Make sure it's in the same folder as index.html.</p></div>`;
    console.error(err);
  });
