/**
 * Sidebar navigation component with Ivory & Midnight Gold aesthetic.
 */
import { getCurrentUser, logout } from '../services/auth.js';
import {
  deleteEventById,
  getCurrentEvent,
  getEventsList,
  selectEventById,
} from '../services/events.js';
import { openNewEventModal } from './NewEventModal.js';
import { escapeHtml, showToast } from '../utils/toast.js';
import { icons } from '../utils/icons.js';

export function renderSidebar(currentRoute) {
  const user = getCurrentUser();
  const currentEvent = getCurrentEvent();
  const events = getEventsList();

  const navItems = [
    { route: 'dashboard', label: 'Overview', icon: icons.dashboard() },
    { route: 'budget', label: 'Budget & Scenarios', icon: icons.budget() },
    { route: 'tasks', label: 'Milestones & Timeline', icon: icons.timeline() },
    { route: 'vendors', label: 'Vendor Directory', icon: icons.vendors() },
    { route: 'guests', label: 'Guests & RSVPs', icon: icons.guests() },
    { route: 'health', label: 'Plan Health & Crisis', icon: icons.alertCircle() },
    { route: 'chat', label: 'AI Co-Pilot & Ideas', icon: icons.coPilot() },
  ];

  const initials = user?.display_name
    ? user.display_name.slice(0, 2).toUpperCase()
    : 'EC';

  return `
    <aside class="sidebar" id="sidebar" role="navigation" aria-label="Main Navigation">
      <!-- Luxury Brand Crest -->
      <div class="sidebar-brand">
        ${icons.crest(30)}
        <div>
          <div class="sidebar-brand-title">EventCraft</div>
          <div class="sidebar-brand-subtitle">Atelier & AI Planner</div>
        </div>
      </div>

      <!-- Active Event Selector -->
      <div class="sidebar-event-selector">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
          <span style="font-size: 0.7rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; color: var(--clr-text-muted);">
            Active Celebration
          </span>
          <button id="btn-sidebar-new-event" class="btn btn-ghost btn-sm" style="padding: 2px 6px; height: 26px; font-size: 0.75rem; color: var(--clr-accent);" title="Create New Event">
            ${icons.plus(14)} New
          </button>
        </div>
        <div style="display: flex; gap: 6px; align-items: center;">
          <select id="event-selector" aria-label="Select event" style="font-size: 0.8rem; padding: 6px 10px; border-radius: var(--radius-sm); width: 100%; min-height: 38px;">
            ${events.length === 0 ? '<option value="">No events yet</option>' : ''}
            ${events.map((event) => `
              <option value="${escapeHtml(event.id)}" ${currentEvent?.id === event.id ? 'selected' : ''}>
                ${escapeHtml(event.name)}
              </option>
            `).join('')}
          </select>
        </div>
        <button
          id="btn-sidebar-delete-event"
          class="btn btn-danger btn-sm"
          style="width: 100%; margin-top: 6px;"
          ${currentEvent ? '' : 'disabled'}
        >Delete selected event</button>
      </div>

      <!-- Navigation Modules -->
      <nav class="sidebar-nav">
        <div class="nav-section-title">Planning Suite</div>
        ${navItems
          .map(
            (item) => `
          <button
            class="nav-item ${currentRoute === item.route ? 'active' : ''}"
            data-route="${item.route}"
            id="nav-${item.route}"
            aria-current="${currentRoute === item.route ? 'page' : 'false'}"
          >
            ${item.icon}
            <span>${item.label}</span>
          </button>
        `
          )
          .join('')}
      </nav>

      <!-- User Profile & Sign Out -->
      <div class="sidebar-user">
        <div class="user-avatar" title="${escapeHtml(user?.display_name || user?.email || '')}">
          ${initials}
        </div>
        <div style="flex: 1; min-width: 0;">
          <div style="font-size: var(--text-sm); font-weight: 700; color: var(--clr-text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
            ${escapeHtml(user?.display_name || 'Event Host')}
          </div>
          <div style="font-size: var(--text-xs); color: var(--clr-text-muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
            ${escapeHtml(user?.email || '')}
          </div>
        </div>
        <button id="btn-logout" class="btn btn-ghost btn-sm" title="Log Out" aria-label="Log Out" style="padding: 6px; width: 36px; height: 36px;">
          ${icons.logout(16)}
        </button>
      </div>
    </aside>
  `;
}

export function initSidebarEvents() {
  document.querySelectorAll('.nav-item').forEach((btn) => {
    btn.addEventListener('click', () => {
      const route = btn.getAttribute('data-route');
      window.location.hash = `#${route}`;
      document.getElementById('sidebar')?.classList.remove('open');
      document.getElementById('sidebar-backdrop')?.remove();
      document.querySelector('.main-content')?.removeAttribute('inert');
      document.body.classList.remove('sidebar-open');
      document.getElementById('btn-mobile-toggle')?.setAttribute('aria-expanded', 'false');
    });
  });

  const select = document.getElementById('event-selector');
  select?.addEventListener('change', async (event) => {
    const id = event.target.value;
    if (id) await selectEventById(id);
  });

  document.getElementById('btn-sidebar-delete-event')?.addEventListener('click', async (event) => {
    const eventId = select?.value;
    const selectedEvent = getEventsList().find((item) => item.id === eventId);
    if (!selectedEvent) return;

    if (!window.confirm(`Delete "${selectedEvent.name}" and all of its planning data? This cannot be undone.`)) {
      return;
    }

    event.currentTarget.disabled = true;
    try {
      await deleteEventById(selectedEvent.id);
      window.location.hash = '#dashboard';
      showToast(`"${selectedEvent.name}" was deleted.`, 'success');
    } catch (err) {
      showToast(err.message || 'Could not delete this event. Please try again.', 'error');
      event.currentTarget.disabled = false;
    }
  });

  const newBtn = document.getElementById('btn-sidebar-new-event');
  if (newBtn) {
    newBtn.addEventListener('click', () => {
      openNewEventModal();
    });
  }

  const logoutBtn = document.getElementById('btn-logout');
  if (logoutBtn) {
    logoutBtn.addEventListener('click', async () => {
      await logout();
      window.location.hash = '#login';
    });
  }
}
