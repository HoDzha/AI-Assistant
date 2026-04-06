const API_BASE_URL = "http://127.0.0.1:8000/api";
const TASKS_API_URL = `${API_BASE_URL}/tasks`;
const TASKS_PER_PAGE = 5;
const today = new Date().toISOString().split("T")[0];
const statusLabels = { todo: "К выполнению", in_progress: "В процессе", blocked: "Заблокировано", done: "Завершено" };
const projectStatusLabels = { planned: "Планируется", in_progress: "В работе", attention_needed: "Требует внимания", done: "Завершено" };
const priorityLabels = { low: "Низкий", medium: "Средний", high: "Высокий", critical: "Критический" };

const state = {
  tasks: [],
  counter: 1,
  currentPage: 1,
  lastAnalysis: null,
  editingTaskId: null,
  filters: { search: "", status: "all", project: "all", showArchived: false },
};

const elements = {
  ctxDate: document.getElementById("ctx-date"),
  ctxHours: document.getElementById("ctx-hours"),
  ctxName: document.getElementById("ctx-name"),
  taskCount: document.getElementById("task-count"),
  taskSummary: document.getElementById("task-summary"),
  taskList: document.getElementById("task-list"),
  taskPagination: document.getElementById("task-pagination"),
  taskSearch: document.getElementById("task-search"),
  taskStatusFilter: document.getElementById("task-status-filter"),
  taskProjectFilter: document.getElementById("task-project-filter"),
  taskShowArchived: document.getElementById("task-show-archived"),
  clearFiltersButton: document.getElementById("clear-filters-button"),
  addTaskButton: document.getElementById("add-task-button"),
  clearTaskButton: document.getElementById("clear-task-button"),
  loadDemoButton: document.getElementById("load-demo-button"),
  analyzeButton: document.getElementById("analyze-button"),
  loadingState: document.getElementById("loading-state"),
  errorState: document.getElementById("error-state"),
  taskFormTitle: document.getElementById("task-form-title"),
  taskFormDescription: document.getElementById("task-form-description"),
  taskFormMode: document.getElementById("task-form-mode"),
  resultsSection: document.getElementById("results-section"),
  overviewSummary: document.getElementById("overview-summary"),
  overviewMeta: document.getElementById("overview-meta"),
  prioritiesOutput: document.getElementById("priorities-output"),
  planOutput: document.getElementById("plan-output"),
  projectsOutput: document.getElementById("projects-output"),
  recommendationsOutput: document.getElementById("recommendations-output"),
  exportActions: document.getElementById("export-actions"),
  exportCsvButton: document.getElementById("export-csv-button"),
  exportPdfButton: document.getElementById("export-pdf-button"),
};

const formFieldIds = [
  "task-title",
  "task-project",
  "task-client",
  "task-github",
  "task-deadline",
  "task-hours",
  "task-dependencies",
  "task-tags",
  "task-description",
  "task-notes",
];

elements.ctxDate.value = today;
elements.addTaskButton.addEventListener("click", submitTaskForm);
elements.clearTaskButton.addEventListener("click", clearTaskForm);
elements.loadDemoButton.addEventListener("click", loadDemoData);
elements.analyzeButton.addEventListener("click", analyzeTasks);
elements.exportCsvButton.addEventListener("click", exportResultsToCsv);
elements.exportPdfButton.addEventListener("click", exportResultsToPdf);
elements.taskSearch.addEventListener("input", (event) => updateFilter("search", event.target.value.trim().toLowerCase()));
elements.taskStatusFilter.addEventListener("change", (event) => updateFilter("status", event.target.value));
elements.taskProjectFilter.addEventListener("change", (event) => updateFilter("project", event.target.value));
elements.taskShowArchived.addEventListener("change", (event) => updateFilter("showArchived", event.target.checked));
elements.clearFiltersButton.addEventListener("click", resetFilters);

function updateFilter(key, value) {
  state.filters[key] = value;
  state.currentPage = 1;
  renderTaskList();
}

function resetFilters() {
  state.filters = { search: "", status: "all", project: "all", showArchived: false };
  elements.taskSearch.value = "";
  elements.taskStatusFilter.value = "all";
  elements.taskProjectFilter.value = "all";
  elements.taskShowArchived.checked = false;
  state.currentPage = 1;
  renderTaskList();
}

async function initializeApp() {
  renderTaskList();
  try {
    const data = await requestJson(TASKS_API_URL);
    state.tasks = Array.isArray(data.tasks) ? data.tasks : [];
    state.counter = getNextTaskCounter(state.tasks);
    renderTaskList();
    showError("");
  } catch (error) {
    renderTaskList();
    showError(`Не удалось загрузить сохраненные задачи: ${error.message}`);
  }
}

function buildTaskFromForm(taskId) {
  const title = document.getElementById("task-title").value.trim();
  const type = document.getElementById("task-type").value;
  const deadline = document.getElementById("task-deadline").value;
  const githubUrl = document.getElementById("task-github").value.trim();
  if (!title) throw new Error("Укажи название задачи.");
  if (!type) throw new Error("Выбери тип задачи.");
  if (!deadline) throw new Error("Укажи дедлайн.");
  if (githubUrl && !isValidUrl(githubUrl)) throw new Error("GitHub-ссылка должна быть корректным URL.");
  const currentTask = state.editingTaskId ? state.tasks.find((task) => task.id === state.editingTaskId) : null;
  return {
    id: taskId,
    title,
    description: document.getElementById("task-description").value.trim() || null,
    project: document.getElementById("task-project").value.trim() || null,
    client: document.getElementById("task-client").value.trim() || null,
    github_url: githubUrl || null,
    type,
    deadline,
    estimated_hours: readOptionalNumber("task-hours"),
    importance: document.getElementById("task-importance").value,
    status: document.getElementById("task-status").value,
    archived: currentTask?.archived || false,
    tags: splitList(document.getElementById("task-tags").value),
    dependencies: splitList(document.getElementById("task-dependencies").value),
    notes: document.getElementById("task-notes").value.trim() || null,
  };
}

async function submitTaskForm() {
  try {
    if (state.editingTaskId) {
      const payload = buildTaskFromForm(state.editingTaskId);
      const saved = await requestJson(`${TASKS_API_URL}/${encodeURIComponent(state.editingTaskId)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      replaceTaskInState(saved);
    } else {
      const payload = buildTaskFromForm(buildTaskId());
      const saved = await requestJson(TASKS_API_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      state.tasks.push(saved);
      state.counter = getNextTaskCounter(state.tasks);
    }
    clearTaskForm();
    renderTaskList();
    showError("");
  } catch (error) {
    showError(error.message);
  }
}

function clearTaskForm() {
  formFieldIds.forEach((id) => {
    document.getElementById(id).value = "";
  });
  document.getElementById("task-type").value = "";
  document.getElementById("task-importance").value = "medium";
  document.getElementById("task-status").value = "todo";
  setEditingTask(null);
}

function setEditingTask(task) {
  state.editingTaskId = task ? task.id : null;
  elements.taskFormTitle.textContent = task ? "Редактировать задачу" : "Добавить задачу";
  elements.taskFormDescription.textContent = task
    ? `Изменения будут сохранены для ${task.id}.`
    : "Используй одну форму для создания и редактирования задач.";
  elements.taskFormMode.textContent = task ? "Редактирование" : "Новая";
  elements.addTaskButton.textContent = task ? "Сохранить изменения" : "Добавить задачу";
  elements.clearTaskButton.textContent = task ? "Отменить редактирование" : "Очистить поля";
}

function fillTaskForm(task) {
  document.getElementById("task-title").value = task.title;
  document.getElementById("task-project").value = task.project || "";
  document.getElementById("task-client").value = task.client || "";
  document.getElementById("task-github").value = task.github_url || "";
  document.getElementById("task-type").value = task.type;
  document.getElementById("task-deadline").value = task.deadline;
  document.getElementById("task-hours").value = task.estimated_hours ?? "";
  document.getElementById("task-importance").value = task.importance;
  document.getElementById("task-status").value = task.status;
  document.getElementById("task-dependencies").value = task.dependencies.join(", ");
  document.getElementById("task-tags").value = task.tags.join(", ");
  document.getElementById("task-description").value = task.description || "";
  document.getElementById("task-notes").value = task.notes || "";
  setEditingTask(task);
}

function renderTaskList() {
  syncProjectFilterOptions();
  const visibleTasks = getVisibleTasks();
  const totalPages = getTotalPages(visibleTasks);
  state.currentPage = Math.min(state.currentPage, totalPages);
  elements.taskCount.textContent = String(visibleTasks.length);
  elements.taskSummary.textContent = `${state.tasks.filter((task) => !task.archived).length} активных · ${state.tasks.filter((task) => task.archived).length} в архиве`;
  if (!visibleTasks.length) {
    elements.taskList.innerHTML =
      '<div class="empty-state">Нет задач под текущие фильтры. Попробуй сбросить фильтры или добавить новую задачу.</div>';
    elements.taskPagination.innerHTML = "";
    return;
  }

  const start = (state.currentPage - 1) * TASKS_PER_PAGE;
  const pageTasks = visibleTasks.slice(start, start + TASKS_PER_PAGE);
  elements.taskList.innerHTML = "";

  pageTasks.forEach((task) => {
    const item = document.createElement("article");
    item.className = `task-item${task.archived ? " task-item-archived" : ""}`;
    item.innerHTML = `
      <div class="task-top">
        <div>
          <h3 class="task-title">${escapeHtml(task.title)}</h3>
          <div class="meta-row">
            <span class="badge status-${task.status}">${statusLabels[task.status]}</span>
            <span class="badge priority-${task.importance}">${priorityLabels[task.importance]}</span>
            <span class="badge">${escapeHtml(task.type)}</span>
            ${task.archived ? '<span class="badge archived-badge">Архив</span>' : ""}
          </div>
        </div>
        <div class="task-actions">
          <button class="action-button" type="button" data-action="edit">Редактировать</button>
          <button class="action-button" type="button" data-action="duplicate">Дубликат</button>
          <button class="action-button" type="button" data-action="archive">${task.archived ? "Вернуть" : "В архив"}</button>
          <button class="action-button danger-action" type="button" data-action="delete">Удалить</button>
        </div>
      </div>
      <div class="task-body">
        <p class="task-copy">${escapeHtml(task.project || "Без проекта")} · ${escapeHtml(task.client || "Клиент не указан")} · дедлайн ${escapeHtml(task.deadline)}</p>
        <div class="task-inline-meta">
          <span>${task.estimated_hours ? `${task.estimated_hours} ч` : "Без оценки"}</span>
          <label class="inline-status-control">
            <span>Статус</span>
            <select class="task-status-select" data-action="status">${buildStatusOptions(task.status)}</select>
          </label>
        </div>
        ${task.description ? `<p class="task-copy">${escapeHtml(task.description)}</p>` : ""}
        ${task.tags.length ? `<div class="meta-row compact-meta">${task.tags.map((tag) => `<span class="badge subtle-badge">#${escapeHtml(tag)}</span>`).join("")}</div>` : ""}
        ${buildSafeExternalLink(task.github_url, "Открыть GitHub")}
      </div>
    `;
    item.querySelector("[data-action='edit']").addEventListener("click", () => {
      fillTaskForm(task);
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
    item.querySelector("[data-action='duplicate']").addEventListener("click", () => duplicateTask(task));
    item.querySelector("[data-action='archive']").addEventListener("click", () => toggleTaskArchive(task));
    item.querySelector("[data-action='delete']").addEventListener("click", () => removeTask(task.id));
    item.querySelector("[data-action='status']").addEventListener("change", (event) => updateTask(task.id, { status: event.target.value }));
    elements.taskList.appendChild(item);
  });

  renderTaskPagination(totalPages);
}

function getVisibleTasks() {
  return state.tasks.filter((task) => {
    if (!state.filters.showArchived && task.archived) return false;
    if (state.filters.status !== "all" && task.status !== state.filters.status) return false;
    if (state.filters.project !== "all" && (task.project || "Без проекта") !== state.filters.project) return false;
    if (!state.filters.search) return true;
    const haystack = [
      task.id,
      task.title,
      task.project || "",
      task.client || "",
      task.type,
      task.description || "",
      task.notes || "",
      task.tags.join(" "),
    ].join(" ").toLowerCase();
    return haystack.includes(state.filters.search);
  });
}

function syncProjectFilterOptions() {
  const currentValue = state.filters.project;
  const projects = Array.from(new Set(state.tasks.map((task) => task.project || "Без проекта")))
    .sort((left, right) => left.localeCompare(right, "ru"));
  elements.taskProjectFilter.innerHTML = '<option value="all">Все проекты</option>';
  projects.forEach((project) => {
    const option = document.createElement("option");
    option.value = project;
    option.textContent = project;
    elements.taskProjectFilter.appendChild(option);
  });
  if (projects.includes(currentValue)) {
    elements.taskProjectFilter.value = currentValue;
  } else {
    state.filters.project = "all";
    elements.taskProjectFilter.value = "all";
  }
}

function buildStatusOptions(selectedStatus) {
  return Object.entries(statusLabels)
    .map(([value, label]) => `<option value="${value}"${value === selectedStatus ? " selected" : ""}>${label}</option>`)
    .join("");
}

function renderTaskPagination(totalPages) {
  if (totalPages <= 1) {
    elements.taskPagination.innerHTML = "";
    return;
  }
  elements.taskPagination.innerHTML = "";
  elements.taskPagination.append(
    buildPaginationButton("Назад", state.currentPage === 1, () => { state.currentPage -= 1; renderTaskList(); }),
    Object.assign(document.createElement("span"), { className: "pagination-info", textContent: `Страница ${state.currentPage} из ${totalPages}` }),
    buildPaginationButton("Вперед", state.currentPage === totalPages, () => { state.currentPage += 1; renderTaskList(); })
  );
}

function buildPaginationButton(label, disabled, onClick) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "button ghost pagination-button";
  button.textContent = label;
  button.disabled = disabled;
  button.addEventListener("click", onClick);
  return button;
}

async function updateTask(taskId, changes) {
  const existingTask = state.tasks.find((task) => task.id === taskId);
  if (!existingTask) return;
  try {
    const saved = await requestJson(`${TASKS_API_URL}/${encodeURIComponent(taskId)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...existingTask, ...changes }),
    });
    replaceTaskInState(saved);
    if (state.editingTaskId === taskId) fillTaskForm(saved);
    renderTaskList();
    showError("");
  } catch (error) {
    showError(error.message);
  }
}

async function duplicateTask(task) {
  try {
    const payload = { ...task, id: buildTaskId(), title: `${task.title} (копия)`, archived: false };
    const saved = await requestJson(TASKS_API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    state.tasks.push(saved);
    state.counter = getNextTaskCounter(state.tasks);
    state.currentPage = getTotalPages(getVisibleTasks());
    renderTaskList();
    showError("");
  } catch (error) {
    showError(error.message);
  }
}

async function toggleTaskArchive(task) {
  await updateTask(task.id, { archived: !task.archived });
}

async function removeTask(taskId) {
  try {
    await requestJson(`${TASKS_API_URL}/${encodeURIComponent(taskId)}`, { method: "DELETE" });
    state.tasks = state.tasks.filter((task) => task.id !== taskId);
    if (state.editingTaskId === taskId) clearTaskForm();
    if ((state.currentPage - 1) * TASKS_PER_PAGE >= getVisibleTasks().length && state.currentPage > 1) {
      state.currentPage -= 1;
    }
    renderTaskList();
    showError("");
  } catch (error) {
    showError(error.message);
  }
}

async function analyzeTasks() {
  const activeTasks = state.tasks.filter((task) => !task.archived);
  if (!activeTasks.length) {
    showError("Добавь хотя бы одну активную задачу перед анализом.");
    return;
  }
  setLoading(true);
  showError("");
  try {
    const data = await requestJson(`${API_BASE_URL}/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        user_context: {
          current_date: elements.ctxDate.value || today,
          working_hours_per_day: Number(elements.ctxHours.value) || 6,
          user_name: elements.ctxName.value.trim() || null,
          work_days: ["Mon", "Tue", "Wed", "Thu", "Fri"],
        },
        tasks: activeTasks,
      }),
    });
    state.lastAnalysis = data;
    renderResults(data);
  } catch (error) {
    showError(error.message);
  } finally {
    setLoading(false);
  }
}

function renderResults(data) {
  elements.resultsSection.classList.remove("hidden");
  elements.exportActions.classList.remove("hidden");
  elements.overviewSummary.textContent = data.overview.summary;
  elements.overviewMeta.textContent = `${data.overview.total_tasks} задач · ${data.overview.total_estimated_hours} ч · ${data.overview.working_hours_per_day} ч в день`;
  renderPriorities(data.prioritized_tasks);
  renderPlan(data.day_plan);
  renderProjects(data.project_summaries);
  renderRecommendations(data.recommendations);
  elements.resultsSection.scrollIntoView({ behavior: "smooth", block: "start" });
}

function renderPriorities(items) {
  if (!items.length) {
    elements.prioritiesOutput.innerHTML = '<div class="empty-state">Нет данных по приоритетам.</div>';
    return;
  }
  elements.prioritiesOutput.innerHTML = "";
  items.forEach((item) => {
    const card = document.createElement("article");
    card.className = "priority-item";
    card.innerHTML = `
      <div class="priority-top">
        <div>
          <h3 class="priority-title">${item.recommended_order}. ${escapeHtml(item.title)}</h3>
          <div class="meta-row">
            <span class="badge priority-${item.ai_priority}">${priorityLabels[item.ai_priority]}</span>
            <span class="badge status-${item.status}">${statusLabels[item.status]}</span>
            <span class="badge">${escapeHtml(item.recommended_day)}</span>
          </div>
        </div>
      </div>
      <p>${escapeHtml(item.priority_reason)}</p>
      <p>Слот: ${escapeHtml(item.recommended_time_block)} · Дедлайн: ${escapeHtml(item.deadline)} · До срока: ${item.days_until_deadline} дн.</p>
      ${item.risk ? `<p>Риск: ${escapeHtml(item.risk)}</p>` : ""}
      ${buildSafeExternalLink(item.github_url, "GitHub проекта")}
    `;
    elements.prioritiesOutput.appendChild(card);
  });
}

function renderPlan(items) {
  if (!items.length) {
    elements.planOutput.innerHTML = '<div class="empty-state">План пока не сформирован.</div>';
    return;
  }
  elements.planOutput.innerHTML = "";
  items.forEach((item) => {
    const card = document.createElement("article");
    card.className = "plan-item";
    card.innerHTML = `<h3 class="priority-title">${escapeHtml(item.day_label)}${item.date ? ` · ${escapeHtml(item.date)}` : ""}</h3><p>Запланировано ${item.total_planned_hours} ч.</p><ul class="plan-task-list">${item.tasks.map((task) => `<li>${escapeHtml(task.title)} · ${task.planned_hours} ч · ${statusLabels[task.status]}</li>`).join("")}</ul>`;
    elements.planOutput.appendChild(card);
  });
}

function renderProjects(items) {
  if (!items.length) {
    elements.projectsOutput.innerHTML = '<div class="empty-state">Проекты не найдены.</div>';
    return;
  }
  elements.projectsOutput.innerHTML = "";
  items.forEach((item) => {
    const card = document.createElement("article");
    card.className = "project-item";
    card.innerHTML = `
      <div class="project-top">
        <div>
          <h3 class="project-title">${escapeHtml(item.project_name)}</h3>
          <div class="meta-row">
            <span class="badge project-${item.overall_status}">${projectStatusLabels[item.overall_status]}</span>
            <span class="badge">${item.total_tasks} задач</span>
          </div>
        </div>
      </div>
      <p>Todo: ${item.todo_count} · In progress: ${item.in_progress_count} · Blocked: ${item.blocked_count} · Done: ${item.done_count}</p>
      ${buildSafeExternalLink(item.github_url, "Открыть репозиторий")}
    `;
    elements.projectsOutput.appendChild(card);
  });
}

function renderRecommendations(items) {
  if (!items.length) {
    elements.recommendationsOutput.innerHTML = "<li>Рекомендации отсутствуют.</li>";
    return;
  }
  elements.recommendationsOutput.innerHTML = "";
  items.forEach((item) => {
    const listItem = document.createElement("li");
    listItem.textContent = item;
    elements.recommendationsOutput.appendChild(listItem);
  });
}

function buildSafeExternalLink(url, label) {
  if (!url || !isValidUrl(url)) return "";
  return `<a class="github-link" href="${escapeHtml(url)}" target="_blank" rel="noreferrer">${escapeHtml(label)}</a>`;
}

function exportResultsToCsv() {
  if (!state.lastAnalysis) {
    showError("Сначала выполни анализ, потом экспортируй результат.");
    return;
  }
  const lines = [
    ["Summary", state.lastAnalysis.overview.summary],
    [],
    ["Recommended order", "Title", "Project", "Priority", "Status", "Deadline", "Reason", "Risk"],
    ...state.lastAnalysis.prioritized_tasks.map((task) => [
      task.recommended_order, task.title, task.project || "", task.ai_priority, task.status, task.deadline, task.priority_reason, task.risk || "",
    ]),
    [],
    ["Recommendations"],
    ...state.lastAnalysis.recommendations.map((item) => [item]),
  ];
  const csvContent = lines.map((row) => row.map((value) => `"${String(value ?? "").replaceAll('"', '""').replaceAll("\r", "").replaceAll("\n", "\\n")}"`).join(",")).join("\n");
  // UTF-8 BOM для корректного открытия в Excel на Windows
  const bom = new Uint8Array([0xef, 0xbb, 0xbf]);
  const blob = new Blob([bom, csvContent], { type: "text/csv;charset=utf-8" });
  downloadBlob(blob, "analysis-results.csv");
}

function exportResultsToPdf() {
  if (!state.lastAnalysis) {
    showError("Сначала выполни анализ, потом экспортируй результат.");
    return;
  }

  const activeTasks = state.tasks.filter((task) => !task.archived);
  if (!activeTasks.length) {
    showError("Нет активных задач для экспорта.");
    return;
  }

  const body = JSON.stringify({
    user_context: {
      current_date: elements.ctxDate.value || today,
      working_hours_per_day: Number(elements.ctxHours.value) || 6,
      user_name: elements.ctxName.value.trim() || null,
      work_days: ["Mon", "Tue", "Wed", "Thu", "Fri"],
    },
    tasks: activeTasks,
  });

  fetch(`${API_BASE_URL}/export-pdf`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body,
  })
    .then((response) => {
      if (!response.ok) throw new Error("Backend вернул ошибку при генерации PDF.");
      return response.blob();
    })
    .then((blob) => {
      downloadBlob(blob, "freelance-flow-report.pdf");
    })
    .catch((error) => {
      showError(error.message);
    });
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

async function loadDemoData() {
  const demoTasks = [
    { id: "task-001", title: "Исправить баг в форме заявки", description: "Починить валидацию email и отправку в CRM.", project: "Client Beta CRM", client: "Beta", github_url: "https://github.com/example/client-beta-crm", type: "development", deadline: addDays(today, 1), estimated_hours: 2, importance: "critical", status: "in_progress", archived: false, tags: ["backend", "crm"], dependencies: [], notes: "Ошибка влияет на лиды." },
    { id: "task-002", title: "Подготовить текст для лендинга", description: "Сделать первый экран и блок преимуществ.", project: "Alpha Landing", client: "Alpha", github_url: "https://github.com/example/alpha-landing", type: "content", deadline: addDays(today, 2), estimated_hours: 3, importance: "high", status: "todo", archived: false, tags: ["copywriting"], dependencies: [], notes: "Сначала уточнить tone of voice." },
    { id: "task-003", title: "Собрать недельный рекламный отчет", description: "Сводка по метрикам и выводам.", project: "Gamma Ads", client: "Gamma", github_url: "https://github.com/example/gamma-ads", type: "analytics", deadline: addDays(today, 4), estimated_hours: 2.5, importance: "medium", status: "todo", archived: false, tags: ["analytics"], dependencies: [], notes: "Нужны данные из Google Sheets." },
    { id: "task-004", title: "Подготовить дизайн обновленного дашборда", description: "Собрать макет для нового блока статистики.", project: "Delta Dashboard", client: "Delta", github_url: "https://github.com/example/delta-dashboard", type: "design", deadline: addDays(today, 6), estimated_hours: 5, importance: "medium", status: "todo", archived: false, tags: ["design", "ui"], dependencies: [], notes: "Согласовать с заказчиком до конца недели." },
    { id: "task-005", title: "Обновить план спринта", description: "Уточнить приоритеты и зависимости по команде.", project: "Internal Ops", client: "Internal", github_url: "https://github.com/example/internal-ops", type: "management", deadline: addDays(today, 3), estimated_hours: 1.5, importance: "high", status: "blocked", archived: false, tags: ["planning"], dependencies: ["task-003"], notes: "Ждем входные данные по отчету." },
    { id: "task-006", title: "Проверить новую onboarding-цепочку", description: "Провести ручное тестирование писем и ссылок.", project: "Product Emails", client: "Omega", github_url: "https://github.com/example/product-emails", type: "analytics", deadline: addDays(today, 5), estimated_hours: 2, importance: "low", status: "todo", archived: false, tags: ["qa", "email"], dependencies: [], notes: "После релиза сверить клики." },
  ];
  try {
    const data = await requestJson(TASKS_API_URL, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tasks: demoTasks }),
    });
    state.tasks = Array.isArray(data.tasks) ? data.tasks : demoTasks;
    state.counter = getNextTaskCounter(state.tasks);
    state.currentPage = 1;
    clearTaskForm();
    renderTaskList();
    showError("");
  } catch (error) {
    showError(error.message);
  }
}

function replaceTaskInState(updatedTask) {
  state.tasks = state.tasks.map((task) => (task.id === updatedTask.id ? updatedTask : task));
}

function setLoading(isLoading) {
  elements.loadingState.classList.toggle("hidden", !isLoading);
  elements.analyzeButton.disabled = isLoading;
}

function showError(message) {
  if (!message) {
    elements.errorState.classList.add("hidden");
    elements.errorState.textContent = "";
    return;
  }
  elements.errorState.classList.remove("hidden");
  elements.errorState.textContent = message;
}

function readOptionalNumber(elementId) {
  const value = document.getElementById(elementId).value.trim();
  return value ? Number(value) : null;
}

const splitList = (value) => value.split(",").map((item) => item.trim()).filter(Boolean);

function isValidUrl(value) {
  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:";
  } catch {
    return false;
  }
}

function addDays(dateString, days) {
  const date = new Date(dateString);
  date.setDate(date.getDate() + days);
  return date.toISOString().split("T")[0];
}

function getTotalPages(tasks) {
  return Math.max(1, Math.ceil(tasks.length / TASKS_PER_PAGE));
}

function buildTaskId() {
  let candidate = "";
  do {
    candidate = `task-${String(state.counter).padStart(3, "0")}`;
    state.counter += 1;
  } while (state.tasks.some((task) => task.id === candidate));
  return candidate;
}

function getNextTaskCounter(tasks) {
  return tasks.reduce((maxValue, task) => {
    const match = /^task-(\d+)$/.exec(task.id);
    return match ? Math.max(maxValue, Number(match[1])) : maxValue;
  }, 0) + 1;
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, options);
  if (response.status === 204) return null;
  const data = await response.json().catch(() => null);
  if (!response.ok) throw new Error(data?.detail || "Не удалось выполнить запрос к backend.");
  return data;
}

function escapeHtml(value) {
  return String(value).replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");
}

initializeApp();
