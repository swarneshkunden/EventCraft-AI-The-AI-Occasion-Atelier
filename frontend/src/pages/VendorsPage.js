/**
 * Vendor Directory & AI Interview Question Generator Page.
 */
import { getCurrentEvent } from '../services/events.js';
import { getCurrentUser } from '../services/auth.js';
import {
  getVendorList,
  createVendorItem,
  updateVendorItem,
  deleteVendorItem,
  generateVendorQuestions,
} from '../services/events.js';
import { formatCurrency } from '../utils/formatters.js';
import { showToast, escapeHtml } from '../utils/toast.js';

let vendorList = [];
let currentFilter = 'all';

export async function renderVendorsPage() {
  const event = getCurrentEvent();
  const user = getCurrentUser();
  const currency = user?.currency || 'USD';

  if (!event) {
    return `
      <div class="page-body">
        <div class="empty-state card">
          <p>Please select or create an event to manage vendors.</p>
        </div>
      </div>
    `;
  }

  try {
    vendorList = (await getVendorList(event.id)) || [];
  } catch (err) {
    console.error('Failed to load vendors', err);
    vendorList = [];
  }

  const preferredCount = vendorList.filter((v) => v.is_selected).length;

  return `
    <div class="page-body">

      <!-- Top Overview Card -->
      <div class="card" style="margin-bottom: 24px;">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 16px;">
          <div>
            <h2 style="font-size: 1.6rem; font-weight: 800; margin-bottom: 4px;">
              Vendor Directory & AI Questions
            </h2>
            <p style="font-size: 0.85rem; color: var(--clr-text-muted);">
              Track vendor contracts and generate tailored interview checklists with Gemini AI to avoid surprise costs.
            </p>
          </div>

          <div style="display: flex; gap: 10px;">
            <button id="btn-add-vendor-modal" class="btn btn-primary">
              ï¼‹ Add Vendor
            </button>
          </div>
        </div>

        <!-- Filter tabs -->
        <div style="display: flex; gap: 8px; margin-top: 20px; border-bottom: 1px solid var(--clr-border); padding-bottom: 8px; flex-wrap: wrap;">
          <button class="btn btn-ghost btn-sm vendor-filter-btn ${currentFilter === 'all' ? 'btn-primary' : ''}" data-filter="all">
            All Vendors (${vendorList.length})
          </button>
          <button class="btn btn-ghost btn-sm vendor-filter-btn ${currentFilter === 'preferred' ? 'btn-primary' : ''}" data-filter="preferred">
            Preferred candidates (${preferredCount})
          </button>
        </div>
      </div>

      <section class="card quote-comparison" aria-labelledby="quote-comparison-title">
        <h2 id="quote-comparison-title" class="serif">Quote comparison</h2>
        <p class="text-muted">Entered quotes are unverified. Confirm availability, scope, taxes, and extra charges directly with each vendor.</p>
        ${renderQuoteComparison(vendorList, currency)}
      </section>

      <!-- Vendors Grid -->
      <div id="vendors-grid-container" class="grid-2">
        ${renderVendorsGrid(vendorList, currentFilter, currency)}
      </div>

    </div>
  `;
}

function renderQuoteComparison(vendors, currency) {
  if (vendors.length === 0) {
    return '<p class="text-muted">Add vendor quotes to compare scope and outstanding questions.</p>';
  }

  const quoteDetails = (vendor) => `
    <span class="badge badge-warning">Needs verification</span>
    <div><strong>${vendor.quoted_price !== null && vendor.quoted_price !== undefined ? formatCurrency(vendor.quoted_price, currency) : 'No quote entered'}</strong></div>
    <div>Guests covered: ${vendor.guests_covered ?? 'Not provided'}</div>
    <div>Inclusions: ${escapeHtml(vendor.inclusions || 'Not provided')}</div>
    <div>Extra charges: ${escapeHtml(vendor.extra_charges || 'Not provided')}</div>
    <div>Open questions: ${escapeHtml(vendor.open_questions || 'None recorded')}</div>
  `;

  return `
    <div class="quote-table-wrap">
      <table class="quote-table">
        <thead><tr><th scope="col">Vendor</th><th scope="col">Quote and coverage</th><th scope="col">Inclusions</th><th scope="col">Extra charges</th><th scope="col">Open questions</th></tr></thead>
        <tbody>${vendors.map((vendor) => `
          <tr>
            <th scope="row">${escapeHtml(vendor.name)}<small>${escapeHtml(vendor.vendor_type)}</small></th>
            <td><span class="badge badge-warning">Needs verification</span><br>${vendor.quoted_price !== null && vendor.quoted_price !== undefined ? formatCurrency(vendor.quoted_price, currency) : 'No quote entered'}<br>Guests: ${vendor.guests_covered ?? 'Not provided'}</td>
            <td>${escapeHtml(vendor.inclusions || 'Not provided')}</td>
            <td>${escapeHtml(vendor.extra_charges || 'Not provided')}</td>
            <td>${escapeHtml(vendor.open_questions || 'None recorded')}</td>
          </tr>
        `).join('')}</tbody>
      </table>
    </div>
    <div class="quote-comparison-cards">
      ${vendors.map((vendor) => `
        <article class="card quote-comparison-card">
          <h3>${escapeHtml(vendor.name)}</h3>
          <p>${escapeHtml(vendor.vendor_type)}</p>
          ${quoteDetails(vendor)}
        </article>
      `).join('')}
    </div>
  `;
}

function renderVendorsGrid(vendors, filter, currency) {
  let filtered = vendors;
  if (filter === 'preferred') {
    filtered = vendors.filter((v) => v.is_selected);
  }

  if (filtered.length === 0) {
    return `
      <div class="card" style="grid-column: 1 / -1; padding: 40px; text-align: center; color: var(--clr-text-muted);">
        ${vendors.length === 0 ? 'No vendors added yet. Click "ï¼‹ Add Vendor" above.' : 'No vendors in this category.'}
      </div>
    `;
  }

  return filtered
    .map((v) => {
      const checklist = v.ai_checklist || [];
      const questions = v.ai_questions || [];

      return `
      <div class="vendor-card ${v.is_selected ? 'selected' : ''}" data-vendor-id="${v.id}">

        <div class="vendor-card-header">
          <div>
            <span class="badge badge-primary" style="text-transform: uppercase; font-size: 0.65rem; margin-bottom: 4px;">
              ${escapeHtml(v.vendor_type)}
            </span>
            <h3 style="font-size: 1.2rem; font-weight: 700;">${escapeHtml(v.name)}</h3>
            <div style="font-size: 0.8rem; color: var(--clr-text-muted);">
              ${v.contact ? `📞 ${escapeHtml(v.contact)}` : 'No contact info'}
            </div>
          </div>

          <div style="text-align: right;">
            <div class="vendor-price">
              ${v.quoted_price !== null && v.quoted_price !== undefined ? formatCurrency(v.quoted_price, currency) : 'No quote entered'}
            </div>
            <span class="badge badge-warning" aria-label="Needs verification">Needs verification</span>
            <select class="vendor-selection-select" data-vendor-id="${v.id}" aria-label="Preferred candidate status for ${escapeHtml(v.name)}" style="font-size: 0.75rem; padding: 4px 6px; width: auto; margin-top: 4px;">
              <option value="false" ${!v.is_selected ? 'selected' : ''}>Not selected</option>
              <option value="true" ${v.is_selected ? 'selected' : ''}>Preferred candidate</option>
            </select>
          </div>
        </div>

        ${
          v.inclusions
            ? `
          <div style="font-size: 0.8rem; color: var(--clr-text-dim); margin-bottom: 12px; background: var(--clr-surface-3); padding: 8px 12px; border-radius: var(--radius-sm);">
            <strong>Inclusions:</strong> ${escapeHtml(v.inclusions)}
          </div>
        `
            : ''
        }

        <!-- AI Checklist & Questions Section -->
        <div style="margin-top: 12px; border-top: 1px solid var(--clr-border); padding-top: 12px;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <span style="font-size: 0.75rem; font-weight: 700; text-transform: uppercase; color: var(--clr-accent-light);">
              ✨ AI Intelligence (${checklist.length + questions.length} items)
            </span>
            <button class="btn btn-ghost btn-sm btn-generate-questions" data-vendor-id="${v.id}" style="font-size: 0.75rem; padding: 2px 8px;">
              ${checklist.length > 0 ? '🔄 Refresh AI Checklist' : '⚡ Generate Questions & Checklist'}
            </button>
          </div>

          ${
            questions.length > 0
              ? `
            <div style="margin-bottom: 8px;">
              <div style="font-size: 0.7rem; color: var(--clr-text-muted); font-weight: 600; margin-bottom: 4px;">Questions to Ask:</div>
              <ul style="font-size: 0.75rem; color: var(--clr-text-muted); padding-left: 16px; line-height: 1.5;">
                ${questions.slice(0, 3).map((q) => `<li>${escapeHtml(q)}</li>`).join('')}
              </ul>
            </div>
          `
              : ''
          }

          ${
            checklist.length > 0
              ? `
            <div>
              <div style="font-size: 0.7rem; color: var(--clr-text-muted); font-weight: 600; margin-bottom: 4px;">Inspection Checklist:</div>
              <div class="vendor-checklist">
                ${checklist
                  .slice(0, 3)
                  .map((item) => `<div class="checklist-item">${escapeHtml(item)}</div>`)
                  .join('')}
              </div>
            </div>
          `
              : ''
          }
        </div>

        <div style="display: flex; justify-content: flex-end; margin-top: 12px;">
          <button class="btn btn-ghost btn-sm btn-delete-vendor" data-vendor-id="${v.id}" style="color: var(--clr-danger); font-size: 0.75rem;">
            Delete
          </button>
        </div>

      </div>
    `;
    })
    .join('');
}

export function initVendorsPageEvents() {
  const event = getCurrentEvent();
  const user = getCurrentUser();
  const currency = user?.currency || 'USD';
  if (!event) return;

  // Filter click
  document.querySelectorAll('.vendor-filter-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.vendor-filter-btn').forEach((b) => b.classList.remove('btn-primary'));
      btn.classList.add('btn-primary');
      currentFilter = btn.getAttribute('data-filter');
      const container = document.getElementById('vendors-grid-container');
      if (container) {
        container.innerHTML = renderVendorsGrid(vendorList, currentFilter, currency);
      }
    });
  });

  // Change status
  document.getElementById('vendors-grid-container')?.addEventListener('change', async (e) => {
    const sel = e.target.closest('.vendor-selection-select');
    if (!sel) return;
    const vendorId = sel.getAttribute('data-vendor-id');
    const isSelected = sel.value === 'true';

    try {
      await updateVendorItem(event.id, vendorId, { is_selected: isSelected });
      vendorList = (await getVendorList(event.id)) || [];
      const container = document.getElementById('vendors-grid-container');
      if (container) container.innerHTML = renderVendorsGrid(vendorList, currentFilter, currency);
      showToast('Preferred candidate updated. Verify availability and terms directly.', 'info');
    } catch (err) {
      showToast(err.message || 'Failed to update vendor status', 'error');
    }
  });

  // Generate AI Questions
  document.getElementById('vendors-grid-container')?.addEventListener('click', async (e) => {
    const btn = e.target.closest('.btn-generate-questions');
    if (!btn) return;

    const vendorId = btn.getAttribute('data-vendor-id');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner spinner-sm"></span> Analyzing...';

    try {
      const updated = await generateVendorQuestions(event.id, vendorId);
      vendorList = (await getVendorList(event.id)) || [];
      const container = document.getElementById('vendors-grid-container');
      if (container) {
        container.innerHTML = renderVendorsGrid(vendorList, currentFilter, currency);
      }
      showToast('AI checklist and interview questions generated!', 'success');
    } catch (err) {
      showToast(err.message || 'Failed to generate questions', 'error');
      btn.disabled = false;
      btn.textContent = '⚡ Generate Questions';
    }
  });

  // Delete vendor
  document.getElementById('vendors-grid-container')?.addEventListener('click', async (e) => {
    const btn = e.target.closest('.btn-delete-vendor');
    if (!btn) return;
    const vendorId = btn.getAttribute('data-vendor-id');

    if (!confirm('Remove this vendor?')) return;

    try {
      await deleteVendorItem(event.id, vendorId);
      vendorList = (await getVendorList(event.id)) || [];
      const container = document.getElementById('vendors-grid-container');
      if (container) {
        container.innerHTML = renderVendorsGrid(vendorList, currentFilter, currency);
      }
      showToast('Vendor removed', 'info');
    } catch (err) {
      showToast(err.message || 'Failed to delete vendor', 'error');
    }
  });

  // Add Vendor Modal
  document.getElementById('btn-add-vendor-modal')?.addEventListener('click', () => {
    openAddVendorModal(event.id, currency);
  });
}

function openAddVendorModal(eventId, currency) {
  document.getElementById('modal-add-vendor')?.remove();

  const modalHtml = `
    <div class="modal-backdrop" id="modal-add-vendor">
      <div class="modal" role="dialog" aria-labelledby="modal-add-vendor-title" aria-modal="true">
        <div class="modal-header">
          <h3 class="modal-title" id="modal-add-vendor-title">🤝 Add Vendor to Directory</h3>
          <button class="btn btn-ghost btn-sm" id="btn-close-add-vendor">✕</button>
        </div>

        <form id="form-add-vendor" class="modal-body">
          <div class="grid-2">
            <div class="form-group">
              <label for="vendor-type">Vendor Type <span class="required">*</span></label>
              <select id="vendor-type" required>
                <option value="venue">Venue</option>
                <option value="caterer">Catering / Food</option>
                <option value="photographer">Photography / Video</option>
                <option value="decorator">Decor & Flowers</option>
                <option value="entertainment">Music / DJ / Band</option>
                <option value="transport">Transport & Logistics</option>
                <option value="other">Other Service</option>
              </select>
            </div>

            <div class="form-group">
              <label for="vendor-name">Business / Vendor Name <span class="required">*</span></label>
              <input type="text" id="vendor-name" required placeholder="e.g. Bella Luna Catering" />
            </div>
          </div>

          <div class="grid-2">
            <div class="form-group">
              <label for="vendor-contact">Contact Info (Phone/Email)</label>
              <input type="text" id="vendor-contact" placeholder="e.g. contact@bellaluna.com or +1 555-0192" />
            </div>

            <div class="form-group">
              <label for="vendor-price">Quoted Price (${currency})</label>
              <input type="number" id="vendor-price" min="0" step="50" placeholder="e.g. 4500" />
            </div>
          </div>

          <div class="form-group">
            <label for="vendor-inclusions">Package Inclusions / Scope</label>
            <textarea id="vendor-inclusions" placeholder="e.g. Includes 3-course dinner, 4 servers, cleanup, tableware rentals..."></textarea>
          </div>
          <div class="grid-2">
            <div class="form-group">
              <label for="vendor-guests-covered">Guests covered</label>
              <input type="number" id="vendor-guests-covered" min="0" max="100000" step="1" />
            </div>
            <div class="form-group">
              <label for="vendor-extra-charges">Extra charges</label>
              <input type="text" id="vendor-extra-charges" maxlength="2000" />
            </div>
          </div>
          <div class="form-group">
            <label for="vendor-open-questions">Questions to clarify</label>
            <textarea id="vendor-open-questions" maxlength="2000"></textarea>
          </div>

          <div class="modal-footer" style="padding: 16px 0 0 0; border-top: none;">
            <button type="button" class="btn btn-secondary" id="btn-cancel-add-vendor">Cancel</button>
            <button type="submit" class="btn btn-primary" id="btn-submit-vendor">
              Add Vendor
            </button>
          </div>
        </form>
      </div>
    </div>
  `;

  document.body.insertAdjacentHTML('beforeend', modalHtml);

  const closeModal = () => document.getElementById('modal-add-vendor')?.remove();
  document.getElementById('btn-close-add-vendor')?.addEventListener('click', closeModal);
  document.getElementById('btn-cancel-add-vendor')?.addEventListener('click', closeModal);

  document.getElementById('form-add-vendor')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const vendorType = document.getElementById('vendor-type').value;
    const name = document.getElementById('vendor-name').value.trim();
    const contact = document.getElementById('vendor-contact').value.trim();
    const priceInput = document.getElementById('vendor-price').value;
    const priceVal = priceInput ? parseFloat(priceInput) : null;
    const inclusions = document.getElementById('vendor-inclusions').value.trim();
    const guestsInput = document.getElementById('vendor-guests-covered').value;
    const guestsCovered = guestsInput ? parseInt(guestsInput, 10) : null;
    const extraCharges = document.getElementById('vendor-extra-charges').value.trim();
    const openQuestions = document.getElementById('vendor-open-questions').value.trim();

    const submitBtn = document.getElementById('btn-submit-vendor');
    submitBtn.disabled = true;
    submitBtn.textContent = 'Saving...';

    try {
      await createVendorItem(eventId, {
        vendor_type: vendorType,
        name,
        contact,
        quoted_price: priceVal,
        guests_covered: guestsCovered,
        inclusions,
        extra_charges: extraCharges,
        open_questions: openQuestions,
      });

      vendorList = (await getVendorList(eventId)) || [];
      const container = document.getElementById('vendors-grid-container');
      if (container) {
        container.innerHTML = renderVendorsGrid(vendorList, currentFilter, currency);
      }

      showToast(`Vendor "${name}" added!`, 'success');
      closeModal();
    } catch (err) {
      showToast(err.message || 'Failed to add vendor', 'error');
      submitBtn.disabled = false;
      submitBtn.textContent = 'Add Vendor';
    }
  });
}
