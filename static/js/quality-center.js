/* Admin quality centre. Every value is written with textContent only. */
(function () {
  var root = document.getElementById('qcRoot');
  if (!root) return;
  var ar = document.documentElement.lang !== 'en';
  function el(tag, text, cls) { var e = document.createElement(tag); if (text !== undefined) e.textContent = String(text); if (cls) e.className = cls; return e; }
  function section(title, rows) {
    var s = el('div'); s.appendChild(el('h2', title));
    var ul = el('ul');
    rows.forEach(function (r) { ul.appendChild(el('li', r[0] + ': ' + r[1])); });
    s.appendChild(ul); return s;
  }
  fetch('/api/admin/quality', {credentials: 'same-origin'}).then(function (r) { return r.json(); }).then(function (d) {
    root.textContent = '';
    if (!d || !d.ok) { root.textContent = ar ? 'تعذر تحميل البيانات.' : 'Could not load data.'; return; }
    document.getElementById('qcNote').textContent = d.scope_note || '';
    var sv = d.service, an = d.analysis, sf = d.safety;
    root.appendChild(section(ar ? 'الخدمة' : 'Service', [
      [ar ? 'الطلبات' : 'Requests', sv.requests], [ar ? 'أخطاء 5xx' : '5xx errors', sv.responses_5xx + ' (' + (sv.error_rate_5xx * 100).toFixed(2) + '%)']]));
    root.appendChild(section(ar ? 'السلامة' : 'Safety', [
      [ar ? 'فشل فحص السلامة (يجب أن يكون 0)' : 'Safety-check failures (must be 0)', sf.check_failures]]));
    var dec = Object.keys(an.decisions || {}).map(function (k) { return k + '=' + an.decisions[k]; }).join('، ');
    root.appendChild(section(ar ? 'التحليل' : 'Analysis', [
      [ar ? 'مكتمل' : 'Completed', an.completed], [ar ? 'معلومات غير كافية' : 'Insufficient', an.insufficient],
      [ar ? 'ثقة منخفضة' : 'Low confidence', an.low_confidence], [ar ? 'نسبة الضعيف' : 'Weak rate', (an.weak_rate * 100).toFixed(1) + '%'],
      [ar ? 'مستويات القرار' : 'Decision mix', dec || '-']]));
    var cs = d.clinical_signoff || {pending: []}, se = d.side_effects || {};
    if (cs.bypass_active && (cs.pending || []).length) {
      var warn = el('p', ar ? 'تحذير: تجاوز الاعتماد السريري مفعّل (Clinical sign-off bypass is active)' : 'Clinical sign-off bypass is active', 'warn');
      warn.setAttribute('role', 'alert'); root.appendChild(warn);
    }
    root.appendChild(section(ar ? 'الاعتماد السريري والتدقيق' : 'Clinical sign-off and audit', [
      [ar ? 'مجالات بانتظار الاعتماد' : 'Areas pending sign-off', (cs.pending || []).length],
      [ar ? 'فشل كتابة سجل التدقيق (يجب أن يكون 0)' : 'Audit-log write failures (should be 0)', se.audit_log_failures_total || 0],
      [ar ? 'فشل عمليات ثانوية أخرى' : 'Other side-effect failures', se.best_effort_failures_total || 0]]));
    root.appendChild(section(ar ? 'البحث' : 'Search', [[ar ? 'استعلامات بلا بطاقة محددة (فجوة محتوى)' : 'Queries without a specific card (content gap)', d.search.content_gaps]]));
    var fu = Object.keys(d.followups || {}).map(function (k) { return k + '=' + d.followups[k].count + (d.followups[k].new_sign ? ' (+' + d.followups[k].new_sign + ' new sign)' : ''); }).join('، ');
    root.appendChild(section(ar ? 'المتابعات' : 'Follow-ups', [[ar ? 'النتائج' : 'Outcomes', fu || '-']]));
    var fr = (d.feedback_reasons || []).map(function (x) { return x.reason + '=' + x.count; }).join('، ');
    root.appendChild(section(ar ? 'أسباب عدم الرضا' : 'Feedback reasons', [[ar ? 'التحليل' : 'Analysis', fr || '-']]));
    var slow = (sv.slowest_routes || []).map(function (r) { return [r.route, 'p95=' + r.p95_ms + 'ms, 5xx=' + r.errors_5xx + ', n=' + r.count]; });
    root.appendChild(section(ar ? 'أبطأ المسارات' : 'Slowest routes', slow.length ? slow : [['-', '-']]));
    var er = (sv.recent_errors || []).map(function (e) { return [e.kind, e.detail]; });
    root.appendChild(section(ar ? 'آخر الأخطاء المهمة' : 'Recent important errors', er.length ? er : [['-', '-']]));
  }).catch(function () { root.textContent = ar ? 'تعذر تحميل البيانات.' : 'Could not load data.'; });
})();
