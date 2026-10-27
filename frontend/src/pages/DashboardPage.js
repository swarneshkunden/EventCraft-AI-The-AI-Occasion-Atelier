/**
 * Executive Event Overview & Dashboard Page.
 * Features an SVG Donut ring chart, tabular financial metrics,
 * next 3 actionable tasks, and "Needs Attention" alerts.
 */
import { getCurrentEvent, updateEventDetails } from '../services/events.js';
import { getCurrentUser } from '../services/auth.js';
import {
  getBudgetCategories,
  getTaskList,
  getVendorList,
  getGuestList,
} from '../services/events.js';
import { formatCurrency, formatDate, daysUntil, formatPercent } from '../utils/formatters.js';
import { openNewEventModal } from '../components/NewEventModal.js';
import { escapeHtml, showToast } from '../utils/toast.js';
import { icons } from '../utils/icons.js';

export async function renderDashboardPage() {
  const event = getCurrentEvent();
  const user = getCurrentUser();
  const currency = user?.currency || 'INR';

  if (!event) {
    return `
      <div class="page-body">
        <div class="empty-state card" style="max-width: 600px; margin: 60px auto;">
          ${icons.crest(64)}
          <h2 class="font-serif" style="margin-top: 12px;">Welcome to EventCraft Atelier</h2>
          <p class="text-muted" style="max-width: 460px; line-height: 1.6;">
            Begin planning your wedding, milestone birthday, or gala with intelligent budgeting, dependency timelines, and vendor interview tools.
          </p>
          <div style="display: flex; gap: 12px; margin-top: 8px;">
            <button id="btn-empty-new-event" class="btn btn-gold">
              ${icons.plus(16)} Plan Your Celebration
            </button>
          </div>
        </div>
      </div>
    `;
  }

  // Fetch subdata in parallel
  let categories = [];
  let tasks = [];
  let vendors = [];
  let guestSummary = { total: 0, attending: 0, pending: 0, declined: 0 };

  try {
    const [catRes, taskRes, vendorRes, guestRes] = await Promise.allSettled([
      getBudgetCategories(event.id),
      getTaskList(event.id),
      getVendorList(event.id),
      getGuestList(event.id, 1, 100),
    ]);

    if (catRes.status === 'fulfilled') categories = catRes.value || [];
    if (taskRes.status === 'fulfilled') tasks = taskRes.value?.tasks || [];
    if (vendorRes.status === 'fulfilled') vendors = vendorRes.value || [];
    if (guestRes.status === 'fulfilled') {
      const gList = guestRes.value?.guests || [];
      guestSummary.total = guestRes.value?.total || gList.length;
      guestSummary.attending = gList.filter((g) => g.rsvp_status === 'attending').length;
      guestSummary.pending = gList.filter((g) => g.rsvp_status === 'pending').length;
      guestSummary.declined = gList.filter((g) => g.rsvp_status === 'declined').length;
    }
  } catch (err) {
    console.error('Error fetching dashboard metrics', err);
  }

  const totalSpent = categories.reduce((sum, c) => sum + (c.spent || 0), 0);
  const totalAllocated = categories.reduce((sum, c) => sum + (c.allocated || 0), 0);
  const remainingBudget = event.total_budget - totalSpent;
  const budgetSpentPct = formatPercent(totalSpent, event.total_budget);

  const doneTasks = tasks.filter((t) => t.status === 'completed').length;
  const readyTasks = tasks.filter((t) => t.is_ready && t.status !== 'completed');
  const blockedTasks = tasks.filter((t) => !t.is_ready && t.status !== 'completed');

  const bookedVendors = vendors.filter((v) => v.status === 'booked' || v.status === 'paid').length;
  const days = daysUntil(event.event_date);
  const theme = event.profile?.theme || event.profile?.atmosphere || 'Boutique Celebration';
  const location = event.profile?.location || event.location || event.profile?.venue_limits || '';
  const profile = event.profile || {};
  const preferenceFields = [
    ['experience_level', 'Planning experience', profile.experience_level || 'moderate'],
    ['atmosphere', 'Atmosphere', profile.atmosphere || ''],
    ['must_haves', 'Must-haves', profile.must_haves || []],
    ['priorities', 'Priorities', profile.priorities || []],
    ['age_groups', 'Guest age groups', profile.age_groups || []],
    ['cultural_preferences', 'Cultural preferences', profile.cultural_preferences || ''],
    ['accessibility_needs', 'Accessibility needs', profile.accessibility_needs || ''],
    ['venue_limits', 'Venue requirements', profile.venue_limits || ''],
  ];

  // SVG Donut calculation
  const donutSvg = generateDonutSvg(categories, event.total_budget, currency);

  return `
    <div class="page-body">

      <!-- Event Hero Card -->
      <div class="card card-luxury dashboard-hero">
        <div class="dashboard-hero-header">
          <div class="dashboard-hero-details">
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px; flex-wrap: wrap;">
              ${renderInlineField('event_type', `<span class="badge badge-gold" style="text-transform: uppercase;">${escapeHtml(event.event_type)}</span>`, 'occasion type')}
              ${renderInlineField('atmosphere', `<span class="badge badge-muted">✨ ${escapeHtml(theme)}</span>`, 'atmosphere')}
              ${
                days !== null
                  ? `<span class="badge ${days < 0 ? 'badge-muted' : days <= 14 ? 'badge-danger' : 'badge-navy'}">
                      ${days < 0 ? 'Concluded' : `${days} days until celebration`}
                     </span>`
                  : ''
              }
            </div>

            <h1 class="font-serif" style="font-size: clamp(1.6rem, 3vw, 2.2rem); margin-bottom: 8px;">
              ${renderInlineField('name', escapeHtml(event.title || event.name), 'event name')}
            </h1>

            <div class="dashboard-event-meta">
              <span>${icons.calendar(14)} ${renderInlineField('event_date', formatDate(event.event_date), 'event date')}</span>
              <span>${icons.mapPin(14)} ${renderInlineField('location', escapeHtml(location || 'Destination TBD'), 'event location')}</span>
              <span>${icons.users(14)} Target: ${renderInlineField('guest_count', `<strong>${event.guest_count}</strong> Guests`, 'guest count')}</span>
            </div>
          </div>

          <div class="dashboard-quick-actions">
            <button class="btn btn-secondary btn-sm" data-dashboard-route="chat">
              ${icons.coPilot(14)} Co-Pilot Chat
            </button>
            <button id="btn-dashboard-plan-health" class="btn btn-secondary btn-sm">
              ${icons.alertCircle(14)} Plan Health & Crisis Mode
            </button>
            <button class="btn btn-gold btn-sm" data-dashboard-route="budget">
              ${icons.budget(14)} Manage Budget
            </button>
          </div>
        </div>
      </div>

      <!-- Needs Attention Alert (if blocked tasks or over budget) -->
      ${
        remainingBudget < 0 || blockedTasks.length > 0
          ? `
        <div style="display: flex; align-items: center; justify-content: space-between; padding: 12px 18px; background: var(--clr-warning-bg); border-left: 4px solid var(--clr-warning); border-radius: var(--radius-md); margin-bottom: 24px; font-size: 0.85rem;">
          <div style="display: flex; align-items: center; gap: 10px;">
            ${icons.alertCircle(18)}
            <div>
              <strong>Action Needed:</strong>
              ${remainingBudget < 0 ? ` Budget is over by ${formatCurrency(Math.abs(remainingBudget), currency)}.` : ''}
              ${blockedTasks.length > 0 ? ` ${blockedTasks.length} task(s) currently blocked by missing prerequisites.` : ''}
            </div>
          </div>
          <button class="btn btn-ghost btn-sm" data-dashboard-route="${remainingBudget < 0 ? 'budget' : 'tasks'}" style="color: var(--clr-warning); font-weight: 700;">
            Resolve →
          </button>
        </div>
      `
          : ''
      }

      <!-- Top Financial & Milestone Stats -->
      <div class="stat-grid">
        <div class="stat-card">
          <div class="stat-label">Total Budget</div>
          <div class="stat-value num">${renderInlineField('budget', formatCurrency(event.total_budget, currency), 'total budget')}</div>
          <div style="margin-top: 8px;">
            <div style="display: flex; justify-content: space-between; font-size: 0.75rem; color: var(--clr-text-muted); margin-bottom: 4px;">
              <span>Spent: ${formatCurrency(totalSpent, currency)}</span>
              <span class="num">${budgetSpentPct}%</span>
            </div>
            <div class="progress-bar">
              <div class="progress-fill ${totalSpent > event.total_budget ? 'over-budget' : ''}" style="width: ${budgetSpentPct}%;"></div>
            </div>
          </div>
          <div style="font-size: 0.75rem; margin-top: 6px; font-weight: 600; color: ${remainingBudget < 0 ? 'var(--clr-danger)' : 'var(--clr-success)'};">
            ${remainingBudget < 0 ? '⚠️ Over budget by ' + formatCurrency(Math.abs(remainingBudget), currency) : '✓ ' + formatCurrency(remainingBudget, currency) + ' available'}
          </div>
        </div>

        <div class="stat-card">
          <div class="stat-label">Milestone Execution</div>
          <div class="stat-value num">${doneTasks} / ${tasks.length}</div>
          <div style="display: flex; gap: 6px; margin-top: 8px; flex-wrap: wrap;">
            <span class="badge badge-success">${readyTasks.length} Ready</span>
            ${blockedTasks.length > 0 ? `<span class="badge badge-danger">${blockedTasks.length} Blocked</span>` : ''}
          </div>
          <div style="font-size: 0.75rem; color: var(--clr-text-muted); margin-top: 6px;">
            ${formatPercent(doneTasks, tasks.length)}% completed on schedule
          </div>
        </div>

        <div class="stat-card">
          <div class="stat-label">Vendor Contracts</div>
          <div class="stat-value num">${bookedVendors} / ${vendors.length}</div>
          <div style="font-size: 0.75rem; color: var(--clr-text-muted); margin-top: 8px;">
            Confirmed contracts
          </div>
          <div style="font-size: 0.75rem; color: var(--clr-accent); margin-top: 6px; font-weight: 600;">
            ${vendors.filter((v) => v.status === 'researching' || v.status === 'contacted').length} in active negotiation
          </div>
        </div>

        <div class="stat-card">
          <div class="stat-label">Guest RSVP Rate</div>
          <div class="stat-value num">${guestSummary.attending} Confirmed</div>
          <div style="display: flex; gap: 6px; margin-top: 8px; flex-wrap: wrap;">
            <span class="badge badge-info">${guestSummary.pending} Pending</span>
            ${guestSummary.declined > 0 ? `<span class="badge badge-muted">${guestSummary.declined} Declined</span>` : ''}
          </div>
          <div style="font-size: 0.75rem; color: var(--clr-text-muted); margin-top: 6px;">
            ${guestSummary.total} Total on invite register
          </div>
        </div>
      </div>

      <section class="card event-preferences-card" aria-labelledby="event-preferences-title">
        <div class="card-header">
          <div>
            <h3 id="event-preferences-title" class="card-title font-serif">Celebration Details</h3>
            <p class="text-muted" style="font-size: 0.8rem;">Edit each detail where it appears. Changes save to this event.</p>
          </div>
        </div>
        <div class="event-preferences-grid">
          ${preferenceFields.map(([field, label, value]) => {
            const display = Array.isArray(value) ? value.map(escapeHtml).join(', ') : escapeHtml(value || 'Not set');
            return `
              <div class="event-preference-item">
                <span class="event-preference-label">${escapeHtml(label)}</span>
                ${renderInlineField(field, display || 'Not set', label)}
              </div>
            `;
          }).join('')}
        </div>
      </section>

      <!-- Donut Chart & Actionable Tasks Grid -->
      <div class="grid-2" style="margin-bottom: 24px;">

        <!-- SVG Donut Chart Card -->
        <div class="card">
          <div class="card-header">
            <div>
              <h3 class="card-title font-serif">Budget Allocation Donut</h3>
              <p class="text-muted" style="font-size: 0.8rem;">Allocated vs available reserves</p>
            </div>
            <button class="btn btn-ghost btn-sm" data-dashboard-route="budget">
              Details →
            </button>
          </div>

          ${donutSvg}
        </div>

        <!-- Next 3 Actionable Tasks (Ready to Execute) -->
        <div class="card">
          <div class="card-header">
            <div>
              <h3 class="card-title font-serif">Next Critical Actions</h3>
              <p class="text-muted" style="font-size: 0.8rem;">Prerequisites met • Ready for immediate execution</p>
            </div>
            <button class="btn btn-ghost btn-sm" data-dashboard-route="tasks">
              All Tasks →
            </button>
          </div>

          ${
            readyTasks.length === 0
              ? `
            <div style="padding: 30px; text-align: center; color: var(--clr-text-muted); font-size: 0.875rem;">
              ${tasks.length === 0 ? 'No tasks generated yet. Let AI architect your milestone schedule.' : 'All ready tasks are completed! Check blocked milestones or add new ones.'}
              ${tasks.length === 0 ? `<div style="margin-top: 12px;"><button class="btn btn-secondary btn-sm" data-dashboard-route="tasks">Build Timeline with AI</button></div>` : ''}
            </div>
          `
              : `
            <div style="display: flex; flex-direction: column; gap: 10px;">
              ${readyTasks
                .slice(0, 3)
                .map(
                  (t) => `
                <div style="display: flex; align-items: center; justify-content: space-between; padding: 12px 14px; background: var(--clr-surface-subtle); border-radius: var(--radius-md); border-left: 3px solid var(--clr-success);">
                  <div style="min-width: 0; flex: 1; padding-right: 10px;">
                    <div style="font-weight: 700; font-size: 0.875rem; color: var(--clr-text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                      ${escapeHtml(t.title)}
                    </div>
                    <div style="font-size: 0.75rem; color: var(--clr-text-muted); margin-top: 2px;">
                      Due: ${formatDate(t.due_date)} • <span class="badge badge-gold" style="font-size: 0.65rem;">Priority ${t.priority}</span>
                    </div>
                  </div>
                  <span class="badge badge-success" style="font-size: 0.7rem;">Actionable Now</span>
                </div>
              `
                )
                .join('')}
            </div>
          `
          }
        </div>

      </div>

    </div>
  `;
}

function generateDonutSvg(categories, totalBudget, currency) {
  if (!categories || categories.length === 0) {
    return `
      <div style="padding: 24px; text-align: center; color: var(--clr-text-muted); font-size: 0.85rem;">
        No budget categories allocated yet. Click "Manage Budget" to split by celebration type.
      </div>
    `;
  }

  const palette = ['#14213D', '#C9A24B', '#2E7D5B', '#E8B4B8', '#2F5D9E', '#B7791F', '#5B6070'];
  const totalAlloc = categories.reduce((sum, c) => sum + (c.allocated || 0), 0);
  const remaining = Math.max(0, totalBudget - totalAlloc);

  const items = categories.slice(0, 4).map((c, i) => ({
    name: c.name,
    amount: c.allocated,
    color: palette[i % palette.length],
  }));

  if (remaining > 0) {
    items.push({
      name: 'Unallocated Reserve',
      amount: remaining,
      color: '#E6DFD3',
    });
  }

  const total = items.reduce((sum, it) => sum + it.amount, 0) || 1;
  const radius = 60;
  const strokeWidth = 24;
  const circumference = 2 * Math.PI * radius;

  let currentOffset = 0;
  const circles = items.map((it) => {
    const fraction = it.amount / total;
    const strokeDasharray = `${fraction * circumference} ${circumference}`;
    const strokeDashoffset = -currentOffset;
    currentOffset += fraction * circumference;

    return `
      <circle
        cx="90" cy="90" r="${radius}"
        fill="transparent"
        stroke="${it.color}"
        stroke-width="${strokeWidth}"
        stroke-dasharray="${strokeDasharray}"
        stroke-dashoffset="${strokeDashoffset}"
      />
    `;
  });

  const legend = items
    .map(
      (it) => `
      <div class="donut-legend-item">
        <span style="display: flex; align-items: center;">
          <span class="donut-legend-dot" style="background: ${it.color};"></span>
          <span style="color: var(--clr-text); font-weight: 600;">${escapeHtml(it.name)}</span>
        </span>
        <span class="num" style="color: var(--clr-text-muted);">${formatCurrency(it.amount, currency)}</span>
      </div>
    `
    )
    .join('');

  return `
    <div class="donut-chart-container">
      <svg width="180" height="180" viewBox="0 0 180 180" style="transform: rotate(-90deg);" aria-label="Budget distribution chart">
        ${circles.join('')}
      </svg>
      <div class="donut-legend">
        ${legend}
      </div>
    </div>
  `;
}

export function initDashboardPageEvents() {
  const pageBody = document.querySelector('.page-body');
  document.querySelectorAll('[data-dashboard-route]').forEach((button) => {
    button.addEventListener('click', () => {
      window.location.hash = `#${button.dataset.dashboardRoute}`;
    });
  });
  document.getElementById('btn-dashboard-plan-health')?.addEventListener('click', () => {
    window.location.hash = '#health';
  });
  document.getElementById('btn-empty-new-event')?.addEventListener('click', () => {
    openNewEventModal();
  });

  pageBody?.addEventListener('click', async (clickEvent) => {
    const editButton = clickEvent.target.closest('[data-inline-edit]');
    if (editButton) {
      const event = getCurrentEvent();
      const field = editButton.dataset.inlineEdit;
      const wrapper = editButton.closest('[data-inline-field]');
      if (!event || !wrapper) return;
      wrapper.dataset.originalMarkup = wrapper.innerHTML;
      wrapper.innerHTML = renderInlineEditor(field, event);
      wrapper.querySelector('[data-inline-control]')?.focus();
      return;
    }

    const cancelButton = clickEvent.target.closest('[data-inline-cancel]');
    if (cancelButton) {
      const wrapper = cancelButton.closest('[data-inline-field]');
      if (wrapper?.dataset.originalMarkup) {
        wrapper.innerHTML = wrapper.dataset.originalMarkup;
        delete wrapper.dataset.originalMarkup;
      }
      return;
    }

    const saveButton = clickEvent.target.closest('[data-inline-save]');
    if (!saveButton) return;

    const wrapper = saveButton.closest('[data-inline-field]');
    const control = wrapper?.querySelector('[data-inline-control]');
    const errorMessage = wrapper?.querySelector('[data-inline-error]');
    const field = wrapper?.dataset.inlineField;
    const event = getCurrentEvent();
    if (!wrapper || !control || !field || !event) return;
    if (!control.reportValidity()) return;

    const value = control.value.trim();
    const profile = { ...(event.profile || {}) };
    const payload = {};
    switch (field) {
      case 'name':
        payload.name = value;
        profile.occasion = value;
        break;
      case 'event_type':
        payload.event_type = value;
        break;
      case 'event_date':
        profile.event_date = value || null;
        break;
      case 'location':
        profile.location = value;
        break;
      case 'guest_count':
        profile.guest_count = Number(value);
        break;
      case 'budget':
        profile.budget = Number(value);
        break;
      case 'experience_level':
        profile.experience_level = value;
        break;
      case 'must_haves':
      case 'priorities':
      case 'age_groups':
        profile[field] = value.split('\n').map((item) => item.trim()).filter(Boolean);
        break;
      case 'atmosphere':
      case 'cultural_preferences':
      case 'accessibility_needs':
      case 'venue_limits':
        profile[field] = value;
        break;
      default:
        return;
    }

    if (field !== 'event_type') payload.profile = profile;
    saveButton.disabled = true;
    try {
      await updateEventDetails(event.id, payload);
      showToast('Event details updated.', 'success');
    } catch (error) {
      if (errorMessage) errorMessage.textContent = error.message || 'Could not save this detail.';
      showToast(error.message || 'Could not save this detail. Please try again.', 'error');
      saveButton.disabled = false;
    }
  });
}

function renderInlineField(field, displayHtml, label) {
  return `
    <span class="inline-edit-field" data-inline-field="${field}">
      <span class="inline-edit-display">${displayHtml}</span>
      <button class="inline-edit-button" type="button" data-inline-edit="${field}" aria-label="Edit ${escapeHtml(label)}" title="Edit ${escapeHtml(label)}">Edit</button>
    </span>
  `;
}

function renderInlineEditor(field, event) {
  const profile = event.profile || {};
  const definitions = {
    name: { label: 'Event name', type: 'text', value: event.name || '', required: true, maxLength: 200 },
    event_type: { label: 'Occasion type', type: 'select', value: event.event_type || 'wedding', options: ['wedding', 'birthday', 'community'] },
    event_date: { label: 'Event date', type: 'date', value: event.event_date || profile.event_date || '' },
    location: { label: 'Event location', type: 'text', value: profile.location || event.location || profile.venue_limits || '', maxLength: 500 },
    guest_count: { label: 'Guest count', type: 'number', value: event.guest_count || profile.guest_count || 1, min: 1, max: 100000, step: 1, required: true },
    budget: { label: 'Total budget', type: 'number', value: event.total_budget || profile.budget || 1, min: 1, max: 1000000000, step: 'any', required: true },
    experience_level: { label: 'Planning experience', type: 'select', value: profile.experience_level || 'moderate', options: ['simple', 'moderate', 'premium'] },
    atmosphere: { label: 'Atmosphere', type: 'text', value: profile.atmosphere || '', maxLength: 500 },
    must_haves: { label: 'Must-haves', type: 'textarea', value: (profile.must_haves || []).join('\n'), maxLength: 4000 },
    priorities: { label: 'Priorities', type: 'textarea', value: (profile.priorities || []).join('\n'), maxLength: 2000 },
    age_groups: { label: 'Guest age groups', type: 'textarea', value: (profile.age_groups || []).join('\n'), maxLength: 2000 },
    cultural_preferences: { label: 'Cultural preferences', type: 'text', value: profile.cultural_preferences || '', maxLength: 500 },
    accessibility_needs: { label: 'Accessibility needs', type: 'text', value: profile.accessibility_needs || '', maxLength: 500 },
    venue_limits: { label: 'Venue requirements', type: 'text', value: profile.venue_limits || '', maxLength: 500 },
  };
  const definition = definitions[field];
  if (!definition) return '';
  const controlId = `inline-edit-${field}`;
  const commonAttributes = `id="${controlId}" data-inline-control aria-label="${escapeHtml(definition.label)}"`;
  let control;

  if (definition.type === 'select') {
    control = `<select ${commonAttributes}>${definition.options.map((option) => `
      <option value="${option}" ${option === definition.value ? 'selected' : ''}>${escapeHtml(option.replace('_', ' '))}</option>
    `).join('')}</select>`;
  } else if (definition.type === 'textarea') {
    control = `<textarea ${commonAttributes} maxlength="${definition.maxLength}" rows="2">${escapeHtml(definition.value)}</textarea>`;
  } else {
    const today = new Date();
    const minDate = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;
    const attributes = [
      definition.required ? 'required' : '',
      definition.min ? `min="${definition.min}"` : '',
      definition.max ? `max="${definition.max}"` : '',
      definition.step ? `step="${definition.step}"` : '',
      definition.maxLength ? `maxlength="${definition.maxLength}"` : '',
      definition.type === 'date' ? `min="${minDate}"` : '',
    ].filter(Boolean).join(' ');
    control = `<input ${commonAttributes} type="${definition.type}" value="${escapeHtml(String(definition.value))}" ${attributes}>`;
  }

  return `
    <span class="inline-edit-form" role="group" aria-label="Edit ${escapeHtml(definition.label)}">
      ${control}
      <span class="inline-edit-actions">
        <button class="btn btn-gold btn-sm" type="button" data-inline-save>Save</button>
        <button class="btn btn-ghost btn-sm" type="button" data-inline-cancel>Cancel</button>
      </span>
      <span class="inline-edit-error" data-inline-error role="alert"></span>
    </span>
  `;
}
