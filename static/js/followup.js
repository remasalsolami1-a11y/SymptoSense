/* Follow-up card ("did it improve?"). Text is written with textContent only. */
(function () {
  var box = document.getElementById('ssFollowup');
  if (!box) return;
  var out = document.getElementById('ssFollowupOut');
  var rec = box.getAttribute('data-record');
  var sign = document.getElementById('ssFollowupSign');
  box.addEventListener('click', function (ev) {
    var b = ev.target.closest('button[data-outcome]');
    if (!b) return;
    var btns = box.querySelectorAll('button[data-outcome]');
    for (var i = 0; i < btns.length; i++) btns[i].disabled = true;
    fetch('/api/followup/answer', {
      method: 'POST', credentials: 'same-origin', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({record_id: Number(rec), outcome: b.getAttribute('data-outcome'), new_sign: !!(sign && sign.checked)})
    }).then(function (r) { return r.json(); }).then(function (d) {
      out.textContent = d && d.ok ? d.message : (box.getAttribute('data-error') || '');
      out.hidden = false;
      if (!(d && d.ok)) for (var i = 0; i < btns.length; i++) btns[i].disabled = false;
    }).catch(function () {
      out.textContent = box.getAttribute('data-error') || '';
      out.hidden = false;
      for (var i = 0; i < btns.length; i++) btns[i].disabled = false;
    });
  });
})();
