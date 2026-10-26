/**
 * Explainable plan-health score and accept-before-save crisis proposals.
 */
import { getCurrentEvent } from '../services/events.js';
import { getCurrentUser } from '../services/auth.js';
import {
  acceptCrisisProposal,
  declineCrisisProposal,
  getPlanHealth,
  proposeCrisisResponse,
  undoCrisisProposal,
} from '../services/events.js';
import { escapeHtml } from '../utils/toast.js';

let activeProposal = null;
let acceptedProposalId = null;

export async function renderPlanHealthPage() {
  const event = getCurrentEvent();
  activeProposal = null;
  acceptedProposalId = event
    ? sessionStorage.getItem(`plan-health:${event.id}:accepted-proposal`)
    : null;

  if (!event) {
    return `
      <div class="page-body">
        <section class="empty-state card" aria-labelledby="plan-health-title">
          <h1 id="plan-health-title" class="font-serif">Plan Health & Crisis Mode</h1>
          <p class="text-muted">Choose or create an event to review its plan health.</p>
        </section>
      </div>
    `;
  }

  let health = null;
  let loadError = '';
  try {
    health = await getPlanHealth(event.id);
  } catch (error) {
    loadError = error.message || 'Plan health could not be loaded.';
  }

  return `
    <div class="page-body plan-health-page">
      <header class="plan-health-header">
        <div>
          <span class="badge badge-gold">Plan Health & Crisis Mode</span>
          <h1 class="font-serif">Keep the celebration on track</h1>
          <p class="text-muted">
            A transparent score flags practical risks. When plans change, compare options before anything is saved.
          </p>
        </div>
        <a class="btn btn-secondary" href="#dashboard">Back to overview</a>
      </header>

      <div id="health-load-error" role="alert" aria-live="assertive">
        ${loadError ? `<p class="plan-health-error">${escapeHtml(loadError)}</p>` : ''}
      </div>

      <section class="health-overview card" aria-labelledby="health-score-title">
        ${renderHealthPanel(health)}
      </section>

      <section class="crisis-card card" aria-labelledby="crisis-title">
        <div class="crisis-card-heading">
          <div>
            <span class="badge badge-warning">Change happens</span>
            <h2 id="crisis-title" class="font-serif">Something went wrong?</h2>
            <p class="text-muted">
              Describe the change. We will show the affected plan and trade-offs; nothing changes until you accept.
            </p>
          </div>
        </div>

        <form id="crisis-form">
          <label for="crisis-description">What changed?</label>
          <textarea
            id="crisis-description"
            name="description"
            rows="3"
            maxlength="500"
            required
            aria-describedby="crisis-help"
            placeholder="For example: guests increased from 150 to 220"
          ></textarea>
          <div class="crisis-form-footer">
            <p id="crisis-help" class="text-muted">Use a short description, up to 500 characters.</p>
            <button id="btn-crisis-propose" class="btn btn-gold" type="submit">
              Review response options
            </button>
          </div>
        </form>

        <div class="crisis-examples" aria-label="Example changes">
          <span class="text-muted">Try:</span>
          <button class="chip crisis-example" type="button" data-scenario="The caterer cancelled">
            Caterer cancelled
          </button>
          <button class="chip crisis-example" type="button" data-scenario="It might rain">
            It might rain
          </button>
          <button class="chip crisis-example" type="button" data-scenario="Guests jumped from 150 to 220">
            Guests increased
          </button>
          <button class="chip crisis-example" type="button" data-scenario="The event moved up 2 weeks">
            Event moved up
          </button>
        </div>

        <div id="crisis-feedback" class="crisis-feedback" role="status" aria-live="polite"></div>
        <div id="crisis-proposal" class="crisis-proposal" aria-live="polite"></div>
      </section>
    </div>
  `;
}

function renderHealthPanel(health) {
  if (!health) {
    return `
      <div class="health-score-copy">
        <h2 id="health-score-title">Plan Health Score</h2>
        <p class="text-muted">The score is unavailable. You can still prepare a change proposal below.</p>
      </div>
    `;
  }
  const score = Math.max(0, Math.min(100, Number(health.score) || 0));
  const deductions = (health.deductions || []).map((item) => `
    <li class="health-risk-item">
      <span class="health-risk-points">−${escapeHtml(item.points)} pts</span>
      <div>
        <strong>${escapeHtml(item.reason)}</strong>
        <p class="text-muted">${escapeHtml(item.next_step)}</p>
      </div>
    </li>
  `).join('');

  return `
    <div class="health-score-layout">
      <div
        class="health-score-ring"
        role="img"
        aria-label="Plan Health Score: ${score} out of 100"
        style="--health-score: ${score}%"
      >
        <span class="health-score-number">${score}</span>
        <span class="health-score-denominator">/ 100</span>
      </div>
      <div class="health-score-copy">
        <h2 id="health-score-title">Plan Health Score</h2>
        <p class="health-score-label">${escapeHtml(health.label)}</p>
        <p class="text-muted">${escapeHtml(health.summary)}</p>
        <p class="health-score-method">
          Rule-based checks: budget pressure, overdue or blocked work, deadline proximity,
          missing vendor quotes, capacity, and dependency cycles.
        </p>
      </div>
    </div>
    <div class="health-risks">
      <h3>Why the score changed</h3>
      ${
        deductions
          ? `<ul class="health-risk-list">${deductions}</ul>`
          : '<p class="health-no-risks">No tracked risks were found in the current plan.</p>'
      }
    </div>
  `;
}

function renderProposal(proposal) {
  const options = proposal.options.map((option, index) => {
    const budget = (option.diff.budget || []).map((item) => `
      <li>
        ${escapeHtml(item.name)}: ${formatMoney(item.before)} → ${formatMoney(item.after)}
        <span class="badge badge-verification">Estimated, not confirmed</span>
      </li>
    `).join('');
    const tasks = (option.diff.tasks || []).map((item) => `
      <li>${escapeHtml(item.title)}: ${item.before ? escapeHtml(item.before) : 'New'} → ${escapeHtml(item.after)}</li>
    `).join('');
    const eventDate = option.diff.event_date
      ? `<li>Event date: ${escapeHtml(option.diff.event_date.before)} → ${escapeHtml(option.diff.event_date.after)}</li>`
      : '';
    const guests = option.diff.guest_count
      ? `<li>Guest target: ${escapeHtml(option.diff.guest_count.before)} → ${escapeHtml(option.diff.guest_count.after)}</li>`
      : '';
    const vendors = (option.diff.vendors || []).length
      ? `<li>${option.diff.vendors.length} selected vendor(s) will be marked unselected. <span class="badge badge-verification">Needs verification</span></li>`
      : '';
    const noChanges = !eventDate && !guests && !budget && !tasks && !vendors
      ? '<li>No structural changes are proposed.</li>'
      : '';

    return `
      <label class="crisis-option" for="crisis-option-${index}">
        <input
          id="crisis-option-${index}"
          type="radio"
          name="crisis-option"
          value="${escapeHtml(option.id)}"
          ${index === 0 ? 'checked' : ''}
        >
        <span class="crisis-option-content">
          <strong>${escapeHtml(option.label)}</strong>
          <span class="text-muted">${escapeHtml(option.tradeoff)}</span>
          <span class="crisis-option-diff">
            <strong>Proposed changes</strong>
            <ul>${eventDate}${guests}${budget}${tasks}${vendors}${noChanges}</ul>
          </span>
        </span>
      </label>
    `;
  }).join('');

  return `
    <div class="crisis-proposal-heading">
      <h3>Compare response options</h3>
      <p class="text-muted">${escapeHtml(proposal.interpretation)}</p>
      <p class="text-muted">AI may help interpret unfamiliar wording; all scores, arithmetic, diffs and saved changes are deterministic.</p>
    </div>
    <form id="crisis-choice-form">
      <fieldset>
        <legend class="sr-only">Choose a response option</legend>
        ${options}
      </fieldset>
      <div class="crisis-actions">
        <button id="btn-crisis-accept" class="btn btn-gold" type="submit">Accept selected changes</button>
        <button id="btn-crisis-decline" class="btn btn-secondary" type="button">Decline proposal</button>
      </div>
    </form>
  `;
}

function formatMoney(value) {
  const currency = getCurrentUser()?.currency || 'INR';
  const amount = Number(value);
  if (!Number.isFinite(amount)) return '—';
  return `${escapeHtml(currency)} ${amount.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}

function setFeedback(message, isError = false) {
  const feedback = document.getElementById('crisis-feedback');
  if (!feedback) return;
  feedback.className = `crisis-feedback${isError ? ' is-error' : ''}`;
  feedback.textContent = message;
}

export function initPlanHealthPageEvents() {
  const event = getCurrentEvent();
  if (!event) return;
  if (acceptedProposalId) {
    setFeedback('A recently accepted change can still be undone if the plan has not changed.');
    renderUndoButton(event.id);
  }

  const description = document.getElementById('crisis-description');
  document.querySelectorAll('.crisis-example').forEach((button) => {
    button.addEventListener('click', () => {
      description.value = button.dataset.scenario || '';
      description.focus();
    });
  });

  document.getElementById('crisis-form')?.addEventListener('submit', async (submitEvent) => {
    submitEvent.preventDefault();
    const button = document.getElementById('btn-crisis-propose');
    const proposalContainer = document.getElementById('crisis-proposal');
    const text = description.value.trim();
    if (!text || !button || !proposalContainer) return;

    button.disabled = true;
    button.textContent = 'Reviewing options…';
    proposalContainer.innerHTML = '';
    setFeedback('Preparing a proposal. Your plan has not been changed.');
    try {
      activeProposal = await proposeCrisisResponse(event.id, text);
      proposalContainer.innerHTML = renderProposal(activeProposal);
      setFeedback('Choose one option to continue, or decline. Nothing has been saved yet.');
      initProposalEvents(event.id);
    } catch (error) {
      setFeedback(error.message || 'Could not prepare options. Please try again.', true);
    } finally {
      button.disabled = false;
      button.textContent = 'Review response options';
    }
  });
}

function initProposalEvents(eventId) {
  document.getElementById('crisis-choice-form')?.addEventListener('submit', async (event) => {
    event.preventDefault();
    const selected = document.querySelector('input[name="crisis-option"]:checked');
    if (!activeProposal || !selected) return;
    const button = document.getElementById('btn-crisis-accept');
    if (button) button.disabled = true;
    try {
      await acceptCrisisProposal(eventId, activeProposal.proposal_id, selected.value);
      acceptedProposalId = activeProposal.proposal_id;
      sessionStorage.setItem(`plan-health:${eventId}:accepted-proposal`, acceptedProposalId);
      activeProposal = null;
      document.getElementById('crisis-proposal').innerHTML = '';
      setFeedback('Changes accepted and saved. You can undo them while the plan has not changed again.');
      renderUndoButton(eventId);
    } catch (error) {
      setFeedback(error.message || 'Changes were not applied. Refresh the proposal and try again.', true);
      if (button) button.disabled = false;
      return;
    }
    await refreshHealthPanel(eventId);
  });

  document.getElementById('btn-crisis-decline')?.addEventListener('click', async () => {
    if (!activeProposal) return;
    const proposalId = activeProposal.proposal_id;
    try {
      await declineCrisisProposal(eventId, proposalId);
      activeProposal = null;
      document.getElementById('crisis-proposal').innerHTML = '';
      setFeedback('Proposal declined. Your plan was not changed.');
    } catch (error) {
      setFeedback(error.message || 'Could not decline this proposal.', true);
    }
  });
}

function renderUndoButton(eventId) {
  const feedback = document.getElementById('crisis-feedback');
  if (!feedback || !acceptedProposalId) return;
  const undo = document.createElement('button');
  undo.type = 'button';
  undo.className = 'btn btn-secondary crisis-undo-button';
  undo.textContent = 'Undo accepted changes';
  undo.addEventListener('click', async () => {
    undo.disabled = true;
    try {
      await undoCrisisProposal(eventId, acceptedProposalId);
      acceptedProposalId = null;
      sessionStorage.removeItem(`plan-health:${eventId}:accepted-proposal`);
      setFeedback('Accepted changes were undone. The original plan is restored.');
      feedback.querySelector('.crisis-undo-button')?.remove();
    } catch (error) {
      undo.disabled = false;
      setFeedback(error.message || 'The plan could not be safely restored.', true);
      return;
    }
    await refreshHealthPanel(eventId);
  });
  feedback.appendChild(undo);
}

async function refreshHealthPanel(eventId) {
  try {
    const health = await getPlanHealth(eventId);
    document.querySelector('.health-overview').innerHTML = renderHealthPanel(health);
  } catch (error) {
    setFeedback(
      `The plan change was saved, but the score could not be refreshed. ${error.message || ''}`,
      true,
    );
  }
}
