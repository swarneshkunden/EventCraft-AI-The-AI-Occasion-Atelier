/**
 * EventCraft AI — Critical Path Execution Graph & Visual Timeline.
 * Palette: Ivory & Midnight Gold (WCAG AA Compliant).
 */
import { getCurrentEvent } from '../services/events.js';
import {
  getTaskList,
  updateTaskItem,
  generateTaskList,
} from '../services/events.js';
import { formatDate } from '../utils/formatters.js';
import { showToast, escapeHtml } from '../utils/toast.js';
import { icons } from '../utils/icons.js';

let allTasks = [];
let currentFilter = 'all';

export async function renderTasksPage() {
  const event = getCurrentEvent();

  if (!event) {
    return `
      <div class="page-body">
        <div class="empty-state card">
          <div class="empty-icon">${icons.timeline(36)}</div>
          <h3 class="serif" style="font-size: 1.4rem; margin-bottom: 8px;">No Active Celebration Selected</h3>
          <p style="color: var(--clr-text-muted); max-width: 440px; margin: 0 auto 20px;">
            Select or create a celebration to generate your milestone schedule.
          </p>
        </div>
      </div>
    `;
  }

  try {
    const res = await getTaskList(event.id);
    allTasks = res?.tasks || [];
  } catch (err) {
    console.error('Failed to load tasks', err);
    allTasks = [];
  }

  const readyCount = allTasks.filter((t) => t.is_ready && t.status !== 'completed').length;
  const blockedCount = allTasks.filter((t) => !t.is_ready && t.status !== 'completed').length;
  const doneCount = allTasks.filter((t) => t.status === 'completed').length;
  const progressPct = allTasks.length > 0 ? Math.round((doneCount / allTasks.length) * 100) : 0;

  return `
    <div class="page-body">

      <!-- Timeline Executive Header Card -->
      <div class="card" style="margin-bottom: 24px; position: relative; overflow: hidden; background: linear-gradient(135deg, var(--clr-surface) 0%, var(--clr-surface-2) 100%);">

        <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 20px; margin-bottom: 20px;">
          <div>
            <div style="display: inline-flex; align-items: center; gap: 6px; font-size: 0.75rem; text-transform: uppercase; color: var(--clr-accent); font-weight: 700; letter-spacing: 0.12em; margin-bottom: 6px;">
              ${icons.timeline(14)} Critical Path Timeline
            </div>
            <h1 class="serif" style="font-size: clamp(1.8rem, 3vw, 2.4rem); font-weight: 700; color: var(--clr-primary); line-height: 1.1; margin-bottom: 4px;">
              Execution Milestones
            </h1>
            <p style="font-size: 0.9rem; color: var(--clr-text-muted);">
              Dependency-aware milestone engine: tasks remain blocked until prerequisite parent deliverables are completed.
            </p>
          </div>

          <div style="display: flex; gap: 10px; flex-wrap: wrap; align-items: center;">
            <button id="btn-generate-tasks" class="btn btn-secondary" title="Use Gemini AI to build milestone calendar relative to event date">
              ${icons.sparkle(16)} AI Generate Timeline
            </button>
            <button id="btn-add-task-modal" class="btn btn-gold">
              ${icons.plus(16)} Add Milestone
            </button>
          </div>
        </div>

        <!-- Timeline Progress Stats -->
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 14px; margin-bottom: 20px;">
          <div style="background: var(--clr-surface); padding: 14px 18px; border-radius: var(--radius-md); border: 1px solid var(--clr-border);">
            <div style="font-size: 0.7rem; color: var(--clr-text-muted); text-transform: uppercase; font-weight: 700; letter-spacing: 0.08em;">Total Milestones</div>
            <div class="serif tabular-nums" style="font-size: 1.5rem; font-weight: 700; color: var(--clr-text);">${allTasks.length}</div>
          </div>
          <div style="background: var(--clr-surface); padding: 14px 18px; border-radius: var(--radius-md); border: 1px solid var(--clr-border); border-left: 3px solid var(--clr-success);">
            <div style="font-size: 0.7rem; color: var(--clr-success); text-transform: uppercase; font-weight: 700; letter-spacing: 0.08em;">Ready to Execute</div>
            <div class="serif tabular-nums" style="font-size: 1.5rem; font-weight: 700; color: var(--clr-success);">${readyCount}</div>
          </div>
          <div style="background: var(--clr-surface); padding: 14px 18px; border-radius: var(--radius-md); border: 1px solid var(--clr-border); border-left: 3px solid var(--clr-danger);">
            <div style="font-size: 0.7rem; color: var(--clr-danger); text-transform: uppercase; font-weight: 700; letter-spacing: 0.08em;">Blocked Dependencies</div>
            <div class="serif tabular-nums" style="font-size: 1.5rem; font-weight: 700; color: var(--clr-danger);">${blockedCount}</div>
          </div>
          <div style="background: var(--clr-surface); padding: 14px 18px; border-radius: var(--radius-md); border: 1px solid var(--clr-border); border-left: 3px solid var(--clr-accent);">
            <div style="font-size: 0.7rem; color: var(--clr-accent); text-transform: uppercase; font-weight: 700; letter-spacing: 0.08em;">Completed</div>
            <div class="serif tabular-nums" style="font-size: 1.5rem; font-weight: 700; color: var(--clr-accent);">${doneCount}</div>
          </div>
        </div>

        <!-- Milestone Velocity Progress Bar -->
        <div>
          <div style="display: flex; justify-content: space-between; align-items: center; font-size: 0.75rem; color: var(--clr-text-muted); margin-bottom: 6px;">
            <span>Project Completion Velocity</span>
            <span class="tabular-nums" style="font-weight: 700; color: var(--clr-text);">${progressPct}% Finished</span>
          </div>
          <div class="progress-bar" style="height: 8px;">
            <div class="progress-fill" style="width: ${progressPct}%;"></div>
          </div>
        </div>

        <!-- Filter tabs -->
        <div style="display: flex; gap: 8px; margin-top: 24px; border-top: 1px solid var(--clr-border); padding-top: 14px; flex-wrap: wrap;">
          <button class="btn btn-ghost btn-sm task-filter-btn ${currentFilter === 'all' ? 'btn-primary' : ''}" data-filter="all">
            All Tasks (${allTasks.length})
          </button>
          <button class="btn btn-ghost btn-sm task-filter-btn ${currentFilter === 'ready' ? 'btn-primary' : ''}" data-filter="ready">
            🟢 Ready to Execute (${readyCount})
          </button>
          <button class="btn btn-ghost btn-sm task-filter-btn ${currentFilter === 'blocked' ? 'btn-primary' : ''}" data-filter="blocked">
            ⛔ Blocked (${blockedCount})
          </button>
          <button class="btn btn-ghost btn-sm task-filter-btn ${currentFilter === 'done' ? 'btn-primary' : ''}" data-filter="done">
            ✓ Completed (${doneCount})
          </button>
        </div>
      </div>

      <!-- Task List Container -->
      <div class="card" style="padding: 0; overflow: hidden;">
        <div id="tasks-list-container">
          ${renderTaskList(allTasks, currentFilter)}
        </div>
      </div>

    </div>
  `;
}

function renderTaskList(tasks, filter) {
  let filtered = tasks;
  if (filter === 'ready') {
    filtered = tasks.filter((t) => t.is_ready && t.status !== 'completed');
  } else if (filter === 'blocked') {
    filtered = tasks.filter((t) => !t.is_ready && t.status !== 'completed');
  } else if (filter === 'done') {
    filtered = tasks.filter((t) => t.status === 'completed');
  }

  if (filtered.length === 0) {
    return `
      <div style="padding: 48px 24px; text-align: center; color: var(--clr-text-muted);">
        <div style="margin-bottom: 12px; color: var(--clr-accent);">
          ${icons.timeline(36)}
        </div>
        <h4 class="serif" style="font-size: 1.15rem; color: var(--clr-text); margin-bottom: 6px;">
          ${tasks.length === 0 ? 'No Milestones Scheduled Yet' : 'No Tasks in This Category'}
        </h4>
        <p style="font-size: 0.85rem; max-width: 440px; margin: 0 auto 16px;">
          ${tasks.length === 0 ? 'Click "✨ AI Generate Timeline" above to let Gemini AI compute all milestones leading up to your date.' : 'Try changing your filter view above.'}
        </p>
      </div>
    `;
  }

  return filtered
    .map((task) => {
      const isDone = task.status === 'completed';
      const isBlocked = !task.is_ready && !isDone;
      const blockedByNames = (task.blocked_by || []).join(', ');

      const priorityBadge =
        task.priority === 'high' || task.priority <= 2
          ? 'badge-danger'
          : task.priority === 'medium' || task.priority <= 4
          ? 'badge-warning'
          : 'badge-secondary';

      const isOverdue = !isDone && task.due_date && new Date(task.due_date) < new Date();

      return `
      <div class="task-item" data-task-id="${task.id}" style="${isDone ? 'opacity: 0.6;' : ''} padding: 16px 20px; border-bottom: 1px solid var(--clr-border); display: flex; align-items: flex-start; gap: 16px; transition: background var(--transition-fast);">

        <div
          class="task-checkbox ${isDone ? 'checked' : isBlocked ? 'blocked' : 'ready'}"
          data-task-id="${task.id}"
          role="checkbox"
          aria-checked="${isDone}"
          tabindex="0"
          title="${isDone ? 'Mark as incomplete' : isBlocked ? 'Blocked by parent tasks' : 'Mark as complete'}"
          style="width: 24px; height: 24px; border-radius: 6px; border: 2px solid ${isDone ? 'var(--clr-accent)' : isBlocked ? 'var(--clr-danger)' : 'var(--clr-border)'}; display: flex; align-items: center; justify-content: center; cursor: pointer; flex-shrink: 0; margin-top: 2px; background: ${isDone ? 'var(--clr-accent)' : 'transparent'}; color: #14213D; font-weight: 800; transition: all var(--transition-fast);"
        >
          ${isDone ? icons.check(14) : isBlocked ? '✕' : ''}
        </div>

        <div class="task-content" style="flex: 1;">
          <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 10px; margin-bottom: 6px;">
            <div class="task-title ${isDone ? 'completed' : ''}" style="font-weight: 600; font-size: 0.95rem; color: var(--clr-text); ${isDone ? 'text-decoration: line-through; color: var(--clr-text-muted);' : ''}">
              ${escapeHtml(task.title)}
            </div>

            <div style="display: flex; gap: 6px; align-items: center; flex-shrink: 0;">
              ${isOverdue ? `<span class="badge badge-danger" style="font-size: 0.65rem;">Overdue</span>` : ''}
              <span class="badge ${priorityBadge}" style="font-size: 0.65rem; text-transform: uppercase;">
                Priority ${task.priority}
              </span>
            </div>
          </div>

          <div class="task-meta" style="display: flex; gap: 12px; align-items: center; flex-wrap: wrap; font-size: 0.8rem; color: var(--clr-text-muted);">
            ${task.category ? `<span class="badge badge-secondary" style="font-size: 0.7rem;">${escapeHtml(task.category)}</span>` : ''}

            <span class="tabular-nums" style="display: inline-flex; align-items: center; gap: 4px;">
              ${icons.calendar(13)} ${formatDate(task.due_date)}
            </span>

            ${
              isBlocked
                ? `<span class="badge badge-danger" style="font-size: 0.7rem; display: inline-flex; align-items: center; gap: 4px;">
                    ⛔ Blocked by: ${escapeHtml(blockedByNames || 'prior deliverables')}
                   </span>`
                : !isDone
                ? `<span class="badge badge-success" style="font-size: 0.7rem; display: inline-flex; align-items: center; gap: 4px;">
                    ✓ Ready to Execute
                   </span>`
                : `<span class="badge badge-gold" style="font-size: 0.7rem;">Completed</span>`
            }
          </div>
        </div>
      </div>
    `;
    })
    .join('');
}

export function initTasksPageEvents() {
  const event = getCurrentEvent();
  if (!event) return;

  // Filter click
  document.querySelectorAll('.task-filter-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.task-filter-btn').forEach((b) => b.classList.remove('btn-primary'));
      btn.classList.add('btn-primary');
      currentFilter = btn.getAttribute('data-filter');
      const container = document.getElementById('tasks-list-container');
      if (container) {
        container.innerHTML = renderTaskList(allTasks, currentFilter);
      }
    });
  });

  // Checkbox toggle
  document.getElementById('tasks-list-container')?.addEventListener('click', async (e) => {
    const cb = e.target.closest('.task-checkbox');
    if (!cb) return;

    const taskId = cb.getAttribute('data-task-id');
    const task = allTasks.find((t) => t.id === taskId);
    if (!task) return;

    const newStatus = task.status === 'completed' ? 'pending' : 'completed';

    // Optimistic UI update
    task.status = newStatus;
    const container = document.getElementById('tasks-list-container');
    if (container) container.innerHTML = renderTaskList(allTasks, currentFilter);

    try {
      await updateTaskItem(event.id, taskId, { status: newStatus });
      // Re-fetch to recalculate dependency readiness of downstream tasks
      const res = await getTaskList(event.id);
      allTasks = res?.tasks || [];
      if (container) container.innerHTML = renderTaskList(allTasks, currentFilter);
      showToast(newStatus === 'completed' ? 'Milestone marked complete!' : 'Milestone reopened.', 'info');
    } catch (err) {
      showToast(err.message || 'Failed to update task state', 'error');
    }
  });

  // AI Generate Timeline
  document.getElementById('btn-generate-tasks')?.addEventListener('click', async () => {
    const btn = document.getElementById('btn-generate-tasks');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner spinner-sm"></span> AI Generating Timeline...';

    try {
      const res = await generateTaskList(event.id);
      allTasks = res?.tasks || [];
      const container = document.getElementById('tasks-list-container');
      if (container) container.innerHTML = renderTaskList(allTasks, currentFilter);
      showToast(`Generated ${allTasks.length} timeline milestones!`, 'success');
    } catch (err) {
      showToast(err.message || 'AI timeline generation encountered an issue', 'error');
    } finally {
      btn.disabled = false;
      btn.innerHTML = `${icons.sparkle(16)} AI Generate Timeline`;
    }
  });

  // Add Task Modal
  document.getElementById('btn-add-task-modal')?.addEventListener('click', () => {
    openAddTaskModal(event.id);
  });
}

function openAddTaskModal(eventId) {
  document.getElementById('modal-add-task')?.remove();

  const modalHtml = `
    <div class="modal-backdrop" id="modal-add-task">
      <div class="modal" role="dialog" aria-labelledby="modal-add-task-title" aria-modal="true">
        <div class="modal-header">
          <div>
            <div style="font-size: 0.7rem; text-transform: uppercase; color: var(--clr-accent); font-weight: 700; letter-spacing: 0.08em;">
              Milestone Creation
            </div>
            <h3 class="serif modal-title" id="modal-add-task-title" style="font-size: 1.3rem;">Add New Milestone</h3>
          </div>
          <button class="btn btn-ghost btn-sm" id="btn-close-add-task" aria-label="Close dialog">✕</button>
        </div>

        <form id="form-add-task" class="modal-body">
          <div class="form-group">
            <label for="task-title">Milestone Title <span class="required">*</span></label>
            <input type="text" id="task-title" class="form-control" required placeholder="e.g. Finalize floral centerpieces with florist" />
          </div>

          <div class="grid-2">
            <div class="form-group">
              <label for="task-category">Category</label>
              <input type="text" id="task-category" class="form-control" placeholder="e.g. Decor, Catering, Venue" />
            </div>

            <div class="form-group">
              <label for="task-priority">Priority Level</label>
              <select id="task-priority" class="form-control">
                <option value="high">High Priority</option>
                <option value="medium" selected>Medium Priority</option>
                <option value="low">Low Priority</option>
              </select>
            </div>
          </div>

          <div class="form-group">
            <label for="task-due-date">Due Date</label>
            <input type="date" id="task-due-date" class="form-control" />
          </div>

          <div class="modal-footer" style="padding: 16px 0 0 0; border-top: none;">
            <button type="button" class="btn btn-secondary" id="btn-cancel-add-task">Cancel</button>
            <button type="submit" class="btn btn-gold" id="btn-submit-task">
              ${icons.check(14)} Save Milestone
            </button>
          </div>
        </form>
      </div>
    </div>
  `;

  document.body.insertAdjacentHTML('beforeend', modalHtml);

  const closeModal = () => document.getElementById('modal-add-task')?.remove();
  document.getElementById('btn-close-add-task')?.addEventListener('click', closeModal);
  document.getElementById('btn-cancel-add-task')?.addEventListener('click', closeModal);

  document.getElementById('form-add-task')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const title = document.getElementById('task-title').value.trim();
    const category = document.getElementById('task-category').value.trim() || 'General';
    const priority = document.getElementById('task-priority').value;
    const dueDate = document.getElementById('task-due-date').value || null;

    const btn = document.getElementById('btn-submit-task');
    btn.disabled = true;
    btn.textContent = 'Saving...';

    try {
      const priorityMap = { high: 1, medium: 5, low: 8 };
      const newTask = {
        title,
        category,
        priority: priorityMap[priority] || 5,
        due_date: dueDate,
        depends_on: [],
      };

      const { api } = await import('../services/api.js');
      await api.post(`/api/events/${eventId}/tasks`, newTask);

      const res = await getTaskList(eventId);
      allTasks = res?.tasks || [];
      const container = document.getElementById('tasks-list-container');
      if (container) container.innerHTML = renderTaskList(allTasks, currentFilter);

      showToast('Milestone successfully added!', 'success');
      closeModal();
    } catch (err) {
      showToast(err.message || 'Failed to add milestone', 'error');
      btn.disabled = false;
      btn.textContent = 'Save Milestone';
    }
  });
}
