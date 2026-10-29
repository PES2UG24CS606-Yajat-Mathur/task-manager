/* =====================================================================
   Task Manager - front-end (User / Admin UI component, SAD 3.4)

   Plain JavaScript, no framework or build step. Structure:
     1. api()            - one function for every HTTP call (adds the token,
                           parses JSON, turns errors into exceptions)
     2. state            - the little bit of data the UI keeps in memory
     3. auth             - register / login / logout / resume session
     4. tasks            - list, create, edit, complete, delete
     5. dashboard        - active / overdue / completed summary
     6. categories       - suggestions for the task form
     7. wiring           - event listeners, started on DOMContentLoaded

   Security notes:
   * User-provided text is ALWAYS inserted with textContent, never innerHTML,
     so a task titled "<script>..." is shown as text (prevents XSS).
   * The session token lives in sessionStorage: it disappears when the tab is
     closed, and the server can revoke it at any time (TMA-SR-004).
   ===================================================================== */
"use strict";

/* ------------------------------------------------------------ 1. API */
const TOKEN_KEY = "tm.sessionToken";

class ApiError extends Error {
  constructor(status, body) {
    super(body?.error?.message || `Request failed (${status})`);
    this.status = status;
    this.code = body?.error?.code;
  }
}

async function api(path, { method = "GET", body } = {}) {
  const headers = { Accept: "application/json" };
  const token = sessionStorage.getItem(TOKEN_KEY);
  if (token) headers.Authorization = `Bearer ${token}`;
  if (body !== undefined) headers["Content-Type"] = "application/json";

  let response;
  try {
    response = await fetch(path, {
      method, headers, body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    // Network down: say so clearly; nothing was changed on the server (TMA-NF-004).
    throw new ApiError(0, { error: { message: "Can't reach the server. Check your connection and try again." } });
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    // Token expired / revoked / account deactivated -> back to the login screen.
    if (response.status === 401 && token) { endSession(); }
    throw new ApiError(response.status, data);
  }
  return data;
}

/* ---------------------------------------------------------- 2. State */
const state = {
  user: null,
  tasks: [],
  categories: [],        // [{id, name, taskCount}] for suggestions (TMA-F-022)
  editingTaskId: null,   // null = creating a new task
};

/* ------------------------------------------------------- DOM helpers */
const $ = (sel) => document.querySelector(sel);

/** Create an element: el("li", {class: "x"}, "text", childNode, ...) */
function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value === false || value == null) continue;
    if (key === "class") node.className = value;
    else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value === true ? "" : value);
  }
  for (const child of children.flat()) {
    if (child == null || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

let toastTimer;
function toast(message, isError = false) {
  const box = $("#toast");
  box.textContent = message;
  box.classList.toggle("error", isError);
  box.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { box.hidden = true; }, 3500);
}

/* ------------------------------------------------------ Date helpers */
// The API always speaks UTC ("2026-10-25T12:30:00Z"); the screen always shows the
// user's local time. These helpers convert between the two (TMA-F-023).
const fmtDateTime = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" });
const fmtDay = new Intl.DateTimeFormat(undefined, { day: "numeric" });
const fmtMon = new Intl.DateTimeFormat(undefined, { month: "short" });

/** UTC ISO string -> "29 Oct 2026, 5:30 pm" in local time ("" for none). */
const formatWhen = (iso) => (iso ? fmtDateTime.format(new Date(iso)) : "");

/** UTC ISO string -> value for <input type="datetime-local"> (local time, no seconds). */
function toLocalInput(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/** datetime-local value (local time) -> UTC ISO string for the API, or null if empty. */
const fromLocalInput = (value) => (value ? new Date(value).toISOString() : null);

/* ---------------------------------------------------------- 3. Auth */
function showAuth() {
  $("#app-view").hidden = true;
  $("#auth-view").hidden = false;
  document.querySelectorAll("dialog[open]").forEach((d) => d.close());
  selectAuthTab("login");          // always come back to the login tab
}

function selectAuthTab(which) {
  const login = which === "login";
  $("#tab-login").setAttribute("aria-selected", String(login));
  $("#tab-register").setAttribute("aria-selected", String(!login));
  $("#login-form").hidden = !login;
  $("#register-form").hidden = login;
  (login ? $("#login-email") : $("#reg-name")).focus();
}

async function handleLogin(event) {
  event.preventDefault();
  const form = event.target;
  $("#login-error").textContent = "";
  try {
    const data = await api("/api/auth/login", {
      method: "POST",
      body: { email: form.email.value, password: form.password.value },
    });
    sessionStorage.setItem(TOKEN_KEY, data.sessionToken);
    form.reset();
    await startApp(data.user);
  } catch (err) {
    $("#login-error").textContent = err.message;   // e.g. "Invalid email or password"
  }
}

async function handleRegister(event) {
  event.preventDefault();
  const form = event.target;
  $("#register-error").textContent = "";
  const body = { name: form.name.value, email: form.email.value, password: form.password.value };
  try {
    await api("/api/auth/register", { method: "POST", body });
    // Log straight in with the same credentials so the user lands on the task list.
    const data = await api("/api/auth/login", {
      method: "POST", body: { email: body.email, password: body.password },
    });
    sessionStorage.setItem(TOKEN_KEY, data.sessionToken);
    form.reset();
    await startApp(data.user);
    toast("Account created. Welcome!");
  } catch (err) {
    $("#register-error").textContent = err.message;
  }
}

function endSession() {
  sessionStorage.removeItem(TOKEN_KEY);
  state.user = null;
  showAuth();
}

async function handleLogout() {
  try { await api("/api/auth/logout", { method: "POST" }); } catch { /* already invalid */ }
  endSession();
  toast("Logged out");
}

/* --------------------------------------------------------- 4. Tasks */
async function loadTasks() {
  try {
    const data = await api("/api/tasks");
    state.tasks = data.tasks;
    renderTasks();
  } catch (err) {
    toast(err.message, true);
  }
}

function renderTasks() {
  $("#task-list").replaceChildren(...state.tasks.map(renderTask));
  const n = state.tasks.length;
  $("#empty-state").hidden = n > 0;
  $("#task-count").textContent = n ? `${n} task${n === 1 ? "" : "s"}` : "";
}

function renderTask(task) {
  // Left column: a "date stamp" with the due day and month, or a dash when there is none.
  const due = task.dueDate ? new Date(task.dueDate) : null;
  const stamp = due
    ? el("div", { class: "stamp", "aria-hidden": "true" },
        el("span", { class: "day" }, fmtDay.format(due)),
        el("span", { class: "mon" }, fmtMon.format(due)))
    : el("div", { class: "stamp none", "aria-hidden": "true" }, el("span", { class: "day" }, "–"));

  const statusLabel = { ACTIVE: "Active", COMPLETED: "Completed", OVERDUE: "Overdue" }[task.status];
  const priorityLabel = { HIGH: "High", MEDIUM: "Medium", LOW: "Low" }[task.priority];
  const meta = el("div", { class: "task-meta" },
    el("span", { class: `status-${task.status}` }, statusLabel),
    el("span", { class: `priority-${task.priority}` }, `${priorityLabel} priority`),
    due && el("span", {}, `Due ${formatWhen(task.dueDate)}`),                 // TMA-F-023
    ...task.categories.map((c) => el("span", { class: "chip" }, c)));       // TMA-F-022

  const done = task.status === "COMPLETED";
  const actions = el("div", { class: "task-actions" },
    el("button", { type: "button", class: "btn link", onclick: () => toggleComplete(task) },
      done ? "Reopen" : "Complete"),
    el("button", { type: "button", class: "btn link", onclick: () => openTaskDialog(task) },
      "Edit"),
    el("button", { type: "button", class: "btn link", onclick: () => confirmDelete(task) },
      "Delete"));

  return el("li", { class: `task p-${task.priority} s-${task.status}` },
    stamp,
    el("div", {},
      el("h3", { class: "task-title" }, task.title),
      task.description && el("p", { class: "task-desc" }, task.description),
      meta),
    actions);
}

function openTaskDialog(task = null) {
  state.editingTaskId = task ? task.id : null;
  const form = $("#task-form");
  form.reset();
  $("#task-error").textContent = "";
  $("#task-dialog-title").textContent = task ? "Edit task" : "New task";
  $("#task-submit").textContent = task ? "Save changes" : "Create task";
  form.title.value = task?.title ?? "";
  form.description.value = task?.description ?? "";
  form.priority.value = task?.priority ?? "MEDIUM";
  // An overdue task is stored as ACTIVE, so the select shows "Active" for it.
  form.status.value = task?.status === "COMPLETED" ? "COMPLETED" : "ACTIVE";
  form.dueDate.value = toLocalInput(task?.dueDate);
  form.categories.value = (task?.categories ?? []).join(", ");
  $("#task-dialog").showModal();
  form.title.focus();
}

async function handleTaskSubmit(event) {
  event.preventDefault();
  const form = event.target;
  $("#task-error").textContent = "";

  // Client-side check for a quick message; the server validates again (never trust the client).
  if (!form.title.value.trim()) {
    $("#task-error").textContent = "Title is required.";
    form.title.focus();
    return;
  }
  const body = {
    title: form.title.value,
    description: form.description.value,
    priority: form.priority.value,             // TMA-F-020
    status: form.status.value,                 // TMA-F-021
    dueDate: fromLocalInput(form.dueDate.value),  // TMA-F-023 (null clears it)
    // "College, SE , " -> ["College", "SE"]   (TMA-F-022)
    categories: form.categories.value.split(",").map((s) => s.trim()).filter(Boolean),
  };

  try {
    if (state.editingTaskId === null) {
      await api("/api/tasks", { method: "POST", body });
      toast("Task created");
    } else {
      await api(`/api/tasks/${state.editingTaskId}`, { method: "PATCH", body });
      toast("Task saved");
    }
    $("#task-dialog").close();
    await refreshAll();
  } catch (err) {
    $("#task-error").textContent = err.message;
  }
}

async function toggleComplete(task) {
  const action = task.status === "COMPLETED" ? "reopen" : "complete";
  try {
    await api(`/api/tasks/${task.id}/${action}`, { method: "POST" });
    toast(action === "complete" ? "Task completed" : "Task reopened");
    await refreshAll();
  } catch (err) {
    toast(err.message, true);
  }
}

/** TMA-F-012: deletion only happens after the user confirms in a dialog. */
function confirmDelete(task) {
  const dialog = $("#confirm-dialog");
  $("#confirm-text").textContent = `"${task.title}" will be removed permanently.`;
  dialog.returnValue = "";
  dialog.showModal();
  dialog.addEventListener("close", async () => {
    if (dialog.returnValue !== "confirm") return;
    try {
      await api(`/api/tasks/${task.id}`, { method: "DELETE" });
      toast("Task deleted");
      await refreshAll();
    } catch (err) {
      toast(err.message, true);
    }
  }, { once: true });
}

/* ----------------------------------------------- 5. Dashboard summary */
/** TMA-F-033: active / overdue / completed counts, completion bar, due this week. */
async function loadSummary() {
  try {
    const { summary, dueSoon } = await api("/api/dashboard/summary");
    $("#count-active").textContent = summary.active;
    $("#count-overdue").textContent = summary.overdue;
    $("#count-completed").textContent = summary.completed;
    $("#progress-bar").style.width = `${summary.completionRate}%`;
    $("#progress-text").textContent = summary.total
      ? `${summary.completionRate}% of ${summary.total} tasks completed`
      : "No tasks yet.";
    $("#due-soon").replaceChildren(...(dueSoon.length
      ? dueSoon.map((t) => el("li", {}, t.title,
          el("span", { class: "when" }, formatWhen(t.dueDate))))
      : [el("li", { class: "hint" }, "Nothing due this week.")]));
  } catch (err) {
    toast(err.message, true);
  }
}

/* ---------------------------------------------------- 6. Categories */
/** TMA-F-022: load my categories and offer them as suggestions in the task form. */
async function loadCategories() {
  try {
    const { categories } = await api("/api/categories");
    state.categories = categories;
    $("#category-options").replaceChildren(
      ...categories.map((c) => el("option", { value: c.name })));
  } catch (err) {
    toast(err.message, true);
  }
}

/* ------------------------------------------------------ 7. App start */
/** Reload everything that a task change can affect. */
async function refreshAll() {
  await Promise.all([loadTasks(), loadSummary(), loadCategories()]);
}

async function startApp(user) {
  state.user = user;
  $("#auth-view").hidden = true;
  $("#app-view").hidden = false;
  $("#user-name").textContent = user.name;
  await refreshAll();
}

document.addEventListener("DOMContentLoaded", async () => {
  // Auth screen
  $("#tab-login").addEventListener("click", () => selectAuthTab("login"));
  $("#tab-register").addEventListener("click", () => selectAuthTab("register"));
  $("#login-form").addEventListener("submit", handleLogin);
  $("#register-form").addEventListener("submit", handleRegister);

  // App
  $("#btn-logout").addEventListener("click", handleLogout);
  $("#btn-new-task").addEventListener("click", () => openTaskDialog());
  $("#btn-empty-new").addEventListener("click", () => openTaskDialog());
  $("#task-form").addEventListener("submit", handleTaskSubmit);

  // Any [data-close] button closes its dialog
  document.querySelectorAll("[data-close]").forEach((btn) =>
    btn.addEventListener("click", () => btn.closest("dialog").close()));

  // Resume an existing session if the tab still has a valid token
  if (sessionStorage.getItem(TOKEN_KEY)) {
    try {
      const { user } = await api("/api/auth/me");
      await startApp(user);
      return;
    } catch { /* token invalid -> fall through to the login screen */ }
  }
  showAuth();
});
