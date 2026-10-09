# حزمة المراجعة السريرية — SymptoSense

> **مولَّدة تلقائيًا من الكود** بـ `python tools/clinical_packet.py` — لا تعدّلها يدويًا. تصف **ما يفعله المنتج الآن** ولا تقترح قيمًا طبية.
> لا يوجد أي اعتماد حتى الآن. الاعتماد يُسجَّل فقط ببيانات المراجِع نفسه:
> `python tools/signoff.py approve <area> --reviewer "الاسم" --credentials "الترخيص" --date YYYY-MM-DD --notes "..."`
> كل ملف CSV في `clinical_review/` فيه عمودان فارغان للقرار والملاحظات.

## حالة المجالات
| المجال | الاسم | الحالة | ملف المراجعة |
|---|---|---|---|
| emergency_rules | قواعد الطوارئ وشاشة التوقف | … بانتظار الاعتماد | `clinical_review/emergency_rules.csv` |
| redflag_screens | أسئلة فحص علامات الخطر | … بانتظار الاعتماد | `clinical_review/redflag_screens.csv` |
| search_new_v251 | مواضيع البحث الجديدة (الحساسية، عرق النسا، الهلع، انخفاض الضغط، زغللة، اكتئاب) | … بانتظار الاعتماد | `clinical_review/search_new_v251.csv` |
| search_base | مكتبة مواضيع البحث | … بانتظار الاعتماد | `clinical_review/search_base.csv` |
| lab_cards | بطاقات التحاليل | … بانتظار الاعتماد | `clinical_review/lab_cards.csv` |
| library_core | مكتبة الأعراض والأمراض | … بانتظار الاعتماد | `clinical_review/library_core.csv` |
| vitals_thresholds | حدود تنبيهات القياسات المنزلية (ضغط، سكر، حرارة، نبض، SpO₂) | … بانتظار الاعتماد | `clinical_review/vitals_thresholds.csv` |
| medication_context | ربط الأدوية بالأعراض والحالات (من نصوص الكتالوج) | … بانتظار الاعتماد | القسم 8 |
| clinical_reasoning | منطق الصورة السريرية وقواعد رفع مستوى المتابعة | … بانتظار الاعتماد | `clinical_review/clinical_reasoning.csv` |

## 1) emergency_rules — قواعد الطوارئ وشاشة التوقف
مجموعة ذهبية من **293** عبارة (لهجات وأخطاء إملائية وضوابط سلبية). الفرق بين المتوقع والفعلي: **0**. القواعد نفسها تعبيرات نمطية في `emergency_lexicon.py` و`safety_engine.py`؛ المراجعة الفعلية: هل **المتوقع** في كل صف صحيح سريريًا؟ وما العبارات المفقودة؟
الملف: `clinical_review/emergency_rules.csv`

## 2) redflag_screens — أسئلة علامات الخطر
**19** سؤال؛ «نعم» على مستوى emergency توقف التحليل، وعلى today ترفع النصيحة إلى «راجع طبيبًا اليوم». حد أقصى 4 أسئلة لكل تحليل.
| # | المعرّف | المستوى | السؤال | قرار الطبيب |
|---|---|---|---|---|
| 1 | cp_radiating | emergency | هل ينتشر ألم الصدر إلى الذراع أو الفك أو الظهر، أو يصاحبه عرق بارد أو ضيق نفس؟ |  |
| 2 | cp_pressure | emergency | هل هو ضغط أو عصر شديد في الصدر مستمر أكثر من 15 دقيقة؟ |  |
| 3 | sob_speech | emergency | هل تعجز عن إكمال جملة كاملة بسبب ضيق النفس، أو يميل لون الشفاه إلى الأزرق؟ |  |
| 4 | sob_legswell | today | هل يصاحب ضيق النفس تورم في الساقين أو ألم في إحداهما؟ |  |
| 5 | ha_thunder | emergency | هل بدأ الصداع فجأة وبأشد درجة (كأسوأ صداع في حياتك)؟ |  |
| 6 | ha_neck_fever | emergency | هل يصاحب الصداع تيبس في الرقبة مع حرارة، أو طفح لا يختفي بالضغط؟ |  |
| 7 | ha_neuro | emergency | هل ظهر مع العرض ضعف في جهة واحدة أو التواء في الوجه أو صعوبة في الكلام أو فقدان مفاجئ للرؤية؟ |  |
| 8 | ha_head_injury | today | هل بدأ الصداع بعد ضربة على الرأس؟ |  |
| 9 | ab_rigid | emergency | هل البطن قاسٍ ومؤلم جدًا عند اللمس بحيث لا تستطيع الحركة أو الاستقامة؟ |  |
| 10 | ab_blood | emergency | هل هناك قيء فيه دم أو براز أسود لزج أو دم غزير في البراز؟ |  |
| 11 | ab_fever | today | هل يصاحب ألم البطن حرارة أو قيء متكرر لا يتوقف؟ |  |
| 12 | fv_rash_neck | emergency | هل تصاحب الحرارة رقبة متيبسة أو طفح لا يختفي بالضغط عليه أو ارتباك في الوعي؟ |  |
| 13 | fv_long | today | هل استمرت الحرارة أكثر من 3 أيام أو تتكرر الارتفاعات فوق 39؟ |  |
| 14 | dz_faint | emergency | هل أغمي عليك أو شعرت أنك ستفقد الوعي مع ألم في الصدر أو خفقان شديد؟ |  |
| 15 | bk_cauda | emergency | هل يصاحب ألم الظهر تنميل بين الساقين أو فقدان التحكم بالبول أو البراز أو ضعف في الساقين؟ |  |
| 16 | vm_dehyd | today | هل مرّت 8 ساعات أو أكثر دون تبول، أو لا تستطيع شرب السوائل دون قيء؟ |  |
| 17 | ur_flank | today | هل يصاحب حرقان البول حرارة أو ألم في الجنب أو الظهر؟ |  |
| 18 | ey_sudden | emergency | هل فقدت الرؤية فجأة أو ظهرت ومضات وستارة سوداء في النظر؟ |  |
| 19 | bl_heavy | emergency | هل النزيف غزير ولا يتوقف بالضغط المباشر عشر دقائق؟ |  |

## 3) vitals_thresholds — حدود تنبيهات القياسات المنزلية
الجداول **مستخرجة بتشغيل `vitals.assess` فعليًا** (السلوك الحالي)، وليست مقترحات. المطلوب: هل كل حد ومستوى ورسالة مقبول؟
| النوع | السياق | المدى | المستوى |
|---|---|---|---|
| glucose | random | 20 – 53 mg/dL | emergency |
| glucose | random | 54 – 69 mg/dL | attention |
| glucose | random | 70 – 199 mg/dL | ok |
| glucose | random | 200 – 300 mg/dL | attention |
| glucose | random | 301 – 800 mg/dL | urgent |
| glucose | fasting | 20 – 53 mg/dL | emergency |
| glucose | fasting | 54 – 69 mg/dL | attention |
| glucose | fasting | 70 – 125 mg/dL | ok |
| glucose | fasting | 126 – 300 mg/dL | attention |
| glucose | fasting | 301 – 800 mg/dL | urgent |
| glucose | after_meal | 20 – 53 mg/dL | emergency |
| glucose | after_meal | 54 – 69 mg/dL | attention |
| glucose | after_meal | 70 – 199 mg/dL | ok |
| glucose | after_meal | 200 – 300 mg/dL | attention |
| glucose | after_meal | 301 – 800 mg/dL | urgent |
| temp |  | 33 – 34.9 °C | urgent |
| temp |  | 35 – 37.9 °C | ok |
| temp |  | 38 – 39.9 °C | attention |
| temp |  | 40 – 43 °C | urgent |
| pulse |  | 20 – 39 bpm | urgent |
| pulse |  | 40 – 49 bpm | attention |
| pulse |  | 50 – 100 bpm | ok |
| pulse |  | 101 – 130 bpm | attention |
| pulse |  | 131 – 250 bpm | urgent |
| spo2 |  | 50 – 89 % | emergency |
| spo2 |  | 90 – 94 % | urgent |
| spo2 |  | 95 – 100 % | ok |
| bp (systolic, diastolic=70) |  | 60 – 89 mmHg systolic | attention |
| bp (systolic, diastolic=70) |  | 90 – 139 mmHg systolic | ok |
| bp (systolic, diastolic=70) |  | 140 – 179 mmHg systolic | attention |
| bp (systolic, diastolic=70) |  | 180 – 260 mmHg systolic | urgent |
| bp (diastolic, systolic=110) |  | 30 – 59 mmHg diastolic | attention |
| bp (diastolic, systolic=110) |  | 60 – 89 mmHg diastolic | ok |
| bp (diastolic, systolic=110) |  | 90 – 119 mmHg diastolic | attention |
| bp (diastolic, systolic=110) |  | 120 – 160 mmHg diastolic | urgent |

**نصوص الرسائل** (AR/EN) لكل نوع في `vitals.assess` — راجعها في `vitals.py` (الدالة `assess`)؛ تتضمن تعليمات (إسعاف 997، سكر سريع المفعول، إعادة القياس). تأكد من سلامة كل تعليمة.

## 4) clinical_reasoning — منطق الصورة السريرية ورفع المستوى
القواعد في `clinical_reasoning.py` (تُرفع المستويات ولا تُخفض أبدًا):
- المستويات بالترتيب: monitor → soon → today → emergency.
- زيادة في الشدة أو عَرَض جديد أو دواء جديد أو تحليل أسوأ ⇒ رفع خطوة واحدة (من monitor/soon فقط).
- تنبيه قياس منزلي «urgent» خلال 24 ساعة ⇒ today كحد أدنى.
- تنبيه قياس منزلي «emergency» ⇒ emergency دائمًا ولا يُخفَّف.

حالات الانحدار الثابتة (المستوى الحالي للمراجعة):
| الحالة | الأعراض | المدخلات | المستوى الحالي | مسار الطوارئ | قرار الطبيب |
|---|---|---|---|---|---|
| knee_click_no_pain | طقطقة الركبة | {"notes": "بدون ألم"} | monitor | لا |  |
| mild_headache | صداع | {} | monitor | لا |  |
| mild_cough | كحة | {} | monitor | لا |  |
| period_nausea | غثيان | {"notes": "مع بداية الدورة الشهرية"} | monitor | لا |  |
| sore_throat | ألم الحلق | {} | monitor | لا |  |
| fainting | إغماء | {"severity": "4"} | emergency | نعم |  |
| chest_pain_severe | ألم في الصدر | {"severity": "5", "notes": "ألم شديد ينتشر للذراع مع تعرق"} | emergency | نعم |  |
| breathing_difficulty | صعوبة في التنفس | {"severity": "5"} | emergency | نعم |  |
| breathing_difficulty_4of5 | صعوبة في التنفس | {"severity": "4"} | today | لا |  |
| sudden_weakness_speech | ضعف مفاجئ في جانب واحد | {"notes": "صعوبة في الكلام"} | emergency | نعم |  |
| suicidal_note | حزن | {"notes": "أفكر أنهي حياتي"} | emergency | نعم |  |
| child_high_fever | حمى | {"age": "1", "severity": "4"} | today | لا |  |
| english_chest_pain | chest pain | {"severity": "5", "notes": "crushing pain, sweating"} | emergency | نعم |  |

تطابق اللقطة المعتمدة مع السلوك الحالي: **نعم**.

> **قرار مفتوح (من نسخة سابقة):** «صعوبة التنفس + شدة 5/5» تُصنَّف طوارئ تعديلًا مؤقتًا من مالك المنتج، و4/5 ⇒ اليوم. يحتاج قرار الطبيب.

## 5) lab_cards — بطاقات التحاليل
**93** مؤشرًا. النطاقات الظاهرة مرجع افتراضي؛ التطبيق يعتمد نطاق المختبر المطبوع في التقرير عند وجوده. حدود الخطر المبرمجة:
| المؤشر | قاعدة الخطر |
|---|---|
| هيموغلوبين | emergency lt 5; urgent lt 7 |
| كريات بيضاء | urgent gt 30; urgent lt 1 |
| الصفائح | emergency lt 10; urgent lt 20 |
وحدات SI (nmol/L و pmol/L) تُقرأ وتُوسَم لكنها تبقى **unclassified** حتى تُحدَّد نطاقات مرجعية معتمدة.

## 6) library_core — مكتبة الأعراض والأمراض
158 مرضًا، 290 عرضًا، 23 قاعدة علامات خطر (نصوص عربية في CSV؛ الإنجليزية في قاعدة المعرفة). الملف: `clinical_review/library_core.csv`.

## 7) search_base و search_new_v251 — مواضيع البحث
6 موضوعًا جديدًا (V251) و143 أساسيًا، لكل موضوع مصادر ملحقة. ملفان: `search_new_v251.csv` و`search_base.csv` (العمود `sources` يسهّل التحقق من أن النص يطابق المصدر).

## 8) medication_context — ربط الأدوية بالأعراض والحالات
لا توجد ادعاءات طبية مكتوبة هنا: يُنتَج الربط فقط إذا كان الدواء في كتالوج الأدوية الموثَّق **و**نص تحذيرات الكتالوج نفسه يذكر الفئة. المطلوب من **صيدلاني/طبيب**: مراجعة قوائم الكلمات التي تُطابَق بها الفئات ونافذة «بدأ حديثًا».
| النوع | الفئة | الاسم | كلمات المستخدم | كلمات نص الكتالوج | قرار |
|---|---|---|---|---|---|
| symptom | gi | الأعراض الهضمية | غثيان، قيء، استفراغ، اسهال، إسهال، ألم بطن، الم بطن، ألم المعدة، إمساك، امساك، حرقة، nausea، vomit، diarrhea، stomach، abdominal | هضمي، معدة، غثيان، إسهال، اسهال، قيء، gastro، stomach، nausea، diarrhea، vomit |  |
| symptom | bleeding | النزف | نزيف، كدمات، كدمة، bleeding، bruis | نزيف، bleeding |  |
| symptom | rash | الطفح والحساسية | طفح، حكة، تورم الوجه، rash، itch، hives | طفح، حساسية، rash، allerg |  |
| condition | kidney | الكلى | كلى، كلية، kidney، renal | كلى، كلية، kidney، renal |  |
| condition | liver | الكبد | كبد، liver، hepatic | كبد، liver، hepatic |  |
| condition | pregnancy | الحمل | حمل، حامل، pregnan | حمل، pregnan |  |
| condition | asthma | الربو | ربو، asthma | ربو، asthma |  |
| condition | heart | القلب | قلب، heart، cardiac | قلب، heart، cardiac |  |

نافذة «دواء بدأ حديثًا»: **21 يومًا**.

> **لا تُكتب تداخلات دوائية أو شدّتها من الذاكرة.** مصدرها الوحيد كتالوج مرخّص يراجعه صيدلاني. انظر `MEDICAL_REVIEW_NEEDED.md` للبنود المفتوحة.
