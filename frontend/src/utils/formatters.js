/**
 * Formatting helpers for currencies, dates, numbers.
 */

const CURRENCY_SYMBOLS = {
  USD: '$',
  EUR: '€',
  GBP: '£',
  INR: '₹',
  CAD: 'CA$',
  AUD: 'AU$',
};

export function formatCurrency(amount, currency = 'USD') {
  const parsedAmount = Number(amount);
  const num = Number.isFinite(parsedAmount) ? parsedAmount : 0;
  const symbol = CURRENCY_SYMBOLS[currency] || currency + ' ';
  return `${symbol}${num.toLocaleString('en-US', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  })}`;
}

function parseDate(dateStr) {
  if (!dateStr) return null;

  const dateOnly = /^(\d{4})-(\d{2})-(\d{2})$/.exec(dateStr);
  const date = dateOnly
    ? new Date(Number(dateOnly[1]), Number(dateOnly[2]) - 1, Number(dateOnly[3]))
    : new Date(dateStr);

  if (!Number.isFinite(date.getTime())) return null;
  if (
    dateOnly &&
    (date.getFullYear() !== Number(dateOnly[1]) ||
      date.getMonth() !== Number(dateOnly[2]) - 1 ||
      date.getDate() !== Number(dateOnly[3]))
  ) {
    return null;
  }

  return date;
}

export function formatDate(dateStr) {
  if (!dateStr) return 'No date set';
  const date = parseDate(dateStr);
  if (!date) return dateStr;
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

export function daysUntil(dateStr) {
  if (!dateStr) return null;
  const target = parseDate(dateStr);
  if (!target) return null;
  const now = new Date();
  now.setHours(0, 0, 0, 0);
  target.setHours(0, 0, 0, 0);
  const diffTime = target - now;
  const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
  return diffDays;
}

export function formatPercent(value, total) {
  const numericValue = Number(value);
  const numericTotal = Number(total);
  if (
    !Number.isFinite(numericValue) ||
    !Number.isFinite(numericTotal) ||
    numericTotal <= 0
  ) {
    return 0;
  }
  return Math.max(0, Math.min(100, Math.round((numericValue / numericTotal) * 100)));
}
