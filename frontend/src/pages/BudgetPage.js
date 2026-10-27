/**
 * EventCraft AI — Luxury Budget Allocation & Scenario Replan Engine.
 * Palette: Ivory & Midnight Gold (WCAG AA Compliant).
 */
import { getCurrentEvent } from '../services/events.js';
import { getCurrentUser } from '../services/auth.js';
import {
  getBudgetCategories,
  saveBudgetCategories,
  generateBudgetSplit,
  runBudgetScenario,
  getTaskList,
  updateTaskItem,
} from '../services/events.js';
import { formatCurrency, formatPercent } from '../utils/formatters.js';
import { showToast, escapeHtml } from '../utils/toast.js';
import { icons } from '../utils/icons.js';

let localCategories = [];

export async function renderBudgetPage() {
  const event = getCurrentEvent();
  const user = getCurrentUser();
  const currency = user?.currency || 'USD';

  if (!event) {
    return `
      <div class="page-body">
        <div class="empty-state card">
          <div class="empty-icon">${icons.budget(36)}</div>
          <h3 class="serif" style="font-size: 1.4rem; margin-bottom: 8px;">No Active Celebration Selected</h3>
          <p style="color: var(--clr-text-muted); max-width: 440px; margin: 0 auto 20px;">
            Select a celebration from the top navigation or create a new celebration to curate your budget.
          </p>
        </div>
      </div>
    `;
  }

  try {
    localCategories = (await getBudgetCategories(event.id)) || [];
  } catch (err) {
    console.error('Failed to load budget categories', err);
    localCategories = [];
  }

  const totalSpent = localCategories.reduce((sum, c) => sum + (c.spent || 0), 0);
  const totalAllocated = localCategories.reduce((sum, c) => sum + (c.allocated || 0), 0);
  const remaining = event.total_budget - totalSpent;
  const unallocated = event.total_budget - totalAllocated;
  const spentPct = formatPercent(totalSpent, event.total_budget);

  return `
    <div class="page-body">

      <!-- Executive Budget Hero Card -->
      <div class="card" style="margin-bottom: 24px; position: relative; overflow: hidden; background: linear-gradient(135deg, var(--clr-surface) 0%, var(--clr-surface-2) 100%);">

        <!-- Header row -->
        <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 20px; margin-bottom: 24px;">
          <div>
            <div style="display: inline-flex; align-items: center; gap: 6px; font-size: 0.75rem; text-transform: uppercase; color: var(--clr-accent); font-weight: 700; letter-spacing: 0.12em; margin-bottom: 6px;">
              ${icons.budget(14)} Financial Architecture
            </div>
            <h1 class="serif" style="font-size: clamp(1.8rem, 3vw, 2.4rem); font-weight: 700; color: var(--clr-primary); line-height: 1.1; margin-bottom: 4px;">
              ${escapeHtml(event.title)}
            </h1>
            <p style="font-size: 0.9rem; color: var(--clr-text-muted);">
              Capped Total: <strong class="tabular-nums" style="color: var(--clr-text);">${formatCurrency(event.total_budget, currency)}</strong> • ${event.guest_count} Invited Guests
            </p>
          </div>

          <!-- Action Buttons -->
          <div style="display: flex; gap: 10px; flex-wrap: wrap; align-items: center;">
            <button id="btn-ai-split" class="btn btn-secondary" title="Use Gemini AI to distribute funds across standard industry tiers">
              ${icons.sparkle(16)} AI Auto-Split Budget
            </button>
            <button id="btn-add-category" class="btn btn-secondary">
              ${icons.plus(16)} Add Category
            </button>
            <button id="btn-save-budget" class="btn btn-gold">
              ${icons.check(16)} Save Budget
            </button>
          </div>
        </div>

        <!-- 3 Executive KPI Cards -->
        <div class="grid-3" style="margin-bottom: 20px;">
          <div style="background: var(--clr-surface); padding: 18px 20px; border-radius: var(--radius-md); border: 1px solid var(--clr-border); box-shadow: var(--shadow-sm);">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
              <span style="font-size: 0.75rem; color: var(--clr-text-muted); text-transform: uppercase; font-weight: 700; letter-spacing: 0.08em;">Allocated Total</span>
              <span class="badge badge-primary" style="font-size: 0.65rem;">Planned</span>
            </div>
            <div class="serif tabular-nums" style="font-size: 1.6rem; font-weight: 700; color: var(--clr-text);" id="summary-allocated">
              ${formatCurrency(totalAllocated, currency)}
            </div>
            <div style="font-size: 0.8rem; margin-top: 4px; color: ${unallocated < 0 ? 'var(--clr-danger)' : 'var(--clr-text-muted)'}; font-weight: 500;" id="summary-unallocated">
              ${unallocated < 0 ? '⚠️ Over-allocated by ' + formatCurrency(Math.abs(unallocated), currency) : formatCurrency(unallocated, currency) + ' unallocated balance'}
            </div>
          </div>

          <div style="background: var(--clr-surface); padding: 18px 20px; border-radius: var(--radius-md); border: 1px solid var(--clr-border); box-shadow: var(--shadow-sm);">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
              <span style="font-size: 0.75rem; color: var(--clr-text-muted); text-transform: uppercase; font-weight: 700; letter-spacing: 0.08em;">Actual Spent</span>
              <span class="badge ${totalSpent > event.total_budget ? 'badge-danger' : 'badge-gold'}" style="font-size: 0.65rem;">Committed</span>
            </div>
            <div class="serif tabular-nums" style="font-size: 1.6rem; font-weight: 700; color: var(--clr-text);" id="summary-spent">
              ${formatCurrency(totalSpent, currency)}
            </div>
            <div style="font-size: 0.8rem; margin-top: 4px; color: var(--clr-text-muted);">
              <span class="tabular-nums" style="font-weight: 600;">${spentPct}%</span> of total celebration allocation
            </div>
          </div>

          <div style="background: var(--clr-surface); padding: 18px 20px; border-radius: var(--radius-md); border: 1px solid var(--clr-border); box-shadow: var(--shadow-sm);">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
              <span style="font-size: 0.75rem; color: var(--clr-text-muted); text-transform: uppercase; font-weight: 700; letter-spacing: 0.08em;">Remaining Balance</span>
              <span class="badge ${remaining >= 0 ? 'badge-success' : 'badge-danger'}" style="font-size: 0.65rem;">
                ${remaining >= 0 ? 'Within Limits' : 'Deficit'}
              </span>
            </div>
            <div class="serif tabular-nums" style="font-size: 1.6rem; font-weight: 700; color: ${remaining < 0 ? 'var(--clr-danger)' : 'var(--clr-success)'};" id="summary-remaining">
              ${formatCurrency(remaining, currency)}
            </div>
            <div style="font-size: 0.8rem; margin-top: 4px; color: var(--clr-text-muted);">
              ${remaining >= 0 ? 'Safe available runway' : 'Immediate rebalancing recommended'}
            </div>
          </div>
        </div>

        <!-- Overall Progress bar -->
        <div>
          <div style="display: flex; justify-content: space-between; align-items: center; font-size: 0.75rem; color: var(--clr-text-muted); margin-bottom: 6px;">
            <span>Overall Spending Velocity</span>
            <span class="tabular-nums" style="font-weight: 700; color: var(--clr-text);">${spentPct}% Utilized</span>
          </div>
          <div class="progress-bar" style="height: 8px;">
            <div id="summary-progress-bar" class="progress-fill ${totalSpent > event.total_budget ? 'over-budget' : ''}" style="width: ${spentPct}%;"></div>
          </div>
        </div>
      </div>

      <!-- AI Scenario & Re-plan Simulator Card -->
      <div class="card" style="margin-bottom: 24px; border: 1px solid var(--clr-accent); background: linear-gradient(135deg, rgba(201, 162, 75, 0.06), var(--clr-surface));">
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; flex-wrap: wrap; gap: 8px;">
          <div style="display: flex; align-items: center; gap: 10px;">
            <div style="width: 34px; height: 34px; border-radius: 8px; background: rgba(201, 162, 75, 0.15); display: flex; align-items: center; justify-content: center; color: var(--clr-accent);">
              ${icons.sparkle(18)}
            </div>
            <div>
              <h3 class="serif" style="font-size: 1.15rem; font-weight: 700; color: var(--clr-primary);">
                AI Re-Plan Simulator & Trade-off Engine
              </h3>
              <p style="font-size: 0.825rem; color: var(--clr-text-muted); margin: 0;">
                Test changing assumptions (guest count surges, budget reductions, quote spikes) with instant trade-off impact analysis.
              </p>
            </div>
          </div>
          <span class="badge badge-gold" style="font-size: 0.7rem; font-weight: 700;">
            Estimated • Not Finalized
          </span>
        </div>

        <div style="display: flex; gap: 10px; flex-wrap: wrap; margin-top: 14px;">
          <input
            type="text"
            id="scenario-input"
            class="form-control"
            placeholder="e.g. Cut overall budget by 15%, how should we rebalance decor and catering? or Guest count increased to 120..."
            style="flex: 1; min-width: 280px;"
          />
          <button id="btn-run-scenario" class="btn btn-primary" style="white-space: nowrap;">
            ${icons.sparkle(15)} Simulate Scenario
          </button>
        </div>

        <!-- Scenario Result Container -->
        <div id="scenario-result-container" style="display: none; margin-top: 16px;"></div>
      </div>

      <!-- Category Allocations & Live Adjustments -->
      <div class="card" style="padding: 0; overflow: hidden;">
        <div style="padding: 20px 24px; border-bottom: 1px solid var(--clr-border); display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;">
          <div>
            <h3 class="serif" style="font-size: 1.25rem; font-weight: 700; margin-bottom: 2px;">
              Category Allocations & Spent
            </h3>
            <p style="font-size: 0.825rem; color: var(--clr-text-muted); margin: 0;">
              Inline editable financial records. Live balance recalculates automatically.
            </p>
          </div>
          <div style="display: flex; gap: 8px; align-items: center;">
            <span class="badge badge-secondary" style="font-size: 0.7rem;">
              ${localCategories.length} Categories Defined
            </span>
          </div>
        </div>

        <div id="budget-categories-list" style="display: flex; flex-direction: column;">
          ${renderCategoryRows(localCategories, currency)}
        </div>
      </div>

    </div>
  `;
}

function renderCategoryRows(categories, currency) {
  if (categories.length === 0) {
    return `
      <div style="padding: 48px 24px; text-align: center; color: var(--clr-text-muted);">
        <div style="font-size: 2rem; margin-bottom: 12px; color: var(--clr-accent);">
          ${icons.budget(36)}
        </div>
        <h4 class="serif" style="font-size: 1.15rem; color: var(--clr-text); margin-bottom: 6px;">No Budget Categories Yet</h4>
        <p style="font-size: 0.85rem; max-width: 440px; margin: 0 auto 16px;">
          Use our AI auto-split engine to generate an industry-calibrated budget breakdown, or add custom categories manually.
        </p>
      </div>
    `;
  }

  return categories
    .map((cat, idx) => {
      const pct = formatPercent(cat.spent || 0, cat.allocated || 1);
      const isOver = (cat.spent || 0) > (cat.allocated || 0);

      return `
      <div class="budget-category-row" data-idx="${idx}" style="padding: 16px 24px; display: grid; grid-template-columns: minmax(180px, 2fr) minmax(140px, 1.2fr) minmax(140px, 1.2fr) minmax(140px, 1.2fr) 40px; gap: 16px; align-items: center; border-bottom: 1px solid var(--clr-border); transition: background var(--transition-fast);">

        <!-- Category Title & Badge -->
        <div>
          <label style="font-size: 0.7rem; color: var(--clr-text-muted); text-transform: uppercase; font-weight: 700; letter-spacing: 0.06em; display: block; margin-bottom: 4px;">Category Name</label>
          <input
            type="text"
            class="input-cat-name form-control"
            value="${escapeHtml(cat.name)}"
            placeholder="Category Name"
            style="font-weight: 600; padding: 6px 10px; font-size: 0.9rem;"
          />
        </div>

        <!-- Allocated Input -->
        <div>
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
            <label style="font-size: 0.7rem; color: var(--clr-text-muted); text-transform: uppercase; font-weight: 700; letter-spacing: 0.06em;">Allocated</label>
            <span class="badge badge-secondary" style="font-size: 0.6rem; padding: 1px 4px;">Estimated</span>
          </div>
          <div style="position: relative;">
            <input
              type="number"
              class="input-cat-allocated form-control tabular-nums"
              value="${cat.allocated || 0}"
              min="0"
              step="50"
              style="padding: 6px 10px; font-weight: 600; text-align: right;"
            />
          </div>
        </div>

        <!-- Spent Input -->
        <div>
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
            <label style="font-size: 0.7rem; color: var(--clr-text-muted); text-transform: uppercase; font-weight: 700; letter-spacing: 0.06em;">Actual Spent</label>
            <span style="font-size: 0.7rem; color: var(--clr-text-dim);">${currency}</span>
          </div>
          <input
            type="number"
            class="input-cat-spent form-control tabular-nums"
            value="${cat.spent || 0}"
            min="0"
            step="50"
            style="padding: 6px 10px; font-weight: 600; text-align: right; color: ${isOver ? 'var(--clr-danger)' : 'var(--clr-text)'};"
          />
        </div>

        <!-- Utilization Bar -->
        <div>
          <div style="display: flex; justify-content: space-between; align-items: center; font-size: 0.7rem; margin-bottom: 4px;">
            <span style="color: var(--clr-text-muted); font-weight: 600;">Paced</span>
            <span class="tabular-nums ${isOver ? 'text-danger' : ''}" style="font-weight: 700;">${pct}%</span>
          </div>
          <div class="progress-bar" style="height: 6px;">
            <div class="progress-fill ${isOver ? 'over-budget' : ''}" style="width: ${pct}%;"></div>
          </div>
        </div>

        <!-- Action / Delete -->
        <div style="text-align: right;">
          <button class="btn btn-ghost btn-sm btn-delete-cat" title="Remove Category" aria-label="Remove Category" style="color: var(--clr-danger); padding: 6px 8px;">
            ${icons.trash(14)}
          </button>
        </div>

      </div>
    `;
    })
    .join('');
}

export function initBudgetPageEvents() {
  const event = getCurrentEvent();
  const user = getCurrentUser();
  const currency = user?.currency || 'USD';
  if (!event) return;

  function refreshTotals() {
    const rows = document.querySelectorAll('.budget-category-row');
    let totalAlloc = 0;
    let totalSpent = 0;

    localCategories = [];
    rows.forEach((row) => {
      const name = row.querySelector('.input-cat-name')?.value.trim() || 'Untitled';
      const allocated = parseFloat(row.querySelector('.input-cat-allocated')?.value) || 0;
      const spent = parseFloat(row.querySelector('.input-cat-spent')?.value) || 0;
      localCategories.push({ name, allocated, spent });
      totalAlloc += allocated;
      totalSpent += spent;
    });

    const unalloc = event.total_budget - totalAlloc;
    const remaining = event.total_budget - totalSpent;

    const elAlloc = document.getElementById('summary-allocated');
    const elUnalloc = document.getElementById('summary-unallocated');
    const elSpent = document.getElementById('summary-spent');
    const elRemaining = document.getElementById('summary-remaining');
    const elProgress = document.getElementById('summary-progress-bar');

    if (elAlloc) elAlloc.textContent = formatCurrency(totalAlloc, currency);
    if (elUnalloc) {
      elUnalloc.textContent =
        unalloc < 0
          ? `⚠️ Over-allocated by ${formatCurrency(Math.abs(unalloc), currency)}`
          : `${formatCurrency(unalloc, currency)} unallocated balance`;
      elUnalloc.style.color = unalloc < 0 ? 'var(--clr-danger)' : 'var(--clr-text-muted)';
    }
    if (elSpent) elSpent.textContent = formatCurrency(totalSpent, currency);
    if (elRemaining) {
      elRemaining.textContent = formatCurrency(remaining, currency);
      elRemaining.style.color = remaining < 0 ? 'var(--clr-danger)' : 'var(--clr-success)';
    }
    if (elProgress) {
      const pct = formatPercent(totalSpent, event.total_budget);
      elProgress.style.width = `${pct}%`;
      if (totalSpent > event.total_budget) {
        elProgress.classList.add('over-budget');
      } else {
        elProgress.classList.remove('over-budget');
      }
    }
  }

  // Input changes
  document.getElementById('budget-categories-list')?.addEventListener('input', (e) => {
    if (
      e.target.classList.contains('input-cat-allocated') ||
      e.target.classList.contains('input-cat-spent') ||
      e.target.classList.contains('input-cat-name')
    ) {
      refreshTotals();
    }
  });

  // Delete Category
  document.getElementById('budget-categories-list')?.addEventListener('click', (e) => {
    const btn = e.target.closest('.btn-delete-cat');
    if (!btn) return;
    const row = btn.closest('.budget-category-row');
    if (row) {
      row.remove();
      refreshTotals();
    }
  });

  // Add Category
  document.getElementById('btn-add-category')?.addEventListener('click', () => {
    const list = document.getElementById('budget-categories-list');
    if (!list) return;

    localCategories.push({ name: 'New Category', allocated: 0, spent: 0 });
    list.innerHTML = renderCategoryRows(localCategories, currency);
    refreshTotals();
  });

  // Save Budget
  document.getElementById('btn-save-budget')?.addEventListener('click', async () => {
    const btn = document.getElementById('btn-save-budget');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner spinner-sm"></span> Saving...';

    refreshTotals();

    try {
      await saveBudgetCategories(event.id, localCategories);
      showToast('Budget allocations successfully updated!', 'success');
    } catch (err) {
      showToast(err.message || 'Failed to save budget allocations', 'error');
    } finally {
      btn.disabled = false;
      btn.innerHTML = `${icons.check(16)} Save Budget`;
    }
  });

  // AI Auto-Split
  document.getElementById('btn-ai-split')?.addEventListener('click', async () => {
    const btn = document.getElementById('btn-ai-split');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner spinner-sm"></span> Calculating Standard Allocations...';

    try {
      const res = await generateBudgetSplit(event.id);
      if (Array.isArray(res)) {
        localCategories = res.map((c) => ({
          name: c.name,
          allocated: c.allocated,
          spent: 0,
          notes: c.notes,
        }));
        const list = document.getElementById('budget-categories-list');
        if (list) {
          list.innerHTML = renderCategoryRows(localCategories, currency);
        }
        refreshTotals();
        showToast('Calibrated budget allocations created by Gemini AI!', 'success');
      }
    } catch (err) {
      showToast(err.message || 'Auto-split encountered an error. Please retry.', 'error');
    } finally {
      btn.disabled = false;
      btn.innerHTML = `${icons.sparkle(16)} AI Auto-Split Budget`;
    }
  });

  // Run Scenario / Replan Diff
  document.getElementById('btn-run-scenario')?.addEventListener('click', async () => {
    const input = document.getElementById('scenario-input');
    const prompt = input?.value.trim();
    if (!prompt) {
      showToast('Please describe a scenario (e.g. "Cut decor budget by 20% and allocate to entertainment")', 'warning');
      return;
    }

    const btn = document.getElementById('btn-run-scenario');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner spinner-sm"></span> Modeling Trade-Offs...';

    const resultBox = document.getElementById('scenario-result-container');

    try {
      const diff = await runBudgetScenario(event.id, prompt);
      btn.disabled = false;
      btn.innerHTML = `${icons.sparkle(15)} Simulate Scenario`;

      if (!resultBox) return;

      const adjustments = diff.budget_changes || [];
      const taskChanges = diff.task_changes || [];
      const tradeoffs = diff.trade_offs || [];

      resultBox.style.display = 'block';
      resultBox.innerHTML = `
        <div class="card" style="background: var(--clr-surface); border: 1px solid var(--clr-accent); padding: 20px; box-shadow: var(--shadow-md);">

          <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; margin-bottom: 14px; border-bottom: 1px solid var(--clr-border); padding-bottom: 12px;">
            <div>
              <div style="font-size: 0.7rem; text-transform: uppercase; color: var(--clr-accent); font-weight: 700; letter-spacing: 0.1em;">
                Scenario Simulation Results
              </div>
              <h4 class="serif" style="font-weight: 700; font-size: 1.15rem; color: var(--clr-primary);">
                AI Re-Plan Diff & Impact Analysis
              </h4>
            </div>

            <div style="display: flex; gap: 8px;">
              <button id="btn-decline-diff" class="btn btn-secondary btn-sm">
                Decline
              </button>
              <button id="btn-apply-diff" class="btn btn-gold btn-sm">
                ${icons.check(14)} Accept & Apply Diff
              </button>
            </div>
          </div>

          <p style="font-size: 0.9rem; color: var(--clr-text); line-height: 1.6; margin-bottom: 16px;">
            ${escapeHtml(diff.summary || 'Scenario analyzed against your current event plan.')}
          </p>

          ${
            adjustments.length > 0
              ? `
            <div style="font-size: 0.75rem; font-weight: 700; text-transform: uppercase; color: var(--clr-text-muted); letter-spacing: 0.08em; margin-bottom: 8px;">
              Proposed Before & After Adjustments
            </div>
            <div style="display: flex; flex-direction: column; gap: 8px; margin-bottom: 18px;">
              ${adjustments
                .map((a) => {
                  const delta = a.new_allocated - a.old_allocated;
                  const isUp = delta > 0;
                  return `
                <div style="display: flex; justify-content: space-between; align-items: center; font-size: 0.875rem; padding: 10px 14px; background: var(--clr-surface-2); border-radius: var(--radius-sm); border-left: 3px solid ${isUp ? 'var(--clr-success)' : 'var(--clr-warning)'};">
                  <span style="font-weight: 600;">${escapeHtml(a.category_name)}<br><small>${escapeHtml(a.reason || '')}</small></span>
                  <div style="display: flex; align-items: center; gap: 10px;" class="tabular-nums">
                    <span style="color: var(--clr-text-muted); text-decoration: line-through;">
                      ${formatCurrency(a.old_allocated, currency)}
                    </span>
                    <span style="color: var(--clr-accent); font-weight: 700;">
                      → ${formatCurrency(a.new_allocated, currency)}
                    </span>
                    <span class="badge ${isUp ? 'badge-success' : 'badge-warning'}" style="font-size: 0.65rem;">
                      ${isUp ? '+' : ''}${formatCurrency(delta, currency)}
                    </span>
                  </div>
                </div>
              `;
                })
                .join('')}
            </div>
          `
              : ''
          }

          ${
            taskChanges.length > 0
              ? `
            <div style="font-size: 0.75rem; font-weight: 700; text-transform: uppercase; color: var(--clr-text-muted); letter-spacing: 0.08em; margin: 14px 0 8px;">
              Proposed timeline changes
            </div>
            <div style="display: flex; flex-direction: column; gap: 8px; margin-bottom: 18px;">
              ${taskChanges
                .map((task) => `
                <div style="padding: 10px 14px; background: var(--clr-surface-2); border-radius: var(--radius-sm);">
                  <strong>${escapeHtml(task.title)}</strong>
                  <span> · ${escapeHtml(task.old_due_date || 'No date')} → ${escapeHtml(task.new_due_date || 'No date')}</span>
                  <small style="display: block;">${escapeHtml(task.reason || '')}</small>
                </div>
              `)
                .join('')}
            </div>
          `
              : ''
          }
          ${
            tradeoffs.length > 0
              ? `
            <div style="background: rgba(183, 121, 31, 0.08); border: 1px solid rgba(183, 121, 31, 0.25); border-radius: var(--radius-md); padding: 14px 16px;">
              <div style="display: flex; align-items: center; gap: 6px; font-size: 0.75rem; font-weight: 700; text-transform: uppercase; color: var(--clr-warning); margin-bottom: 6px;">
                ${icons.alertCircle(14)} Critical Trade-Offs & Compromises
              </div>
              <ul style="font-size: 0.85rem; color: var(--clr-text); padding-left: 20px; line-height: 1.6; margin: 0;">
                ${tradeoffs.map((t) => `<li>${escapeHtml(t)}</li>`).join('')}
              </ul>
            </div>
          `
              : ''
          }
        </div>
      `;

      // Decline diff
      document.getElementById('btn-decline-diff')?.addEventListener('click', () => {
        resultBox.style.display = 'none';
        showToast('Scenario simulation dismissed.', 'info');
      });

      // Apply Diff
      document.getElementById('btn-apply-diff')?.addEventListener('click', async () => {
        const applyBtn = document.getElementById('btn-apply-diff');
        applyBtn.disabled = true;
        applyBtn.textContent = 'Applying...';

        const proposedCategories = localCategories.map((category) => ({ ...category }));
        adjustments.forEach((adj) => {
          const cat = localCategories.find(
            (c) => c.name.toLowerCase() === adj.category_name.toLowerCase()
          );
          if (cat) {
            const proposed = proposedCategories.find(
              (item) => item.name.toLowerCase() === adj.category_name.toLowerCase()
            );
            proposed.allocated = adj.new_allocated;
          } else {
            proposedCategories.push({
              name: adj.category_name,
              allocated: adj.new_allocated,
              spent: 0,
              notes: 'Estimated (assumption), not a confirmed price.',
            });
          }
        });

        try {
          if (adjustments.length > 0) {
            await saveBudgetCategories(event.id, proposedCategories);
          }
          if (taskChanges.length > 0) {
            const taskList = await getTaskList(event.id);
            const updates = taskChanges.map((change) => {
              const task = taskList.tasks.find((item) => item.title === change.title);
              if (!task) {
                throw new Error(`Could not find task "${change.title}" to apply its proposed change.`);
              }
              return updateTaskItem(event.id, task.id, {
                due_date: change.new_due_date,
                status: change.new_status,
              });
            });
            await Promise.all(updates);
          }
          localCategories = proposedCategories;
          const list = document.getElementById('budget-categories-list');
          if (list) list.innerHTML = renderCategoryRows(localCategories, currency);
          refreshTotals();
          showToast('Accepted scenario changes saved.', 'success');
          resultBox.style.display = 'none';
        } catch (err) {
          showToast(err.message || 'Failed to persist adjustments', 'error');
          applyBtn.disabled = false;
          applyBtn.textContent = 'Accept & Apply Diff';
        }
      });
    } catch (err) {
      showToast(err.message || 'Simulation encountered an error', 'error');
      btn.disabled = false;
      btn.innerHTML = `${icons.sparkle(15)} Simulate Scenario`;
    }
  });
}
