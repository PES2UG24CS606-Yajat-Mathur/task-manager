/* =====================================================================
   Task Manager - front-end (User / Admin UI component, SAD 3.4)

   Plain JavaScript, no framework or build step. Structure:
     1. api()            - one function for every HTTP call (adds the token,
                           parses JSON, turns errors into exceptions)
     2. state            - the little bit of data the UI keeps in memory
     3. auth             - register / login / logout / resume session
     4. tasks            - list, create, edit
     5. wiring           - event listeners, started on DOMContentLoaded

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
  const statusLabel = { ACTIVE: "Active", COMPLETED: "Completed" }[task.status];
  const meta = el("div", { class: "task-meta" },
    el("span", { class: `status-${task.status}` }, statusLabel));

  const actions = el("div", { class: "task-actions" },
    el("button", { type: "button", class: "btn link", onclick: () => openTaskDialog(task) },
      "Edit"));

  return el("li", { class: `task s-${task.status}` },
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
  const body = { title: form.title.value, description: form.description.value };

  try {
    if (state.editingTaskId === null) {
      await api("/api/tasks", { method: "POST", body });
      toast("Task created");
    } else {
      await api(`/api/tasks/${state.editingTaskId}`, { method: "PATCH", body });
      toast("Task saved");
    }
    $("#task-dialog").close();
    await loadTasks();
  } catch (err) {
    $("#task-error").textContent = err.message;
  }
}

/* ------------------------------------------------------ 5. App start */
async function startApp(user) {
  state.user = user;
  $("#auth-view").hidden = true;
  $("#app-view").hidden = false;
  $("#user-name").textContent = user.name;
  await loadTasks();
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
