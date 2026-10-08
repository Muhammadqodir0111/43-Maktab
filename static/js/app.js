"use strict";

const API = {
  me: "/api/me/",
  summary: "/api/summary/",
  subjects: "/api/subjects/",
  teachers: "/api/teachers/",
  parents: "/api/parents/",
  classes: "/api/classes/",
  students: "/api/students/",
  schedule: "/api/schedule/",
  grades: "/api/grades/",
  homework: "/api/homework/",
  attendance: "/api/attendance/",
  announcements: "/api/announcements/",
  lessons: "/api/lessons/",
  lessonWorkspace: "/api/lessons/workspace/",
};

const state = {
  role: "guest",
  isAdmin: false,
  isTeacher: false,
  studentId: null,
  teacherId: null,
  parentId: null,
  children: [],
  page: null,
  cache: {},
  refsReady: false,
  classes: [],
  subjects: [],
  teachers: [],
  parents: [],
  students: [],
  journal: null,
  hwSubs: null,
  lesson: null,
  lessonDay: null,
  quarter: null,
};

const WEEKDAYS = { 1: "Dushanba", 2: "Seshanba", 3: "Chorshanba", 4: "Payshanba", 5: "Juma", 6: "Shanba" };
const MONTHS = ["Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun", "Iyul", "Avgust", "Sentabr", "Oktabr", "Noyabr", "Dekabr"];

/* ------------------------------ yordamchilar ------------------------------ */
function todayStr() {
  const d = new Date();
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
}
function fmtDate(s) {
  if (!s) return "—";
  const d = new Date(s + "T00:00:00");
  if (isNaN(d)) return s;
  return d.getDate() + "-" + MONTHS[d.getMonth()];
}
function fmtDateFull(s) {
  if (!s) return "—";
  const d = new Date(s + "T00:00:00");
  if (isNaN(d)) return s;
  return d.getDate() + " " + MONTHS[d.getMonth()] + " " + d.getFullYear();
}
function fmtTime(t) { return t ? String(t).slice(0, 5) : ""; }
function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}
function initials(name) {
  return (name || "?").trim().split(/\s+/).slice(0, 2).map((w) => w[0]).join("").toUpperCase();
}
const AVATAR_COLORS = ["#4f46e5", "#0891b2", "#0d9488", "#7c3aed", "#c026d3", "#ea580c", "#2563eb", "#16a34a"];
function avatarColor(name) {
  let h = 0;
  for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) >>> 0;
  return AVATAR_COLORS[h % AVATAR_COLORS.length];
}
function $(s) { return document.querySelector(s); }
function $$(s) { return Array.from(document.querySelectorAll(s)); }
function getCookie(name) {
  const m = document.cookie.match("(^|;)\\s*" + name + "\\s*=\\s*([^;]+)");
  return m ? decodeURIComponent(m.pop()) : "";
}
async function api(url, opts) {
  opts = opts || {};
  const headers = Object.assign({ "Content-Type": "application/json" }, opts.headers || {});
  const method = (opts.method || "GET").toUpperCase();
  if (method !== "GET") headers["X-CSRFToken"] = getCookie("csrftoken");
  const res = await fetch(url, Object.assign({}, opts, { headers }));
  if (res.status === 401) { window.location.href = "/login/"; throw new Error("Kirish talab qilinadi"); }
  if (!res.ok) {
    let msg = "Xatolik (" + res.status + ")";
    try {
      const j = await res.json();
      if (j.detail) msg = j.detail;
      else if (typeof j === "object") msg = Object.values(j).flat().join(", ");
    } catch (e) { /* ignore */ }
    throw new Error(msg);
  }
  return res.status === 204 ? null : res.json();
}
function toast(msg, type) {
  type = type || "ok";
  const t = $("#toast");
  t.textContent = msg;
  t.className = "toast show " + type;
  clearTimeout(toast._timer);
  toast._timer = setTimeout(() => t.classList.remove("show"), 2600);
}

/* -------------------------------- modallar -------------------------------- */
function openModal(id) { $("#" + id).classList.add("open"); }
function closeModal(id) { $("#" + id).classList.remove("open"); }
$$(".modal-bg").forEach((bg) => {
  bg.addEventListener("click", (e) => { if (e.target === bg) closeModal(bg.id); });
  bg.querySelectorAll("[data-close]").forEach((b) => b.addEventListener("click", () => closeModal(bg.id)));
});
let confirmAction = null;
$("#confirmOk").addEventListener("click", () => {
  closeModal("confirmModal");
  if (confirmAction) confirmAction();
  confirmAction = null;
});
function askConfirm(text, action) { $("#confirmText").textContent = text; confirmAction = action; openModal("confirmModal"); }
function openInfo(title, html) { $("#infoModalTitle").textContent = title; $("#infoModalBody").innerHTML = html; openModal("infoModal"); }

function fieldHTML(f, value) {
  const v = value === undefined || value === null ? (f.value !== undefined ? f.value : "") : value;
  if (f.type === "checkbox") {
    return `<label class="switch-row" style="margin-bottom:13px"><input type="checkbox" name="${f.name}" ${v ? "checked" : ""}> <span>${esc(f.label)}</span></label>`;
  }
  let inner = "";
  if (f.type === "textarea") {
    inner = `<textarea name="${f.name}" rows="${f.rows || 3}" ${f.required ? "required" : ""} placeholder="${esc(f.placeholder || "")}">${esc(v)}</textarea>`;
  } else if (f.type === "select") {
    inner = `<select name="${f.name}" ${f.required ? "required" : ""}>` +
      (f.empty !== undefined ? `<option value="">${esc(f.empty)}</option>` : "") +
      (f.options || []).map((o) => `<option value="${esc(o.value)}"${String(o.value) === String(v) ? " selected" : ""}>${esc(o.label)}</option>`).join("") +
      `</select>`;
  } else if (f.type === "multiselect") {
    const arr = (value || []).map(String);
    inner = `<select name="${f.name}" class="multiselect" multiple>` +
      (f.options || []).map((o) => `<option value="${esc(o.value)}"${arr.includes(String(o.value)) ? " selected" : ""}>${esc(o.label)}</option>`).join("") +
      `</select>` + (f.help ? `<div class="help" style="font-size:12px;color:var(--muted);margin-top:5px">${esc(f.help)}</div>` : "");
  } else {
    inner = `<input type="${f.type || "text"}" name="${f.name}" value="${esc(v)}" ${f.required ? "required" : ""} placeholder="${esc(f.placeholder || "")}" ${f.autocomplete ? `autocomplete="${f.autocomplete}"` : ""}>`;
  }
  return `<div class="field"><label>${esc(f.label)}${f.required ? " *" : ""}</label>${inner}</div>`;
}

function openForm(cfg) {
  const fields = cfg.fields || [];
  $("#formModalTitle").textContent = cfg.title;
  $("#formModalBox").classList.toggle("modal-lg", !!cfg.wide);
  $("#formModalSubmit").textContent = cfg.submitLabel || "Saqlash";
  $("#formModalBody").innerHTML =
    fields.map((f) => fieldHTML(f, (cfg.values || {})[f.name])).join("") +
    (cfg.onDelete ? `<div style="margin-top:6px"><button type="button" class="btn btn-danger" id="formDeleteBtn">🗑 ${esc(cfg.deleteLabel || "O'chirish")}</button></div>` : "");
  if (cfg.onDelete) $("#formDeleteBtn").onclick = cfg.onDelete;
  const form = $("#formModalForm");
  form.onsubmit = async (e) => {
    e.preventDefault();
    const payload = {};
    fields.forEach((f) => {
      const el = form.elements[f.name];
      if (!el) return;
      if (f.type === "checkbox") payload[f.name] = el.checked;
      else if (f.type === "multiselect") payload[f.name] = Array.from(el.selectedOptions).map((o) => o.value);
      else if (f.type === "number") payload[f.name] = el.value === "" ? null : Number(el.value);
      else if (f.type === "date" || f.type === "time") payload[f.name] = el.value || null;
      else if (f.type === "select" && !f.required && el.value === "") payload[f.name] = null;
      else payload[f.name] = el.value;
    });
    try { await cfg.onSubmit(payload); closeModal("formModal"); }
    catch (err) { toast(err.message, "err"); }
  };
  openModal("formModal");
}

/* ------------------------------ umumiy CRUD ------------------------------- */
const classOptions = () => state.classes.map((c) => ({ value: c.id, label: `${c.name} (${c.year})` }));
const subjectOptions = () => state.subjects.map((s) => ({ value: s.id, label: s.name }));
const teacherOptions = () => state.teachers.map((t) => ({ value: t.id, label: t.full_name }));
const parentOptions = () => state.parents.map((p) => ({ value: p.id, label: p.full_name }));

function activeBadge(v) {
  return v ? '<span class="badge green"><span class="dot"></span>Faol</span>'
           : '<span class="badge gray"><span class="dot"></span>Nofaol</span>';
}
function loginBadge(v) {
  return v ? '<span class="badge indigo">🔑 Mavjud</span>' : '<span class="badge gray">Yo\'q</span>';
}

const CRUDS = {
  classes: {
    endpoint: API.classes, view: "classesView", singular: "Sinf",
    columns: [
      { label: "Sinf", render: (c) => `<b>${esc(c.name)}</b>` },
      { label: "O'quv yili", key: "year" },
      { label: "Sinf rahbari", render: (c) => esc(c.curator_name || "—") },
      { label: "O'quvchilar", render: (c) => `<span class="badge indigo">${c.students_count}</span>` },
      { label: "Holat", render: (c) => activeBadge(c.is_active) },
    ],
    fields: () => [
      { name: "name", label: "Sinf nomi", required: true, placeholder: "5-A" },
      { name: "year", label: "O'quv yili", placeholder: "2025-2026" },
      { name: "curator", label: "Sinf rahbari", type: "select", empty: "— yo'q —", options: teacherOptions() },
      { name: "is_active", label: "Faol", type: "checkbox", value: true },
    ],
    values: (c) => ({ name: c.name, year: c.year, curator: c.curator, is_active: c.is_active }),
  },
  subjects: {
    endpoint: API.subjects, view: "subjectsView", singular: "Fan",
    columns: [
      { label: "Fan", render: (s) => `<b>${esc(s.name)}</b>` },
      { label: "Kod", render: (s) => esc(s.code || "—") },
      { label: "Holat", render: (s) => activeBadge(s.is_active) },
    ],
    fields: () => [
      { name: "name", label: "Fan nomi", required: true, placeholder: "Matematika" },
      { name: "code", label: "Kod", placeholder: "MAT" },
      { name: "is_active", label: "Faol", type: "checkbox", value: true },
    ],
    values: (s) => ({ name: s.name, code: s.code, is_active: s.is_active }),
  },
  teachers: {
    endpoint: API.teachers, view: "teachersView", singular: "O'qituvchi",
    columns: [
      { label: "F.I.Sh.", render: (t) => `<b>${esc(t.full_name)}</b>` },
      { label: "Telefon", render: (t) => esc(t.phone || "—") },
      { label: "Fanlar", render: (t) => (t.subject_names || []).map((n) => `<span class="badge indigo">${esc(n)}</span>`).join(" ") || "—" },
      { label: "Login", render: (t) => loginBadge(t.has_login) },
      { label: "Holat", render: (t) => activeBadge(t.is_active) },
    ],
    fields: () => [
      { name: "full_name", label: "F.I.Sh.", required: true, placeholder: "Karimov Ali" },
      { name: "phone", label: "Telefon", type: "tel", placeholder: "+998 90 123 45 67" },
      { name: "subjects", label: "Fanlar", type: "multiselect", options: subjectOptions() },
      { name: "username", label: "Login", autocomplete: "off" },
      { name: "password", label: "Parol", type: "password", autocomplete: "new-password", placeholder: "yangi login uchun" },
      { name: "is_active", label: "Faol", type: "checkbox", value: true },
    ],
    values: (t) => ({ full_name: t.full_name, phone: t.phone, subjects: t.subjects, is_active: t.is_active }),
  },
  parents: {
    endpoint: API.parents, view: "parentsView", singular: "Ota-ona",
    columns: [
      { label: "F.I.Sh.", render: (p) => `<b>${esc(p.full_name)}</b>` },
      { label: "Telefon", render: (p) => esc(p.phone || "—") },
      { label: "Farzandlar", render: (p) => esc((p.children_names || []).join(", ") || "—") },
      { label: "Login", render: (p) => loginBadge(p.has_login) },
      { label: "Holat", render: (p) => activeBadge(p.is_active) },
    ],
    fields: () => [
      { name: "full_name", label: "F.I.Sh.", required: true },
      { name: "phone", label: "Telefon", type: "tel" },
      { name: "username", label: "Login", autocomplete: "off" },
      { name: "password", label: "Parol", type: "password", autocomplete: "new-password", placeholder: "yangi login uchun" },
      { name: "is_active", label: "Faol", type: "checkbox", value: true },
    ],
    values: (p) => ({ full_name: p.full_name, phone: p.phone, is_active: p.is_active }),
  },
  students: {
    endpoint: () => API.students + ($("#stdClassFilter").value ? "?class=" + $("#stdClassFilter").value : ""),
    writeEndpoint: API.students,
    view: "studentsView", singular: "O'quvchi",
    columns: [
      { label: "Ism familiya", render: (s) => `<b>${esc(s.name)}</b>` },
      { label: "Sinf", render: (s) => s.class_name ? `<span class="badge indigo">${esc(s.class_name)}</span>` : "—" },
      { label: "Telefon", render: (s) => esc(s.phone || "—") },
      { label: "Ota-onalar", render: (s) => esc((s.parent_names || []).join(", ") || "—") },
      { label: "Login", render: (s) => loginBadge(s.has_login) },
      { label: "Holat", render: (s) => activeBadge(s.is_active) },
    ],
    fields: () => [
      { name: "name", label: "Ism familiya", required: true },
      { name: "phone", label: "Telefon", type: "tel" },
      { name: "school_class", label: "Sinf", type: "select", empty: "— yo'q —", options: classOptions() },
      { name: "parents", label: "Ota-onalar", type: "multiselect", options: parentOptions() },
      { name: "username", label: "Login", autocomplete: "off" },
      { name: "password", label: "Parol", type: "password", autocomplete: "new-password", placeholder: "yangi login uchun" },
      { name: "note", label: "Izoh", type: "textarea", rows: 2 },
      { name: "is_active", label: "Faol", type: "checkbox", value: true },
    ],
    values: (s) => ({ name: s.name, phone: s.phone, school_class: s.school_class, parents: s.parents, note: s.note, is_active: s.is_active }),
    extraActions: (s) => `<button class="btn btn-sm" data-student-profile="${s.id}">📊 Profil</button>`,
  },
};

async function loadCrud(key) {
  const cfg = CRUDS[key];
  const url = typeof cfg.endpoint === "function" ? cfg.endpoint() : cfg.endpoint;
  state.cache[key] = await api(url);
  renderCrudTable($("#" + cfg.view), key, cfg, state.cache[key]);
}

function renderCrudTable(box, key, cfg, items) {
  if (!items.length) {
    box.innerHTML = '<div class="empty">Ma\'lumot yo\'q. Yuqoridagi "➕" tugmasini bosing.</div>';
    return;
  }
  const extra = cfg.extraActions || (() => "");
  box.innerHTML = `<table class="table"><thead><tr>` +
    cfg.columns.map((c) => `<th>${c.label}</th>`).join("") +
    `<th class="th-actions">Amallar</th></tr></thead><tbody>` +
    items.map((it) => {
      const tds = cfg.columns.map((c) => `<td>${c.render ? c.render(it) : esc(it[c.key] != null ? it[c.key] : "—")}</td>`).join("");
      return `<tr>${tds}<td><div class="td-actions">${extra(it)}` +
        `<button class="btn btn-sm" data-crud-edit="${key}" data-crud-id="${it.id}">✏️</button>` +
        `<button class="btn btn-sm btn-danger" data-crud-del="${key}" data-crud-id="${it.id}">🗑</button></div></td></tr>`;
    }).join("") + `</tbody></table>`;
}

function openCrudForm(key, item) {
  const cfg = CRUDS[key];
  const fields = typeof cfg.fields === "function" ? cfg.fields() : cfg.fields;
  openForm({
    title: (item ? "Tahrirlash — " : "Qo'shish — ") + cfg.singular,
    fields,
    values: item && cfg.values ? cfg.values(item) : {},
    wide: ["students", "teachers"].includes(key),
    onSubmit: async (payload) => {
      const base = cfg.writeEndpoint || (typeof cfg.endpoint === "function" ? cfg.endpoint() : cfg.endpoint);
      await api(base + (item ? item.id + "/" : ""),
        { method: item ? "PATCH" : "POST", body: JSON.stringify(payload) });
      toast("Saqlandi");
      await refreshRefs();
      await loadCrud(key);
    },
  });
}

function deleteCrud(key, id) {
  const cfg = CRUDS[key];
  askConfirm("Bu yozuv o'chirilsinmi?", async () => {
    try {
      const base = cfg.writeEndpoint || (typeof cfg.endpoint === "function" ? cfg.endpoint() : cfg.endpoint);
      await api(base + id + "/", { method: "DELETE" });
      toast("O'chirildi");
      await refreshRefs();
      await loadCrud(key);
    } catch (err) { toast(err.message, "err"); }
  });
}

document.addEventListener("click", (e) => {
  const edit = e.target.closest("[data-crud-edit]");
  if (edit) {
    const key = edit.dataset.crudEdit;
    const item = (state.cache[key] || []).find((x) => x.id === Number(edit.dataset.crudId));
    openCrudForm(key, item);
    return;
  }
  const del = e.target.closest("[data-crud-del]");
  if (del) { deleteCrud(del.dataset.crudDel, Number(del.dataset.crudId)); return; }
  const prof = e.target.closest("[data-student-profile]");
  if (prof) { openStudentProfile(Number(prof.dataset.studentProfile)); return; }
});

/* -------------------------------- reference -------------------------------- */
async function refreshRefs() {
  const [classes, subjects, teachers, parents] = await Promise.all([
    api(API.classes), api(API.subjects), api(API.teachers), api(API.parents),
  ]);
  state.classes = classes; state.subjects = subjects;
  state.teachers = teachers; state.parents = parents;
  fillClassSelects();
}
async function ensureRefs() {
  if (!state.refsReady) { await refreshRefs(); state.refsReady = true; }
}
function fillSelect(el, options, placeholder, selected) {
  if (!el) return;
  el.innerHTML = (placeholder !== undefined ? `<option value="">${esc(placeholder)}</option>` : "") +
    options.map((o) => `<option value="${o.value}"${String(o.value) === String(selected) ? " selected" : ""}>${esc(o.label)}</option>`).join("");
}
function fillClassSelects() {
  ["#stdClassFilter", "#jrnClass", "#attClass", "#hwClass", "#schClass", "#lesClass"].forEach((sel) => {
    const el = $(sel);
    fillSelect(el, classOptions(), sel === "#stdClassFilter" ? "Barcha sinflar" : "Sinf tanlang", el.value);
  });
  fillSelect($("#jrnSubject"), subjectOptions(), "Fan tanlang", $("#jrnSubject").value);
  fillSelect($("#hwSubject"), subjectOptions(), "Barcha fanlar", $("#hwSubject").value);
}

/* -------------------------------- thema ----------------------------------- */
function applyTheme() {
  const dark = localStorage.getItem("theme") === "dark";
  document.documentElement.setAttribute("data-theme", dark ? "dark" : "light");
  const b = $("#themeBtn");
  if (b) b.textContent = dark ? "☀️" : "🌙";
}
$("#themeBtn").addEventListener("click", () => {
  localStorage.setItem("theme", localStorage.getItem("theme") === "dark" ? "light" : "dark");
  applyTheme();
});

/* -------------------------------- sahifalar ------------------------------- */
const PAGE_TITLES = {
  dashboard: "Boshqaruv paneli", journal: "Baholar jurnali", lesson: "Dars o'tkazish",
  attendance: "Davomat",
  homework: "Uyga vazifa", schedule: "Dars jadvali", classes: "Sinflar",
  students: "O'quvchilar", teachers: "O'qituvchilar", subjects: "Fanlar",
  parents: "Ota-onalar", announcements: "E'lonlar", mypanel: "Shaxsiy panel",
  registrations: "Ro'yxatdan o'tish so'rovlari",
};

$$("#nav .nav-item").forEach((el) => el.addEventListener("click", (e) => {
  e.preventDefault();
  switchPage(el.dataset.page);
}));

async function switchPage(page) {
  state.page = page;
  $$("#nav .nav-item").forEach((n) => n.classList.toggle("active", n.dataset.page === page));
  $$(".page").forEach((p) => p.classList.toggle("active", p.id === "page-" + page));
  $("#pageTitle").textContent = PAGE_TITLES[page] || "";
  try {
    if (page === "dashboard") await loadDashboard();
    else if (page === "journal") await initJournal();
    else if (page === "lesson") await initLesson();
    else if (page === "attendance") await initAttendance();
    else if (page === "homework") await initHomework();
    else if (page === "schedule") await initSchedule();
    else if (page === "students") { await ensureRefs(); fillSelect($("#stdClassFilter"), classOptions(), "Barcha sinflar", $("#stdClassFilter").value); await loadCrud("students"); }
    else if (page === "announcements") await loadAnnouncements();
    else if (page === "registrations") await loadRegistrations();
    else if (page === "mypanel") await loadMyPanel();
    else if (CRUDS[page]) { await ensureRefs(); await loadCrud(page); }
  } catch (err) { toast(err.message, "err"); }
}

/* ------------------------------- Boshqaruv -------------------------------- */
function statCard(icon, cls, val, label) {
  return `<div class="stat"><div class="stat-ico ${cls}">${icon}</div><div>` +
    `<div class="stat-val">${val}</div><div class="stat-lab">${label}</div></div></div>`;
}
function weekChartHTML(records) {
  const max = Math.max(1, ...records.map((r) => r.present + r.absent));
  return '<div class="week-chart">' + records.map((r) => {
    const hP = Math.round((r.present / max) * 100);
    const hA = Math.round((r.absent / max) * 100);
    return '<div class="wbar"><div class="wbar-col">' +
      '<div class="wbar-count">' + (r.present + r.absent) + '</div>' +
      '<div class="wbar-present" style="height:' + hP + '%"></div>' +
      (r.absent ? '<div class="wbar-absent" style="height:' + Math.max(4, hA) + '%"></div>' : "") +
      '</div><div class="wbar-label">' + r.label + '</div></div>';
  }).join("") + '</div>';
}
async function loadDashboard() {
  const s = await api(API.summary);
  if (s.role === "teacher") { renderTeacherDashboard(s); return; }
  renderAdminDashboard(s);
}
function gradesTableHTML(list) {
  return list.length
    ? '<table class="table"><thead><tr><th>O\'quvchi</th><th>Fan</th><th>Baho</th><th>Sana</th></tr></thead><tbody>' +
      list.map((g) => `<tr><td>${esc(g.student_name)}</td><td>${esc(g.subject_name)}</td>` +
        `<td>${gradeBadge(g.value)}</td><td>${fmtDate(g.date)}</td></tr>`).join("") + '</tbody></table>'
    : '<div class="empty">Baholar yo\'q.</div>';
}
function newsHTML(list) {
  return list.length
    ? list.map((a) => `<div class="ann-item" style="padding:11px 13px"><div class="ann-title" style="font-size:14px">${a.is_pinned ? "📌 " : ""}${esc(a.title)}</div>` +
      `<div class="ann-meta"><span>${esc(a.author_name || "Administrator")}</span></div></div>`).join("")
    : '<div class="empty">E\'lonlar yo\'q.</div>';
}
function renderAdminDashboard(s) {
  $("#dashWeekTitle").textContent = "Haftalik davomat";
  $("#dashClassesTitle").textContent = "Sinflar";
  $("#dashGradesTitle").textContent = "So'nggi baholar";
  $("#dashNewsTitle").textContent = "E'lonlar";
  $("#dashStats").innerHTML =
    statCard("🎓", "blue", s.students_active, `O'quvchilar (${s.students_total} jami)`) +
    statCard("👨‍🏫", "orange", s.teachers_total, "O'qituvchilar") +
    statCard("🏫", "green", s.classes_total, "Sinflar") +
    statCard("⭐", "blue", s.grade_avg || "—", "O'rtacha baho") +
    statCard("✅", "green", s.today_percent + "%", `Bugun keldi (${s.today_present}/${s.today_total})`);
  $("#dashWeek").innerHTML = weekChartHTML(s.week_records);
  $("#dashClasses").innerHTML = s.class_stats.length ? s.class_stats.map((c) =>
    `<div class="cycle-row"><div class="cycle-name">${esc(c.name)}</div>` +
    `<div class="cycle-track" style="--fill:${Math.min(100, c.students_count * 8)}%"></div>` +
    `<div class="cycle-meta">${c.students_count} o'quvchi</div></div>`).join("")
    : '<div class="empty">Sinflar yo\'q.</div>';
  $("#dashGrades").innerHTML = gradesTableHTML(s.latest_grades);
  $("#dashNews").innerHTML = newsHTML(s.announcements);
}
function renderTeacherDashboard(s) {
  const st = s.stats;
  $("#dashWeekTitle").textContent = "Mening darslarim — haftalik davomat";
  $("#dashClassesTitle").textContent = "Bugungi darslarim";
  $("#dashGradesTitle").textContent = "Bergan so'nggi baholarim";
  $("#dashNewsTitle").textContent = "E'lonlar";
  $("#dashStats").innerHTML =
    statCard("🏫", "green", st.classes, "Sinflarim") +
    statCard("🎓", "blue", st.students, "O'quvchilarim") +
    statCard("📚", "orange", st.lessons_today, "Bugungi darslar") +
    statCard("⭐", "blue", st.grade_avg || "—", `Bergan baholarim (${st.grades_total})`) +
    statCard("✅", "green", st.today_percent + "%", `Bugun keldi (${st.today_present}/${st.today_total})`);
  $("#dashWeek").innerHTML = weekChartHTML(s.week_records);
  $("#dashClasses").innerHTML = s.today_lessons.length ? s.today_lessons.map((l) => {
    const done = l.students_count > 0 && l.attendance_marked >= l.students_count;
    return `<div class="lesson-row"><span class="lesson-para">${l.period}</span>` +
      `<div class="lr-main"><div class="lr-title">${esc(l.subject_name)} · ${esc(l.class_name)}</div>` +
      `<div class="lr-meta">${l.start_time ? l.start_time + "–" + l.end_time : ""}${l.room ? " · 🚪 " + esc(l.room) : ""} · ✅ ${l.attendance_marked}/${l.students_count}</div></div>` +
      `<button class="btn btn-sm ${done ? "" : "btn-primary"}" data-dash-lesson="${l.schedule_id}">${done ? "Ko'rish" : "Ochish"}</button></div>`;
  }).join("") : '<div class="empty">Bugun darsingiz yo\'q.</div>';
  $("#dashGrades").innerHTML = gradesTableHTML(s.latest_grades);
  $("#dashNews").innerHTML = newsHTML(s.announcements);
}
function gradeBadge(v) {
  return v ? `<span class="grade-badge grade-${v}">${v}</span>` : '<span class="grade-badge grade-na">—</span>';
}

/* -------------------------------- Jurnal ---------------------------------- */
async function initJournal() {
  await ensureRefs();
  if (!$("#jrnMonth").value) $("#jrnMonth").value = todayStr().slice(0, 7);
  if ($("#jrnClass").value && $("#jrnSubject").value) await loadJournal();
  else $("#journalView").innerHTML = '<div class="card"><div class="empty">Sinf va fanni tanlang.</div></div>';
}
async function loadJournal() {
  const cls = $("#jrnClass").value, sub = $("#jrnSubject").value, month = $("#jrnMonth").value || todayStr().slice(0, 7);
  if (!cls || !sub) { $("#journalView").innerHTML = '<div class="card"><div class="empty">Sinf va fanni tanlang.</div></div>'; return; }
  const start = month + "-01", end = month + "-31";
  const data = await api(`${API.grades}journal/?class=${cls}&subject=${sub}&start=${start}&end=${end}`);
  state.journal = { data, cls, sub };
  const dates = data.dates;
  if (!data.students.length) { $("#journalView").innerHTML = '<div class="card"><div class="empty">Bu sinfda o\'quvchilar yo\'q.</div></div>'; return; }
  let head = '<tr><th class="jrn-head jrn-name">O\'quvchi</th><th class="jrn-head">O\'rtacha</th>' +
    `<th class="jrn-head jrn-quarter">${esc(data.quarter_label || "Chorak")}</th>` +
    dates.map((d) => `<th class="jrn-head"><div class="jrn-date"><b>${new Date(d + "T00:00:00").getDate()}</b>${MONTHS[new Date(d + "T00:00:00").getMonth()].slice(0, 3)}</div></th>`).join("") +
    '<th class="jrn-head">➕</th></tr>';
  let bodyrows = data.students.map((s) => {
    const cells = dates.map((d) => {
      const c = data.cells[`${s.student_id}:${d}`];
      return `<td class="jrn-cell${c ? " has" : ""}" data-jrn-cell data-student="${s.student_id}" data-date="${d}" data-name="${esc(s.student_name)}">` +
        (c ? gradeBadge(c.value) : '<span class="plus">·</span>') + `</td>`;
    }).join("");
    return `<tr><td class="jrn-name">${esc(s.student_name)}</td>` +
      `<td class="jrn-cell" style="cursor:default">${s.average ? `<span class="avg-chip">${s.average}</span>` : "—"}</td>` +
      `<td class="jrn-cell" style="cursor:default">${quarterBadge(s)}</td>` +
      cells +
      `<td class="jrn-cell" data-jrn-cell data-student="${s.student_id}" data-date="${todayStr()}" data-name="${esc(s.student_name)}"><span class="plus">＋</span></td></tr>`;
  }).join("");
  $("#journalView").innerHTML = `<div class="card"><div class="jrn-wrap"><table class="jrn-table">` +
    `<thead>${head}</thead><tbody>${bodyrows}</tbody></table></div>` +
    `<div class="muted" style="margin-top:10px;font-size:12.5px">Katak ustiga bosib baho qo'ying. ` +
    `<b>${esc(data.quarter_label || "Chorak")}</b> ustuni — avtomatik o'rtacha (rangli) yoki saqlangan chorak bahosi. ` +
    `"🎯 Chorak baholari" tugmasi orqali tasdiqlang.</div></div>`;
}
function quarterBadge(s) {
  if (s.quarter_saved) return `<span class="grade-badge grade-${s.quarter_saved} quarter-saved" title="Saqlangan chorak bahosi">${s.quarter_saved}</span>`;
  if (s.quarter_computed) return `<span class="grade-badge grade-na quarter-auto" title="Avtomatik hisoblangan">${s.quarter_computed}</span>`;
  return '<span class="grade-badge grade-na">—</span>';
}
async function openQuarterModal() {
  const cls = $("#jrnClass").value, sub = $("#jrnSubject").value;
  if (!cls || !sub) { toast("Sinf va fanni tanlang", "err"); return; }
  const q = (state.journal && state.journal.data.quarter) || 1;
  const data = await api(API.grades + `quarter/?class=${cls}&subject=${sub}&quarter=${q}`);
  state.quarter = { cls, sub, quarter: q, data };
  const rows = data.rows.map((r) =>
    `<div class="stu-row"><span class="stu-name">${esc(r.student_name)}</span>` +
    `<span class="muted" style="min-width:130px">O'rtacha: ${r.average != null ? r.average : "—"} (${r.count})</span>` +
    `<span class="muted" style="min-width:95px">Avto: ${r.computed != null ? r.computed : "—"}</span>` +
    `<select class="inp" data-q-student="${r.student_id}" style="width:90px">` +
    `<option value="">—</option>` +
    [5, 4, 3, 2].map((v) => `<option value="${v}"${r.saved === v ? " selected" : ""}>${v}</option>`).join("") +
    `</select></div>`).join("");
  openInfo("🎯 Chorak baholari — " + data.label,
    `<div class="muted" style="padding-bottom:10px">${data.label} (${fmtDateFull(data.start)} — ${fmtDateFull(data.end)}) · ` +
    `avtomatik o'rtacha asosida hisoblangan. Kerak bo'lsa qo'lda o'zgartirib saqlang.</div>` +
    `<div class="stu-list">${rows || '<div class="empty">O\'quvchilar yo\'q.</div>'}</div>` +
    `<div class="modal-actions" style="border:0"><button class="btn" data-close="infoModal">Bekor qilish</button>` +
    `<button class="btn btn-primary" data-quarter-save>💾 Saqlash</button></div>`);
}
$("#jrnQuarter").addEventListener("click", () => { openQuarterModal().catch((err) => toast(err.message, "err")); });
$("#jrnLoad").addEventListener("click", loadJournal);
$("#jrnClass").addEventListener("change", loadJournal);
$("#jrnSubject").addEventListener("change", loadJournal);
$("#jrnMonth").addEventListener("change", loadJournal);
$("#journalView").addEventListener("click", (e) => {
  const cell = e.target.closest("[data-jrn-cell]");
  if (!cell) return;
  const studentId = Number(cell.dataset.student);
  const day = cell.dataset.date;
  const existing = state.journal.data.cells[`${studentId}:${day}`];
  openGradeModal(studentId, day, existing, cell.dataset.name);
});
function openGradeModal(studentId, day, existing, name) {
  const cls = Number($("#jrnClass").value), sub = Number($("#jrnSubject").value);
  const fields = [
    { name: "value", label: "Baho", type: "select", required: true, options: [5, 4, 3, 2].map((v) => ({ value: v, label: String(v) })), empty: "— tanlang —" },
    { name: "type", label: "Baho turi", type: "select", options: [
      { value: "joriy", label: "Joriy" }, { value: "oraliq", label: "Oraliq" }, { value: "chorak", label: "Chorak" }] },
    { name: "comment", label: "Izoh", placeholder: "ixtiyoriy" },
  ];
  if (state.isAdmin) fields.push({ name: "teacher", label: "O'qituvchi", type: "select", empty: "— yo'q —", options: teacherOptions() });
  openForm({
    title: `${name} — ${fmtDateFull(day)} — ${$("#jrnSubject").selectedOptions[0].text}`,
    fields,
    values: existing
      ? { value: existing.value, type: existing.type, comment: existing.comment }
      : { type: "joriy" },
    onDelete: existing ? () => deleteGrade(existing.id) : null,
    onSubmit: async (payload) => {
      const body = Object.assign({ student: studentId, subject: sub, school_class: cls, date: day }, payload);
      if (state.isTeacher && !state.isAdmin) body.teacher = state.teacherId;
      if (existing) await api(API.grades + existing.id + "/", { method: "PATCH", body: JSON.stringify(body) });
      else await api(API.grades, { method: "POST", body: JSON.stringify(body) });
      toast("Baho saqlandi");
      await loadJournal();
    },
  });
}
async function deleteGrade(id) {
  try {
    await api(API.grades + id + "/", { method: "DELETE" });
    toast("Baho o'chirildi");
    closeModal("formModal");
    await loadJournal();
  } catch (err) { toast(err.message, "err"); }
}

/* ------------------------------- Davomat ---------------------------------- */
async function initAttendance() {
  await ensureRefs();
  if (!$("#attDate").value) $("#attDate").value = todayStr();
  if ($("#attClass").value) await loadAttendance();
  else $("#attendanceView").innerHTML = '<div class="card"><div class="empty">Sinfni tanlang.</div></div>';
}
async function loadAttendance() {
  const cls = $("#attClass").value, day = $("#attDate").value;
  if (!cls) { $("#attendanceView").innerHTML = '<div class="card"><div class="empty">Sinfni tanlang.</div></div>'; return; }
  const [students, records] = await Promise.all([
    api(`${API.students}?class=${cls}&active=1`),
    api(`${API.attendance}?class=${cls}&date=${day}`),
  ]);
  const byStudent = {};
  records.forEach((r) => { byStudent[r.student] = r; });
  if (!students.length) { $("#attendanceView").innerHTML = '<div class="card"><div class="empty">Bu sinfda o\'quvchilar yo\'q.</div></div>'; return; }
  const present = records.filter((r) => r.status === "present" || r.status === "late").length;
  const rows = students.map((s) => {
    const rec = byStudent[s.id];
    const st = rec ? rec.status : "";
    const color = avatarColor(s.name);
    const pills = [["present", "Keldi", "on-present"], ["absent", "Kelmadi", "on-absent"], ["late", "Kechikdi", "on-late"], ["sick", "Kasal", "on-sick"]]
      .map(([val, lab, cls2]) => `<button class="status-pill ${st === val ? cls2 : ""}" data-att-status="${val}" data-student="${s.id}">${lab}</button>`).join("");
    return `<div class="stu-row"><span class="avatar" style="background:${color}">${initials(s.name)}</span>` +
      `<span class="stu-name">${esc(s.name)}</span><div class="status-group">${pills}</div></div>`;
  }).join("");
  $("#attendanceView").innerHTML = `<div class="card"><div class="card-head"><h3>${esc($("#attClass").selectedOptions[0].text)} — ${fmtDateFull(day)}</h3>` +
    `<div class="muted">Keldi: ${present}/${students.length}</div></div><div class="stu-list">${rows}</div></div>`;
}
async function markAttendance(studentId, statusVal) {
  const day = $("#attDate").value;
  const schedule = null;
  await api(API.attendance + "mark/", { method: "POST", body: JSON.stringify({ student: studentId, date: day, status: statusVal, schedule }) });
  return true;
}
$("#attLoad").addEventListener("click", loadAttendance);
$("#attClass").addEventListener("change", loadAttendance);
$("#attDate").addEventListener("change", loadAttendance);
$("#attendanceView").addEventListener("click", async (e) => {
  const pill = e.target.closest("[data-att-status]");
  if (!pill) return;
  try { await markAttendance(Number(pill.dataset.student), pill.dataset.attStatus); toast("Saqlandi"); await loadAttendance(); }
  catch (err) { toast(err.message, "err"); }
});
$("#attAllPresent").addEventListener("click", async () => {
  const cls = $("#attClass").value; if (!cls) return;
  const students = await api(`${API.students}?class=${cls}&active=1`);
  try {
    await Promise.all(students.map((s) => markAttendance(s.id, "present")));
    toast("Hammasi 'Keldi' deb belgilandi");
    await loadAttendance();
  } catch (err) { toast(err.message, "err"); }
});

/* ------------------------------ Uyga vazifa ------------------------------- */
async function initHomework() {
  await ensureRefs();
  await loadHomework();
}
async function loadHomework() {
  const cls = $("#hwClass").value, sub = $("#hwSubject").value;
  const q = [];
  if (cls) q.push("class=" + cls);
  if (sub) q.push("subject=" + sub);
  const list = await api(API.homework + (q.length ? "?" + q.join("&") : ""));
  $("#homeworkView").innerHTML = list.length ? list.map((h) => {
    const done = h.submissions_count ? Math.round(h.done_count / h.submissions_count * 100) : 0;
    const actions = (state.isAdmin || state.isTeacher)
      ? `<div class="hw-actions"><button class="btn btn-sm btn-primary" data-hw-subs="${h.id}">📋 Topshiriqlar</button>` +
        `<button class="btn btn-sm" data-hw-edit="${h.id}">✏️</button>` +
        `<button class="btn btn-sm btn-danger" data-hw-del="${h.id}">🗑</button></div>` : "";
    return `<div class="hw-item"><div class="hw-head"><span class="badge indigo">${esc(h.class_name)}</span>` +
      `<span class="hw-title">${esc(h.title)}</span>${actions}</div>` +
      (h.description ? `<div class="hw-desc">${esc(h.description)}</div>` : "") +
      `<div class="hw-meta"><span>📚 ${esc(h.subject_name)}</span><span>📅 ${fmtDateFull(h.date)}</span>` +
      (h.due_date ? `<span>⏰ Muddat: ${fmtDateFull(h.due_date)}</span>` : "") +
      `<span>✅ Bajarildi: ${h.done_count}/${h.submissions_count} (${done}%)</span></div></div>`;
  }).join("") : '<div class="card"><div class="empty">Vazifalar yo\'q. "➕ Vazifa qo\'shish" tugmasini bosing.</div></div>';
  state.cache.homework = list;
}
$("#hwLoad").addEventListener("click", loadHomework);
$("#hwClass").addEventListener("change", loadHomework);
$("#hwSubject").addEventListener("change", loadHomework);
function homeworkFields(h) {
  const fields = [
    { name: "school_class", label: "Sinf", type: "select", required: true, empty: "— tanlang —", options: classOptions() },
    { name: "subject", label: "Fan", type: "select", required: true, empty: "— tanlang —", options: subjectOptions() },
    { name: "date", label: "Berilgan sana", type: "date", required: true },
    { name: "due_date", label: "Topshirish muddati", type: "date" },
    { name: "title", label: "Sarlavha", required: true },
    { name: "description", label: "Mazmuni", type: "textarea", rows: 4 },
  ];
  if (state.isAdmin) fields.splice(2, 0, { name: "teacher", label: "O'qituvchi", type: "select", empty: "— yo'q —", options: teacherOptions() });
  return fields;
}
$("#hwAdd").addEventListener("click", () => {
  openForm({
    title: "Yangi uyga vazifa", wide: true, fields: homeworkFields(),
    values: { date: todayStr(), school_class: $("#hwClass").value, subject: $("#hwSubject").value },
    onSubmit: async (payload) => {
      if (state.isTeacher && !state.isAdmin) payload.teacher = state.teacherId;
      await api(API.homework, { method: "POST", body: JSON.stringify(payload) });
      toast("Vazifa qo'shildi"); await loadHomework();
    },
  });
});
$("#homeworkView").addEventListener("click", async (e) => {
  const subs = e.target.closest("[data-hw-subs]");
  if (subs) { await openHomeworkSubs(Number(subs.dataset.hwSubs)); return; }
  const edit = e.target.closest("[data-hw-edit]");
  if (edit) {
    const h = state.cache.homework.find((x) => x.id === Number(edit.dataset.hwEdit));
    openForm({
      title: "Tahrirlash — uyga vazifa", wide: true, fields: homeworkFields(h),
      values: { school_class: h.school_class, subject: h.subject, teacher: h.teacher, date: h.date, due_date: h.due_date, title: h.title, description: h.description },
      onDelete: () => deleteHomework(h.id),
      onSubmit: async (payload) => { await api(API.homework + h.id + "/", { method: "PATCH", body: JSON.stringify(payload) }); toast("Saqlandi"); await loadHomework(); },
    });
    return;
  }
  const del = e.target.closest("[data-hw-del]");
  if (del) {
    askConfirm("Vazifa o'chirilsinmi?", async () => {
      try { await api(API.homework + del.dataset.hwDel + "/", { method: "DELETE" }); toast("O'chirildi"); await loadHomework(); }
      catch (err) { toast(err.message, "err"); }
    });
  }
});
async function deleteHomework(id) {
  try { await api(API.homework + id + "/", { method: "DELETE" }); toast("O'chirildi"); closeModal("formModal"); await loadHomework(); }
  catch (err) { toast(err.message, "err"); }
}
async function openHomeworkSubs(id) {
  const data = await api(API.homework + id + "/submissions/");
  state.hwSubs = data;
  const rows = data.rows.map((r) =>
    `<div class="stu-row" data-hwsub="${r.student_id}">` +
    `<span class="stu-name">${esc(r.student_name)}</span>` +
    `<label class="switch-row" style="margin:0"><input type="checkbox" data-sub-done ${r.is_done ? "checked" : ""}> Bajarildi</label>` +
    `<select class="inp" data-sub-grade style="width:90px">` +
    `<option value="">Baho</option>` +
    [5, 4, 3, 2].map((v) => `<option value="${v}"${r.grade === v ? " selected" : ""}>${v}</option>`).join("") +
    `</select></div>`).join("");
  openInfo("Topshiriqlar — " + data.homework.title, `<div class="stu-list">${rows || '<div class="empty">O\'quvchilar yo\'q.</div>'}</div>`);
}
$("#infoModalBody").addEventListener("change", async (e) => {
  const row = e.target.closest("[data-hwsub]");
  if (!row || !state.hwSubs) return;
  const hwId = state.hwSubs.homework.id;
  const studentId = row.dataset.hwsub;
  const done = row.querySelector("[data-sub-done]").checked;
  const grade = row.querySelector("[data-sub-grade]").value || null;
  try {
    await api(API.homework + hwId + "/submit/", { method: "POST", body: JSON.stringify({ student: studentId, is_done: done, grade }) });
    toast("Saqlandi");
  } catch (err) { toast(err.message, "err"); }
});

/* ----------------------------- Dars jadvali ------------------------------- */
async function initSchedule() {
  await ensureRefs();
  if (state.role === "student" && state.classId) {
    $("#schClass").value = state.classId;
    $("#schClass").disabled = true;
    $("#schLoad").classList.add("hidden");
  }
  if ($("#schClass").value) await loadSchedule();
  else $("#scheduleView").innerHTML = '<div class="card"><div class="empty">Sinfni tanlang.</div></div>';
}
async function loadSchedule() {
  const cls = $("#schClass").value;
  if (!cls) { $("#scheduleView").innerHTML = '<div class="card"><div class="empty">Sinfni tanlang.</div></div>'; return; }
  const list = await api(API.schedule + "?class=" + cls);
  state.cache.schedule = list;
  const maxPeriod = Math.max(7, ...list.map((s) => s.period));
  const map = {};
  list.forEach((s) => { map[`${s.weekday}:${s.period}`] = s; });
  let html = '<div class="sch-grid-wrap"><div class="sch-grid"><div class="sch-corner">Para</div>';
  for (let d = 1; d <= 6; d++) html += `<div class="sch-day">${WEEKDAYS[d]}</div>`;
  for (let p = 1; p <= maxPeriod; p++) {
    html += `<div class="sch-para"><b>${p}</b>para</div>`;
    for (let d = 1; d <= 6; d++) {
      const s = map[`${d}:${p}`];
      if (s) {
        html += `<div class="day-cell" data-sch-id="${s.id}" data-sch-day="${d}" data-sch-para="${p}">` +
          `<span class="dc-subject">${esc(s.subject_name)}</span>` +
          `<span class="dc-meta">${esc(s.teacher_name || "—")}</span>` +
          (s.start_time ? `<span class="dc-meta">${fmtTime(s.start_time)}–${fmtTime(s.end_time)}</span>` : "") +
          (s.room ? `<span class="dc-room">🚪 ${esc(s.room)}</span>` : "") + `</div>`;
      } else {
        html += `<div class="day-cell empty" data-sch-day="${d}" data-sch-para="${p}">＋</div>`;
      }
    }
  }
  html += "</div></div>";
  $("#scheduleView").innerHTML = `<div class="card">${html}</div>`;
}
function scheduleFields(s) {
  const fields = [
    { name: "school_class", label: "Sinf", type: "select", required: true, empty: "— tanlang —", options: classOptions() },
    { name: "subject", label: "Fan", type: "select", required: true, empty: "— tanlang —", options: subjectOptions() },
    { name: "teacher", label: "O'qituvchi", type: "select", empty: "— yo'q —", options: teacherOptions() },
    { name: "weekday", label: "Kun", type: "select", required: true, options: Object.entries(WEEKDAYS).map(([v, l]) => ({ value: v, label: l })) },
    { name: "period", label: "Para (raqam)", type: "number", required: true },
    { name: "start_time", label: "Boshlanish vaqti", type: "time" },
    { name: "end_time", label: "Tugash vaqti", type: "time" },
    { name: "room", label: "Xona", placeholder: "101" },
    { name: "is_active", label: "Faol", type: "checkbox", value: true },
  ];
  return fields;
}
$("#schLoad").addEventListener("click", loadSchedule);
$("#schClass").addEventListener("change", loadSchedule);
$("#schAdd").addEventListener("click", () => openScheduleForm(null, {}));
$("#scheduleView").addEventListener("click", (e) => {
  const cell = e.target.closest("[data-sch-day]");
  if (!cell) return;
  const day = Number(cell.dataset.schDay), para = Number(cell.dataset.schPara);
  const id = cell.dataset.schId;
  const item = id ? state.cache.schedule.find((s) => s.id === Number(id)) : null;
  openScheduleForm(item, { weekday: day, period: para, school_class: $("#schClass").value });
});
function openScheduleForm(item, defaults) {
  const values = item
    ? { school_class: item.school_class, subject: item.subject, teacher: item.teacher, weekday: item.weekday, period: item.period, start_time: item.start_time, end_time: item.end_time, room: item.room, is_active: item.is_active }
    : Object.assign({ weekday: 1, period: 1, is_active: true }, defaults);
  openForm({
    title: item ? "Tahrirlash — dars" : "Dars qo'shish",
    wide: true, fields: scheduleFields(), values,
    onDelete: item ? () => deleteSchedule(item.id) : null,
    onSubmit: async (payload) => {
      if (item) await api(API.schedule + item.id + "/", { method: "PATCH", body: JSON.stringify(payload) });
      else await api(API.schedule, { method: "POST", body: JSON.stringify(payload) });
      toast("Saqlandi");
      await loadSchedule();
    },
  });
}
async function deleteSchedule(id) {
  try { await api(API.schedule + id + "/", { method: "DELETE" }); toast("O'chirildi"); closeModal("formModal"); await loadSchedule(); }
  catch (err) { toast(err.message, "err"); }
}

/* --------------------------- Dars o'tkazish ------------------------------- */
const ATT_STATUSES = [
  ["present", "Keldi", "on-present"],
  ["absent", "Kelmadi", "on-absent"],
  ["late", "Kechikdi", "on-late"],
  ["sick", "Kasal", "on-sick"],
];
async function initLesson() {
  await ensureRefs();
  if (!$("#lesDate").value) $("#lesDate").value = todayStr();
  if ($("#lesClass").value) await loadLessonDay();
  else $("#lessonView").innerHTML = '<div class="card"><div class="empty">Sinfni tanlang.</div></div>';
}
async function loadLessonDay() {
  const cls = $("#lesClass").value, day = $("#lesDate").value;
  if (!cls) { $("#lessonView").innerHTML = '<div class="card"><div class="empty">Sinfni tanlang.</div></div>'; return; }
  const data = await api(`${API.lessons}?class=${cls}&date=${day}`);
  state.lessonDay = data;
  if (!data.lessons.length) {
    $("#lessonView").innerHTML = `<div class="card"><div class="empty">${fmtDateFull(day)} kuni bu sinfda jadval bo'yicha dars yo'q.</div></div>`;
    return;
  }
  $("#lessonView").innerHTML = '<div class="lesson-grid">' + data.lessons.map((l) => {
    const attDone = l.students_count > 0 && l.attendance_marked >= l.students_count;
    return `<div class="lesson-card"><div class="lesson-top"><span class="lesson-para">${l.period}-para</span>` +
      (l.start_time ? `<span class="muted">${l.start_time}–${l.end_time}</span>` : "") + `</div>` +
      `<div class="lesson-sub">${esc(l.subject_name)}</div>` +
      `<div class="lesson-meta">${esc(l.teacher_name || "—")}${l.room ? " · 🚪 " + esc(l.room) : ""}</div>` +
      `<div class="lesson-chips">` +
      `<span class="lchip ${attDone ? "ok" : "warn"}">✅ ${l.attendance_marked}/${l.students_count}</span>` +
      `<span class="lchip ${l.grades_count ? "ok" : ""}">⭐ ${l.grades_count}</span>` +
      `<span class="lchip ${l.has_homework ? "ok" : ""}">📝 ${l.has_homework ? "bor" : "yo'q"}</span>` +
      `</div>` +
      `<button class="btn btn-primary" data-lesson-open="${l.id}">Darsni ochish</button></div>`;
  }).join("") + '</div>';
}
async function openLessonWorkspace(id) {
  const day = $("#lesDate").value;
  const data = await api(`${API.lessonWorkspace}?schedule=${id}&date=${day}`);
  state.lesson = { id, day };
  const sch = data.schedule;
  const rows = data.students.map((r) => {
    const pills = ATT_STATUSES.map(([val, lab, cls2]) =>
      `<button class="status-pill ${r.status === val ? cls2 : ""}" data-ls-att="${val}">${lab}</button>`).join("");
    const gradeOpts = ["", 5, 4, 3, 2].map((v) =>
      `<option value="${v}"${String(r.grade_value) === String(v) ? " selected" : ""}>${v === "" ? "—" : v}</option>`).join("");
    return `<div class="stu-row" data-ls-row data-student="${r.student_id}">` +
      `<span class="stu-name">${esc(r.student_name)}</span>` +
      `<div class="status-group">${pills}</div>` +
      `<select class="inp" data-ls-grade style="width:80px">${gradeOpts}</select></div>`;
  }).join("");
  const hw = data.homework || {};
  openInfo(`Dars — ${sch.subject_name}`,
    `<div class="lesson-head"><span class="badge indigo">${sch.period}-para</span> <b>${esc(sch.subject_name)}</b> ` +
    `<span class="muted">${esc(sch.class_name)} · ${fmtDateFull(day)}${sch.start_time ? " · " + sch.start_time + "–" + sch.end_time : ""}` +
    `${sch.teacher_name ? " · " + esc(sch.teacher_name) : ""}</span></div>` +
    `<div class="lesson-sec"><h4>✅ Davomat va baholar</h4><div class="stu-list">${rows || '<div class="empty">O\'quvchilar yo\'q.</div>'}</div></div>` +
    `<div class="lesson-sec"><h4>📝 Uyga vazifa</h4>` +
    `<input class="inp" id="lsHwTitle" placeholder="Vazifa sarlavhasi" value="${esc(hw.title || "")}" style="margin-bottom:8px">` +
    `<textarea class="inp" id="lsHwDesc" rows="3" placeholder="Mazmuni / topshiriq">${esc(hw.description || "")}</textarea>` +
    `<div class="date-ctrl" style="margin-top:8px"><label>Topshirish muddati</label><input type="date" id="lsHwDue" value="${hw.due_date || ""}"></div>` +
    `</div>` +
    `<div class="modal-actions" style="border:0"><button class="btn" data-close="infoModal">Bekor qilish</button>` +
    `<button class="btn btn-primary" data-lesson-save>💾 Darsni saqlash</button></div>`);
}
$("#lesLoad").addEventListener("click", loadLessonDay);
$("#lesClass").addEventListener("change", loadLessonDay);
$("#lesDate").addEventListener("change", loadLessonDay);
$("#lessonView").addEventListener("click", (e) => {
  const open = e.target.closest("[data-lesson-open]");
  if (open) openLessonWorkspace(Number(open.dataset.lessonOpen)).catch((err) => toast(err.message, "err"));
});
document.addEventListener("click", (e) => {
  const open = e.target.closest("[data-dash-lesson]");
  if (!open) return;
  $("#lesDate").value = todayStr();
  openLessonWorkspace(Number(open.dataset.dashLesson)).catch((err) => toast(err.message, "err"));
});
$("#infoModalBody").addEventListener("click", (e) => {
  const close = e.target.closest("[data-close]");
  if (close) { closeModal(close.dataset.close); return; }
  const pill = e.target.closest("[data-ls-att]");
  if (pill) {
    const group = pill.closest(".status-group");
    group.querySelectorAll(".status-pill").forEach((p) => { p.className = "status-pill"; });
    const map = { present: "on-present", absent: "on-absent", late: "on-late", sick: "on-sick" };
    pill.classList.add(map[pill.dataset.lsAtt]);
    return;
  }
  if (e.target.closest("[data-lesson-save]") && state.lesson) {
    const rows = $$("#infoModalBody [data-ls-row]");
    const attendance = rows.map((row) => {
      const st = ["present", "absent", "late", "sick"].find((v) => row.querySelector(".status-pill.on-" + v));
      return { student: Number(row.dataset.student), status: st || "" };
    });
    const grades = $$("#infoModalBody [data-ls-grade]").map((el, i) =>
      ({ student: Number(rows[i].dataset.student), value: el.value || null }));
    const homework = {
      title: $("#lsHwTitle").value, description: $("#lsHwDesc").value,
      due_date: $("#lsHwDue").value || null,
    };
    api(API.lessonWorkspace, {
      method: "POST",
      body: JSON.stringify({ schedule: state.lesson.id, date: state.lesson.day, attendance, grades, homework }),
    }).then(() => {
      toast("Dars saqlandi");
      closeModal("infoModal");
      if (state.page === "lesson") return loadLessonDay();
      return loadDashboard();
    }).catch((err) => toast(err.message, "err"));
    return;
  }
  if (e.target.closest("[data-quarter-save]") && state.quarter) {
    const grades = $$("#infoModalBody [data-q-student]").map((el) =>
      ({ student: Number(el.dataset.qStudent), value: el.value || null }));
    api(API.grades + "quarter/", {
      method: "POST",
      body: JSON.stringify({ class: state.quarter.cls, subject: state.quarter.sub, quarter: state.quarter.quarter, grades }),
    }).then(() => { toast("Chorak baholari saqlandi"); closeModal("infoModal"); return loadJournal(); })
      .catch((err) => toast(err.message, "err"));
  }
});

/* ------------------------------- E'lonlar --------------------------------- */
async function loadAnnouncements() {
  const list = await api(API.announcements);
  $("#announcementsView").innerHTML = list.length ? list.map((a) => {
    const actions = (state.isAdmin || state.isTeacher)
      ? `<div class="hw-actions"><button class="btn btn-sm" data-ann-edit="${a.id}">✏️</button>` +
        `<button class="btn btn-sm btn-danger" data-ann-del="${a.id}">🗑</button></div>` : "";
    return `<div class="ann-item"><div class="ann-head">${a.is_pinned ? "📌 " : ""}<span class="ann-title">${esc(a.title)}</span>${actions}</div>` +
      (a.body ? `<div class="ann-body">${esc(a.body)}</div>` : "") +
      `<div class="ann-meta"><span>👤 ${esc(a.author_name || "Administrator")}</span><span>📅 ${fmtDateFull(a.created_at.slice(0, 10))}</span></div></div>`;
  }).join("") : '<div class="card"><div class="empty">E\'lonlar yo\'q.</div></div>';
  state.cache.announcements = list;
}
function announcementFields() {
  return [
    { name: "title", label: "Sarlavha", required: true },
    { name: "body", label: "Matn", type: "textarea", rows: 4 },
    { name: "audience", label: "Kimga", type: "select", options: [
      { value: "all", label: "Hamma" }, { value: "teachers", label: "O'qituvchilar" },
      { value: "students", label: "O'quvchilar" }, { value: "parents", label: "Ota-onalar" },
      { value: "class", label: "Bitta sinf" }] },
    { name: "school_class", label: "Sinf (agar 'Bitta sinf' bo'lsa)", type: "select", empty: "—", options: classOptions() },
    { name: "is_pinned", label: "Qadab qo'yish", type: "checkbox", value: false },
  ];
}
$("#annAdd").addEventListener("click", () => {
  openForm({
    title: "Yangi e'lon", wide: true, fields: announcementFields(), values: { audience: "all" },
    onSubmit: async (payload) => { await api(API.announcements, { method: "POST", body: JSON.stringify(payload) }); toast("E'lon qo'shildi"); await loadAnnouncements(); },
  });
});
$("#announcementsView").addEventListener("click", (e) => {
  const edit = e.target.closest("[data-ann-edit]");
  if (edit) {
    const a = state.cache.announcements.find((x) => x.id === Number(edit.dataset.annEdit));
    openForm({
      title: "Tahrirlash — e'lon", wide: true, fields: announcementFields(),
      values: { title: a.title, body: a.body, audience: a.audience, school_class: a.school_class, is_pinned: a.is_pinned },
      onDelete: () => deleteAnnouncement(a.id),
      onSubmit: async (payload) => { await api(API.announcements + a.id + "/", { method: "PATCH", body: JSON.stringify(payload) }); toast("Saqlandi"); await loadAnnouncements(); },
    });
    return;
  }
  const del = e.target.closest("[data-ann-del]");
  if (del) askConfirm("E'lon o'chirilsinmi?", async () => {
    try { await api(API.announcements + del.dataset.annDel + "/", { method: "DELETE" }); toast("O'chirildi"); await loadAnnouncements(); }
    catch (err) { toast(err.message, "err"); }
  });
});
async function deleteAnnouncement(id) {
  try { await api(API.announcements + id + "/", { method: "DELETE" }); toast("O'chirildi"); closeModal("formModal"); await loadAnnouncements(); }
  catch (err) { toast(err.message, "err"); }
}

/* --------------------- Ro'yxatdan o'tish so'rovlari ----------------------- */
const REG_ROLE_LABELS = { teacher: "O'qituvchi", student: "O'quvchi", parent: "Ota-ona" };
const REG_STATUS_CLS = { pending: "warn", approved: "ok", rejected: "" };
async function loadRegistrations() {
  const st = $("#regStatus").value;
  const list = await api("/api/registrations/" + (st ? "?status=" + st : ""));
  state.cache.registrations = list;
  if (!list.length) {
    $("#registrationsView").innerHTML = '<div class="card"><div class="empty">So\'rovlar yo\'q.</div></div>';
    return;
  }
  $("#registrationsView").innerHTML = list.map((r) => {
    const actions = r.status === "pending"
      ? `<button class="btn btn-sm btn-primary" data-reg-approve="${r.id}">✅ Tasdiqlash</button>` +
        `<button class="btn btn-sm btn-danger" data-reg-reject="${r.id}">✕ Rad etish</button>`
      : "";
    return `<div class="reg-item"><div class="reg-head">` +
      `<span class="reg-name">${esc(r.full_name)}</span>` +
      `<span class="badge indigo">${esc(REG_ROLE_LABELS[r.role] || r.role)}</span>` +
      `<span class="lchip ${REG_STATUS_CLS[r.status] || ""}">${esc(r.status_display)}</span>` +
      `<span class="reg-date">${fmtDateFull(r.created_at.slice(0, 10))}</span></div>` +
      `<div class="reg-meta">🔑 ${esc(r.username)}${r.phone ? " · 📞 " + esc(r.phone) : ""}` +
      `${r.class_name ? " · 🏫 " + esc(r.class_name) : ""}</div>` +
      `${r.message ? `<div class="reg-msg">${esc(r.message)}</div>` : ""}` +
      `${actions ? `<div class="hw-actions" style="margin-top:8px">${actions}</div>` : ""}</div>`;
  }).join("");
}
async function updateRegBadge() {
  if (!state.isAdmin) return;
  const badge = $("#regBadge");
  if (!badge) return;
  try {
    const list = await api("/api/registrations/?status=pending");
    badge.textContent = list.length || "";
    badge.style.display = list.length ? "inline-block" : "none";
  } catch (e) { /* ignore */ }
}
$("#regLoad").addEventListener("click", loadRegistrations);
$("#regStatus").addEventListener("change", loadRegistrations);
$("#registrationsView").addEventListener("click", async (e) => {
  const ap = e.target.closest("[data-reg-approve]");
  const rj = e.target.closest("[data-reg-reject]");
  if (!ap && !rj) return;
  try {
    if (ap) await api(`/api/registrations/${ap.dataset.regApprove}/approve/`, { method: "POST" });
    else await api(`/api/registrations/${rj.dataset.regReject}/reject/`, { method: "POST" });
    toast(ap ? "Tasdiqlandi" : "Rad etildi");
    await loadRegistrations();
    await updateRegBadge();
  } catch (err) { toast(err.message, "err"); }
});

/* ------------------------------ Shaxsiy panel ----------------------------- */
async function loadMyPanel() {
  if (state.role === "student") {
    $("#myPanelToolbar").innerHTML = "";
    const d = await api(API.students + state.studentId + "/dashboard/");
    $("#myPanelView").innerHTML = panelHTML(d);
  } else if (state.role === "parent") {
    if (!state.children.length) {
      $("#myPanelToolbar").innerHTML = "";
      $("#myPanelView").innerHTML = '<div class="card"><div class="empty">Sizga farzand biriktirilmagan. Administratorga murojaat qiling.</div></div>';
      return;
    }
    const current = $("#childSelect") ? $("#childSelect").value : state.children[0].id;
    $("#myPanelToolbar").innerHTML = `<div class="date-ctrl"><label>Farzand</label><select id="childSelect">` +
      state.children.map((c) => `<option value="${c.id}"${String(c.id) === String(current) ? " selected" : ""}>${esc(c.name)} — ${esc(c.class_name || "")}</option>`).join("") +
      `</select></div>`;
    $("#childSelect").addEventListener("change", async (e) => {
      const d = await api(API.students + e.target.value + "/dashboard/");
      $("#myPanelView").innerHTML = panelHTML(d);
    });
    const d = await api(API.students + current + "/dashboard/");
    $("#myPanelView").innerHTML = panelHTML(d);
  } else {
    $("#myPanelView").innerHTML = '<div class="card"><div class="empty">Bu bo\'lim o\'quvchi va ota-onalar uchun.</div></div>';
  }
}
function panelHTML(d) {
  const s = d.student, st = d.stats;
  const color = avatarColor(s.name);
  const hero = `<div class="panel-hero"><span class="avatar" style="background:${color}">${initials(s.name)}</span>` +
    `<div><div class="ph-name">${esc(s.name)}</div><div class="ph-sub">${esc(s.class_name || "Sinf yo'q")}</div></div></div>`;
  const stats = `<div class="mini-stats">` +
    `<div class="mini-stat"><div class="ms-val">${st.avg_grade || "—"}</div><div class="ms-lab">O'rtacha baho</div></div>` +
    `<div class="mini-stat"><div class="ms-val">${st.grades_count}</div><div class="ms-lab">Baholar</div></div>` +
    `<div class="mini-stat"><div class="ms-val">${st.attendance_percent}%</div><div class="ms-lab">Davomat</div></div>` +
    `<div class="mini-stat"><div class="ms-val">${st.homework_done}/${st.homework_total}</div><div class="ms-lab">Uyga vazifa</div></div></div>`;
  const subjects = d.subjects.length ? `<div class="card"><div class="card-head"><h3>Fanlar bo'yicha o'zlashtirish</h3></div>` +
    d.subjects.map((x) => `<div class="subject-line"><span class="sl-name">${esc(x.subject_name)}</span>` +
      `<span class="avg-chip">${x.avg}</span><span class="muted">${x.count} baho</span></div>`).join("") + `</div>` : "";
  const today = d.today_schedule.length ? `<div class="card"><div class="card-head"><h3>Bugungi darslar</h3></div><div class="today-list">` +
    d.today_schedule.map((x) => `<div class="today-item"><span class="today-para">${x.period}</span>` +
      `<span class="today-sub">${esc(x.subject_name)}</span>` +
      `<span class="today-time">${x.start_time ? fmtTime(x.start_time) + "–" + fmtTime(x.end_time) : ""} ${esc(x.room || "")}</span></div>`).join("") + `</div></div>` : "";
  const grades = d.recent_grades.length ? `<div class="card"><div class="card-head"><h3>So'nggi baholar</h3></div>` +
    `<table class="table"><thead><tr><th>Fan</th><th>Baho</th><th>Tur</th><th>Sana</th></tr></thead><tbody>` +
    d.recent_grades.map((g) => `<tr><td>${esc(g.subject_name)}</td><td>${gradeBadge(g.value)}</td>` +
      `<td>${esc(g.type)}</td><td>${fmtDate(g.date)}</td></tr>`).join("") + `</tbody></table></div>` : "";
  const quarters = (d.quarter_grades || []).length ? `<div class="card"><div class="card-head"><h3>🎯 Chorak baholari</h3></div>` +
    d.quarter_grades.map((x) => `<div class="subject-line"><span class="sl-name">${esc(x.subject_name)}</span>${gradeBadge(x.value)}</div>`).join("") + `</div>` : "";
  return hero + stats + `<div class="grid-2">${subjects}${today}</div>` + quarters + grades;
}
async function openStudentProfile(id) {
  try {
    const d = await api(API.students + id + "/dashboard/");
    openInfo("O'quvchi profili — " + d.student.name, panelHTML(d));
  } catch (err) { toast(err.message, "err"); }
}

/* --------------------------------- init ----------------------------------- */
async function loadMe() {
  const me = await api(API.me);
  state.role = me.role;
  state.isAdmin = me.is_admin;
  state.isTeacher = me.role === "teacher";
  state.studentId = me.student_id;
  state.teacherId = me.teacher_id;
  state.parentId = me.parent_id;
  state.children = me.children || [];
  state.classId = me.class_id || null;
  $("#userName").textContent = me.display_name || me.username || "";
  const roleLabels = { admin: "Administrator", teacher: "O'qituvchi", student: "O'quvchi", parent: "Ota-ona" };
  $("#userRole").textContent = roleLabels[me.role] || "Foydalanuvchi";
  $$("#nav .nav-item").forEach((a) => {
    const roles = (a.dataset.roles || "").split(",");
    a.classList.toggle("hidden", !roles.includes(state.role));
  });
  $$(".admin-teacher").forEach((el) => el.classList.toggle("hidden", !(state.isAdmin || state.isTeacher)));
  updateRegBadge();
  const start = (state.role === "student" || state.role === "parent") ? "mypanel" : "dashboard";
  await switchPage(start);
}

(function init() {
  applyTheme();
  const d = new Date();
  const dayNames = ["Yakshanba", "Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba"];
  $("#todayDate").textContent = dayNames[d.getDay()] + ", " + d.getDate() + "-" + MONTHS[d.getMonth()];
  loadMe().catch((err) => toast(err.message, "err"));
})();
