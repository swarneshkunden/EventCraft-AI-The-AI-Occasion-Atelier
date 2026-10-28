import assert from 'node:assert/strict';
import test from 'node:test';

import {
  daysUntil,
  formatCurrency,
  formatDate,
  formatPercent,
} from '../src/utils/formatters.js';

function localDateOffset(days) {
  const date = new Date();
  date.setHours(0, 0, 0, 0);
  date.setDate(date.getDate() + days);
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

test('formatCurrency formats INR and falls back for non-finite amounts', () => {
  assert.equal(formatCurrency(1250000, 'INR'), '₹1,250,000');
  assert.equal(formatCurrency(Number.NaN, 'USD'), '$0');
});

test('formatDate preserves calendar dates in the local timezone', () => {
  assert.equal(formatDate('2026-10-28'), 'Oct 28, 2026');
  assert.equal(formatDate('2026-02-31'), '2026-02-31');
  assert.equal(formatDate('not-a-date'), 'not-a-date');
  assert.equal(formatDate(''), 'No date set');
});

test('daysUntil counts local calendar days and rejects invalid input', () => {
  assert.equal(daysUntil(localDateOffset(2)), 2);
  assert.equal(daysUntil(localDateOffset(-2)), -2);
  assert.equal(daysUntil('2026-02-31'), null);
  assert.equal(daysUntil(''), null);
});

test('formatPercent handles invalid values and clamps to progress bounds', () => {
  assert.equal(formatPercent(40, 100), 40);
  assert.equal(formatPercent(120, 100), 100);
  assert.equal(formatPercent(-10, 100), 0);
  assert.equal(formatPercent(Number.NaN, 100), 0);
  assert.equal(formatPercent(40, 0), 0);
});
