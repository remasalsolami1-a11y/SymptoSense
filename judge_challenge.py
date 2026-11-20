from __future__ import annotations

from html import escape

import analysis_core


ACTIONS = {
    "emergency": {
        "ar": "طوارئ الآن",
        "en": "Emergency now",
        "icon": "🚨",
    },
    "today": {
        "ar": "تقييم طبي اليوم",
        "en": "Medical review today",
        "icon": "🟠",
    },
    "soon": {
        "ar": "موعد قريب",
        "en": "Book a near-term appointment",
        "icon": "🟡",
    },
    "monitor": {
        "ar": "مراقبة ومتابعة",
        "en": "Monitor and follow up",
        "icon": "🟢",
    },
}


CASES = [
    {
        "id": "chest-breath",
        "title_ar": "ألم صدر شديد مع ضيق تنفس",
        "title_en": "Severe chest pain with shortness of breath",
        "story_ar": "شخص يصف ألمًا شديدًا في الصدر مع صعوبة واضحة في التنفس.",
        "story_en": "A person reports severe chest pain with clear difficulty breathing.",
        "symptoms": ["ألم صدر شديد", "ضيق التنفس"],
        "notes": "",
        "severity": 5,
        "duration": "منذ 20 دقيقة",
        "age": 48,
        "expected": "emergency",
    },
    {
        "id": "sudden-neuro",
        "title_ar": "ضعف مفاجئ بجهة واحدة",
        "title_en": "Sudden one-sided weakness",
        "story_ar": "بدأ فجأة ضعف في جهة واحدة مع صعوبة في الكلام.",
        "story_en": "Sudden one-sided weakness with difficulty speaking.",
        "symptoms": ["ضعف مفاجئ في جهة واحدة", "صعوبة في الكلام"],
        "notes": "",
        "severity": 4,
        "duration": "منذ 10 دقائق",
        "age": 61,
        "expected": "emergency",
    },
    {
        "id": "chest-alone",
        "title_ar": "ألم صدر بدون علامات خطر إضافية",
        "title_en": "Chest pain without additional red flags",
        "story_ar": "ألم في الصدر بدون ضيق تنفس أو إغماء أو دوار.",
        "story_en": "Chest pain without shortness of breath, fainting, or dizziness.",
        "symptoms": ["ألم في الصدر"],
        "notes": "لا يوجد ضيق تنفس ولا إغماء",
        "severity": 2,
        "duration": "منذ ساعة",
        "age": 34,
        "expected": "today",
    },
    {
        "id": "persistent-moderate",
        "title_ar": "أعراض متوسطة مستمرة",
        "title_en": "Persistent moderate symptoms",
        "story_ar": "صداع وغثيان بشدة متوسطة مستمرين منذ عدة أيام، بدون علامات خطر.",
        "story_en": "Moderate headache and nausea for several days, without red flags.",
        "symptoms": ["صداع", "غثيان"],
        "notes": "لا توجد علامات خطر",
        "severity": 3,
        "duration": "5 أيام",
        "age": 24,
        "expected": "soon",
    },
    {
        "id": "mild-joint",
        "title_ar": "طقطقة ركبة بدون ألم",
        "title_en": "Knee clicking without pain",
        "story_ar": "طقطقة في الركبة بدون ألم أو تورم أو إصابة حديثة.",
        "story_en": "Knee clicking without pain, swelling, or recent injury.",
        "symptoms": ["طقطقة الركبة"],
        "notes": "بدون ألم أو تورم أو إصابة",
        "severity": 1,
        "duration": "3 أيام",
        "age": 22,
        "expected": "monitor",
    },
]


def public_cases(lang: str = "ar") -> list[dict]:
    ar = lang != "en"
    return [
        {
            "id": c["id"],
            "title": c["title_ar"] if ar else c["title_en"],
            "story": c["story_ar"] if ar else c["story_en"],
        }
        for c in CASES
    ]


def run_case(case_id: str, lang: str = "ar") -> dict:
    case = next((c for c in CASES if c["id"] == case_id), None)
    if not case:
        raise ValueError("unknown_case")
    lang = "en" if lang == "en" else "ar"
    payload = {
        "symptoms": list(case["symptoms"]),
        "notes": case["notes"],
        "severity": case["severity"],
        "duration": case["duration"],
        "age": case["age"],
    }
    triage = analysis_core._triage(payload, lang)
    actual = str(triage.get("level") or "monitor")
    expected = str(case["expected"])
    flags = analysis_core.detect_red_flags(payload["symptoms"], payload["notes"], lang)
    return {
        "case_id": case["id"],
        "engine_action": actual,
        "engine_label": ACTIONS.get(actual, ACTIONS["monitor"])[lang],
        "expected_action": expected,
        "expected_label": ACTIONS.get(expected, ACTIONS["monitor"])[lang],
        "passed": actual == expected,
        "red_flags": flags[:4],
        "reason": str(triage.get("reason") or ""),
        "synthetic": True,
        "clinical_validation": False,
    }


def render_page(*, page, lang: str):
    ar = lang != "en"
    bi = lambda a, e: a if ar else e
    cards = []
    for index, case in enumerate(public_cases(lang), start=1):
        cards.append(
            f'''<article class="jc-case" data-case="{escape(case['id'])}">
              <div class="jc-case-top"><span class="jc-num">{index:02d}</span><span class="jc-status">{bi('بانتظار توقع الحكم','Waiting for judge')}</span></div>
              <h3>{escape(case['title'])}</h3><p>{escape(case['story'])}</p>
              <div class="jc-options" role="group" aria-label="{bi('توقع القرار','Predict the action')}">
                {''.join(f'<button type="button" data-guess="{key}"><span>{meta["icon"]}</span>{escape(meta["ar" if ar else "en"])}</button>' for key,meta in ACTIONS.items())}
              </div>
              <button class="jc-run" type="button" disabled>{bi('شغّل محرك SymptoSense','Run SymptoSense engine')}</button>
              <div class="jc-result" hidden></div>
            </article>'''
        )
    body = r'''
    <main class="jc-page">
      <section class="jc-hero"><div><span class="jc-kicker">JUDGE CHALLENGE · LIVE ENGINE</span><h1>__TITLE__</h1><p>__SUB__</p><div class="jc-badges"><span>🛡️ Real safety engine</span><span>🧪 Synthetic cases</span><span>🔒 Admin only</span><span>🚫 Not clinical validation</span></div></div><div class="jc-score"><small>__SCORE__</small><strong id="jcScore">0 / 0</strong><span id="jcEngineScore">Engine: 0 / 0</span></div></section>
      <section class="jc-instructions"><b>__HOW__</b><span>1. __H1__</span><span>2. __H2__</span><span>3. __H3__</span></section>
      <section class="jc-grid">__CASES__</section>
      <section class="jc-final"><div><span>🏁</span><h2>__FINAL_H__</h2><p>__FINAL_P__</p></div><button type="button" id="jcReset">__RESET__</button></section>
    </main>
    <script>
    (function(){
      const cards=[...document.querySelectorAll('.jc-case')]; let answered=0,judgeCorrect=0,enginePassed=0;
      const labels={emergency:'__LE__',today:'__LT__',soon:'__LS__',monitor:'__LM__'};
      function updateScore(){document.getElementById('jcScore').textContent=judgeCorrect+' / '+answered;document.getElementById('jcEngineScore').textContent='Engine: '+enginePassed+' / '+answered;}
      cards.forEach(card=>{
        let guess=null,done=false; const opts=[...card.querySelectorAll('[data-guess]')],run=card.querySelector('.jc-run'),result=card.querySelector('.jc-result'),status=card.querySelector('.jc-status');
        opts.forEach(btn=>btn.addEventListener('click',()=>{if(done)return;guess=btn.dataset.guess;opts.forEach(x=>x.classList.toggle('on',x===btn));run.disabled=false;status.textContent='__READY__';}));
        run.addEventListener('click',async()=>{if(done||!guess)return;run.disabled=true;run.textContent='__RUNNING__';try{const r=await fetch('/api/admin/judge-challenge/run',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':document.querySelector('meta[name="admin-csrf"]').content},body:JSON.stringify({case_id:card.dataset.case,lang:document.documentElement.lang==='en'?'en':'ar'})});const d=await r.json();if(!r.ok||!d.ok)throw new Error('run_failed');done=true;answered+=1;if(guess===d.result.expected_action)judgeCorrect+=1;if(d.result.passed)enginePassed+=1;status.textContent=d.result.passed?'✓ ENGINE PASS':'⚠ ENGINE CHECK';status.classList.add(d.result.passed?'pass':'fail');const guessOk=guess===d.result.expected_action;result.hidden=false;result.innerHTML='<div class="jc-result-grid"><div><small>__YOUR__</small><b class="'+(guessOk?'good':'warn')+'">'+labels[guess]+'</b></div><div><small>__EXPECTED__</small><b>'+d.result.expected_label+'</b></div><div><small>__ENGINE__</small><b class="'+(d.result.passed?'good':'warn')+'">'+d.result.engine_label+'</b></div></div><div class="jc-trace"><b>Safety trace</b><p>'+esc(d.result.reason||'—')+'</p>'+(d.result.red_flags&&d.result.red_flags.length?'<div class="jc-flags">'+d.result.red_flags.map(x=>'<span>🚩 '+esc(x)+'</span>').join('')+'</div>':'<span class="jc-no-flag">✓ __NOFLAG__</span>')+'<small>__SYNTH__</small></div>';run.textContent='__DONE__';opts.forEach(x=>x.disabled=true);updateScore();}catch(e){run.disabled=false;run.textContent='__RETRY__';status.textContent='__ERROR__';}});
      });
      document.getElementById('jcReset').addEventListener('click',()=>location.reload());
      function esc(v){const d=document.createElement('div');d.textContent=String(v==null?'':v);return d.innerHTML;}
    })();
    </script>
    '''
    repl = {
        "__TITLE__": bi("تحدَّ SymptoSense بنفسك", "Challenge SymptoSense yourself"),
        "__SUB__": bi("توقّع ماذا يجب أن يفعل النظام، ثم شغّل نفس محرك السلامة المستخدم في المشروع وشاهد القرار الفعلي أمامك. كل الحالات صناعية ولا تمثل مرضى حقيقيين.", "Predict what the system should do, then run the same safety engine used by the project and see the real decision live. Every case is synthetic and represents no real patient."),
        "__SCORE__": bi("نتيجة الحكم", "Judge score"),
        "__HOW__": bi("كيف تعمل التجربة؟", "How it works"),
        "__H1__": bi("اقرأ الحالة", "Read the case"), "__H2__": bi("اختر توقعك", "Make your prediction"), "__H3__": bi("شغّل المحرك وقارن", "Run the engine and compare"),
        "__FINAL_H__": bi("أنت الآن اختبرت طبقة السلامة بنفسك", "You have now tested the safety layer yourself"),
        "__FINAL_P__": bi("النتيجة هنا تحقق هندسي على سيناريوهات صناعية وليست قياسًا للدقة الطبية أو تحققًا سريريًا.", "This is engineering verification on synthetic scenarios, not a measure of medical accuracy or clinical validation."),
        "__RESET__": bi("إعادة التحدي", "Restart challenge"),
        "__LE__": bi("طوارئ الآن", "Emergency now"), "__LT__": bi("تقييم طبي اليوم", "Medical review today"), "__LS__": bi("موعد قريب", "Near-term appointment"), "__LM__": bi("مراقبة ومتابعة", "Monitor and follow up"),
        "__READY__": bi("جاهز للتشغيل", "Ready to run"), "__RUNNING__": bi("جارٍ تشغيل المحرك…", "Running engine…"), "__YOUR__": bi("توقعك", "Your prediction"), "__EXPECTED__": bi("السلوك المتوقع", "Expected behavior"), "__ENGINE__": bi("قرار المحرك", "Engine decision"), "__NOFLAG__": bi("لا توجد علامة خطر صريحة في هذه الحالة", "No explicit red flag in this case"), "__SYNTH__": bi("سيناريو صناعي · لا يمثل تشخيصًا أو مريضًا حقيقيًا", "Synthetic scenario · not a diagnosis or a real patient"), "__DONE__": bi("تم التشغيل", "Completed"), "__RETRY__": bi("إعادة المحاولة", "Retry"), "__ERROR__": bi("تعذر تشغيل الجولة", "Unable to run round"),
        "__CASES__": "".join(cards),
    }
    for key, value in repl.items():
        body = body.replace(key, str(value))
    css = r'''
    .jc-page{width:min(1160px,100%);margin:auto;display:grid;gap:18px}.jc-hero{display:flex;justify-content:space-between;gap:22px;align-items:center;padding:clamp(26px,5vw,46px);border-radius:28px;color:#fff;background:linear-gradient(135deg,#071C31,#0C3156 58%,#0B5663);box-shadow:0 24px 65px rgba(7,28,49,.2)}.jc-kicker{font-size:10px;font-weight:900;letter-spacing:.16em;color:#91D9F3}.jc-hero h1{margin:10px 0;color:#fff;font-size:clamp(32px,5vw,55px)}.jc-hero p{max-width:720px;color:#C5D7E5;line-height:1.9}.jc-badges{display:flex;gap:7px;flex-wrap:wrap;margin-top:16px}.jc-badges span{padding:6px 9px;border-radius:999px;background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.13);font-size:9.5px}.jc-score{min-width:185px;padding:22px;border-radius:22px;background:rgba(255,255,255,.09);border:1px solid rgba(255,255,255,.16);text-align:center}.jc-score small,.jc-score span{display:block;color:#BFD5E4}.jc-score strong{display:block;font-size:34px;margin:4px 0}.jc-instructions{display:flex;gap:10px;align-items:center;flex-wrap:wrap;padding:13px 16px;border:1px solid #DCE8F0;border-radius:16px;background:#fff}.jc-instructions b{color:#123B70}.jc-instructions span{font-size:11px;color:#566a7d}.jc-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:13px}.jc-case{padding:20px;border:1px solid #DCE8F0;border-radius:22px;background:#fff;box-shadow:0 7px 22px rgba(22,59,92,.045)}.jc-case-top{display:flex;align-items:center;justify-content:space-between;gap:12px}.jc-num{width:34px;height:34px;display:grid;place-items:center;border-radius:11px;background:#EAF5FC;color:#1f6fae;font-size:11px;font-weight:900}.jc-status{padding:5px 8px;border-radius:999px;background:#F3F7FA;color:#566a7d;font-size:9px;font-weight:900}.jc-status.pass{background:#ECFDF5;color:#166534}.jc-status.fail{background:#FFF7ED;color:#9A5410}.jc-case h3{color:#163B5C;margin:14px 0 7px}.jc-case>p{color:#566a7d;line-height:1.75;min-height:45px}.jc-options{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px;margin:15px 0}.jc-options button{min-height:48px;border:1px solid #D5E5EF;border-radius:13px;background:#F9FCFE;color:#35536B;font:inherit;font-size:11px;font-weight:850;cursor:pointer}.jc-options button span{margin-inline-end:5px}.jc-options button.on{background:#EAF5FC;border-color:#1f6fae;color:#155D8B;box-shadow:0 0 0 2px rgba(40,127,193,.08)}.jc-run{width:100%;min-height:48px;border:0;border-radius:14px;background:#1f6fae;color:#fff;font:inherit;font-weight:900;cursor:pointer}.jc-run:disabled{opacity:.45;cursor:not-allowed}.jc-result{margin-top:13px;padding:14px;border-radius:16px;background:#F8FBFD;border:1px solid #E0EBF2}.jc-result-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:7px}.jc-result-grid>div{padding:10px;border-radius:12px;background:#fff;border:1px solid #E3EDF3}.jc-result-grid small{display:block;color:#718899;font-size:9px}.jc-result-grid b{display:block;margin-top:4px;color:#29485F;font-size:11px}.jc-result-grid b.good{color:#166534}.jc-result-grid b.warn{color:#9A5410}.jc-trace{margin-top:10px}.jc-trace>b{color:#123B70;font-size:11px}.jc-trace p{white-space:pre-line;color:#566a7d;font-size:10.5px;line-height:1.7}.jc-flags{display:flex;gap:5px;flex-wrap:wrap}.jc-flags span{padding:5px 7px;border-radius:999px;background:#FFF1F2;color:#9F1239;font-size:9px}.jc-no-flag{display:inline-block;color:#166534;font-size:9.5px}.jc-trace>small{display:block;margin-top:9px;color:#8293A1;font-size:8.5px}.jc-final{display:flex;justify-content:space-between;align-items:center;gap:18px;padding:22px;border-radius:22px;background:#F7FBFE;border:1px solid #DCE8F0}.jc-final>div{display:grid;grid-template-columns:auto 1fr;column-gap:10px}.jc-final>div>span{grid-row:1/3;font-size:30px}.jc-final h2{margin:0;color:#163B5C;font-size:18px}.jc-final p{margin:4px 0 0;color:#566a7d}.jc-final button{min-height:46px;padding:0 16px;border:1px solid #BFD9EA;border-radius:13px;background:#fff;color:#155D8B;font:inherit;font-weight:900;cursor:pointer}@media(max-width:800px){.jc-hero{align-items:flex-start;flex-direction:column}.jc-score{width:100%}.jc-grid{grid-template-columns:1fr}}@media(max-width:520px){.jc-hero,.jc-case{padding:18px 14px;border-radius:20px}.jc-options,.jc-result-grid{grid-template-columns:1fr}.jc-final{align-items:flex-start;flex-direction:column}.jc-final button{width:100%}}@media(prefers-reduced-motion:reduce){.jc-page *{animation:none!important;transition:none!important}}
    '''
    return page(bi("تحدي الحكم — SymptoSense", "Judge Challenge — SymptoSense"), body, extra_css=css)
