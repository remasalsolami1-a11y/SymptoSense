'use strict';
/* Dependency-free behavior check for the data-ss-* delegated actions in static/js/interaction-bridge.js
   (the old inline on* attributes were removed; the audit tool asserts none remain). */
class FakeElement {
  constructor(id, attrs, value) { this.id = id; this.attrs = Object.assign({}, attrs || {}); this.value = value || ''; }
  hasAttribute(n) { return Object.prototype.hasOwnProperty.call(this.attrs, n); }
  getAttribute(n) { return this.attrs[n] == null ? null : this.attrs[n]; }
  closest(sel) { const m = /^\[([\w-]+)\]$/.exec(sel); return m && this.hasAttribute(m[1]) ? this : null; }
}
const listeners = {};
global.window = global;
global.location = {href: 'https://example.test/', origin: 'https://example.test', pathname: '/'};
global.document = {
  readyState: 'complete', nodeType: 9, documentElement: {},
  addEventListener(type, fn) { (listeners[type] ||= []).push(fn); },
  querySelectorAll() { return []; },
  getElementById() { return null; }
};
function fire(type, target, extra) {
  const event = Object.assign({type, target, key: '', prevented: false, preventDefault() { this.prevented = true; }}, extra || {});
  (listeners[type] || []).forEach((fn) => fn(event));
  return event;
}
global.calls = [];
global.pwaInstallNow = () => calls.push(['pwa']);
global.asstFb = (el, n) => calls.push(['fb', el.id, n]);
global.switchFamilyMember = (v) => calls.push(['switch', v]);
global.asstSend = () => calls.push(['send']);
global.logMed = (id, tm, st) => calls.push(['log', id, tm, st]);
global.notAllowedFn = () => calls.push(['BAD']);

require('../static/js/interaction-bridge.js');
const a = new FakeElement('a', {'data-ss-click': 'pwaInstallNow'});
const b = new FakeElement('b', {'data-ss-click': 'asstFb', 'data-ss-args': '["$this",2]'});
const c = new FakeElement('c', {'data-ss-change': 'switchFamilyMember', 'data-ss-args': '["$value"]'}, 'hello');
const d = new FakeElement('d', {'data-ss-keydown': 'asstSend', 'data-ss-key': 'Enter'});
const e = new FakeElement('e', {'data-ss-click': 'logMed', 'data-ss-args': '[7,"08:00","taken"]'});
const bad = new FakeElement('x', {'data-ss-click': 'notAllowedFn'});
fire('click', a); fire('click', b); fire('change', c);
fire('keydown', d, {key: 'Enter'}); fire('keydown', d, {key: 'Escape'});
fire('click', e); fire('click', bad);
const expected = [['pwa'], ['fb', 'b', 2], ['switch', 'hello'], ['send'], ['log', 7, '08:00', 'taken']];
if (JSON.stringify(calls) !== JSON.stringify(expected)) throw new Error(`unexpected calls: ${JSON.stringify(calls)}`);
console.log('INTERACTION BRIDGE CHECK: PASS');
