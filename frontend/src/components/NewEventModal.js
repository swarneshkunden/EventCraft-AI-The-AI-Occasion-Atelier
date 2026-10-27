/**
 * Guided Intake Wizard for creating an event.
 * Multi-step stepper with large tap-friendly cards, budget slider + numeric sync,
 * and experience level customization.
 */
import { createNewEvent, updateEventDetails } from '../services/events.js';
import { getCurrentUser } from '../services/auth.js';
import { showToast, escapeHtml } from '../utils/toast.js';
import { icons } from '../utils/icons.js';
import { formatCurrency } from '../utils/formatters.js';

export function openNewEventModal(eventToEdit = null) {
  document.getElementById('modal-new-event')?.remove();

  const user = getCurrentUser();
  const currency = user?.currency || 'INR';
  const profile = eventToEdit?.profile || {};
  const budget = Number(profile.budget || eventToEdit?.total_budget || 1500000);
  const eventType = eventToEdit?.event_type || 'wedding';
  const experienceLevel = profile.experience_level || 'moderate';
  const atmosphere = profile.atmosphere || 'Royal Regal';
  const title = eventToEdit?.name || 'Royal Udaipur Wedding';
  const notes = Array.isArray(profile.must_haves) ? profile.must_haves.join('\n') : '';
  const location = profile.location || profile.venue_limits || '';
  const actionLabel = eventToEdit ? 'Save Celebration Changes' : 'Create Celebration Plan';
  const modalTitle = eventToEdit ? 'Edit Celebration Details' : 'Architect Your Celebration';

  const modalHtml = `
    <div class="modal-backdrop" id="modal-new-event">
      <div class="modal" role="dialog" aria-labelledby="intake-wizard-title" aria-modal="true" style="max-width: 680px;">

        <!-- Header -->
        <div class="modal-header">
          <div>
            <div style="font-size: 0.7rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.1em; color: var(--clr-accent);">
              Guided Intake Wizard
            </div>
            <h3 class="modal-title font-serif" id="intake-wizard-title">${modalTitle}</h3>
          </div>
          <button class="btn btn-ghost btn-sm" id="btn-close-new-event" aria-label="Close modal" style="padding: 6px; width: 36px; height: 36px;">
            ${icons.cross(16)}
          </button>
        </div>

        <!-- Stepper Progress Dots -->
        <div style="padding: 18px 24px 0;">
          <div class="stepper" id="intake-stepper">
            <div class="step-item active" data-step="1">
              <div class="step-circle">1</div>
              <span class="step-label">Occasion</span>
            </div>
            <div class="step-item" data-step="2">
              <div class="step-circle">2</div>
              <span class="step-label">Scale & Date</span>
            </div>
            <div class="step-item" data-step="3">
              <div class="step-circle">3</div>
              <span class="step-label">Budget</span>
            </div>
            <div class="step-item" data-step="4">
              <div class="step-circle">4</div>
              <span class="step-label">Experience</span>
            </div>
          </div>
        </div>

        <!-- Form Body -->
        <form id="form-new-event" class="modal-body" style="padding-top: 10px;">

          <!-- STEP 1: Occasion & Vision -->
          <div class="wizard-step" id="step-1">
            <h4 class="font-serif" style="margin-bottom: 6px;">What celebration are we crafting?</h4>
            <p class="text-muted" style="font-size: 0.85rem; margin-bottom: 16px;">
              Select the occasion to calibrate AI budgeting, timelines, and vendor interview checklists.
            </p>

            <div class="grid-2" id="occasion-cards" style="gap: 12px; margin-bottom: 18px;">
              <div class="chip card ${eventType === 'wedding' ? 'selected' : ''}" data-type="wedding" style="border-radius: var(--radius-md); padding: 14px; text-align: left; cursor: pointer;">
                <div style="font-size: 1.1rem; margin-bottom: 4px;">💍 Wedding</div>
                <div class="text-muted" style="font-size: 0.75rem;">Ceremony, reception, banquet & entertainment</div>
              </div>
              <div class="chip card ${eventType === 'birthday' ? 'selected' : ''}" data-type="birthday" style="border-radius: var(--radius-md); padding: 14px; text-align: left; cursor: pointer;">
                <div style="font-size: 1.1rem; margin-bottom: 4px;">🎂 Milestone Birthday</div>
                <div class="text-muted" style="font-size: 0.75rem;">Intimate or grand milestone party</div>
              </div>
              <div class="chip card ${eventType === 'community' ? 'selected' : ''}" data-type="community" style="border-radius: var(--radius-md); padding: 14px; text-align: left; cursor: pointer;">
                <div style="font-size: 1.1rem; margin-bottom: 4px;">🎪 Community Festival</div>
                <div class="text-muted" style="font-size: 0.75rem;">Neighborhood gathering, cultural fair</div>
              </div>
            </div>

            <div class="form-group">
              <label for="event-title">Celebration Name / Title <span class="required">*</span></label>
              <input type="text" id="event-title" required maxlength="200" placeholder="e.g. Priya & Arjun's Royal Udaipur Wedding" value="${escapeHtml(title)}" />
            </div>
          </div>

          <!-- STEP 2: Scale, Guests & Date -->
          <div class="wizard-step" id="step-2" style="display: none;">
            <h4 class="font-serif" style="margin-bottom: 6px;">When & where will it take place?</h4>
            <p class="text-muted" style="font-size: 0.85rem; margin-bottom: 16px;">
              EventCraft uses guest counts to accurately size catering and venue allocations.
            </p>

            <div class="grid-2" style="margin-bottom: 16px;">
              <div class="form-group">
                <label for="event-date">Target Date</label>
                <input type="date" id="event-date" value="${escapeHtml(profile.event_date || '')}" />
              </div>

              <div class="form-group">
                <label for="event-guests">Estimated Guests <span class="required">*</span></label>
                <input type="number" id="event-guests" min="1" max="100000" value="${Number(profile.guest_count || eventToEdit?.guest_count || 180)}" required />
              </div>
            </div>

            <div class="form-group">
              <label for="event-location">Venue / Destination City</label>
              <input type="text" id="event-location" maxlength="500" placeholder="e.g. Udaipur Palace Grounds or The Glasshouse" value="${escapeHtml(location)}" />
            </div>
          </div>

          <!-- STEP 3: Budget Range & Calibration -->
          <div class="wizard-step" id="step-3" style="display: none;">
            <h4 class="font-serif" style="margin-bottom: 6px;">Establish your financial boundaries</h4>
            <p class="text-muted" style="font-size: 0.85rem; margin-bottom: 16px;">
              Total budget will be distributed by AI across catering, decor, entertainment, and contingency.
            </p>

            <div class="card card-luxury" style="padding: 20px; margin-bottom: 16px;">
              <div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 12px;">
                <span style="font-size: var(--text-sm); font-weight: 700; color: var(--clr-text-muted);">Total Budget Allocation</span>
                <span class="badge badge-gold" id="budget-tier-badge">Grand Celebration</span>
              </div>

              <div style="font-size: 2.2rem; font-weight: 800; font-family: var(--font-display); color: var(--clr-accent); margin-bottom: 16px;" id="display-budget-val">
                ${formatCurrency(budget, currency)}
              </div>

              <input
                type="range"
                id="event-budget-slider"
                min="50000"
                max="10000000"
                step="50000"
                value="${Math.min(10000000, Math.max(50000, budget))}"
                aria-label="Budget slider"
              />

              <div style="display: flex; justify-content: space-between; font-size: 0.75rem; color: var(--clr-text-dim); margin-top: 8px;">
                <span>${formatCurrency(50000, currency)}</span>
                <span>${formatCurrency(5000000, currency)}</span>
                <span>${formatCurrency(10000000, currency)}</span>
              </div>
            </div>

            <div class="form-group">
              <label for="event-budget">Exact Budget Figure (${currency})</label>
              <input type="number" id="event-budget" min="1000" max="1000000000" step="500" value="${budget}" required />
            </div>
          </div>

          <!-- STEP 4: Experience Level & Priorities -->
          <div class="wizard-step" id="step-4" style="display: none;">
            <h4 class="font-serif" style="margin-bottom: 6px;">Refine the aesthetic & must-haves</h4>
            <p class="text-muted" style="font-size: 0.85rem; margin-bottom: 16px;">
              Guide our AI on where to prioritize investment and what vibe to emulate.
            </p>

            <div class="form-group" style="margin-bottom: 16px;">
              <label>Experience Tier</label>
              <div class="grid-3" id="experience-tier-cards" style="gap: 8px;">
                <div class="chip card ${experienceLevel === 'simple' ? 'selected' : ''}" data-level="simple" style="border-radius: var(--radius-md); padding: 10px; text-align: center; cursor: pointer;">
                  <div style="font-weight: 700; font-size: 0.85rem;">Essential & Clean</div>
                  <div class="text-muted" style="font-size: 0.7rem;">Focus on essentials</div>
                </div>
                <div class="chip card ${experienceLevel === 'moderate' ? 'selected' : ''}" data-level="moderate" style="border-radius: var(--radius-md); padding: 10px; text-align: center; cursor: pointer;">
                  <div style="font-weight: 700; font-size: 0.85rem;">Polished & Elegant</div>
                  <div class="text-muted" style="font-size: 0.7rem;">Balanced luxury</div>
                </div>
                <div class="chip card ${experienceLevel === 'premium' ? 'selected' : ''}" data-level="premium" style="border-radius: var(--radius-md); padding: 10px; text-align: center; cursor: pointer;">
                  <div style="font-weight: 700; font-size: 0.85rem;">Opulent Haute</div>
                  <div class="text-muted" style="font-size: 0.7rem;">Highest craft tier</div>
                </div>
              </div>
            </div>

            <div class="form-group" style="margin-bottom: 16px;">
              <label>Atmosphere & Vibe</label>
              <div class="chip-group" id="theme-chips">
                <span class="chip ${atmosphere === 'Royal Regal' ? 'selected' : ''}" data-vibe="Royal Regal">👑 Royal Regal</span>
                <span class="chip ${atmosphere === 'Romantic Candlelight' ? 'selected' : ''}" data-vibe="Romantic Candlelight">🕯️ Romantic Candlelight</span>
                <span class="chip ${atmosphere === 'Rustic Elegance' ? 'selected' : ''}" data-vibe="Rustic Elegance">🌿 Rustic Elegance</span>
                <span class="chip ${atmosphere === 'Modern Haute Minimalist' ? 'selected' : ''}" data-vibe="Modern Haute Minimalist">✨ Haute Minimalist</span>
                <span class="chip ${atmosphere === 'Festive Carnival' ? 'selected' : ''}" data-vibe="Festive Carnival">🎉 Festive & Vibrant</span>
              </div>
            </div>

            <div class="form-group">
              <label for="event-notes">Special Must-Haves or Notes</label>
              <textarea id="event-notes" maxlength="4000" placeholder="e.g. Sangeet stage, live sitar quartet, drone photography, farm-to-table cuisine...">${escapeHtml(notes)}</textarea>
            </div>
          </div>

          <!-- Wizard Footer Controls -->
          <div class="modal-footer" style="padding: 16px 0 0 0; border-top: 1px solid var(--clr-border-subtle);">
            <button type="button" class="btn btn-secondary" id="btn-wizard-prev" style="display: none;">
              Previous
            </button>
            <button type="button" class="btn btn-primary" id="btn-wizard-next">
              Next Step ${icons.arrowRight(14)}
            </button>
            <button type="submit" class="btn btn-gold" id="btn-submit-new-event" style="display: none;">
              ${icons.sparkle(16)} ${actionLabel}
            </button>
          </div>

        </form>
      </div>
    </div>
  `;

  document.body.insertAdjacentHTML('beforeend', modalHtml);

  // Wizard Step Controller
  let currentStep = 1;
  const totalSteps = 4;

  const updateWizardUi = () => {
    // Hide all steps
    for (let i = 1; i <= totalSteps; i++) {
      const stepEl = document.getElementById(`step-${i}`);
      if (stepEl) stepEl.style.display = i === currentStep ? 'block' : 'none';

      // Update stepper dots
      const dotEl = document.querySelector(`.step-item[data-step="${i}"]`);
      if (dotEl) {
        dotEl.classList.remove('active', 'done');
        if (i === currentStep) dotEl.classList.add('active');
        else if (i < currentStep) dotEl.classList.add('done');
      }
    }

    const prevBtn = document.getElementById('btn-wizard-prev');
    const nextBtn = document.getElementById('btn-wizard-next');
    const submitBtn = document.getElementById('btn-submit-new-event');

    if (prevBtn) prevBtn.style.display = currentStep > 1 ? 'inline-flex' : 'none';
    if (nextBtn) nextBtn.style.display = currentStep < totalSteps ? 'inline-flex' : 'none';
    if (submitBtn) submitBtn.style.display = currentStep === totalSteps ? 'inline-flex' : 'none';
  };

  document.getElementById('btn-wizard-next')?.addEventListener('click', () => {
    if (currentStep < totalSteps) {
      currentStep++;
      updateWizardUi();
    }
  });

  document.getElementById('btn-wizard-prev')?.addEventListener('click', () => {
    if (currentStep > 1) {
      currentStep--;
      updateWizardUi();
    }
  });

  // Occasion card selection
  const occasionCards = document.querySelectorAll('#occasion-cards .card');
  occasionCards.forEach((card) => {
    card.addEventListener('click', () => {
      occasionCards.forEach((c) => c.classList.remove('selected'));
      card.classList.add('selected');
    });
  });

  // Experience level cards
  const expCards = document.querySelectorAll('#experience-tier-cards .card');
  expCards.forEach((card) => {
    card.addEventListener('click', () => {
      expCards.forEach((c) => c.classList.remove('selected'));
      card.classList.add('selected');
    });
  });

  // Theme chips
  const themeChips = document.querySelectorAll('#theme-chips .chip');
  themeChips.forEach((chip) => {
    chip.addEventListener('click', () => {
      themeChips.forEach((c) => c.classList.remove('selected'));
      chip.classList.add('selected');
    });
  });

  // Budget slider and input synchronization
  const slider = document.getElementById('event-budget-slider');
  const numInput = document.getElementById('event-budget');
  const displayVal = document.getElementById('display-budget-val');
  const tierBadge = document.getElementById('budget-tier-badge');

  const updateBudgetTier = (val) => {
    if (displayVal) displayVal.textContent = formatCurrency(val, currency);
    if (tierBadge) {
      if (val < 200000) tierBadge.textContent = 'Intimate & Chic';
      else if (val < 1000000) tierBadge.textContent = 'Polished Classic';
      else if (val < 3000000) tierBadge.textContent = 'Grand Celebration';
      else tierBadge.textContent = 'Haute Luxury';
    }
  };

  slider?.addEventListener('input', (e) => {
    const val = parseFloat(e.target.value) || 0;
    if (numInput) numInput.value = val;
    updateBudgetTier(val);
  });

  numInput?.addEventListener('input', (e) => {
    const val = parseFloat(e.target.value) || 0;
    if (slider) slider.value = val;
    updateBudgetTier(val);
  });

  // Close handlers
  const closeModal = () => document.getElementById('modal-new-event')?.remove();
  document.getElementById('btn-close-new-event')?.addEventListener('click', closeModal);

  // Form Submission
  document.getElementById('form-new-event')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const title = document.getElementById('event-title').value.trim();
    const selectedOccasion = document.querySelector('#occasion-cards .card.selected')?.getAttribute('data-type') || eventType;
    const dateVal = document.getElementById('event-date').value || null;
    const guestCount = parseInt(document.getElementById('event-guests').value, 10) || 100;
    const budgetVal = parseFloat(document.getElementById('event-budget').value) || 500000;
    const locationVal = document.getElementById('event-location').value.trim();
    const selectedExp = document.querySelector('#experience-tier-cards .card.selected')?.getAttribute('data-level') || experienceLevel;
    const selectedVibe = document.querySelector('#theme-chips .chip.selected')?.getAttribute('data-vibe') || atmosphere;
    const notesVal = document.getElementById('event-notes').value.trim();

    const submitBtn = document.getElementById('btn-submit-new-event');
    submitBtn.disabled = true;
    submitBtn.innerHTML = `<span class="spinner spinner-sm"></span> ${eventToEdit ? 'Saving Changes...' : 'Architecting Plan...'}`;

    try {
      const updatedProfile = {
        ...profile,
        occasion: title,
        budget: budgetVal,
        guest_count: guestCount,
        event_date: dateVal,
        experience_level: selectedExp,
        priorities: profile.priorities || ["Venue & Atmosphere", "Catering & Bar", "Photography & Video"],
        must_haves: notesVal ? notesVal.split('\n').map((item) => item.trim()).filter(Boolean) : [],
        atmosphere: selectedVibe,
        age_groups: profile.age_groups || [],
        cultural_preferences: profile.cultural_preferences || "",
        accessibility_needs: profile.accessibility_needs || "",
        venue_limits: profile.venue_limits || '',
        location: locationVal,
      };
      const event = eventToEdit
        ? await updateEventDetails(eventToEdit.id, {
            name: title,
            event_type: selectedOccasion,
            profile: updatedProfile,
          })
        : await createNewEvent({
            name: title,
            event_type: selectedOccasion,
            profile: updatedProfile,
          });

      showToast(
        eventToEdit ? `Celebration "${event.name}" updated.` : `Celebration "${event.name}" created!`,
        'success'
      );
      closeModal();
      window.location.hash = '#dashboard';
    } catch (err) {
      showToast(err.message || `Failed to ${eventToEdit ? 'update' : 'create'} celebration plan`, 'error');
      submitBtn.disabled = false;
      submitBtn.textContent = actionLabel;
    }
  });
}
