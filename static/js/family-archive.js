/* Family page: people removed with "keep their records" can be restored (same id, records re-linked) or erased for good. */
(function () {
  'use strict';
  var box = document.getElementById('famArchive');
  if (!box || !window.ssFamilyOps) return;
  var en = document.documentElement.lang === 'en';
  var tx = function (ar, e) { return en ? e : ar; };
  function el(tag, text, cls) { var n = document.createElement(tag); if (text) n.textContent = text; if (cls) n.className = cls; return n; }
  function render(list) {
    box.textContent = '';
    if (!list.length) return;
    var card = el('div', '', 'card'); card.style.marginTop = '14px';
    var title = el('h3', tx('الأرشيف: أشخاص أُزيلوا مع الاحتفاظ بسجلاتهم', 'Archive: people removed with their records kept')); title.style.color = '#123B70';
    var msg = el('p', '', 'muted'); msg.setAttribute('role', 'status');
    card.appendChild(title);
    card.appendChild(el('p', tx('الاستعادة تعيد الشخص بنفس المعرّف فترتبط سجلاته به من جديد. الحذف النهائي يمحو سجلاته الصحية.',
      'Restoring brings the person back with the same id so their records are linked again. Permanent deletion erases their health records.'), 'muted'));
    list.forEach(function (a) {
      var row = el('div'); row.style.cssText = 'display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:8px 0';
      row.appendChild(el('b', a.name));
      row.appendChild(el('span', tx(a.records + ' تحليل • ' + a.blood_tests + ' CBC • ' + a.vitals + ' مؤشر', a.records + ' analyses • ' + a.blood_tests + ' CBC • ' + a.vitals + ' vitals'), 'muted'));
      var restore = el('button', tx('استعادة', 'Restore'), 'btn small'); restore.type = 'button';
      var erase = el('button', tx('حذف نهائي', 'Delete permanently'), 'btn small'); erase.type = 'button';
      var ops = window.ssFamilyOps, locked = false;
      var eraseLabel = tx('حذف نهائي', 'Delete permanently');
      var eraseBtn = ops.confirmButton(erase, eraseLabel, tx('⚠️ اضغطي مرة أخرى لتأكيد الحذف النهائي (لا رجعة فيه)', '⚠️ Press again to confirm permanent deletion (cannot be undone)'));
      function lockRow(on) { locked = on; restore.disabled = on; erase.disabled = on; }
      function act(method, url, done, failText, unknownText) {
        if (locked) return;                               // no duplicate requests while one is running
        var leaving = false;
        lockRow(true); msg.textContent = tx('جارٍ التنفيذ…', 'Working…');
        ops.call(method, url).then(function (res) {
          if (res.state === 'ok') { leaving = true; msg.textContent = done; location.reload(); }
          else if (res.state === 'gone') { leaving = true; msg.textContent = tx('تغيّرت الحالة من مكان آخر؛ نحدّث القائمة.', 'This already changed elsewhere; refreshing the list.'); location.reload(); }
          else if (res.state === 'unknown') msg.textContent = unknownText;
          else msg.textContent = failText;
        }).finally(function () { if (!leaving) { lockRow(false); eraseBtn.disarm(); } });
      }
      restore.addEventListener('click', function () {
        eraseBtn.disarm();
        act('POST', '/api/family/archived/' + a.id + '/restore', tx('تمت الاستعادة.', 'Restored.'),
          tx('فشلت الاستعادة ولم يتغير شيء.', 'Restore failed; nothing was changed.'),
          tx('لا نعرف إن اكتملت الاستعادة (انقطاع الاتصال أو خطأ في الخادم). حدّثي الصفحة للتحقق.', 'We cannot tell whether the restore finished (connection dropped or server error). Reload the page to check.'));
      });
      erase.addEventListener('click', function () {  // two presses: the first only asks for confirmation (auto-disarms after 8 s)
        if (locked) return;
        if (!eraseBtn.armed()) { eraseBtn.arm(); return; }
        eraseBtn.disarm();
        act('DELETE', '/api/family/archived/' + a.id, tx('تم الحذف النهائي.', 'Deleted permanently.'),
          tx('فشل الحذف ولم يتغير شيء.', 'Delete failed; nothing was changed.'),
          tx('لا نعرف إن اكتمل الحذف (انقطاع الاتصال أو خطأ في الخادم). حدّثي الصفحة للتحقق.', 'We cannot tell whether the delete finished (connection dropped or server error). Reload the page to check.'));
      });
      row.appendChild(restore); row.appendChild(erase); card.appendChild(row);
    });
    card.appendChild(msg); box.appendChild(card);
  }
  fetch('/api/family/archived', {credentials: 'same-origin'}).then(function (r) { return r.ok ? r.json() : {archived: []}; })
    .then(function (d) { render(d.archived || []); }).catch(function () {});
})();
