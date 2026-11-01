/**
 * HTML helpers: escaping is the default, raw() is the explicit opt-out.
 *
 * Prefer the `html` tagged template over manual string building:
 *
 *   html`<span>${userName}</span>`                    // escaped
 *   html`<span>${raw(icons.check(14))}</span>`        // trusted markup
 *
 * Values interpolated by `html` are escaped unless they are wrapped in raw(),
 * so untrusted event, guest, task, or AI text can never become markup.
 */

const RAW = Symbol('rawHtml');
const ESCAPES = {
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
  "'": '&#039;',
};

export function escapeHtml(value) {
  if (value === null || value === undefined) return '';
  return String(value).replace(/[&<>"']/g, (char) => ESCAPES[char]);
}

/** Mark a string as trusted markup. Never pass user or AI text to raw(). */
export function raw(value) {
  return { [RAW]: value === null || value === undefined ? '' : String(value) };
}

function interpolate(value) {
  if (Array.isArray(value)) {
    return value.map(interpolate).join('');
  }
  if (value && typeof value === 'object' && RAW in value) {
    return value[RAW];
  }
  return escapeHtml(value);
}

/** Tagged template that escapes every interpolation by default. */
export function html(strings, ...values) {
  let out = strings[0];
  for (let i = 0; i < values.length; i += 1) {
    out += interpolate(values[i]) + strings[i + 1];
  }
  return out;
}

/** Replace an element's content with escaped-or-raw markup. */
export function setHtml(element, markup) {
  if (!element) return;
  element.innerHTML = markup;
}

/** Append markup without re-parsing the element's existing children. */
export function appendHtml(element, markup) {
  if (!element) return;
  element.insertAdjacentHTML('beforeend', markup);
}
