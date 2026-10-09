"""Clinical review queue: nothing medical is published before a second person approves it.

Admin edits to diseases, symptoms and red-flag rules are NOT applied to the live
knowledge base. They are stored here as a *proposal* (the exact payload) and are
applied through the normal ``medical_knowledge.save_*`` validation only when a
reviewer other than the author approves. Rejected proposals keep their note.

``SYMPTOSENSE_REQUIRE_CLINICAL_REVIEW=0`` disables the queue (local development);
``SYMPTOSENSE_ALLOW_SELF_REVIEW=1`` lets the author approve their own proposal
(only sensible for a single-admin deployment and recorded in the audit trail).
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from html import escape

import db
import medical_knowledge

KINDS = {"disease": "save_disease", "symptom": "save_symptom", "red_flag": "save_red_flag"}
MAX_PAYLOAD = 200_000
_READY = False


def required() -> bool:
    return os.environ.get("SYMPTOSENSE_REQUIRE_CLINICAL_REVIEW", "1").strip().lower() not in {"0", "false", "no", "off"}


def _self_review_allowed() -> bool:
    return os.environ.get("SYMPTOSENSE_ALLOW_SELF_REVIEW", "0").strip().lower() in {"1", "true", "yes", "on"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _ensure(conn) -> None:
    global _READY
    if _READY:
        return
    pk = "SERIAL PRIMARY KEY" if db.USE_POSTGRES else "INTEGER PRIMARY KEY AUTOINCREMENT"
    conn.cursor().execute(
        f"CREATE TABLE IF NOT EXISTS mk_clinical_reviews ("
        f"id {pk}, entity_type TEXT NOT NULL, entity_id INTEGER, name TEXT, payload TEXT NOT NULL, "
        f"status TEXT NOT NULL DEFAULT 'pending', requested_by_id INTEGER, requested_by_email TEXT, requested_at TEXT NOT NULL, "
        f"reviewer_id INTEGER, reviewer_email TEXT, reviewed_at TEXT, note TEXT, result_entity_id INTEGER)"
    )
    conn.commit()
    _READY = True


_COLS = ["id", "entity_type", "entity_id", "name", "payload", "status", "requested_by_id", "requested_by_email",
         "requested_at", "reviewer_id", "reviewer_email", "reviewed_at", "note", "result_entity_id"]


def _row(r):
    item = dict(zip(_COLS, r))
    try:
        item["payload"] = json.loads(item["payload"])
    except (TypeError, ValueError, OverflowError):
        item["payload"] = {}
    return item


def _who(admin):
    return (int((admin or {}).get("id") or 0) or None), str((admin or {}).get("email") or "system")


def submit(kind: str, payload: dict, admin: dict, entity_id: int | None = None) -> dict:
    """Queue a proposal. Returns the stored review row (status ``pending``)."""
    if kind not in KINDS:
        raise ValueError("invalid_entity")
    blob = json.dumps(payload or {}, ensure_ascii=False)
    if len(blob) > MAX_PAYLOAD:
        raise ValueError("payload_too_large")
    name = str((payload or {}).get("name_ar") or (payload or {}).get("name_en") or "")[:200]
    uid, email = _who(admin)
    conn = db._conn()
    try:
        _ensure(conn)
        c = conn.cursor()
        if entity_id:
            c.execute(f"UPDATE mk_clinical_reviews SET status='superseded' WHERE entity_type={db.PH} AND entity_id={db.PH} AND status='pending'",
                      (kind, int(entity_id)))
        insert = (f"INSERT INTO mk_clinical_reviews (entity_type,entity_id,name,payload,status,requested_by_id,requested_by_email,requested_at) "
                  f"VALUES ({','.join([db.PH] * 8)})")
        args = (kind, int(entity_id) if entity_id else None, name, blob, "pending", uid, email, _now())
        if db.USE_POSTGRES:
            c.execute(insert + " RETURNING id", args)
            new_id = c.fetchone()[0]
        else:
            c.execute(insert, args)
            new_id = c.lastrowid
        conn.commit()
        return _get(c, new_id)
    finally:
        conn.close()


def list_reviews(status: str | None = "pending", limit: int = 100) -> list[dict]:
    conn = db._conn()
    try:
        _ensure(conn)
        c = conn.cursor()
        sql = f"SELECT {','.join(_COLS)} FROM mk_clinical_reviews"
        params: list = []
        if status:
            sql += f" WHERE status={db.PH}"
            params.append(status)
        sql += f" ORDER BY id DESC LIMIT {db.PH}"
        params.append(max(1, min(int(limit), 500)))
        c.execute(sql, tuple(params))
        return [_row(r) for r in c.fetchall()]
    finally:
        conn.close()


def _get(c, review_id):
    c.execute(f"SELECT {','.join(_COLS)} FROM mk_clinical_reviews WHERE id={db.PH}", (int(review_id),))
    r = c.fetchone()
    return _row(r) if r else None


def decide(review_id: int, approve: bool, reviewer: dict, note: str = "") -> dict:
    """Approve (apply to the live knowledge base) or reject a pending proposal."""
    uid, email = _who(reviewer)
    note = str(note or "").strip()[:1000]
    if not approve and not note:
        raise ValueError("rejection_note_required")
    conn = db._conn()
    try:
        _ensure(conn)
        c = conn.cursor()
        review = _get(c, review_id)
        if not review:
            raise ValueError("not_found")
        if review["status"] != "pending":
            raise ValueError("already_decided")
        same_person = (uid and uid == review["requested_by_id"]) or email == review["requested_by_email"]
        if approve and same_person and not _self_review_allowed():
            raise ValueError("self_review_not_allowed")
    finally:
        conn.close()
    result_id = None
    if approve:
        saver = getattr(medical_knowledge, KINDS[review["entity_type"]])
        saved = saver(dict(review["payload"]), reviewer, review["entity_id"])
        result_id = int((saved or {}).get("id") or review["entity_id"] or 0) or None
    conn = db._conn()
    try:
        c = conn.cursor()
        c.execute(
            f"UPDATE mk_clinical_reviews SET status={db.PH}, reviewer_id={db.PH}, reviewer_email={db.PH}, reviewed_at={db.PH}, note={db.PH}, result_entity_id={db.PH} "
            f"WHERE id={db.PH} AND status='pending'",
            ("approved" if approve else "rejected", uid, email, _now(), note + (" [self-review]" if approve and same_person else ""), result_id, int(review_id)))
        conn.commit()
        return _get(c, review_id)
    finally:
        conn.close()


def counts() -> dict:
    conn = db._conn()
    try:
        _ensure(conn)
        c = conn.cursor()
        c.execute("SELECT status, COUNT(*) FROM mk_clinical_reviews GROUP BY status")
        return {str(k): int(v) for k, v in c.fetchall()}
    finally:
        conn.close()


# --------------------------------------------------------------------- admin page
_KIND_LABEL = {"disease": ("حالة", "Condition"), "symptom": ("عرض", "Symptom"), "red_flag": ("قاعدة خطر", "Red-flag rule")}


def render_page(*, page, lang: str, csrf: str, decision_summary: dict | None = None):
    ar = lang != "en"
    t = (lambda a, e: a if ar else e)
    pending = list_reviews("pending")
    recent = [r for r in list_reviews(None, 30) if r["status"] != "pending"][:15]
    ds = decision_summary or {}

    def card(r):
        kind = _KIND_LABEL.get(r["entity_type"], (r["entity_type"], r["entity_type"]))[0 if ar else 1]
        p = r["payload"]
        fields = "".join(
            f"<tr><th>{escape(str(k))}</th><td>{escape(json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v)[:400]}</td></tr>"
            for k, v in p.items())
        verb = t("تعديل على موجود", "Change to live item") if r["entity_id"] else t("جديد", "New")
        return (f'<article class="cr-card" data-id="{r["id"]}"><header><b>{escape(kind)} · {escape(r["name"] or "—")}</b>'
                f'<span class="cr-tag">{escape(verb)}</span></header>'
                f'<p class="cr-meta">{escape(t("قدّمه", "Submitted by"))}: {escape(r["requested_by_email"] or "—")} · {escape(r["requested_at"])}</p>'
                f'<details><summary>{escape(t("عرض المحتوى المقترح", "View proposed content"))}</summary><table class="cr-table">{fields}</table></details>'
                f'<textarea placeholder="{escape(t("ملاحظة المراجع (إلزامية عند الرفض)", "Reviewer note (required when rejecting)"))}" aria-label="note"></textarea>'
                f'<div class="cr-actions"><button type="button" data-act="approve" class="cr-ok">✅ {escape(t("اعتماد ونشر", "Approve & publish"))}</button>'
                f'<button type="button" data-act="reject" class="cr-no">⛔ {escape(t("رفض", "Reject"))}</button></div>'
                f'<p class="cr-status" aria-live="polite"></p></article>')

    done = "".join(
        f'<tr><td>{r["id"]}</td><td>{escape(r["entity_type"])}</td><td>{escape(r["name"] or "")}</td>'
        f'<td>{escape(r["status"])}</td><td>{escape(r["reviewer_email"] or "")}</td><td>{escape(r["note"] or "")}</td></tr>' for r in recent)
    levels = ds.get("by_level") or {}
    rules = "".join(f"<li><code>{escape(k)}</code> — {v}</li>" for k, v in (ds.get("top_rules") or []))
    body = f"""
<meta name="admin-csrf" content="{escape(csrf, quote=True)}">
<main class="cr-wrap" dir="{'rtl' if ar else 'ltr'}">
<h1>🩺 {escape(t('مراجعة المحتوى الطبي', 'Clinical content review'))}</h1>
<p class="cr-lead">{escape(t('لا يُنشر أي محتوى طبي جديد أو معدّل قبل اعتماد مراجع غير كاتبه.', 'No new or edited medical content is published until a reviewer other than its author approves it.'))}</p>
<section><h2>{escape(t('بانتظار المراجعة', 'Pending review'))} ({len(pending)})</h2>
{''.join(card(r) for r in pending) or f'<p class="cr-empty">{escape(t("لا شيء بانتظار المراجعة.", "Nothing is waiting for review."))}</p>'}</section>
<section><h2>{escape(t('آخر القرارات', 'Recent decisions'))}</h2>
<table class="cr-table"><tr><th>#</th><th>{escape(t('النوع','Type'))}</th><th>{escape(t('الاسم','Name'))}</th><th>{escape(t('القرار','Decision'))}</th><th>{escape(t('المراجع','Reviewer'))}</th><th>{escape(t('ملاحظة','Note'))}</th></tr>{done}</table></section>
<section><h2>{escape(t('قرارات الأمان المسجلة (بدون هوية)', 'Logged safety decisions (anonymous)'))}</h2>
<p>{escape(t('الإجمالي', 'Total'))}: <b>{ds.get('total', 0)}</b> · 🚨 {levels.get('emergency', 0)} · 🔴 {levels.get('high', 0)} · 🟡 {levels.get('medium', 0)} · 🟢 {levels.get('low', 0)}</p>
<ul>{rules or '<li>—</li>'}</ul></section>
</main>
<style>.cr-wrap{{max-width:900px;margin:24px auto;padding:0 16px;line-height:1.7}}.cr-card{{border:1px solid #D5E2EA;border-radius:14px;padding:14px;margin:12px 0;background:#fff}}
.cr-card header{{display:flex;justify-content:space-between;gap:8px}}.cr-tag{{background:#EAF4FB;border-radius:99px;padding:2px 10px;font-size:12px}}.cr-meta{{color:#4B6074;font-size:13px;margin:4px 0}}
.cr-table{{width:100%;border-collapse:collapse;font-size:13px}}.cr-table th,.cr-table td{{border-top:1px solid #E5EEF3;padding:6px;text-align:start;vertical-align:top}}
.cr-card textarea{{width:100%;min-height:60px;margin:8px 0;border:1px solid #C9DCE5;border-radius:10px;padding:8px;font:inherit}}
.cr-actions{{display:flex;gap:8px;flex-wrap:wrap}}.cr-actions button{{min-height:44px;padding:0 16px;border-radius:10px;border:0;font-weight:800;cursor:pointer}}.cr-ok{{background:#1F8F4E;color:#fff}}.cr-no{{background:#C62828;color:#fff}}</style>
<script>
document.querySelectorAll('.cr-card').forEach(function(card){{card.querySelectorAll('button[data-act]').forEach(function(btn){{btn.addEventListener('click',async function(){{
 var st=card.querySelector('.cr-status'),note=card.querySelector('textarea').value.trim(),act=btn.dataset.act;
 if(act==='reject'&&!note){{st.textContent={json.dumps(t('اكتب سبب الرفض.', 'Please write the rejection reason.'), ensure_ascii=False)};return;}}
 card.querySelectorAll('button').forEach(function(b){{b.disabled=true}});
 try{{var r=await fetch('/api/admin/clinical-reviews/'+card.dataset.id+'/'+act,{{method:'POST',headers:{{'Content-Type':'application/json','X-CSRF-Token':document.querySelector('meta[name=admin-csrf]').content}},body:JSON.stringify({{note:note}})}});
 var d=await r.json();if(!r.ok||!d.ok)throw new Error(d.error||'failed');st.textContent=act==='approve'?{json.dumps(t('تم الاعتماد والنشر.', 'Approved and published.'), ensure_ascii=False)}:{json.dumps(t('تم الرفض.', 'Rejected.'), ensure_ascii=False)};}}
 catch(e){{st.textContent={json.dumps(t('تعذر التنفيذ: ', 'Could not complete: '), ensure_ascii=False)}+e.message;card.querySelectorAll('button').forEach(function(b){{b.disabled=false}});}}
}})}})}});
</script>"""
    return page(t("مراجعة المحتوى الطبي", "Clinical content review"), body)
