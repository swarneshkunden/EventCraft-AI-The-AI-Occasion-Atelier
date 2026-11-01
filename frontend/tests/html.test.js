import assert from 'node:assert/strict';
import test from 'node:test';

import { appendHtml, escapeHtml, html, raw, setHtml } from '../src/utils/html.js';

test('escapeHtml neutralizes every HTML metacharacter', () => {
  assert.equal(
    escapeHtml('<img src=x onerror="alert(1)">&\'`'),
    '&lt;img src=x onerror=&quot;alert(1)&quot;&gt;&amp;&#039;`',
  );
});

test('escapeHtml refuses to inject null or undefined', () => {
  assert.equal(escapeHtml(null), '');
  assert.equal(escapeHtml(undefined), '');
  assert.equal(escapeHtml(''), '');
});

test('escapeHtml renders numbers and booleans as text', () => {
  assert.equal(escapeHtml(0), '0');
  assert.equal(escapeHtml(false), 'false');
});

test('html escapes interpolated user text by default', () => {
  const title = '<script>alert("xss")</script>';
  const markup = html`<h1 class="title">${title}</h1>`;

  assert.equal(
    markup,
    '<h1 class="title">&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt;</h1>',
  );
  assert.ok(!markup.includes('<script>'));
});

test('raw opts trusted markup in without escaping it', () => {
  const markup = html`<span class="icon">${raw('<svg aria-hidden="true"></svg>')}</span>`;

  assert.equal(markup, '<span class="icon"><svg aria-hidden="true"></svg></span>');
});

test('html joins arrays and escapes each item', () => {
  const markup = html`<ul>${['<b>one</b>', '<b>two</b>']}</ul>`;

  assert.equal(
    markup,
    '<ul>&lt;b&gt;one&lt;/b&gt;&lt;b&gt;two&lt;/b&gt;</ul>',
  );
});

test('arrays of html() fragments must be wrapped in raw()', () => {
  const items = ['one', 'two'].map((value) => html`<li>${value}</li>`);

  assert.equal(html`<ul>${raw(items.join(''))}</ul>`, '<ul><li>one</li><li>two</li></ul>');
});

test('html keeps literal template text untouched', () => {
  assert.equal(html`<p class="a &amp; b">ok</p>`, '<p class="a &amp; b">ok</p>');
});

test('setHtml and appendHtml no-op on a missing element', () => {
  assert.doesNotThrow(() => setHtml(null, '<p>x</p>'));
  assert.doesNotThrow(() => appendHtml(undefined, '<p>x</p>'));
});
