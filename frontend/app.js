const API_BASE_URL = "http://127.0.0.1:8000/api";

const state = {
  tasks: [],
  counter: 1,
};

const today = new Date().toISOString().split("T")[0];

const statusLabels = {
  todo: "К выполнению",
  in_progress: "В процессе",
  blocked: "Заблокировано",
  done: "Завершено",
};

const projectStatusLabels = {
  planned: "Планируется",
  in_progress: "В работе",
  attention_needed: "Требует внимания",
  done: "Завершён",
};

const priorityLabels = {
  low: "Низкий",
  medium: "Средний",
  high: "Высокий",
  critical: "Критический",
};

const elements = {
  ctxDate: document.getElementById("ctx-date"),
  ctxHours: document.getElementById("ctx-hours"),
  ctxName: document.getElementById("ctx-name"),
  taskCount: document.getElementById("task-count"),
  taskList: document.getElementById("task-list"),
  addTaskButton: document.getElementById("add-task-button"),
  clearTaskButton: document.getElementById("clear-task-button"),
  loadDemoButton: document.getElementById("load-demo-button"),
  analyzeButton: document.getElementById("analyze-button"),
  loadingState: document.getElementById("loading-state"),
  errorState: document.getElementById("error-state"),
  resultsSection: document.getElementById("results-section"),
  overviewSummary: document.getElementById("overview-summary"),
  overviewMeta: document.getElementById("overview-meta"),
  prioritiesOutput: document.getElementById("priorities-output"),
  planOutput: document.getElementById("plan-output"),
  projectsOutput: document.getElementById("projects-output"),
  recommendationsOutput: document.getElementById("recommendations-output"),
};

elements.ctxDate.value = today;

elements.addTaskButton.addEventListener("click", addTask);
elements.clearTaskButton.addEventListener("click", clearTaskForm);
elements.loadDemoButton.addEventListener("click", loadDemoData);
elements.analyzeButton.addEventListener("click", analyzeTasks);

function readTaskForm() {
  const title = document.getElementById("task-title").value.trim();
  const type = document.getElementById("task-type").value;
  const deadline = document.getElementById("task-deadline").value;
  const githubUrl = document.getElementById("task-github").value.trim();

  if (!title) {
    throw new Error("Укажи название задачи.");
  }
  if (!type) {
    throw new Error("Выбери тип задачи.");
  }
  if (!deadline) {
    throw new Error("Укажи дедлайн.");
  }
  if (githubUrl && !isValidUrl(githubUrl)) {
    throw new Error("GitHub-ссылка должна быть корректным URL.");
  }

  return {
    id: `task-${String(state.counter).padStart(3, "0")}`,
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
    tags: splitList(document.getElementById("task-tags").value),
    dependencies: splitList(document.getElementById("task-dependencies").value),
    notes: document.getElementById("task-notes").value.trim() || null,
  };
}

function addTask() {
  try {
    const task = readTaskForm();
    state.tasks.push(task);
    state.counter += 1;
    renderTaskList();
    clearTaskForm();
    showError("");
  } catch (error) {
    showError(error.message);
  }
}

function clearTaskForm() {
  [
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
  ].forEach((id) => {
    document.getElementById(id).value = "";
  });
  document.getElementById("task-type").value = "";
  document.getElementById("task-importance").value = "medium";
  document.getElementById("task-status").value = "todo";
}

function renderTaskList() {
  elements.taskCount.textContent = String(state.tasks.length);
  if (state.tasks.length === 0) {
    elements.taskList.innerHTML = '<div class="empty-state">Пока нет задач. Добавь хотя бы одну задачу для анализа.</div>';
    return;
  }

  elements.taskList.innerHTML = "";
  state.tasks.forEach((task, index) => {
    const item = document.createElement("article");
    item.className = "task-item";
    item.innerHTML = `
      <div class="task-top">
        <div>
          <h3 class="task-title">${escapeHtml(task.title)}</h3>
          <div class="meta-row">
            <span class="badge status-${task.status}">${statusLabels[task.status]}</span>
            <span class="badge priority-${task.importance}">${priorityLabels[task.importance]}</span>
            <span class="badge">${escapeHtml(task.type)}</span>
          </div>
        </div>
        <div class="task-actions">
          <button class="icon-button" type="button" aria-label="Удалить задачу">×</button>
        </div>
      </div>
      <p>${escapeHtml(task.project || "Без проекта")} · дедлайн ${escapeHtml(task.deadline)}</p>
      ${task.github_url ? `<a class="github-link" href="${task.github_url}" target="_blank" rel="noreferrer">Открыть GitHub</a>` : ""}
    `;
    item.querySelector("button").addEventListener("click", () => removeTask(index));
    elements.taskList.appendChild(item);
  });
}

function removeTask(index) {
  state.tasks.splice(index, 1);
  renderTaskList();
}

async function analyzeTasks() {
  if (state.tasks.length === 0) {
    showError("Добавь хотя бы одну задачу перед анализом.");
    return;
  }

  const payload = {
    user_context: {
      current_date: elements.ctxDate.value || today,
      working_hours_per_day: Number(elements.ctxHours.value) || 6,
      user_name: elements.ctxName.value.trim() || null,
      work_days: ["Mon", "Tue", "Wed", "Thu", "Fri"],
    },
    tasks: state.tasks,
  };

  setLoading(true);
  showError("");
  try {
    const response = await fetch(`${API_BASE_URL}/analyze`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "Не удалось получить ответ от backend.");
    }
    renderResults(data);
  } catch (error) {
    showError(error.message);
  } finally {
    setLoading(false);
  }
}

function renderResults(data) {
  elements.resultsSection.classList.remove("hidden");
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
      ${item.github_url ? `<a class="github-link" href="${item.github_url}" target="_blank" rel="noreferrer">GitHub проекта</a>` : ""}
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
    const tasksMarkup = item.tasks
      .map((task) => `<li>${escapeHtml(task.title)} · ${task.planned_hours} ч · ${statusLabels[task.status]}</li>`)
      .join("");
    card.innerHTML = `
      <h3 class="priority-title">${escapeHtml(item.day_label)}${item.date ? ` · ${escapeHtml(item.date)}` : ""}</h3>
      <p>Запланировано ${item.total_planned_hours} ч.</p>
      <ul class="plan-task-list">${tasksMarkup}</ul>
    `;
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
      ${item.github_url ? `<a class="github-link" href="${item.github_url}" target="_blank" rel="noreferrer">Открыть репозиторий</a>` : ""}
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

function loadDemoData() {
  state.tasks = [
    {
      id: "task-001",
      title: "Исправить баг в форме заявки",
      description: "Починить валидацию email и отправку в CRM.",
      project: "Client Beta CRM",
      client: "Beta",
      github_url: "https://github.com/example/client-beta-crm",
      type: "development",
      deadline: addDays(today, 1),
      estimated_hours: 2,
      importance: "critical",
      status: "in_progress",
      tags: ["backend", "crm"],
      dependencies: [],
      notes: "Ошибка влияет на лиды.",
    },
    {
      id: "task-002",
      title: "Подготовить текст для лендинга",
      description: "Сделать первый экран и блок преимуществ.",
      project: "Alpha Landing",
      client: "Alpha",
      github_url: "https://github.com/example/alpha-landing",
      type: "content",
      deadline: addDays(today, 2),
      estimated_hours: 3,
      importance: "high",
      status: "todo",
      tags: ["copywriting"],
      dependencies: [],
      notes: "Сначала уточнить tone of voice.",
    },
    {
      id: "task-003",
      title: "Собрать недельный рекламный отчёт",
      description: "Сводка по метрикам и выводам.",
      project: "Gamma Ads",
      client: "Gamma",
      github_url: "https://github.com/example/gamma-ads",
      type: "analytics",
      deadline: addDays(today, 4),
      estimated_hours: 2.5,
      importance: "medium",
      status: "todo",
      tags: ["analytics"],
      dependencies: [],
      notes: "Нужны данные из Google Sheets.",
    },
  ];
  state.counter = 4;
  renderTaskList();
  showError("");
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

function splitList(value) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

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

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

renderTaskList();
