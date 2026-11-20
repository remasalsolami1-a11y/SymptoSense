/* SymptoSense V253 - shows a call-now banner when an API response carries `safety_notice`
 * (health search, medicine lookup, blood-test notes). DOM is built with textContent only. */
(function () {
  'use strict';
  if (window.__ssSafetyNotice) return;
  window.__ssSafetyNotice = true;
  var WATCH = /^\/api\/(search|drug|meds|blood)(\/|$|\?)/;
  var original = window.fetch;
  if (typeof original !== 'function') return;

  function show(n) {
    var ar = (document.documentElement.getAttribute('lang') || 'ar').indexOf('en') !== 0;
    var old = document.getElementById('ssSafetyNotice');
    if (old) old.remove();
    var box = document.createElement('div');
    box.id = 'ssSafetyNotice';
    box.setAttribute('role', 'alert');
    box.style.cssText = 'position:sticky;top:0;z-index:2147483000;background:#B3261E;color:#fff;padding:12px 16px;' +
      'display:flex;flex-wrap:wrap;gap:10px;align-items:center;justify-content:center;font-weight:700;line-height:1.7';
    var msg = document.createElement('span');
    msg.textContent = (ar ? '⚠️ ما كتبته قد يدل على حالة طارئة. إذا كان يحدث الآن اتصل بالطوارئ فورًا.' :
      '⚠️ What you wrote may describe an emergency. If this is happening now, call emergency services immediately.');
    box.appendChild(msg);
    var num = String(n.number || '997').replace(/[^0-9]/g, '') || '997';
    var call = document.createElement('a');
    call.href = 'tel:' + num;
    call.textContent = (ar ? 'اتصل ' : 'Call ') + num;
    call.style.cssText = 'background:#fff;color:#B3261E;border-radius:999px;padding:6px 16px;text-decoration:none;font-weight:800';
    box.appendChild(call);
    if (n.message) {
      var detail = document.createElement('div');
      detail.style.cssText = 'flex-basis:100%;text-align:center;font-weight:500;font-size:13px';
      detail.textContent = String(n.message).slice(0, 400);
      box.appendChild(detail);
    }
    document.body.insertBefore(box, document.body.firstChild);
  }

  window.fetch = function (input, init) {
    var p = original.apply(this, arguments);
    try {
      var url = typeof input === 'string' ? input : (input && input.url) || '';
      var path = url.replace(/^https?:\/\/[^/]+/, '');
      if (WATCH.test(path)) {
        p.then(function (res) {
          try {
            if (res && res.ok && (res.headers.get('content-type') || '').indexOf('json') !== -1) {
              res.clone().json().then(function (b) { if (b && b.safety_notice) show(b.safety_notice); }).catch(function () {});
            }
          } catch (e) { /* display only */ }
        }).catch(function () {});
      }
    } catch (e) { /* never block the request */ }
    return p;
  };
})();
