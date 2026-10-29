/* =====================================================================
   Task Manager - front-end (User / Admin UI component, SAD 3.4)

   Plain JavaScript, no framework or build step. Structure:
     1. api()            - one function for every HTTP call (adds the token,
                           parses JSON, turns errors into exceptions)
     2. state            - the little bit of data the UI keeps in memory
     3. auth             - register / login / logout / resume session
     4. tasks            - list, create, edit, complete, delete
     5. dashboard        - active / overdue / completed summary
     6. categories       - suggestions, filter options, sidebar chips
     7. notifications    - unread badge (polled), list, preferences
     8. admin            - users and security events (administrators only)
     9. wiring           - event listeners, started on DOMContentLoaded

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
  preferences: null,     // {notifications, defaultPriority, defaultSort} (TMA-F-041)
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
  clearInterval(notificationTimer);        // stop polling for notifications
  showAuth();
}

async function handleLogout() {
  try { await api("/api/auth/logout", { method: "POST" }); } catch { /* already invalid */ }
  endSession();
  toast("Logged out");
}

/* --------------------------------------------------------- 4. Tasks */
/** Read the filter form into a query string, e.g. "q=lab&status=OVERDUE&sort=priority". */
function filterQuery() {
  const params = new URLSearchParams();
  for (const [key, value] of new FormData($("#filters"))) {
    if (value) params.set(key, value);          // leave out "Any" (empty) choices
  }
  return params.toString();
}

async function loadTasks() {
  try {
    const data = await api(`/api/tasks?${filterQuery()}`);
    state.tasks = data.tasks;
    renderTasks();
  } catch (err) {
    toast(err.message, true);
  }
}

function renderTasks() {
  $("#task-list").replaceChildren(...state.tasks.map(renderTask));
  const n = state.tasks.length;
  // Is a search or filter active? (sort and order only reorder, they never hide tasks)
  const filtered = filterQuery().replace(/(^|&)(sort|order)=[^&]*/g, "") !== "";
  // The "add your first task" message is only for a truly empty list, not "no matches".
  $("#empty-state").hidden = n > 0 || filtered;
  $("#task-count").textContent = filtered
    ? `${n} matching task${n === 1 ? "" : "s"}`
    : (n ? `${n} task${n === 1 ? "" : "s"}` : "");
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
    task.nextReminder && el("span", {}, `Reminder ${formatWhen(task.nextReminder)}`),  // F-024
    ...task.categories.map((c) => el("span", { class: "chip" }, c)));       // TMA-F-022

  // TMA-NF-005: a screen reader hears "Delete Buy milk", not just "Delete" three times over
  const done = task.status === "COMPLETED";
  const actions = el("div", { class: "task-actions" },
    el("button", {
      type: "button", class: "btn link",
      "aria-label": `${done ? "Reopen" : "Complete"} ${task.title}`,
      onclick: () => toggleComplete(task),
    }, done ? "Reopen" : "Complete"),
    el("button", {
      type: "button", class: "btn link", "aria-label": `Edit ${task.title}`,
      onclick: () => openTaskDialog(task),
    }, "Edit"),
    el("button", {
      type: "button", class: "btn link", "aria-label": `Delete ${task.title}`,
      onclick: () => confirmDelete(task),
    }, "Delete"));

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
  // New tasks start with the default priority from Preferences (TMA-F-041)
  form.priority.value = task?.priority ?? state.preferences?.defaultPriority ?? "MEDIUM";
  // An overdue task is stored as ACTIVE, so the select shows "Active" for it.
  form.status.value = task?.status === "COMPLETED" ? "COMPLETED" : "ACTIVE";
  form.dueDate.value = toLocalInput(task?.dueDate);
  form.categories.value = (task?.categories ?? []).join(", ");
  $("#t-reminder-note").textContent = task?.nextReminder
    ? `Next reminder: ${formatWhen(task.nextReminder)}` : "";
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
  // "15 minutes before" only makes sense with a due date (the server checks this too)
  const reminder = form.reminder.value;      // "" = no new reminder, else minutes before
  if (reminder !== "" && !form.dueDate.value) {
    $("#task-error").textContent = "Set a due date before choosing a reminder.";
    form.dueDate.focus();
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
      // New task: the reminder is created in the same request (one transaction)
      if (reminder !== "") body.minutesBefore = Number(reminder);
      await api("/api/tasks", { method: "POST", body });
      toast("Task created");
    } else {
      // Existing task: save the fields, then add the extra reminder (TMA-F-024)
      await api(`/api/tasks/${state.editingTaskId}`, { method: "PATCH", body });
      if (reminder !== "") {
        await api(`/api/tasks/${state.editingTaskId}/reminders`, {
          method: "POST", body: { minutesBefore: Number(reminder) },
        });
      }
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
/**
 * TMA-F-022 / F-031: load my categories and show them in three places:
 *   the task form suggestions, the Category filter, and the sidebar chips.
 */
async function loadCategories() {
  try {
    const { categories } = await api("/api/categories");
    state.categories = categories;
    $("#category-options").replaceChildren(
      ...categories.map((c) => el("option", { value: c.name })));

    // Filter dropdown: keep the current choice if that category still exists
    const select = $("#f-category");
    const current = select.value;
    select.replaceChildren(el("option", { value: "" }, "Any"),
      ...categories.map((c) => el("option", { value: c.name }, c.name)));
    select.value = categories.some((c) => c.name === current) ? current : "";

    // Sidebar chips work as a quick filter: click to filter, click again to clear
    $("#category-list").replaceChildren(...(categories.length
      ? categories.map((c) => el("li", {}, el("button", {
          type: "button", class: "chip", "aria-pressed": String(select.value === c.name),
          onclick: () => {
            select.value = select.value === c.name ? "" : c.name;
            loadCategories();
            loadTasks();
          },
        }, `${c.name} (${c.taskCount})`)))
      : [el("li", { class: "hint" }, "Add categories when you create a task.")]));
  } catch (err) {
    toast(err.message, true);
  }
}

/* ------------------------------------------------- 7a. Notifications */
// The badge is refreshed every 30 s. Asking the server for notifications also makes it
// deliver any reminder that has just become due (the "lazy trigger" in notifications.py).
let notificationTimer;

async function loadNotifications() {
  try {
    const { notifications, unread } = await api("/api/notifications");
    const badge = $("#notif-count");
    badge.textContent = unread;
    badge.hidden = unread === 0;
    // The badge is a red dot to the eye; say the number out loud for screen readers
    $("#btn-notifications").setAttribute("aria-label", `Notifications, ${unread} unread`);
    $("#notif-list").replaceChildren(...(notifications.length
      ? notifications.map((n) => el("li", { class: n.read ? "" : "unread" },
          n.taskDueDate ? `${n.message} is due ${formatWhen(n.taskDueDate)}` : n.message,
          el("time", { datetime: n.createdAt }, `Sent ${formatWhen(n.createdAt)}`)))
      : [el("li", { class: "hint" }, "No notifications. Reminders you set will appear here.")]));
  } catch {
    /* polling failures stay silent; the next poll tries again */
  }
}

async function openNotifications() {
  await loadNotifications();
  $("#notif-dialog").showModal();
}

async function markAllRead() {
  try {
    await api("/api/notifications/read-all", { method: "POST" });
    await loadNotifications();
  } catch (err) {
    toast(err.message, true);
  }
}

/* --------------------------------------------------- 7b. Preferences */
async function loadPreferences() {
  const { preferences } = await api("/api/preferences");
  state.preferences = preferences;
  return preferences;
}

async function openPreferences() {
  try {
    const p = await loadPreferences();
    $("#p-inapp").checked = p.notifications.in_app;
    $("#p-email").checked = p.notifications.email;
    $("#p-priority").value = p.defaultPriority;
    $("#p-sort").value = p.defaultSort;
    $("#prefs-dialog").showModal();
  } catch (err) {
    toast(err.message, true);
  }
}

async function handlePrefsSubmit(event) {
  event.preventDefault();
  try {
    const { preferences } = await api("/api/preferences", {
      method: "PUT",
      body: {
        notifications: { in_app: $("#p-inapp").checked, email: $("#p-email").checked },
        defaultPriority: $("#p-priority").value,
        defaultSort: $("#p-sort").value,
      },
    });
    state.preferences = preferences;
    $("#f-sort").value = preferences.defaultSort;   // apply the new default sort now
    $("#prefs-dialog").close();
    toast("Preferences saved");
    await loadTasks();
  } catch (err) {
    toast(err.message, true);
  }
}

/* ---------------------------------------------------------- 8. Admin */
// TMA-F-042. Hiding the Admin button from normal users is only for convenience:
// every /api/admin call is refused by the server (403) unless the user is an admin.
async function openAdmin() {
  $(".tasks").hidden = true;
  $("#admin-view").hidden = false;
  await loadAdmin();
  $("#admin-title").focus();
}

function closeAdmin() {
  $("#admin-view").hidden = true;
  $(".tasks").hidden = false;
}

async function loadAdmin() {
  try {
    const [{ users }, { events }] = await Promise.all([
      api("/api/admin/users"), api("/api/admin/security-events?limit=25"),
    ]);
    $("#admin-users").replaceChildren(...users.map((u) => {
      const self = u.id === state.user.id;          // no buttons on my own row
      return el("tr", {},
        el("td", {}, u.name), el("td", {}, u.email), el("td", {}, u.role),
        el("td", {}, u.taskCount), el("td", {}, u.isActive ? "Active" : "Deactivated"),
        el("td", {}, self ? el("span", { class: "hint" }, "You") : [
          el("button", {
            type: "button", class: "btn link",
            onclick: () => adminUpdate(u.id, { isActive: !u.isActive }),
          }, u.isActive ? "Deactivate" : "Activate"),
          el("button", {
            type: "button", class: "btn link",
            onclick: () => adminUpdate(u.id, { role: u.role === "admin" ? "user" : "admin" }),
          }, u.role === "admin" ? "Make user" : "Make admin"),
        ]));
    }));
    $("#admin-events").replaceChildren(...events.map((e) => el("tr", {},
      el("td", {}, formatWhen(e.createdAt)), el("td", {}, e.type),
      el("td", {}, e.email ?? ""), el("td", {}, e.ip ?? ""))));
  } catch (err) {
    toast(err.message, true);
  }
}

async function adminUpdate(userId, changes) {
  try {
    await api(`/api/admin/users/${userId}`, { method: "PATCH", body: changes });
    toast("User updated");
    await loadAdmin();
  } catch (err) {
    toast(err.message, true);
  }
}

/* ------------------------------------------------------ 9. App start */
/** Reload everything that a task change can affect. */
async function refreshAll() {
  await Promise.all([loadTasks(), loadSummary(), loadCategories()]);
}

async function startApp(user) {
  state.user = user;
  $("#auth-view").hidden = true;
  $("#app-view").hidden = false;
  $("#user-name").textContent = user.name;
  $("#btn-admin").hidden = user.role !== "admin";
  closeAdmin();

  try {
    const prefs = await loadPreferences();
    $("#f-sort").value = prefs.defaultSort;          // the list opens in my default order
  } catch { /* keep the built-in defaults */ }
  await refreshAll();
  await loadNotifications();
  clearInterval(notificationTimer);
  notificationTimer = setInterval(loadNotifications, 30000);
}

/** Wait until the user stops typing for `ms` milliseconds before calling fn. */
function debounce(fn, ms) {
  let timer;
  return (...args) => { clearTimeout(timer); timer = setTimeout(() => fn(...args), ms); };
}

document.addEventListener("DOMContentLoaded", async () => {
  // Auth screen
  $("#tab-login").addEventListener("click", () => selectAuthTab("login"));
  $("#tab-register").addEventListener("click", () => selectAuthTab("register"));
  $("#login-form").addEventListener("submit", handleLogin);
  $("#register-form").addEventListener("submit", handleRegister);

  // App
  $("#btn-logout").addEventListener("click", handleLogout);
  $("#btn-notifications").addEventListener("click", openNotifications);
  $("#btn-read-all").addEventListener("click", markAllRead);
  $("#btn-preferences").addEventListener("click", openPreferences);
  $("#prefs-form").addEventListener("submit", handlePrefsSubmit);
  $("#btn-admin").addEventListener("click", openAdmin);
  $("#btn-admin-close").addEventListener("click", closeAdmin);
  $("#btn-new-task").addEventListener("click", () => openTaskDialog());
  $("#btn-empty-new").addEventListener("click", () => openTaskDialog());
  $("#task-form").addEventListener("submit", handleTaskSubmit);

  // Search / filter / sort: dropdowns reload at once, typing reloads after a short pause
  $("#filters").addEventListener("submit", (e) => e.preventDefault());
  $("#filters").addEventListener("change", () => { loadTasks(); loadCategories(); });
  $("#f-q").addEventListener("input", debounce(loadTasks, 250));

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
