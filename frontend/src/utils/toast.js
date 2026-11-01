/**
 * Toast notifications & accessibility announcements.
 */
import { escapeHtml } from './html.js';

export function showToast(message, type = 'info', duration = 3500) {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.setAttribute('role', type === 'error' ? 'alert' : 'status');

  const icons = {
    success: '✓',
    error: '✕',
    warning: '⚠',
    info: 'ℹ',
  };

  toast.innerHTML = `
    <span style="font-weight: 700; margin-right: 4px;">${icons[type] || '•'}</span>
    <span class="toast-message">${escapeHtml(message)}</span>
  `;

  container.appendChild(toast);

  // Announce to screen readers
  announceToScreenReader(message, type === 'error' ? 'assertive' : 'polite');

  setTimeout(() => {
    toast.classList.add('toast-out');
    toast.addEventListener('animationend', () => toast.remove());
  }, duration);
}

export function announceToScreenReader(message, priority = 'polite') {
  const elId = priority === 'assertive' ? 'aria-alert' : 'aria-status';
  const el = document.getElementById(elId);
  if (el) {
    el.textContent = message;
  }
}
