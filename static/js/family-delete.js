/* Family member page: remove the person, with an explicit choice about their health data.
   Permanent deletion needs a second confirmation; buttons are locked while a request is running. */
(function () {
  'use strict';
  var box = document.getElementById('famDelete');
  if (!box || !window.ssFamilyOps) return;
  var mid = parseInt(box.getAttribute('data-mid'), 10);
  var en = document.documentElement.lang === 'en';
  var tx = function (ar, e) { return en ? e : ar; };
  var busy = false;
  function el(tag, text, cls) { var n = document.createElement(tag); if (text) n.textContent = text; if (cls) n.className = cls; return n; }
  var open = el('button', tx('🗑️ حذف هذا الفرد', '🗑️ Remove this person'), 'btn small');
  open.type = 'button';
  var panel = el('div', '', 'card'); panel.hidden = true; panel.style.marginTop = '14px';
  var msg = el('p', '', 'muted'); msg.setAttribute('role', 'status');
  var keep = el('button', tx('إزالة الفرد مع أرشفة سجلاته الصحية (يمكن استعادته)', 'Remove the person, archive their health records (restorable)'), 'btn');
  var wipeLabel = tx('حذف الفرد وجميع بياناته الصحية نهائيًا', 'Delete the person and all their health data permanently');
  var wipe = el('button', wipeLabel, 'btn pri');
  var cancel = el('button', tx('إلغاء', 'Cancel'), 'btn small');
  var all = [keep, wipe, cancel];
  all.forEach(function (b) { b.type = 'button'; b.style.margin = '4px'; });
  var ops = window.ssFamilyOps;
  var wipeBtn = ops.confirmButton(wipe, wipeLabel, tx('⚠️ اضغطي مرة أخرى لتأكيد الحذف النهائي (لا رجعة فيه)', '⚠️ Press again to confirm permanent deletion (cannot be undone)'));
  function lock(on) { busy = on; all.forEach(function (b) { b.disabled = on; }); open.disabled = on; }
  function run(deleteData) {
    if (busy) return;                                   // one request at a time
    var leaving = false;
    lock(true); msg.textContent = tx('جارٍ الحذف…', 'Deleting…');
    ops.call('DELETE', '/api/family/' + mid + (deleteData ? '?delete_data=1' : '')).then(function (res) {
      if (res.state === 'ok' || res.state === 'gone') {   // 'gone' = already deleted (earlier attempt or another tab): same end result
        leaving = true; msg.textContent = tx('تم الحذف.', 'Deleted.');
        location.href = location.pathname.replace(/\/family\/\d+.*$/, '/family');
      } else if (res.state === 'unknown') {
        msg.textContent = tx('لا نعرف إن اكتمل الحذف (انقطاع الاتصال أو خطأ في الخادم). حدّثي الصفحة للتحقق قبل المحاولة مجددًا.', 'We cannot tell whether the delete finished (connection dropped or server error). Reload the page to check before trying again.');
      } else {
        msg.textContent = tx('فشل الحذف ولم يتغير شيء. حاولي مرة أخرى.', 'The delete failed and nothing was changed. Please try again.');
      }
    }).finally(function () { if (!leaving) lock(false); });
  }
  keep.addEventListener('click', function () { wipeBtn.disarm(); run(false); });
  wipe.addEventListener('click', function () {
    if (busy) return;
    if (!wipeBtn.armed()) { wipeBtn.arm(); return; }    // first press only arms (auto-disarms after 8 s)
    wipeBtn.disarm(); run(true);
  });
  cancel.addEventListener('click', function () { if (!busy) { wipeBtn.disarm(); panel.hidden = true; } });
  open.addEventListener('click', function () { panel.hidden = false; });
  panel.appendChild(el('p', tx('خطط الأدوية والتذكيرات تُحذف دائمًا. اختاري ما يحدث لسجلاته الصحية (تحليل الأعراض، CBC، المؤشرات)؛ المؤرشفة يمكن استعادتها من صفحة العائلة:', 'Medication plans and reminders are always deleted. Choose what happens to their health records (symptom analyses, CBC, vitals); archived records can be restored from the Family page:')));
  [keep, wipe, cancel, msg].forEach(function (n) { panel.appendChild(n); });
  box.appendChild(open); box.appendChild(panel);
})();
