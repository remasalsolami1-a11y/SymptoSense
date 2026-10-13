/* Shared helpers for the family delete / archive screens.
   call():  one request, never rejects, answers {state}:
            'ok'      HTTP 2xx AND a JSON body with ok:true
            'gone'    404 from our API ({ok:false,error:'family_member_not_found'|'not_found'}): already deleted / restored / lost a race
            'failed'  the server refused (4xx, or 2xx with ok:false): nothing changed
            'unknown' network drop, 5xx, an empty/invalid reply, or a bare 404: we cannot tell whether it finished
   confirmButton(): two-press confirmation that disarms itself after 8 seconds. */
(function () {
  'use strict';
  var CONFIRM_MS = 8000;
  function csrf() { var m = document.querySelector('meta[name="symptosense-csrf"]'); return m ? String(m.content || '') : ''; }
  function call(method, url) {
    return fetch(url, {method: method, credentials: 'same-origin', headers: {'X-CSRF-Token': csrf()}}).then(function (r) {
      return r.text().then(function (t) { return t; }, function () { return ''; }).then(function (text) {
        var d = null;
        try { d = JSON.parse(text); } catch (e) { d = null; }                 // empty / HTML / truncated body -> no usable answer
        var json = !!d && typeof d === 'object' && !Array.isArray(d);
        var s = r.status, err = json && typeof d.error === 'string' ? d.error : '';
        if (r.ok) {
          if (json && d.ok === true) return {state: 'ok', status: s};          // success needs BOTH a 2xx status and ok:true
          if (json && d.ok === false) return {state: 'failed', status: s, error: err};
          return {state: 'unknown', status: s};                                // 2xx but no confirmation: we cannot tell
        }
        // Only our own API's "not found" answer means "already gone"; a bare/HTML 404 (proxy, wrong route) is not proof.
        if (s === 404) return json && d.ok === false && (err === 'family_member_not_found' || err === 'not_found') ? {state: 'gone', status: s} : {state: 'unknown', status: s};
        if (s >= 500) return {state: 'unknown', status: s};
        return {state: 'failed', status: s, error: err};
      });
    }, function () { return {state: 'unknown', status: 0}; });
  }
  function confirmButton(btn, label, armedLabel) {
    var timer = null;
    var api = {
      armed: function () { return btn.getAttribute('data-armed') === '1'; },
      disarm: function () { clearTimeout(timer); timer = null; btn.textContent = label; btn.setAttribute('data-armed', ''); },
      arm: function () {
        btn.setAttribute('data-armed', '1'); btn.textContent = armedLabel;
        clearTimeout(timer); timer = setTimeout(api.disarm, CONFIRM_MS);
      }
    };
    return api;
  }
  window.ssFamilyOps = {call: call, confirmButton: confirmButton, CONFIRM_MS: CONFIRM_MS};
})();
