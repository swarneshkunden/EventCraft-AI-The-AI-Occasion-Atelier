import assert from 'node:assert/strict';
import test from 'node:test';

import { escapeHtml } from '../src/utils/html.js';

test('escapeHtml escapes HTML special characters to prevent XSS', () => {
  assert.equal(escapeHtml('<script>alert(1)</script>'), '&lt;script&gt;alert(1)&lt;/script&gt;');
  assert.equal(escapeHtml('<img src=x onerror=alert(1)>'), '&lt;img src=x onerror=alert(1)&gt;');
  assert.equal(escapeHtml('"quoted" & \'single\''), '&quot;quoted&quot; &amp; &#039;single&#039;');
  assert.equal(escapeHtml('safe text'), 'safe text');
});

test('escapeHtml handles non-strings and empty input', () => {
  assert.equal(escapeHtml(null), '');
  assert.equal(escapeHtml(undefined), '');
  assert.equal(escapeHtml(42), '42');
  assert.equal(escapeHtml(''), '');
});

test('escapeHtml does not double-escape already-safe text', () => {
  assert.equal(escapeHtml('Hello World'), 'Hello World');
  assert.equal(escapeHtml('Priya & Arjun’s Wedding'), 'Priya &amp; Arjun’s Wedding');
});
