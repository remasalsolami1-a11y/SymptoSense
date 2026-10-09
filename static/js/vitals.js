/* Home vitals form. Messages are written with textContent only. */
(function () {
  var form = document.getElementById('vitalsForm');
  if (!form) return;
  var kind = document.getElementById('vKind'), msg = document.getElementById('vMsg');
  var ar = document.documentElement.lang !== 'en';
  function sync() {
    document.getElementById('vV2Wrap').hidden = kind.value !== 'bp';
    document.getElementById('vUnitWrap').hidden = kind.value !== 'glucose';
    document.getElementById('vCtxWrap').hidden = kind.value !== 'glucose';
  }
  kind.addEventListener('change', sync); sync();
  function say(t) { msg.textContent = t; msg.hidden = false; }
  form.addEventListener('submit', function (ev) {
    ev.preventDefault();
    var body = {kind: kind.value, v1: document.getElementById('vV1').value, v2: document.getElementById('vV2').value,
                unit: document.getElementById('vUnit').value, context: document.getElementById('vCtx').value};
    fetch('/api/vitals', {method: 'POST', credentials: 'same-origin', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)})
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (d && d.ok) { say(d.alert.message); setTimeout(function () { location.reload(); }, d.alert.level === 'ok' ? 600 : 2500); }
        else say(ar ? 'القيمة غير منطقية، راجع الأرقام.' : 'That value looks implausible; please check the numbers.');
      }).catch(function () { say(ar ? 'تعذر الحفظ.' : 'Could not save.'); });
  });
  document.addEventListener('click', function (ev) {
    var b = ev.target.closest('button[data-del]');
    if (!b) return;
    fetch('/api/vitals/' + encodeURIComponent(b.getAttribute('data-del')), {method: 'DELETE', credentials: 'same-origin'})
      .then(function () { location.reload(); });
  });
})();
