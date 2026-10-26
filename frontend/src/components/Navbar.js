/**
 * Top Navbar component with theme switcher and luxury countdown pills.
 */
import { getCurrentEvent } from '../services/events.js';
import { daysUntil } from '../utils/formatters.js';
import { openNewEventModal } from './NewEventModal.js';
import { escapeHtml } from '../utils/toast.js';
import { icons } from '../utils/icons.js';
import { getPreferredTheme, toggleTheme } from '../utils/theme.js';

export function renderNavbar() {
  const event = getCurrentEvent();
  const days = event ? daysUntil(event.event_date) : null;
  const currentTheme = document.documentElement.getAttribute('data-theme') || getPreferredTheme();
  const isDemo = event?.is_demo || false;

  return `
    ${
      isDemo
        ? `
      <div class="demo-banner" id="demo-banner">
        <div style="display: flex; align-items: center; gap: 8px;">
          ${icons.sparkle(14)}
          <span><strong>Demo mode:</strong> Exploring a sample wedding. Try Plan Health, budget scenarios, timeline dependencies, and vendor questions.</span>
        </div>
        <button id="btn-dismiss-demo-banner" class="btn btn-ghost btn-sm" style="color: #FAF7F2; padding: 2px 8px; font-size: 0.75rem;" aria-label="Dismiss banner">
          ✕
        </button>
      </div>
    `
        : ''
    }

    <header class="top-navbar" role="banner">
      <div class="navbar-context">
        <button id="btn-mobile-toggle" class="btn btn-secondary mobile-menu-btn" aria-label="Toggle menu" aria-controls="sidebar" aria-expanded="false" style="padding: 6px 10px; min-height: 40px;">
          ☰
        </button>

        ${
          event
            ? `
          <div class="navbar-event-details">
            <span class="font-serif" style="font-weight: 700; font-size: 1.15rem; color: var(--clr-text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 280px;">
              ${escapeHtml(event.title || event.name)}
            </span>
            <span class="badge badge-gold" style="text-transform: uppercase;">
              ${escapeHtml(event.event_type)}
            </span>
            ${
              days !== null
                ? `<span class="badge ${days < 0 ? 'badge-muted' : days <= 14 ? 'badge-danger' : 'badge-navy'}">
                    ${icons.timeline(12)} ${days < 0 ? 'Concluded' : days === 0 ? 'Today!' : `${days} days left`}
                   </span>`
                : ''
            }
          </div>
        `
            : `
          <div class="text-muted" style="font-size: 0.875rem;">
            No celebration selected. Plan a new event or load a demo below.
          </div>
        `
        }
      </div>

      <!-- Action Suite: Theme Switcher, Quick Ideas, New Event -->
      <div class="navbar-actions">
        <!-- Theme Toggle -->
        <button id="btn-theme-toggle" class="btn btn-secondary btn-icon" title="Toggle Light / Dark mode" aria-label="Toggle Light / Dark mode">
          ${currentTheme === 'dark' ? icons.sun(18) : icons.moon(18)}
        </button>

        <button id="btn-nav-ideas" class="btn btn-secondary btn-sm" title="AI Inspiration & Moodboards" aria-label="Open ideas">
          ${icons.ideas(14)} <span>Ideas</span>
        </button>

        <button id="btn-nav-new-event" class="btn btn-gold btn-sm" aria-label="Plan a new event">
          ${icons.plus(14)} <span>Plan Event</span>
        </button>
      </div>
    </header>
  `;
}

export function initNavbarEvents() {
  // Mobile drawer toggle
  const toggleBtn = document.getElementById('btn-mobile-toggle');
  if (toggleBtn) {
    const closeSidebar = () => {
      const sidebar = document.getElementById('sidebar');
      if (!sidebar) return;

      sidebar.classList.remove('open');
      document.getElementById('sidebar-backdrop')?.remove();
      document.querySelector('.main-content')?.removeAttribute('inert');
      document.body.classList.remove('sidebar-open');
      toggleBtn.setAttribute('aria-expanded', 'false');
      toggleBtn.focus();
      sidebar.removeEventListener('keydown', onSidebarKeydown);
    };

    const onSidebarKeydown = (event) => {
      if (event.key === 'Escape') closeSidebar();
    };

    toggleBtn.addEventListener('click', () => {
      const sidebar = document.getElementById('sidebar');
      if (!sidebar) return;
      const isOpen = sidebar.classList.toggle('open');
      toggleBtn.setAttribute('aria-expanded', String(isOpen));
      if (isOpen) {
        document.querySelector('.main-content')?.setAttribute('inert', '');
        document.body.classList.add('sidebar-open');
        const backdrop = document.createElement('div');
        backdrop.id = 'sidebar-backdrop';
        backdrop.className = 'sidebar-backdrop';
        backdrop.setAttribute('aria-hidden', 'true');
        backdrop.addEventListener('click', closeSidebar);
        document.body.appendChild(backdrop);
        sidebar.addEventListener('keydown', onSidebarKeydown);
        sidebar.querySelector('.nav-item')?.focus();
      } else {
        closeSidebar();
      }
    });
  }

  // Theme toggle button
  const themeBtn = document.getElementById('btn-theme-toggle');
  if (themeBtn) {
    themeBtn.addEventListener('click', () => {
      const newTheme = toggleTheme();
      themeBtn.innerHTML = newTheme === 'dark' ? icons.sun(18) : icons.moon(18);
    });
  }

  // Dismiss demo banner
  document.getElementById('btn-dismiss-demo-banner')?.addEventListener('click', () => {
    document.getElementById('demo-banner')?.remove();
  });

  // Navigation shortcuts
  document.getElementById('btn-nav-ideas')?.addEventListener('click', () => {
    window.location.hash = '#chat';
  });

  document.getElementById('btn-nav-new-event')?.addEventListener('click', () => {
    openNewEventModal();
  });
}
