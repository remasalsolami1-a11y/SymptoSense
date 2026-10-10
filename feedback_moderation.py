"""Admin tool: review and un-publish comments shown on the public reviews page.

Un-publishing only sets ``public_comment=0``: the comment is kept as private
feedback and nothing is deleted. Page: /admin/feedback-moderation (Admin only).
"""
import hmac
from html import escape

import db
import public_feedback


def _rows(limit=200):
    conn = db._conn()
    try:
        c = conn.cursor()
        c.execute("SELECT id, comment, rating, timestamp FROM feedback "
                  "WHERE COALESCE(public_comment,0)=1 AND comment IS NOT NULL AND TRIM(comment) <> '' "
                  "ORDER BY id DESC LIMIT %s" % db.PH, (max(1, min(int(limit), 500)),))
        return c.fetchall()
    finally:
        conn.close()


def unpublish(ids):
    ids = [int(x) for x in ids if str(x).strip().lstrip("-").isdigit()][:500]
    if not ids:
        return 0
    conn = db._conn()
    try:
        c = conn.cursor()
        done = 0
        for fid in ids:
            c.execute("UPDATE feedback SET public_comment=0 WHERE id=%s AND COALESCE(public_comment,0)=1" % db.PH, (fid,))
            done += int(c.rowcount or 0)
        conn.commit()
        return done
    finally:
        conn.close()


def weak_ids():
    return [r[0] for r in _rows(500) if not public_feedback.acceptable(r[1])]


def render(page, lang, csrf):
    ar = lang != "en"
    t = (lambda a, e: a if ar else e)
    rows = _rows()
    body_rows = []
    for fid, comment, rating, ts in rows:
        ok = public_feedback.acceptable(comment)
        badge = t("يظهر للعامة", "Shown publicly") if ok else t("مخفي تلقائيًا (ضعيف)", "Auto-hidden (weak)")
        body_rows.append(
            '<tr data-id="%d"><td>%d</td><td style="white-space:pre-wrap;max-width:420px">%s</td><td>%s</td>'
            '<td>%s</td><td><button type="button" class="btn" data-hide="%d">%s</button></td></tr>'
            % (fid, fid, escape(str(comment)[:500]), escape(str(rating or "")), escape(badge), fid, escape(t("إخفاء نهائيًا", "Unpublish"))))
    empty = '<tr><td colspan="5">%s</td></tr>' % escape(t("لا توجد تعليقات منشورة.", "No published comments."))
    body = (
        '<main class="container" style="max-width:980px;padding:24px 0"><h1>%s</h1><p class="muted">%s</p>'
        '<p><button type="button" class="btn pri" id="hideWeak">%s</button> <span id="fmStatus" role="status"></span></p>'
        '<div style="overflow:auto"><table class="table" style="width:100%%"><thead><tr><th>#</th><th>%s</th><th>%s</th><th>%s</th><th></th></tr></thead>'
        '<tbody>%s</tbody></table></div></main>'
        '<script>(function(){var T=%s;var st=document.getElementById("fmStatus");'
        'function post(ids){return fetch("/admin/feedback-moderation/unpublish",{method:"POST",credentials:"same-origin",'
        'headers:{"Content-Type":"application/json","X-CSRF-Token":T},body:JSON.stringify({ids:ids})}).then(function(r){return r.json()});}'
        'document.addEventListener("click",function(e){var b=e.target.closest("[data-hide]");if(b){post([b.getAttribute("data-hide")]).then(function(d){'
        'if(d.ok){var tr=b.closest("tr");if(tr)tr.remove();}else{st.textContent="error"}});}'
        'if(e.target.id==="hideWeak"){post("weak").then(function(d){st.textContent=d.ok?(d.count+" ✓"):"error";if(d.ok)location.reload();});}});})();</script>'
        % (escape(t("إدارة آراء المستخدمين", "Reviews moderation")),
           escape(t("الإخفاء لا يحذف التعليق؛ يبقى كملاحظة خاصة ولا يظهر في الصفحة العامة.",
                    "Unpublishing does not delete the comment; it stays as private feedback and leaves the public page.")),
           escape(t("إخفاء كل التعليقات الضعيفة", "Unpublish all weak comments")),
           escape(t("التعليق", "Comment")), escape(t("التقييم", "Rating")), escape(t("الحالة", "Status")),
           "".join(body_rows) or empty, __import__("json").dumps(csrf)))
    return page(t("إدارة الآراء", "Reviews moderation"), body)


def register(app, page_gate, csrf_token, admin_valid, admin_allowed, page, lang_fn):
    from flask import jsonify, request, session

    @app.route("/admin/feedback-moderation")
    def admin_feedback_moderation():
        denied = page_gate("/admin/feedback-moderation")
        if denied is not None:
            return denied
        return render(page, lang_fn(), csrf_token())

    @app.route("/admin/feedback-moderation/unpublish", methods=["POST"])
    def admin_feedback_unpublish():
        if not admin_valid() or not admin_allowed("moderation"):
            return jsonify({"ok": False, "error": "forbidden"}), 403
        supplied, expected = request.headers.get("X-CSRF-Token", ""), session.get("admin_csrf", "")
        if not expected or not hmac.compare_digest(supplied, expected):
            return jsonify({"ok": False, "error": "csrf_failed"}), 403
        data = request.get_json(silent=True) or {}
        ids = weak_ids() if data.get("ids") == "weak" else (data.get("ids") if isinstance(data.get("ids"), list) else [])
        return jsonify({"ok": True, "count": unpublish(ids)})
