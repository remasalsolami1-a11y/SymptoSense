"""
dashboard.py — SymptoSense Admin Dashboard
Web interface to monitor bot usage and symptom trends in real time.
Run with: python dashboard.py
"""

from flask import Flask, render_template_string, jsonify
import db
import os

app = Flask(__name__)

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SymptoSense Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800&display=swap');
  :root {
    --primary: #1976D2;
    --primary-dark: #123B70;
    --primary-mid: #64B5F6;
    --primary-pale: #B8D8F8;
    --primary-light: #EAF4FF;
    --text-body: #40566F;
    --text-muted: #718096;
    --bg-page: #F5F9FF;
    --bg-card: #FFFFFF;
    --border-card: #DCEBFA;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Cairo','Segoe UI',Tahoma,sans-serif; background: var(--bg-page); color: var(--text-body); min-height: 100vh; }
  button { font-family: inherit; }
  .header { position: sticky; top: 0; z-index: 20; background: rgba(255,255,255,.96); backdrop-filter: blur(12px); padding: 14px clamp(16px,4vw,42px); display: flex; align-items: center; justify-content: space-between; gap: 16px; border-bottom: 1px solid var(--border-card); box-shadow: 0 4px 18px rgba(25,118,210,.06); }
  .brand-wrap { display: flex; align-items: center; gap: 11px; min-width: 0; }
  .brand-icon { width: 45px; height: 45px; border-radius: 14px; background: var(--primary-light); display: flex; align-items: center; justify-content: center; font-size: 23px; }
  .header h1 { font-size: clamp(17px,3vw,22px); color: var(--primary-dark); line-height: 1.35; }
  .header h1 span { color: var(--primary); }
  .header-sub { color: var(--text-muted); font-size: 11.5px; margin-top: 1px; }
  .header-actions { display: flex; align-items: center; gap: 9px; }
  .live-badge { background: var(--primary-light); color: var(--primary); border: 1px solid var(--primary-pale); padding: 6px 11px; border-radius: 999px; font-size: 11px; font-weight: 800; }
  .container { max-width: 1240px; margin: 0 auto; padding: 28px 20px 42px; }
  .page-intro { display: flex; align-items: flex-end; justify-content: space-between; gap: 16px; margin-bottom: 20px; }
  .page-intro h2 { color: var(--primary-dark); font-size: clamp(22px,4vw,31px); margin-bottom: 3px; }
  .page-intro p { color: var(--text-muted); font-size: 13px; }
  .section-title { color: var(--primary-dark); font-size: 16px; font-weight: 800; margin: 4px 0 11px; }
  .stats-grid { display: grid; grid-template-columns: repeat(3,minmax(0,1fr)); gap: 14px; margin-bottom: 24px; }
  .stat-card { position: relative; overflow: hidden; background: var(--bg-card); border-radius: 18px; padding: 19px; border: 1px solid var(--border-card); box-shadow: 0 6px 20px rgba(25,118,210,.06); text-align: start; }
  .stat-card::after { content:''; position:absolute; inset-inline-end:-26px; top:-26px; width:78px; height:78px; border-radius:50%; background:var(--primary-light); }
  .stat-card .number { position:relative; z-index:1; font-size: 31px; line-height: 1.2; font-weight: 900; color: var(--primary); }
  .stat-card .label { font-size: 13px; color: var(--primary-dark); font-weight: 800; margin-top: 6px; }
  .stat-card .sub { font-size: 10.5px; color: #94A3B8; margin-top: 2px; }
  .charts-grid { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 16px; margin-bottom: 24px; }
  .chart-card { background: var(--bg-card); border-radius: 18px; padding: 19px; border: 1px solid var(--border-card); box-shadow: 0 6px 20px rgba(25,118,210,.06); }
  .chart-card h3 { font-size: 14px; color: var(--primary-dark); margin-bottom: 15px; padding-bottom: 11px; border-bottom: 1px solid var(--border-card); }
  .chart-wrap { position: relative; height: 250px; }
  .footer { text-align: center; padding: 24px; color: #94A3B8; font-size: 11px; }
  .refresh-btn { background: var(--primary); border: 0; color: var(--bg-card); min-height: 40px; padding: 8px 16px; border-radius: 11px; cursor: pointer; font-size: 12px; font-weight: 800; box-shadow: 0 7px 16px rgba(25,118,210,.18); }
  .refresh-btn:hover { background: #1565C0; }
  .refresh-btn:focus-visible { outline: 3px solid rgba(25,118,210,.28); outline-offset: 3px; }
  .last-updated { font-size: 11px; color: var(--text-muted); margin-top: 8px; text-align:center; }
  .empty { color:#94A3B8; text-align:center; padding:18px; font-size:13px; }
  @media (max-width: 850px) { .stats-grid { grid-template-columns: repeat(2,minmax(0,1fr)); } .charts-grid { grid-template-columns: 1fr; } }
  @media (max-width: 560px) {
    .header { align-items:flex-start; padding:12px 14px; }
    .header-sub, .live-badge { display:none; }
    .brand-icon { width:40px; height:40px; border-radius:12px; }
    .container { padding:20px 12px 34px; }
    .page-intro { align-items:flex-start; flex-direction:column; }
    .stats-grid { grid-template-columns: repeat(2,minmax(0,1fr)); gap:10px; }
    .stat-card { padding:15px 13px; border-radius:15px; }
    .stat-card .number { font-size:25px; }
    .chart-card { padding:15px 12px; border-radius:16px; }
    .chart-wrap { height:230px; }
  }
  @media (max-width: 350px) { .stats-grid { grid-template-columns: 1fr; } }
</style>
</head>
<body>

<div class="header">
  <div class="brand-wrap">
    <div class="brand-icon">❤️‍🩹</div>
    <div><h1>Sympto<span>Sense</span></h1><div class="header-sub">لوحة إدارة المنصة الصحية</div></div>
  </div>
  <div class="header-actions">
    <span class="live-badge">● مباشر</span>
    <button class="refresh-btn" onclick="loadAll()">🔄 تحديث</button>
  </div>
</div>

<div class="container">

  <div class="page-intro">
    <div><h2>الزوار والتقييمات</h2><p>ملخص واضح لعدد زوار SymptoSense وآرائهم فقط.</p></div>
  </div>

  <div class="section-title">👥 الزوار</div>
  <div class="stats-grid" id="stats-grid">
    <div class="stat-card"><div class="number" id="total-visits">-</div><div class="label">إجمالي الزيارات</div><div class="sub">Total Visits</div></div>
    <div class="stat-card"><div class="number" id="unique-visitors">-</div><div class="label">مستخدمون فريدون</div><div class="sub">Unique Users</div></div>
    <div class="stat-card"><div class="number" id="week-visits">-</div><div class="label">زيارات آخر 7 أيام</div><div class="sub">Visits in 7 Days</div></div>
  </div>

  <div class="section-title">⭐ التقييمات</div>
  <div class="stats-grid">
    <div class="stat-card"><div class="number" id="total-feedback">-</div><div class="label">التقييمات</div><div class="sub">Feedback</div></div>
    <div class="stat-card"><div class="number" id="positive-feedback">-</div><div class="label">التقييمات الإيجابية</div><div class="sub">Positive Ratings</div></div>
    <div class="stat-card"><div class="number" id="average-feedback">-</div><div class="label">متوسط التقييم</div><div class="sub">Average Rating</div></div>
  </div>

  <div class="section-title">📊 ملخص مرئي</div>
  <div class="charts-grid">
    <div class="chart-card">
      <h3>👥 ملخص الزوار</h3>
      <div class="chart-wrap"><canvas id="visitorsChart"></canvas></div>
    </div>
    <div class="chart-card">
      <h3>⭐ توزيع التقييمات</h3>
      <div class="chart-wrap"><canvas id="feedbackChart"></canvas></div>
    </div>
  </div>

  <!-- ملاحظات التقييم -->
  <div class="chart-card" style="margin-bottom:28px;">
    <h3>📝 ملاحظات المستخدمين على التقييم السلبي</h3>
    <div id="feedback-comments">
      <p class="empty">لا توجد ملاحظات بعد</p>
    </div>
  </div>

  <div class="last-updated" id="last-updated"></div>
</div>

<div class="footer">SymptoSense © 2026 — ريماس السلمي | للتوعية الصحية فقط</div>

<script>
let visitorsChart, feedbackChart;

async function loadAll() {
  try {
    const r = await fetch('/api/stats');
    const d = await r.json();
    
    // Stats
    document.getElementById('total-visits').textContent = d.stats.total_visits;
    document.getElementById('unique-visitors').textContent = d.stats.unique_visitors;
    document.getElementById('week-visits').textContent = d.stats.visits_this_period;
    const fbCount = (d.feedback.great||0) + (d.feedback.good||0) + (d.feedback.ok||0) + (d.feedback.bad||0);
    const positiveCount = (d.feedback.great||0) + (d.feedback.good||0);
    const positivePct = fbCount ? Math.round((positiveCount / fbCount) * 100) : 0;
    const average = fbCount
      ? (((d.feedback.great||0)*4 + (d.feedback.good||0)*3 + (d.feedback.ok||0)*2 + (d.feedback.bad||0)) / fbCount).toFixed(1)
      : '0.0';
    document.getElementById('total-feedback').textContent = fbCount;
    document.getElementById('positive-feedback').textContent = positivePct + '%';
    document.getElementById('average-feedback').textContent = average + '/4';

    if (visitorsChart) visitorsChart.destroy();
    visitorsChart = new Chart(document.getElementById('visitorsChart'), {
      type: 'bar',
      data: {
        labels: ['إجمالي الزيارات', 'زوار فريدون', 'آخر 7 أيام'],
        datasets: [{ data: [d.stats.total_visits||0, d.stats.unique_visitors||0, d.stats.visits_this_period||0], backgroundColor: ['#123B70','#1976D2','#64B5F6'], borderRadius: 8 }]
      },
      options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } },
        scales: { x: { ticks: { color: '#718096', font: { size: 11 } }, grid: { color: '#DCEBFA' } },
                   y: { beginAtZero:true, ticks: { color: '#718096', stepSize: 1 }, grid: { color: '#DCEBFA' } } } }
    });

    // Feedback chart
    if (feedbackChart) feedbackChart.destroy();
    feedbackChart = new Chart(document.getElementById('feedbackChart'), {
      type: 'doughnut',
      data: { labels: ['ممتاز 😍', 'جيد 🙂', 'عادي 😐', 'لا 😞'],
              datasets: [{ data: [d.feedback.great||0, d.feedback.good||0, d.feedback.ok||0, d.feedback.bad||0],
                           backgroundColor: ['#123B70', '#1976D2', '#64B5F6', '#B8D8F8'], borderWidth: 0 }] },
      options: { responsive: true, maintainAspectRatio: false,
        plugins: { legend: { labels: { color: '#40566F', usePointStyle:true } } } }
    });

    // Feedback comments
    const fbBox = document.getElementById('feedback-comments');
    if (!d.fb_comments.length) {
      fbBox.innerHTML = '<p class="empty">لا توجد ملاحظات بعد</p>';
    } else {
      fbBox.innerHTML = d.fb_comments.map(c => {
        const emoji = {bad:'😞', ok:'😐', good:'🙂', great:'😍', 1:'😍', 2:'🙂', 3:'😐', 4:'😞'}[c.rating] || '⭐';
        const ts = (c.timestamp || '').replace('T', ' ').slice(0, 16);
        return '<div style="padding:11px 13px;margin:7px 0;background:#F5F9FF;border:1px solid #DCEBFA;border-radius:11px;">'
             + '<div style="color:#718096;font-size:11px;margin-bottom:4px;">' + emoji + ' ' + ts + '</div>'
             + '<div style="color:#40566F;font-size:13px;">' + (c.comment || '') + '</div></div>';
      }).join('');
    }

    document.getElementById('last-updated').textContent = 'آخر تحديث: ' + new Date().toLocaleTimeString('ar-SA')
      + ' | قاعدة البيانات: ' + (d.db_backend || '?');
  } catch(e) { console.error(e); }
}

loadAll();
setInterval(loadAll, 30000); // تحديث كل 30 ثانية
</script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(DASHBOARD_HTML)

@app.route('/api/stats')
def api_stats():
    db.init_db()
    stats = db.get_usage_stats(days=7)
    trends, _ = db.get_trends(days=7)

    # Top 8 symptoms
    top_symptoms = trends.most_common(8)

    # Urgency, lang, age from DB
    urgency = dict(db.fetchall("SELECT urgency, COUNT(*) FROM records GROUP BY urgency"))
    lang = dict(db.fetchall("SELECT lang, COUNT(*) FROM records GROUP BY lang"))
    ages = [row[0] for row in db.fetchall("SELECT age FROM records WHERE age IS NOT NULL")]

    age_groups = {"0-17": 0, "18-30": 0, "31-45": 0, "46-60": 0, "60+": 0}
    for a in ages:
        if a <= 17: age_groups["0-17"] += 1
        elif a <= 30: age_groups["18-30"] += 1
        elif a <= 45: age_groups["31-45"] += 1
        elif a <= 60: age_groups["46-60"] += 1
        else: age_groups["60+"] += 1

    feedback = db.feedback_counts()
    fb_comments = db.fetchall(
        "SELECT rating, comment, timestamp FROM feedback "
        "WHERE comment IS NOT NULL AND comment != '' ORDER BY timestamp DESC LIMIT 20"
    )

    return jsonify({
        "stats": stats,
        "symptoms": top_symptoms,
        "urgency": urgency,
        "lang": lang,
        "age_groups": list(age_groups.items()),
        "feedback": feedback,
        "fb_comments": [
            {"rating": r, "comment": c, "timestamp": t} for r, c, t in fb_comments
        ],
        "assistant_feedback": db.assistant_feedback_stats(),
        "db_backend": "PostgreSQL" if db.USE_POSTGRES else "SQLite",
    })

def run_dashboard():
    port = int(os.environ.get("PORT", 5000))
    try:
        from waitress import serve
        serve(app, host='0.0.0.0', port=port, threads=8)
    except ImportError:
        app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

if __name__ == '__main__':
    run_dashboard()
