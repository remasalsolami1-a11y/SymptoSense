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
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Segoe UI', Tahoma, sans-serif; background: #0d1b2a; color: #e0e0e0; }
  
  .header { background: #112240; padding: 20px 30px; display: flex; align-items: center; justify-content: space-between; border-bottom: 2px solid #00b4d8; }
  .header h1 { font-size: 22px; color: #fff; }
  .header h1 span { color: #00b4d8; }
  .live-badge { background: #00b4d8; color: #0d1b2a; padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: 700; animation: pulse 2s infinite; }
  @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.6; } }
  
  .container { max-width: 1200px; margin: 0 auto; padding: 24px 20px; }
  
  .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 28px; }
  .stat-card { background: #112240; border-radius: 14px; padding: 20px; border: 1px solid #1e3a5f; text-align: center; }
  .stat-card .number { font-size: 36px; font-weight: 700; color: #00b4d8; }
  .stat-card .label { font-size: 13px; color: #90caf9; margin-top: 6px; }
  .stat-card .sub { font-size: 11px; color: #546e7a; margin-top: 4px; }

  .charts-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 28px; }
  @media (max-width: 768px) { .charts-grid { grid-template-columns: 1fr; } }
  
  .chart-card { background: #112240; border-radius: 14px; padding: 20px; border: 1px solid #1e3a5f; }
  .chart-card h3 { font-size: 15px; color: #90caf9; margin-bottom: 16px; padding-bottom: 10px; border-bottom: 1px solid #1e3a5f; }
  .chart-wrap { position: relative; height: 260px; }

  .urgency-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 28px; }
  .urgency-card { background: #112240; border-radius: 12px; padding: 16px; text-align: center; border: 1px solid #1e3a5f; }
  .urgency-card.low { border-top: 3px solid #4caf50; }
  .urgency-card.medium { border-top: 3px solid #ff9800; }
  .urgency-card.high { border-top: 3px solid #f44336; }
  .urgency-card .num { font-size: 28px; font-weight: 700; }
  .urgency-card.low .num { color: #4caf50; }
  .urgency-card.medium .num { color: #ff9800; }
  .urgency-card.high .num { color: #f44336; }
  .urgency-card .lbl { font-size: 12px; color: #90caf9; margin-top: 4px; }

  .footer { text-align: center; padding: 20px; color: #37474f; font-size: 12px; }
  .refresh-btn { background: #1e3a5f; border: 1px solid #00b4d8; color: #00b4d8; padding: 8px 18px; border-radius: 8px; cursor: pointer; font-size: 13px; }
  .refresh-btn:hover { background: #00b4d8; color: #0d1b2a; }
  .last-updated { font-size: 11px; color: #546e7a; margin-top: 6px; }
</style>
</head>
<body>

<div class="header">
  <h1>Sympto<span>Sense</span> Dashboard</h1>
  <div style="display:flex;align-items:center;gap:12px;">
    <span class="live-badge">🟢 LIVE</span>
    <button class="refresh-btn" onclick="loadAll()">🔄 تحديث</button>
  </div>
</div>

<div class="container">

  <!-- إحصائيات عامة -->
  <div class="stats-grid" id="stats-grid">
    <div class="stat-card"><div class="number" id="total-visits">-</div><div class="label">إجمالي الزيارات</div><div class="sub">Total Visits</div></div>
    <div class="stat-card"><div class="number" id="unique-visitors">-</div><div class="label">مستخدمون فريدون</div><div class="sub">Unique Users</div></div>
    <div class="stat-card"><div class="number" id="total-sessions">-</div><div class="label">تحليلات مكتملة</div><div class="sub">Completed Sessions</div></div>
    <div class="stat-card"><div class="number" id="week-sessions">-</div><div class="label">آخر 7 أيام</div><div class="sub">Last 7 Days</div></div>
    <div class="stat-card"><div class="number" id="total-feedback">-</div><div class="label">التقييمات</div><div class="sub">Feedback</div></div>
  </div>

  <!-- مستويات الخطورة -->
  <div class="urgency-grid" id="urgency-grid">
    <div class="urgency-card low"><div class="num" id="urg-low">-</div><div class="lbl">🟢 بسيط</div></div>
    <div class="urgency-card medium"><div class="num" id="urg-med">-</div><div class="lbl">🟡 يحتاج موعد</div></div>
    <div class="urgency-card high"><div class="num" id="urg-high">-</div><div class="lbl">🔴 طوارئ</div></div>
  </div>

  <!-- الرسوم البيانية -->
  <div class="charts-grid">
    <div class="chart-card">
      <h3>📊 أكثر الأعراض انتشاراً (آخر 7 أيام)</h3>
      <div class="chart-wrap"><canvas id="symptomsChart"></canvas></div>
    </div>
    <div class="chart-card">
      <h3>🌐 توزيع اللغة</h3>
      <div class="chart-wrap"><canvas id="langChart"></canvas></div>
    </div>
    <div class="chart-card">
      <h3>📈 مستويات الخطورة</h3>
      <div class="chart-wrap"><canvas id="urgencyChart"></canvas></div>
    </div>
    <div class="chart-card">
      <h3>👥 توزيع الأعمار</h3>
      <div class="chart-wrap"><canvas id="ageChart"></canvas></div>
    </div>
    <div class="chart-card">
      <h3>💬 التقييمات</h3>
      <div class="chart-wrap"><canvas id="feedbackChart"></canvas></div>
    </div>
  </div>

  <!-- ملاحظات التقييم -->
  <div class="chart-card" style="margin-bottom:28px;">
    <h3>📝 ملاحظات المستخدمين على التقييم السلبي</h3>
    <div id="feedback-comments">
      <p style="color:#546e7a;">لا توجد ملاحظات بعد</p>
    </div>
  </div>

  <div class="last-updated" id="last-updated"></div>
</div>

<div class="footer">SymptoSense © 2026 — ريماس السلمي | للتوعية الصحية فقط</div>

<script>
let symptomsChart, langChart, urgencyChart, ageChart, feedbackChart;

async function loadAll() {
  try {
    const r = await fetch('/api/stats');
    const d = await r.json();
    
    // Stats
    document.getElementById('total-visits').textContent = d.stats.total_visits;
    document.getElementById('unique-visitors').textContent = d.stats.unique_visitors;
    document.getElementById('total-sessions').textContent = d.stats.total_sessions;
    document.getElementById('week-sessions').textContent = d.stats.sessions_this_period;
    const fbCount = (d.feedback.great||0) + (d.feedback.good||0) + (d.feedback.ok||0) + (d.feedback.bad||0);
    document.getElementById('total-feedback').textContent = fbCount;
    
    // Urgency
    document.getElementById('urg-low').textContent = d.urgency.low || 0;
    document.getElementById('urg-med').textContent = d.urgency.medium || 0;
    document.getElementById('urg-high').textContent = d.urgency.high || 0;
    
    // Symptoms chart
    const symLabels = d.symptoms.map(s => s[0]);
    const symData = d.symptoms.map(s => s[1]);
    if (symptomsChart) symptomsChart.destroy();
    symptomsChart = new Chart(document.getElementById('symptomsChart'), {
      type: 'bar',
      data: { labels: symLabels, datasets: [{ data: symData, backgroundColor: '#00b4d8', borderRadius: 6 }] },
      options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } },
        scales: { x: { ticks: { color: '#90caf9', font: { size: 11 } }, grid: { color: '#1e3a5f' } },
                   y: { ticks: { color: '#90caf9' }, grid: { color: '#1e3a5f' } } } }
    });
    
    // Language chart
    if (langChart) langChart.destroy();
    langChart = new Chart(document.getElementById('langChart'), {
      type: 'doughnut',
      data: { labels: ['العربية 🇸🇦', 'English 🇺🇸'],
              datasets: [{ data: [d.lang.ar || 0, d.lang.en || 0], backgroundColor: ['#00b4d8', '#1565c0'], borderWidth: 0 }] },
      options: { responsive: true, maintainAspectRatio: false,
        plugins: { legend: { labels: { color: '#90caf9' } } } }
    });
    
    // Urgency chart
    if (urgencyChart) urgencyChart.destroy();
    urgencyChart = new Chart(document.getElementById('urgencyChart'), {
      type: 'doughnut',
      data: { labels: ['بسيط 🟢', 'يحتاج موعد 🟡', 'طوارئ 🔴'],
              datasets: [{ data: [d.urgency.low||0, d.urgency.medium||0, d.urgency.high||0],
                           backgroundColor: ['#4caf50','#ff9800','#f44336'], borderWidth: 0 }] },
      options: { responsive: true, maintainAspectRatio: false,
        plugins: { legend: { labels: { color: '#90caf9' } } } }
    });

    // Age chart
    if (ageChart) ageChart.destroy();
    ageChart = new Chart(document.getElementById('ageChart'), {
      type: 'bar',
      data: { labels: d.age_groups.map(a => a[0]),
              datasets: [{ data: d.age_groups.map(a => a[1]), backgroundColor: '#1565c0', borderRadius: 6 }] },
      options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } },
        scales: { x: { ticks: { color: '#90caf9' }, grid: { color: '#1e3a5f' } },
                   y: { ticks: { color: '#90caf9' }, grid: { color: '#1e3a5f' } } } }
    });

    // Feedback chart
    if (feedbackChart) feedbackChart.destroy();
    feedbackChart = new Chart(document.getElementById('feedbackChart'), {
      type: 'doughnut',
      data: { labels: ['ممتاز 😍', 'جيد 🙂', 'عادي 😐', 'لا 😞'],
              datasets: [{ data: [d.feedback.great||0, d.feedback.good||0, d.feedback.ok||0, d.feedback.bad||0],
                           backgroundColor: ['#4caf50', '#00b4d8', '#ff9800', '#f44336'], borderWidth: 0 }] },
      options: { responsive: true, maintainAspectRatio: false,
        plugins: { legend: { labels: { color: '#90caf9' } } } }
    });

    // Feedback comments
    const fbBox = document.getElementById('feedback-comments');
    if (!d.fb_comments.length) {
      fbBox.innerHTML = '<p style="color:#546e7a;">لا توجد ملاحظات بعد</p>';
    } else {
      fbBox.innerHTML = d.fb_comments.map(c => {
        const emoji = {bad:'😞', ok:'😐', good:'🙂', great:'😍'}[c.rating] || '⭐';
        const ts = (c.timestamp || '').replace('T', ' ').slice(0, 16);
        return '<div style="padding:10px 12px;margin:6px 0;background:#0d1b2a;border:1px solid #1e3a5f;border-radius:8px;">'
             + '<div style="color:#90caf9;font-size:12px;margin-bottom:4px;">' + emoji + ' ' + ts + '</div>'
             + '<div style="color:#e0e0e0;font-size:14px;">' + (c.comment || '') + '</div></div>';
      }).join('');
    }

    document.getElementById('last-updated').textContent = 'آخر تحديث: ' + new Date().toLocaleTimeString('ar-SA');
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

    feedback = dict(db.fetchall("SELECT rating, COUNT(*) FROM feedback GROUP BY rating"))
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
