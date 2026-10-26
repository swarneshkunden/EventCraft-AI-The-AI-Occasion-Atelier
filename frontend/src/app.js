/**
 * EventCraft AI — Main Single Page Application Bootstrap & Router.
 */
import { checkSession, getCurrentUser, subscribeAuth } from './services/auth.js';
import { fetchEvents, getCurrentEvent, subscribeEvents } from './services/events.js';
import { renderNavbar, initNavbarEvents } from './components/Navbar.js';
import { renderSidebar, initSidebarEvents } from './components/Sidebar.js';

import { renderAuthPage, initAuthPageEvents } from './pages/AuthPage.js';
import { renderDashboardPage, initDashboardPageEvents } from './pages/DashboardPage.js';
import { renderBudgetPage, initBudgetPageEvents } from './pages/BudgetPage.js';
import { renderTasksPage, initTasksPageEvents } from './pages/TasksPage.js';
import { renderVendorsPage, initVendorsPageEvents } from './pages/VendorsPage.js';
import { renderGuestsPage, initGuestsPageEvents } from './pages/GuestsPage.js';
import { renderChatPage, initChatPageEvents } from './pages/ChatPage.js';
import { renderPlanHealthPage, initPlanHealthPageEvents } from './pages/PlanHealthPage.js';
import { hasPendingMutations } from './services/api.js';

const appEl = document.getElementById('app');
let renderSequence = 0;
let refreshInProgress = false;
let pendingAppRender = false;
let lastUserActivity = Date.now();

function hasUnsavedFormChanges() {
  return [...document.querySelectorAll('#page-content input, #page-content textarea, #page-content select')]
    .some((control) => {
      if (control instanceof HTMLInputElement) {
        if (control.type === 'checkbox' || control.type === 'radio') {
          return control.checked !== control.defaultChecked;
        }
        if (control.type === 'file') return control.files?.length > 0;
        return control.value !== control.defaultValue;
      }
      if (control instanceof HTMLTextAreaElement) {
        return control.value !== control.defaultValue;
      }
      if (control instanceof HTMLSelectElement) {
        return [...control.options].some((option) => option.selected !== option.defaultSelected);
      }
      return false;
    });
}

function canAutoRefresh() {
  const activeElement = document.activeElement;
  return Boolean(
    getCurrentUser()
    && document.visibilityState === 'visible'
    && !document.querySelector('.modal-backdrop')
    && !activeElement?.matches('input, textarea, select, [contenteditable="true"]')
    && Date.now() - lastUserActivity >= 5000
    && !hasUnsavedFormChanges()
    && !hasPendingMutations()
  );
}

function getRoute() {
  const hash = window.location.hash.replace('#', '').trim();
  return hash || 'dashboard';
}

async function renderPage(route, contentEl) {
  const sequence = ++renderSequence;
  const pages = {
    dashboard: [renderDashboardPage, initDashboardPageEvents],
    budget: [renderBudgetPage, initBudgetPageEvents],
    tasks: [renderTasksPage, initTasksPageEvents],
    vendors: [renderVendorsPage, initVendorsPageEvents],
    guests: [renderGuestsPage, initGuestsPageEvents],
    chat: [renderChatPage, initChatPageEvents],
    health: [renderPlanHealthPage, initPlanHealthPageEvents],
  };
  const [render, initialize] = pages[route] || pages.dashboard;

  try {
    const html = await render();
    if (
      sequence !== renderSequence
      || route !== getRoute()
      || contentEl !== document.getElementById('page-content')
    ) {
      return;
    }
    contentEl.innerHTML = html;
    initialize();
  } catch (err) {
    console.error('Page render error', err);
    if (
      sequence !== renderSequence
      || route !== getRoute()
      || contentEl !== document.getElementById('page-content')
    ) {
      return;
    }
    contentEl.innerHTML = `
      <div class="page-body">
        <div class="card" style="border-left: 4px solid var(--clr-danger);">
          <h3>Error loading page</h3>
          <p style="color: var(--clr-text-muted);">${err.message || 'An unexpected error occurred.'}</p>
          <button id="btn-reload-application" class="btn btn-secondary btn-sm" style="margin-top: 12px;">
            Reload Application
          </button>
        </div>
      </div>
    `;
    document.getElementById('btn-reload-application')?.addEventListener('click', () => {
      window.location.reload();
    });
  }
}

async function renderApp() {
  pendingAppRender = false;
  renderSequence++;
  const user = getCurrentUser();
  const route = getRoute();

  if (!user) {
    if (route !== 'login') {
      window.location.hash = '#login';
      return;
    }
    appEl.innerHTML = renderAuthPage();
    initAuthPageEvents();
    return;
  }

  // User is logged in. If on #login, redirect to #dashboard
  if (route === 'login') {
    window.location.hash = '#dashboard';
    return;
  }

  // Render Shell: Sidebar + Main Content (Navbar + Active Page)
  appEl.innerHTML = `
    <div class="app-shell">
      ${renderSidebar(route)}
      <div class="main-content">
        ${renderNavbar()}
        <main id="main-content" class="workspace-main" tabindex="-1">
          <div id="page-content" style="min-height: calc(100vh - var(--header-height));">
            <div style="padding: 40px; text-align: center;">
              <span class="spinner spinner-lg"></span>
            </div>
          </div>
        </main>
      </div>
    </div>
  `;

  initSidebarEvents();
  initNavbarEvents();

  const contentEl = document.getElementById('page-content');
  await renderPage(route, contentEl);
}

async function refreshCurrentPage() {
  if (
    refreshInProgress
    || !canAutoRefresh()
  ) {
    return;
  }

  if (pendingAppRender) {
    pendingAppRender = false;
    await renderApp();
    return;
  }

  const route = getRoute();
  const contentEl = document.getElementById('page-content');
  if (!contentEl) return;

  const previousEvent = JSON.stringify(getCurrentEvent());
  refreshInProgress = true;

  try {
    await fetchEvents();
    if (
      route !== getRoute()
      || contentEl !== document.getElementById('page-content')
    ) {
      return;
    }

    if (previousEvent !== JSON.stringify(getCurrentEvent())) {
      if (!canAutoRefresh()) {
        pendingAppRender = true;
        return;
      }
      await renderPage(route, contentEl);
    }
  } catch (err) {
    console.error('Background refresh failed', err);
  } finally {
    refreshInProgress = false;
  }
}

// Router listener
window.addEventListener('hashchange', () => {
  renderApp();
});
window.addEventListener('focus', refreshCurrentPage);
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible') refreshCurrentPage();
});
window.setInterval(refreshCurrentPage, 15000);
window.addEventListener('beforeunload', (event) => {
  if (!hasUnsavedFormChanges()) return;
  event.preventDefault();
  event.returnValue = '';
});

for (const eventName of ['pointerdown', 'keydown', 'input', 'change', 'submit']) {
  document.addEventListener(eventName, () => {
    lastUserActivity = Date.now();
  }, true);
}

// Subscribe to auth & event changes
subscribeAuth(() => {
  renderApp();
});

subscribeEvents(() => {
  if (!canAutoRefresh()) {
    pendingAppRender = true;
    return;
  }
  pendingAppRender = false;
  renderApp();
});

// App Startup
async function init() {
  appEl.innerHTML = `
    <div style="display: flex; height: 100vh; align-items: center; justify-content: center; flex-direction: column; gap: 16px;">
      <span class="spinner spinner-lg"></span>
      <p style="color: var(--clr-text-muted); font-size: 0.9rem;">Starting EventCraft AI...</p>
    </div>
  `;

  const user = await checkSession();
  if (user) {
    await fetchEvents();
  }
  await renderApp();
}

init();
