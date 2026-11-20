"""Confirmation page for medication e-mail action links.

A GET on the e-mail link must never change data (mail scanners, link previews
and prefetchers open links). It only shows this page; the POST button runs the
one-time action.
"""
from html import escape

_T = {
    "taken": ("تأكيد: تناولتُ الجرعة", "Confirm: I took this dose", "تسجيل الجرعة كمأخوذة", "Mark taken"),
    "snooze": ("تأكيد: تأجيل التذكير ١٠ دقائق", "Confirm: snooze the reminder for 10 minutes", "تأجيل ١٠ دقائق", "Snooze 10 minutes"),
    "other": ("تأكيد الإجراء من رسالة التذكير", "Confirm the action from your reminder e-mail", "تأكيد", "Confirm"),
}


def render(token: str, action: str, lang: str) -> str:
    en = lang == "en"
    t = _T.get(action) or _T["other"]
    title, button = (t[1], t[3]) if en else (t[0], t[2])
    note = ("Nothing is saved until you press the button." if en
            else "لن يُسجَّل أي شيء حتى تضغط الزر.")
    return (
        '<!doctype html><html lang="%s" dir="%s"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="robots" content="noindex,nofollow"><title>SymptoSense</title>'
        '<style>body{font-family:system-ui,Tahoma,sans-serif;background:#f4f8f8;color:#12303a;margin:0;'
        'display:grid;place-items:center;min-height:100vh}main{background:#fff;border-radius:16px;'
        'padding:28px;max-width:420px;margin:16px;box-shadow:0 4px 24px #0001;text-align:center}'
        'button{min-height:48px;padding:0 28px;border:0;border-radius:12px;background:#0b7a75;color:#fff;'
        'font-size:16px;cursor:pointer}p{color:#47606a}</style></head><body><main><h1 style="font-size:20px">%s</h1>'
        '<p>%s</p><form method="post" action="/meds/email-action/%s?lang=%s">'
        '<button type="submit">%s</button></form></main></body></html>'
    ) % ("en" if en else "ar", "ltr" if en else "rtl", escape(title), escape(note),
         escape(token, quote=True), "en" if en else "ar", escape(button))
