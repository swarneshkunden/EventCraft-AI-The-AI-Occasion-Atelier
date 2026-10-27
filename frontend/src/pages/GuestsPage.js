/**
 * Guest List, RSVP Tracking, and CSV Import Page.
 */
import { getCurrentEvent } from '../services/events.js';
import {
  getGuestList,
  createGuestItem,
  updateGuestItem,
  deleteGuestItem,
  importGuestsCsv,
} from '../services/events.js';
import { showToast, escapeHtml } from '../utils/toast.js';

let guestsData = { guests: [], total: 0, page: 1, page_size: 50 };
let currentFilter = 'all';
let searchQuery = '';

export async function renderGuestsPage() {
  const event = getCurrentEvent();

  if (!event) {
    return `
      <div class="page-body">
        <div class="empty-state card">
          <p>Please select or create an event to manage guest lists.</p>
        </div>
      </div>
    `;
  }

  try {
    guestsData = (await getGuestList(event.id, 1, 100)) || { guests: [], total: 0 };
  } catch (err) {
    console.error('Failed to load guest list', err);
    guestsData = { guests: [], total: 0 };
  }

  const allGuests = guestsData.guests || [];
  const attendingCount = allGuests.filter((g) => g.rsvp_status === 'confirmed').length;
  const pendingCount = allGuests.filter((g) => g.rsvp_status === 'pending').length;
  const declinedCount = allGuests.filter((g) => g.rsvp_status === 'declined').length;

  // Compute dietary counts
  const dietaryCounts = {};
  allGuests.forEach((g) => {
    if (g.dietary_needs && g.dietary_needs.trim()) {
      const notes = g.dietary_needs.split(/[,;]/).map((s) => s.trim());
      notes.forEach((d) => {
        if (d) {
          dietaryCounts[d] = (dietaryCounts[d] || 0) + 1;
        }
      });
    }
  });

  return `
    <div class="page-body">

      <!-- Top Overview Card -->
      <div class="card" style="margin-bottom: 24px;">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 16px;">
          <div>
            <h2 style="font-size: 1.6rem; font-weight: 800; margin-bottom: 4px;">
              Guest List & RSVP Manager
            </h2>
            <p style="font-size: 0.85rem; color: var(--clr-text-muted);">
              Track RSVP status, dietary restrictions, and accessibility needs.
            </p>
          </div>

          <div style="display: flex; gap: 10px; flex-wrap: wrap;">
            <button id="btn-import-csv-modal" class="btn btn-secondary">
              📥 Import CSV
            </button>
            <button id="btn-add-guest-modal" class="btn btn-primary">
              ï¼‹ Add Guest
            </button>
          </div>
        </div>

        <!-- RSVP Summary Stat Grid -->
        <div class="grid-4" style="margin-top: 20px;">
          <div style="background: var(--clr-surface-2); padding: 12px 16px; border-radius: var(--radius-md);">
            <div style="font-size: 0.75rem; color: var(--clr-text-muted); text-transform: uppercase;">Total Invites</div>
            <div style="font-size: 1.4rem; font-weight: 800;">${guestsData.total || allGuests.length}</div>
          </div>
          <div style="background: var(--clr-surface-2); padding: 12px 16px; border-radius: var(--radius-md); border-left: 3px solid var(--clr-success);">
            <div style="font-size: 0.75rem; color: var(--clr-success); text-transform: uppercase;">Attending</div>
            <div style="font-size: 1.4rem; font-weight: 800;">${attendingCount}</div>
          </div>
          <div style="background: var(--clr-surface-2); padding: 12px 16px; border-radius: var(--radius-md); border-left: 3px solid var(--clr-info);">
            <div style="font-size: 0.75rem; color: var(--clr-info); text-transform: uppercase;">Pending</div>
            <div style="font-size: 1.4rem; font-weight: 800;">${pendingCount}</div>
          </div>
          <div style="background: var(--clr-surface-2); padding: 12px 16px; border-radius: var(--radius-md); border-left: 3px solid var(--clr-danger);">
            <div style="font-size: 0.75rem; color: var(--clr-danger); text-transform: uppercase;">Declined</div>
            <div style="font-size: 1.4rem; font-weight: 800;">${declinedCount}</div>
          </div>
        </div>

        <!-- Dietary Breakdown Chips -->
        ${
          Object.keys(dietaryCounts).length > 0
            ? `
          <div style="margin-top: 16px; padding-top: 12px; border-top: 1px solid var(--clr-border);">
            <div style="font-size: 0.75rem; color: var(--clr-text-muted); font-weight: 600; margin-bottom: 6px;">
              🥗 Dietary Requirements for Caterer:
            </div>
            <div style="display: flex; gap: 8px; flex-wrap: wrap;">
              ${Object.entries(dietaryCounts)
                .map(
                  ([diet, count]) => `
                <span class="badge badge-warning" style="font-size: 0.75rem;">
                  ${escapeHtml(diet)}: <strong>${count}</strong>
                </span>
              `
                )
                .join('')}
            </div>
          </div>
        `
            : ''
        }
      </div>

      <!-- Search & Filters -->
      <div class="card" style="margin-bottom: 16px; padding: 16px;">
        <div style="display: flex; gap: 12px; flex-wrap: wrap; justify-content: space-between; align-items: center;">
          <input
            type="text"
            id="input-guest-search"
            placeholder="🔍 Search guests by name or email..."
            style="max-width: 300px;"
            value="${escapeHtml(searchQuery)}"
          />

          <div style="display: flex; gap: 6px; flex-wrap: wrap;">
            <button class="btn btn-ghost btn-sm guest-filter-btn ${currentFilter === 'all' ? 'btn-primary' : ''}" data-filter="all">All</button>
            <button class="btn btn-ghost btn-sm guest-filter-btn ${currentFilter === 'confirmed' ? 'btn-primary' : ''}" data-filter="confirmed">Confirmed</button>
            <button class="btn btn-ghost btn-sm guest-filter-btn ${currentFilter === 'pending' ? 'btn-primary' : ''}" data-filter="pending">Pending</button>
            <button class="btn btn-ghost btn-sm guest-filter-btn ${currentFilter === 'declined' ? 'btn-primary' : ''}" data-filter="declined">Declined</button>
          </div>
        </div>
      </div>

      <!-- Guest Table Container -->
      <div class="card" style="padding: 0; overflow-x: auto;">
        <table style="width: 100%; border-collapse: collapse; text-align: left; font-size: 0.875rem;">
          <thead>
            <tr style="background: var(--clr-surface-2); border-bottom: 1px solid var(--clr-border);">
              <th style="padding: 12px 16px; font-weight: 700; color: var(--clr-text-muted);">Guest Name</th>
              <th style="padding: 12px 16px; font-weight: 700; color: var(--clr-text-muted);">Contact</th>
              <th style="padding: 12px 16px; font-weight: 700; color: var(--clr-text-muted);">RSVP</th>
              <th style="padding: 12px 16px; font-weight: 700; color: var(--clr-text-muted);">Dietary needs</th>
              <th style="padding: 12px 16px; font-weight: 700; color: var(--clr-text-muted);">Accessibility needs</th>
              <th style="padding: 12px 16px; text-align: right; color: var(--clr-text-muted);">Actions</th>
            </tr>
          </thead>
          <tbody id="guests-table-body">
            ${renderGuestRows(allGuests, currentFilter, searchQuery)}
          </tbody>
        </table>
      </div>

    </div>
  `;
}

function renderGuestRows(guests, filter, query) {
  let filtered = guests;
  if (filter !== 'all') {
    filtered = filtered.filter((g) => g.rsvp_status === filter);
  }
  if (query) {
    const q = query.toLowerCase();
    filtered = filtered.filter(
      (g) =>
        (g.name && g.name.toLowerCase().includes(q)) ||
        (g.email && g.email.toLowerCase().includes(q))
    );
  }

  if (filtered.length === 0) {
    return `
      <tr>
        <td colspan="6" style="padding: 32px; text-align: center; color: var(--clr-text-muted);">
          No guests found matching your criteria.
        </td>
      </tr>
    `;
  }

  return filtered
    .map((g) => {
      return `
      <tr style="border-bottom: 1px solid var(--clr-border);">
        <td style="padding: 12px 16px; font-weight: 600;">
          ${escapeHtml(g.name)}
        </td>
        <td style="padding: 12px 16px; font-size: 0.8rem; color: var(--clr-text-muted);">
          ${escapeHtml(g.email || g.phone || '—')}
        </td>
        <td style="padding: 12px 16px;">
          <select class="guest-rsvp-select" data-guest-id="${g.id}" aria-label="RSVP status for ${escapeHtml(g.name)}" style="font-size: 0.75rem; padding: 4px 6px; width: auto;">
            <option value="pending" ${g.rsvp_status === 'pending' ? 'selected' : ''}>⏳ Pending</option>
            <option value="confirmed" ${g.rsvp_status === 'confirmed' ? 'selected' : ''}>✓ Confirmed</option>
            <option value="declined" ${g.rsvp_status === 'declined' ? 'selected' : ''}>✕ Declined</option>
          </select>
        </td>
        <td style="padding: 12px 16px; font-size: 0.8rem; color: var(--clr-text-dim);">
          ${escapeHtml(g.dietary_needs || 'None')}
        </td>
        <td style="padding: 12px 16px; font-size: 0.8rem; color: var(--clr-text-dim);">
          ${escapeHtml(g.accessibility_needs || 'None')}
        </td>
        <td style="padding: 12px 16px; text-align: right;">
          <button class="btn btn-ghost btn-sm btn-delete-guest" data-guest-id="${g.id}" style="color: var(--clr-danger); padding: 4px 8px;">
            ✕
          </button>
        </td>
      </tr>
    `;
    })
    .join('');
}

export function initGuestsPageEvents() {
  const event = getCurrentEvent();
  if (!event) return;

  // Filter clicks
  document.querySelectorAll('.guest-filter-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.guest-filter-btn').forEach((b) => b.classList.remove('btn-primary'));
      btn.classList.add('btn-primary');
      currentFilter = btn.getAttribute('data-filter');
      const tbody = document.getElementById('guests-table-body');
      if (tbody) {
        tbody.innerHTML = renderGuestRows(guestsData.guests || [], currentFilter, searchQuery);
      }
    });
  });

  // Search input
  document.getElementById('input-guest-search')?.addEventListener('input', (e) => {
    searchQuery = e.target.value.trim();
    const tbody = document.getElementById('guests-table-body');
    if (tbody) {
      tbody.innerHTML = renderGuestRows(guestsData.guests || [], currentFilter, searchQuery);
    }
  });

  // RSVP status change
  document.getElementById('guests-table-body')?.addEventListener('change', async (e) => {
    const sel = e.target.closest('.guest-rsvp-select');
    if (!sel) return;
    const guestId = sel.getAttribute('data-guest-id');
    const newRsvp = sel.value;

    try {
      await updateGuestItem(event.id, guestId, { rsvp_status: newRsvp });
      showToast('RSVP updated', 'info');
      guestsData = (await getGuestList(event.id, 1, 100)) || { guests: [], total: 0 };
    } catch (err) {
      showToast(err.message || 'Failed to update RSVP', 'error');
    }
  });

  // Delete guest
  document.getElementById('guests-table-body')?.addEventListener('click', async (e) => {
    const btn = e.target.closest('.btn-delete-guest');
    if (!btn) return;
    const guestId = btn.getAttribute('data-guest-id');

    if (!confirm('Remove this guest?')) return;

    try {
      await deleteGuestItem(event.id, guestId);
      guestsData = (await getGuestList(event.id, 1, 100)) || { guests: [], total: 0 };
      const tbody = document.getElementById('guests-table-body');
      if (tbody) {
        tbody.innerHTML = renderGuestRows(guestsData.guests || [], currentFilter, searchQuery);
      }
      showToast('Guest removed', 'info');
    } catch (err) {
      showToast(err.message || 'Failed to remove guest', 'error');
    }
  });

  // Add Guest Modal
  document.getElementById('btn-add-guest-modal')?.addEventListener('click', () => {
    openAddGuestModal(event.id);
  });

  // Import CSV Modal
  document.getElementById('btn-import-csv-modal')?.addEventListener('click', () => {
    openImportCsvModal(event.id);
  });
}

function openAddGuestModal(eventId) {
  document.getElementById('modal-add-guest')?.remove();

  const modalHtml = `
    <div class="modal-backdrop" id="modal-add-guest">
      <div class="modal" role="dialog" aria-labelledby="modal-add-guest-title" aria-modal="true">
        <div class="modal-header">
          <h3 class="modal-title" id="modal-add-guest-title">👥 Add New Guest</h3>
          <button class="btn btn-ghost btn-sm" id="btn-close-add-guest">✕</button>
        </div>

        <form id="form-add-guest" class="modal-body">
          <div class="form-group">
            <label for="guest-name">Full Name <span class="required">*</span></label>
            <input type="text" id="guest-name" required placeholder="e.g. Meera Patel" />
          </div>

          <div class="grid-2">
            <div class="form-group">
              <label for="guest-email">Email Address</label>
              <input type="email" id="guest-email" placeholder="meera@example.com" />
            </div>

            <div class="form-group">
              <label for="guest-phone">Phone Number</label>
              <input type="tel" id="guest-phone" placeholder="+1 555-0123" />
            </div>
          </div>

          <div class="form-group">
            <div class="form-group">
              <label for="guest-rsvp">RSVP Status</label>
              <select id="guest-rsvp">
                <option value="pending" selected>Pending</option>
                <option value="confirmed">Confirmed</option>
                <option value="declined">Declined</option>
              </select>
            </div>
          </div>

          <div class="form-group">
            <label for="guest-dietary">Dietary Preferences / Allergies</label>
            <input type="text" id="guest-dietary" maxlength="200" placeholder="e.g. Vegetarian, Gluten-Free, Nut allergy" />
          </div>
          <div class="form-group">
            <label for="guest-accessibility">Accessibility needs</label>
            <input type="text" id="guest-accessibility" maxlength="200" placeholder="e.g. Wheelchair access" />
          </div>

          <div class="modal-footer" style="padding: 16px 0 0 0; border-top: none;">
            <button type="button" class="btn btn-secondary" id="btn-cancel-add-guest">Cancel</button>
            <button type="submit" class="btn btn-primary" id="btn-submit-guest">
              Add Guest
            </button>
          </div>
        </form>
      </div>
    </div>
  `;

  document.body.insertAdjacentHTML('beforeend', modalHtml);

  const closeModal = () => document.getElementById('modal-add-guest')?.remove();
  document.getElementById('btn-close-add-guest')?.addEventListener('click', closeModal);
  document.getElementById('btn-cancel-add-guest')?.addEventListener('click', closeModal);

  document.getElementById('form-add-guest')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const name = document.getElementById('guest-name').value.trim();
    const email = document.getElementById('guest-email').value.trim();
    const phone = document.getElementById('guest-phone').value.trim();
    const rsvpStatus = document.getElementById('guest-rsvp').value;
    const dietaryNotes = document.getElementById('guest-dietary').value.trim();
    const accessibilityNeeds = document.getElementById('guest-accessibility').value.trim();

    const submitBtn = document.getElementById('btn-submit-guest');
    submitBtn.disabled = true;
    submitBtn.textContent = 'Saving...';

    try {
      await createGuestItem(eventId, {
        name,
        email,
        phone,
        rsvp_status: rsvpStatus,
        dietary_needs: dietaryNotes,
        accessibility_needs: accessibilityNeeds,
      });

      guestsData = (await getGuestList(eventId, 1, 100)) || { guests: [], total: 0 };
      const tbody = document.getElementById('guests-table-body');
      if (tbody) {
        tbody.innerHTML = renderGuestRows(guestsData.guests || [], currentFilter, searchQuery);
      }

      showToast(`Guest "${name}" added!`, 'success');
      closeModal();
    } catch (err) {
      showToast(err.message || 'Failed to add guest', 'error');
      submitBtn.disabled = false;
      submitBtn.textContent = 'Add Guest';
    }
  });
}

function openImportCsvModal(eventId) {
  document.getElementById('modal-import-csv')?.remove();

  const sampleCsvContent = `name,email,phone,rsvp_status,dietary_needs,accessibility_needs
Kavita Sharma,kavita@test.com,+91 9876543210,confirmed,Vegetarian,
Rohan Verma,rohan@test.com,+91 9876543211,confirmed,Gluten-Free,
Ananya Rao,ananya@test.com,+91 9876543212,pending,Vegan,
Vikram Mehta,vikram@test.com,+91 9876543213,declined,,Wheelchair access`;

  const modalHtml = `
    <div class="modal-backdrop" id="modal-import-csv">
      <div class="modal" role="dialog" aria-labelledby="modal-import-title" aria-modal="true">
        <div class="modal-header">
          <h3 class="modal-title" id="modal-import-title">📥 Import Guests from CSV</h3>
          <button class="btn btn-ghost btn-sm" id="btn-close-import">✕</button>
        </div>

        <div class="modal-body">
          <p style="font-size: 0.85rem; color: var(--clr-text-muted);">
            Upload a CSV file containing columns: <code>name</code>, <code>email</code>, <code>phone</code>, <code>rsvp_status</code>, <code>dietary_needs</code>, <code>accessibility_needs</code>.
          </p>

          <div style="background: var(--clr-surface-2); padding: 12px; border-radius: var(--radius-md); display: flex; justify-content: space-between; align-items: center;">
            <span style="font-size: 0.8rem; color: var(--clr-text-muted);">Need a format sample?</span>
            <button id="btn-download-sample-csv" class="btn btn-secondary btn-sm">
              📄 Download Sample CSV
            </button>
          </div>

          <div class="form-group" style="margin-top: 12px;">
            <label for="csv-file-input">Select CSV File</label>
            <input type="file" id="csv-file-input" accept=".csv,text/csv" />
          </div>

          <div class="modal-footer" style="padding: 16px 0 0 0; border-top: none;">
            <button type="button" class="btn btn-secondary" id="btn-cancel-import">Cancel</button>
            <button type="button" class="btn btn-primary" id="btn-upload-csv">
              Upload & Import Guests
            </button>
          </div>
        </div>
      </div>
    </div>
  `;

  document.body.insertAdjacentHTML('beforeend', modalHtml);

  const closeModal = () => document.getElementById('modal-import-csv')?.remove();
  document.getElementById('btn-close-import')?.addEventListener('click', closeModal);
  document.getElementById('btn-cancel-import')?.addEventListener('click', closeModal);

  // Download Sample
  document.getElementById('btn-download-sample-csv')?.addEventListener('click', () => {
    const blob = new Blob([sampleCsvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = 'sample_eventcraft_guests.csv';
    link.click();
  });

  // Upload handler
  document.getElementById('btn-upload-csv')?.addEventListener('click', async () => {
    const fileInput = document.getElementById('csv-file-input');
    const file = fileInput?.files?.[0];
    if (!file) {
      showToast('Please select a CSV file first', 'warning');
      return;
    }

    const btn = document.getElementById('btn-upload-csv');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner spinner-sm"></span> Importing...';

    try {
      const res = await importGuestsCsv(eventId, file);
      showToast(res.message || `Imported ${res.imported} guests!`, 'success');
      closeModal();
      guestsData = (await getGuestList(eventId, 1, 100)) || { guests: [], total: 0 };
      const tbody = document.getElementById('guests-table-body');
      if (tbody) {
        tbody.innerHTML = renderGuestRows(guestsData.guests || [], currentFilter, searchQuery);
      }
    } catch (err) {
      showToast(err.message || 'Import failed. Check CSV formatting.', 'error');
      btn.disabled = false;
      btn.textContent = 'Upload & Import Guests';
    }
  });
}
