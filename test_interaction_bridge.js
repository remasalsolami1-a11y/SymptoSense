'use strict';
/* Dependency-free behavior check for static/js/interaction-bridge.js. */
class FakeElement {
  constructor(id, attrs, value) {
    this.id = id;
    this.nodeType = 1;
    this.attrs = Object.assign({}, attrs || {});
    this.value = value || '';
    this.listeners = {};
  }
  hasAttribute(name) { return Object.prototype.hasOwnProperty.call(this.attrs, name); }
  getAttribute(name) { return this.attrs[name] == null ? null : this.attrs[name]; }
  removeAttribute(name) { delete this.attrs[name]; }
  addEventListener(name, fn) { (this.listeners[name] ||= []).push(fn); }
  querySelectorAll() { return []; }
  fire(name, extra) {
    const event = Object.assign({
      key: '', target: this, currentTarget: this, prevented: false, stopped: false,
      preventDefault() { this.prevented = true; },
      stopPropagation() { this.stopped = true; }
    }, extra || {});
    (this.listeners[name] || []).forEach((fn) => fn.call(this, event));
    return event;
  }
}

const a = new FakeElement('a', {onclick: 'pwaInstallNow()'});
const b = new FakeElement('b', {onclick: 'asstFb(this,2)'});
const c = new FakeElement('c', {onchange: 'switchFamilyMember(this.value)'}, 'hello');
const d = new FakeElement('d', {onkeydown: "if(event.key==='Enter')asstSend()"});
const e = new FakeElement('e', {onclick: 'if(event.target===this)closeExplain()'});
const f = new FakeElement('f', {onclick: "event.stopPropagation();smartCtxAction('use')"});
const elements = [a, b, c, d, e, f];

global.window = global;
global.location = {href: 'https://example.test/', origin: 'https://example.test'};
global.document = {
  readyState: 'complete',
  nodeType: 9,
  documentElement: {},
  querySelectorAll() {
    return elements.filter((el) => Object.keys(el.attrs).some((key) => /^on/.test(key)));
  },
  getElementById(id) { return elements.find((el) => el.id === id) || null; }
};

global.calls = [];
global.pwaInstallNow = () => calls.push(['pwa']);
global.asstFb = (el, n) => calls.push(['fb', el.id, n]);
global.switchFamilyMember = (value) => calls.push(['switch', value]);
global.asstSend = () => calls.push(['send']);
global.closeExplain = () => calls.push(['close']);
global.smartCtxAction = (value) => calls.push(['ctx', value]);

require('./static/js/interaction-bridge.js');
a.fire('click');
b.fire('click');
c.fire('change');
d.fire('keydown', {key: 'Enter'});
d.fire('keydown', {key: 'Escape'});
e.fire('click', {target: {id: 'child'}});
e.fire('click', {target: e});
const stoppedEvent = f.fire('click');

const expected = [['pwa'], ['fb', 'b', 2], ['switch', 'hello'], ['send'], ['close'], ['ctx', 'use']];
if (JSON.stringify(calls) !== JSON.stringify(expected)) {
  throw new Error(`unexpected calls: ${JSON.stringify(calls)}`);
}
if (!stoppedEvent.stopped) throw new Error('stopPropagation semantics were not preserved');
if (elements.some((el) => Object.keys(el.attrs).some((key) => /^on/.test(key)))) {
  throw new Error('legacy event attributes were not removed');
}
console.log('INTERACTION BRIDGE CHECK: PASS');
