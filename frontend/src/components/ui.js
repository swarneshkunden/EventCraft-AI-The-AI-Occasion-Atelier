/**
 * Small, shared markup builders for the most-repeated page chrome.
 *
 * Every helper returns a string of safe HTML: caller-supplied text is escaped,
 * and richer fragments must be marked with raw() explicitly.
 */
import { escapeHtml, html, raw } from '../utils/html.js';

/** Standard "nothing selected / nothing scheduled" panel. */
export function emptyState({ icon = '', eyebrow = '', title, message }) {
  return html`
    <div class="empty-state card">
      ${raw(icon ? `<div class="empty-icon">${icon}</div>` : '')}
      ${raw(
        eyebrow
          ? `<h1 class="serif" style="font-size: 1.4rem; margin-bottom: 8px;">${escapeHtml(eyebrow)}</h1>`
          : '',
      )}
      <h2 class="serif" style="font-size: 1.4rem; margin-bottom: 8px;">${title}</h2>
      <p style="color: var(--clr-text-muted); max-width: 440px; margin: 0 auto 20px;">${message}</p>
    </div>
  `;
}

/**
 * Dashboard style metric card.
 * `value` and `body` are trusted fragments, so wrap them in raw() or pass html().
 */
export function statCard({ label, value, body = '' }) {
  return html`
    <div class="stat-card">
      <div class="stat-label">${label}</div>
      <div class="stat-value num">${raw(value)}</div>
      ${raw(body)}
    </div>
  `;
}

/**
 * Row of filter buttons driven by `data-filter` attributes.
 * `items` is a list of { value, label }, where label may be trusted markup.
 */
export function filterTabs({ className, items, active }) {
  return items
    .map(
      ({ value, label }) => html`
        <button
          class="btn btn-ghost btn-sm ${className} ${active === value ? 'btn-primary' : ''}"
          data-filter="${value}"
        >${raw(label)}</button>
      `,
    )
    .join('');
}

/** Keep exactly one filter button active and hand the chosen value to `onSelect`. */
export function bindFilterButtons(selector, onSelect) {
  document.querySelectorAll(selector).forEach((button) => {
    button.addEventListener('click', () => {
      document
        .querySelectorAll(selector)
        .forEach((other) => other.classList.remove('btn-primary'));
      button.classList.add('btn-primary');
      onSelect(button.getAttribute('data-filter'));
    });
  });
}
