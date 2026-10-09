"""Independent research-validation workspace for SymptoSense.

The workspace is deliberately separated from live user health records. It ships
with a 180-case *starter benchmark* that is NOT counted as validation evidence
until an independent reviewer marks each case as verified and records a source.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

import db
import research_study
import release_candidate

PH = db.PH
_SCHEMA_READY = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _serial() -> str:
    return "SERIAL PRIMARY KEY" if db.USE_POSTGRES else "INTEGER PRIMARY KEY AUTOINCREMENT"


def _cols(c, table: str) -> set[str]:
    if db.USE_POSTGRES:
        c.execute("SELECT column_name FROM information_schema.columns WHERE table_name=%s", (table,))
        return {r[0] for r in c.fetchall()}
    c.execute(f"PRAGMA table_info({table})")
    return {r[1] for r in c.fetchall()}


# These are workflow templates, not clinician-validated ground truth. Their
# purpose is to give the research workspace a balanced set that can be reviewed
# independently. Metrics exclude them until reference_verified=1.
_STARTER = [
    # High / urgent (20)
    ("BENCH-H01", "Severe crushing chest pain with sweating and shortness of breath.", "high", "Acute coronary syndrome / emergency chest pain", "cardiovascular"),
    ("BENCH-H02", "Sudden weakness and numbness on one side with new speech difficulty.", "high", "Possible stroke", "neurologic"),
    ("BENCH-H03", "Sudden loss of vision in one eye.", "high", "Acute vision loss", "eye"),
    ("BENCH-H04", "Severe difficulty breathing at rest with bluish lips.", "high", "Severe respiratory distress", "respiratory"),
    ("BENCH-H05", "Unresponsive person who cannot be awakened normally.", "high", "Loss of consciousness", "neurologic"),
    ("BENCH-H06", "Generalized seizure lasting longer than five minutes.", "high", "Prolonged seizure", "neurologic"),
    ("BENCH-H07", "Rapid swelling of lips and tongue with breathing difficulty after food exposure.", "high", "Possible anaphylaxis", "allergy"),
    ("BENCH-H08", "Vomiting blood with dizziness and weakness.", "high", "Possible upper GI bleeding", "gastrointestinal"),
    ("BENCH-H09", "Black tarry stool with faintness.", "high", "Possible gastrointestinal bleeding", "gastrointestinal"),
    ("BENCH-H10", "Head injury followed by repeated vomiting and increasing drowsiness.", "high", "Potential serious head injury", "injury"),
    ("BENCH-H11", "Very severe sudden headache described as the worst headache ever.", "high", "Thunderclap headache", "neurologic"),
    ("BENCH-H12", "Severe abdominal pain with a rigid abdomen and persistent vomiting.", "high", "Acute abdomen", "gastrointestinal"),
    ("BENCH-H13", "High fever with stiff neck, confusion, and severe headache.", "high", "Possible meningitis / sepsis", "infection"),
    ("BENCH-H14", "New severe chest pain after a long flight with breathlessness and coughing blood.", "high", "Possible pulmonary embolism", "respiratory"),
    ("BENCH-H15", "Sudden severe testicular pain with swelling.", "high", "Possible testicular torsion", "genitourinary"),
    ("BENCH-H16", "Heavy vaginal bleeding with fainting or severe weakness.", "high", "Severe acute bleeding", "gynecologic"),
    ("BENCH-H17", "Diabetic person with confusion, deep rapid breathing, and repeated vomiting.", "high", "Possible diabetic emergency", "metabolic"),
    ("BENCH-H18", "Severe asthma symptoms not improving with usual reliever medicine.", "high", "Severe asthma exacerbation", "respiratory"),
    ("BENCH-H19", "Sudden facial droop with arm weakness even if symptoms begin to improve.", "high", "Possible TIA / stroke", "neurologic"),
    ("BENCH-H20", "Severe allergic reaction with widespread hives, wheeze, and dizziness.", "high", "Possible anaphylaxis", "allergy"),
    # Medium / needs medical review (20)
    ("BENCH-M01", "Fever lasting four days with worsening fatigue but no emergency red flags.", "medium", "Persistent fever requiring review", "infection"),
    ("BENCH-M02", "Cough lasting more than three weeks without severe breathing difficulty.", "medium", "Persistent cough", "respiratory"),
    ("BENCH-M03", "Burning urination with fever and pain in the side or back.", "medium", "Possible upper urinary infection", "genitourinary"),
    ("BENCH-M04", "New recurrent headaches increasing in frequency over several weeks.", "medium", "Recurrent/worsening headache", "neurologic"),
    ("BENCH-M05", "Persistent abdominal pain for several days with reduced appetite.", "medium", "Persistent abdominal pain", "gastrointestinal"),
    ("BENCH-M06", "Red painful eye with light sensitivity but no sudden vision loss.", "medium", "Painful red eye", "eye"),
    ("BENCH-M07", "Unexplained weight loss over several weeks.", "medium", "Unintentional weight loss", "general"),
    ("BENCH-M08", "New ankle swelling on both sides persisting for a week.", "medium", "Persistent peripheral edema", "cardiovascular"),
    ("BENCH-M09", "Palpitations occurring repeatedly with light-headedness but no fainting.", "medium", "Recurrent palpitations", "cardiovascular"),
    ("BENCH-M10", "Diarrhea lasting five days with signs of mild dehydration.", "medium", "Persistent diarrhea/dehydration", "gastrointestinal"),
    ("BENCH-M11", "Constipation lasting more than two weeks with abdominal discomfort.", "medium", "Persistent constipation", "gastrointestinal"),
    ("BENCH-M12", "Back pain with fever but no weakness, numbness, or bladder symptoms.", "medium", "Back pain with systemic symptom", "musculoskeletal"),
    ("BENCH-M13", "New tremor with unexplained weight loss and fast heartbeat.", "medium", "Possible thyroid or neurologic disorder", "endocrine"),
    ("BENCH-M14", "Repeated episodes of dizziness affecting walking but no focal neurologic deficit.", "medium", "Recurrent vertigo/dizziness", "neurologic"),
    ("BENCH-M15", "Sore throat with fever lasting several days and difficulty swallowing solids.", "medium", "Persistent throat infection", "ENT"),
    ("BENCH-M16", "Tooth pain with facial swelling and fever.", "medium", "Possible dental infection", "dental"),
    ("BENCH-M17", "Persistent low mood for several weeks without immediate self-harm danger.", "medium", "Mental health review indicated", "mental_health"),
    ("BENCH-M18", "Frequent thirst and urination with unexplained fatigue over weeks.", "medium", "Possible hyperglycemia", "metabolic"),
    ("BENCH-M19", "Knee pain and swelling after a minor injury, still unable to bear weight normally the next day.", "medium", "Musculoskeletal injury requiring assessment", "musculoskeletal"),
    ("BENCH-M20", "Persistent rash with fever but no breathing difficulty or facial swelling.", "medium", "Rash with systemic symptoms", "dermatology"),
    # Low / self-care appropriate unless worsening (20)
    ("BENCH-L01", "Mild runny nose and sneezing for one day with no fever or breathing difficulty.", "low", "Mild upper respiratory/allergy symptoms", "respiratory"),
    ("BENCH-L02", "Knee clicking without pain, swelling, or injury.", "low", "Benign joint clicking pattern", "musculoskeletal"),
    ("BENCH-L03", "Mild gas and bloating after a large meal, improving over several hours.", "low", "Transient bloating", "gastrointestinal"),
    ("BENCH-L04", "Mild tension-type headache after long screen use, no red flags.", "low", "Tension-type headache pattern", "neurologic"),
    ("BENCH-L05", "Constipation for two days without severe pain, vomiting, or bleeding.", "low", "Short-duration constipation", "gastrointestinal"),
    ("BENCH-L06", "Mild sore throat for one day with normal breathing and swallowing.", "low", "Mild sore throat", "ENT"),
    ("BENCH-L07", "Occasional heartburn after spicy food with no chest pain or swallowing difficulty.", "low", "Simple reflux symptoms", "gastrointestinal"),
    ("BENCH-L08", "Mild neck stiffness after sleeping awkwardly, no fever or neurologic symptoms.", "low", "Muscular neck strain pattern", "musculoskeletal"),
    ("BENCH-L09", "Minor bruise after bumping the leg, not enlarging and no unusual bleeding.", "low", "Simple bruise", "injury"),
    ("BENCH-L10", "Mild menstrual cramps similar to usual pattern and relieved by rest.", "low", "Typical menstrual cramps", "gynecologic"),
    ("BENCH-L11", "Mild dry skin itching without rash, swelling, or breathing symptoms.", "low", "Dry skin irritation", "dermatology"),
    ("BENCH-L12", "Brief dizziness after standing up quickly that resolves within seconds.", "low", "Transient postural dizziness", "general"),
    ("BENCH-L13", "Mild muscle soreness the day after exercise with normal strength.", "low", "Post-exercise muscle soreness", "musculoskeletal"),
    ("BENCH-L14", "Small mouth ulcer present for two days with normal eating and drinking.", "low", "Minor aphthous ulcer pattern", "dental"),
    ("BENCH-L15", "Mild nausea after a heavy meal without vomiting or abdominal pain.", "low", "Transient nausea", "gastrointestinal"),
    ("BENCH-L16", "Mild seasonal itchy eyes and sneezing with no eye pain or vision change.", "low", "Seasonal allergy pattern", "allergy"),
    ("BENCH-L17", "Temporary hoarse voice after prolonged speaking, no breathing difficulty.", "low", "Voice strain", "ENT"),
    ("BENCH-L18", "Mild localized insect bite redness with no spreading swelling or systemic symptoms.", "low", "Local insect bite reaction", "dermatology"),
    ("BENCH-L19", "Occasional hiccups lasting a few minutes and resolving spontaneously.", "low", "Transient hiccups", "general"),
    ("BENCH-L20", "Mild tiredness after a short night of sleep, improving after rest.", "low", "Sleep-related fatigue", "general"),
]


# V33 expands the starter workspace with 60 additional synthetic review
# templates. Like starter_v1, these are workflow examples only and are never
# counted as clinical validation until an independent reviewer verifies them
# and adds a source.
_STARTER_V2 = [
    # High / urgent (20)
    ("BENCH2-H01", "Sudden chest pain radiating to the arm with nausea and cold sweating.", "high", "Emergency chest pain / possible acute coronary syndrome", "cardiovascular"),
    ("BENCH2-H02", "New facial droop with slurred speech beginning 20 minutes ago.", "high", "Possible stroke", "neurologic"),
    ("BENCH2-H03", "Severe wheeze with inability to finish sentences and rapidly worsening breathlessness.", "high", "Severe asthma / respiratory distress", "respiratory"),
    ("BENCH2-H04", "Sudden severe headache with vomiting and new confusion.", "high", "Acute neurological emergency", "neurologic"),
    ("BENCH2-H05", "Repeated fainting with an irregular heartbeat and ongoing dizziness.", "high", "Potential cardiac syncope", "cardiovascular"),
    ("BENCH2-H06", "Heavy rectal bleeding with weakness and near-fainting.", "high", "Significant gastrointestinal bleeding", "gastrointestinal"),
    ("BENCH2-H07", "Severe abdominal pain with repeated vomiting and inability to keep fluids down.", "high", "Acute abdominal emergency", "gastrointestinal"),
    ("BENCH2-H08", "Fever, confusion, very rapid breathing, and marked weakness.", "high", "Possible sepsis", "infection"),
    ("BENCH2-H09", "Sudden one-sided numbness involving face and arm with trouble speaking.", "high", "Possible stroke", "neurologic"),
    ("BENCH2-H10", "First seizure followed by prolonged confusion and failure to return to normal awareness.", "high", "New seizure requiring emergency assessment", "neurologic"),
    ("BENCH2-H11", "Red painful eye with sudden major loss of vision.", "high", "Acute eye emergency", "eye"),
    ("BENCH2-H12", "Severe shortness of breath with chest tightness and faintness after a new medication.", "high", "Possible severe allergic reaction", "allergy"),
    ("BENCH2-H13", "Very high fever, stiff neck, light sensitivity, and drowsiness.", "high", "Possible meningitis", "infection"),
    ("BENCH2-H14", "One leg suddenly swollen and painful followed by new breathlessness.", "high", "Possible venous thromboembolism", "cardiovascular"),
    ("BENCH2-H15", "Persistent vomiting with severe dehydration, minimal urine, and increasing drowsiness.", "high", "Severe dehydration", "gastrointestinal"),
    ("BENCH2-H16", "Chest pain with collapse during physical exertion.", "high", "Cardiac emergency", "cardiovascular"),
    ("BENCH2-H17", "Sudden inability to speak clearly with new arm weakness, even though symptoms partly improve.", "high", "Possible TIA / stroke", "neurologic"),
    ("BENCH2-H18", "Severe bleeding from a wound that does not stop with firm pressure.", "high", "Uncontrolled bleeding", "injury"),
    ("BENCH2-H19", "Rapidly spreading facial swelling with tongue swelling and wheeze.", "high", "Possible anaphylaxis", "allergy"),
    ("BENCH2-H20", "New severe confusion in an older adult with fever and reduced responsiveness.", "high", "Acute confusion with systemic illness", "general"),
    # Medium / needs medical review (20)
    ("BENCH2-M01", "Sore throat, fever, swollen neck glands, and difficulty swallowing for four days.", "medium", "Tonsillitis / throat infection pattern", "ENT"),
    ("BENCH2-M02", "Recurrent spinning dizziness with tinnitus and balance difficulty.", "medium", "Inner ear / vestibular disorder pattern", "ENT"),
    ("BENCH2-M03", "Burning urination, frequent urination, fever, and new back pain.", "medium", "Possible kidney infection", "genitourinary"),
    ("BENCH2-M04", "Repeated upper abdominal pain after meals with nausea lasting about an hour.", "medium", "Possible gallbladder disorder", "gastrointestinal"),
    ("BENCH2-M05", "Persistent upper abdominal discomfort, nausea, bloating, and reduced appetite for ten days.", "medium", "Gastritis / dyspepsia pattern", "gastrointestinal"),
    ("BENCH2-M06", "Recurrent blood on toilet paper with constipation but no heavy bleeding or faintness.", "medium", "Rectal bleeding requiring assessment", "gastrointestinal"),
    ("BENCH2-M07", "Dry itchy scaly rash recurring on elbows and knees.", "medium", "Chronic inflammatory skin condition", "dermatology"),
    ("BENCH2-M08", "Painful one-sided blistering rash with burning skin pain.", "medium", "Possible shingles", "dermatology"),
    ("BENCH2-M09", "Widespread muscle pain, poor sleep, fatigue, and concentration difficulty for months.", "medium", "Widespread pain syndrome requiring assessment", "musculoskeletal"),
    ("BENCH2-M10", "Persistent joint pain and swelling affecting both wrists and knees with morning stiffness.", "medium", "Inflammatory arthritis pattern", "musculoskeletal"),
    ("BENCH2-M11", "Extreme fatigue, memory difficulty, and numbness in both feet developing gradually.", "medium", "Possible vitamin deficiency / neurologic cause", "general"),
    ("BENCH2-M12", "Severe fatigue lasting months with sleep problems and worsening after activity.", "medium", "Persistent fatigue syndrome requiring assessment", "general"),
    ("BENCH2-M13", "Anxiety most days for months with insomnia, irritability, and difficulty concentrating.", "medium", "Generalised anxiety pattern", "mental_health"),
    ("BENCH2-M14", "Painful swollen knee without major injury that has not improved after ten days.", "medium", "Persistent joint inflammation", "musculoskeletal"),
    ("BENCH2-M15", "Flank and back pain coming in waves with nausea and painful urination.", "medium", "Possible kidney stone", "genitourinary"),
    ("BENCH2-M16", "Red itchy dry skin that repeatedly cracks and interferes with sleep.", "medium", "Eczema pattern", "dermatology"),
    ("BENCH2-M17", "Blurred vision and persistent red sore eyes despite several weeks of self-care.", "medium", "Persistent eye-surface disorder", "eye"),
    ("BENCH2-M18", "Recurrent bloating, gas, abdominal cramps, and diarrhoea after dairy foods.", "medium", "Possible lactose intolerance", "gastrointestinal"),
    ("BENCH2-M19", "Shoulder pain with swelling and restricted movement persisting for two weeks.", "medium", "Bursitis / musculoskeletal inflammation", "musculoskeletal"),
    ("BENCH2-M20", "Unexplained palpitations, tremor, sweating, anxiety, and weight loss.", "medium", "Possible thyroid disorder", "endocrine"),
    # Low / self-care appropriate unless worsening (20)
    ("BENCH2-L01", "Mild dry itchy eyes after a long day of screen use, with normal vision.", "low", "Dry-eye irritation pattern", "eye"),
    ("BENCH2-L02", "Mild bloating and gas shortly after drinking milk, resolving the same day.", "low", "Possible mild lactose intolerance pattern", "gastrointestinal"),
    ("BENCH2-L03", "Mild itchy dry patch of skin with no fever, swelling, or discharge.", "low", "Mild eczema / dry skin pattern", "dermatology"),
    ("BENCH2-L04", "Brief heartburn after a large late meal with no chest pressure or swallowing problem.", "low", "Simple reflux pattern", "gastrointestinal"),
    ("BENCH2-L05", "Minor wrist soreness after repetitive typing that improves with rest.", "low", "Mild overuse strain", "musculoskeletal"),
    ("BENCH2-L06", "Mild knee soreness after exercise with no swelling, instability, or trauma.", "low", "Post-exercise knee pain", "musculoskeletal"),
    ("BENCH2-L07", "Occasional neck tightness after desk work, improving with movement and rest.", "low", "Mechanical neck strain pattern", "musculoskeletal"),
    ("BENCH2-L08", "One day of mild runny nose, sneezing, and itchy eyes during pollen season.", "low", "Seasonal allergy pattern", "allergy"),
    ("BENCH2-L09", "Mild constipation for three days after travel with no vomiting, bleeding, or severe pain.", "low", "Short-term constipation", "gastrointestinal"),
    ("BENCH2-L10", "Mild period cramps similar to previous months and not limiting normal activity.", "low", "Typical menstrual cramps", "gynecologic"),
    ("BENCH2-L11", "Temporary hoarseness after cheering at an event, with normal breathing and swallowing.", "low", "Voice strain", "ENT"),
    ("BENCH2-L12", "Mild headache after missing sleep and drinking little water, improving with rest.", "low", "Non-specific mild headache", "neurologic"),
    ("BENCH2-L13", "Brief light-headedness after standing quickly, resolving immediately without fainting.", "low", "Transient postural light-headedness", "general"),
    ("BENCH2-L14", "Mild abdominal discomfort and gas after a very large meal, improving within hours.", "low", "Transient indigestion / bloating", "gastrointestinal"),
    ("BENCH2-L15", "Localized mild rash after contact with a new soap, without facial swelling or breathing symptoms.", "low", "Mild contact dermatitis pattern", "dermatology"),
    ("BENCH2-L16", "Mild muscle cramp after exercise that resolves with rest and hydration.", "low", "Transient muscle cramp", "musculoskeletal"),
    ("BENCH2-L17", "Occasional harmless joint clicking without pain, swelling, or loss of movement.", "low", "Benign joint clicking", "musculoskeletal"),
    ("BENCH2-L18", "Mild nausea after a rich meal with no vomiting, fever, or ongoing abdominal pain.", "low", "Transient nausea", "gastrointestinal"),
    ("BENCH2-L19", "Mild tiredness during a stressful week, improving after sleep and rest.", "low", "Short-term fatigue", "general"),
    ("BENCH2-L20", "Small bruise after a known bump with no unusual bleeding elsewhere.", "low", "Simple bruise", "injury"),
]


# V34 adds 60 more synthetic review templates to broaden research-validation
# coverage across common symptom domains and edge cases. These remain pending
# review and are excluded from all scientific metrics until independently
# verified and sourced.
_STARTER_V3 = [
    # High / urgent (20)
    ("BENCH3-H01", "Sudden severe chest pressure with nausea and pain spreading to the jaw.", "high", "Emergency chest pain pattern", "cardiovascular"),
    ("BENCH3-H02", "New one-sided facial weakness with slurred speech and difficulty lifting one arm.", "high", "Possible stroke", "neurologic"),
    ("BENCH3-H03", "Sudden severe breathlessness with blue lips and inability to speak full sentences.", "high", "Severe respiratory distress", "respiratory"),
    ("BENCH3-H04", "Collapse with no normal response after a severe headache.", "high", "Loss of consciousness with neurologic red flag", "neurologic"),
    ("BENCH3-H05", "Severe abdominal pain with repeated vomiting and a swollen rigid abdomen.", "high", "Acute abdominal emergency", "gastrointestinal"),
    ("BENCH3-H06", "Pregnant person with severe lower abdominal pain, dizziness, and heavy bleeding.", "high", "Pregnancy-related bleeding emergency", "gynecologic"),
    ("BENCH3-H07", "High fever, rapidly spreading purple rash, confusion, and extreme weakness.", "high", "Possible sepsis / meningococcal illness", "infection"),
    ("BENCH3-H08", "Severe wheezing and breathing difficulty after an insect sting with facial swelling.", "high", "Possible anaphylaxis", "allergy"),
    ("BENCH3-H09", "Head injury followed by unequal pupils, worsening drowsiness, and repeated vomiting.", "high", "Serious head injury", "injury"),
    ("BENCH3-H10", "Sudden severe eye pain with vomiting and marked reduction in vision.", "high", "Acute eye emergency", "eye"),
    ("BENCH3-H11", "New severe back pain with leg weakness and loss of bladder control.", "high", "Possible spinal cord / cauda equina emergency", "neurologic"),
    ("BENCH3-H12", "Vomiting blood repeatedly with fainting and rapid heartbeat.", "high", "Major gastrointestinal bleeding", "gastrointestinal"),
    ("BENCH3-H13", "Severe dehydration with confusion, very little urine, and inability to keep fluids down.", "high", "Severe dehydration", "general"),
    ("BENCH3-H14", "Sudden painful cold pale leg with loss of normal sensation.", "high", "Acute limb circulation emergency", "cardiovascular"),
    ("BENCH3-H15", "Severe chest pain and breathlessness shortly after surgery with faintness.", "high", "Possible pulmonary embolism", "respiratory"),
    ("BENCH3-H16", "First seizure followed by persistent confusion and another seizure soon after.", "high", "Recurrent seizure emergency", "neurologic"),
    ("BENCH3-H17", "Heavy bleeding after childbirth with dizziness and weakness.", "high", "Postpartum bleeding emergency", "gynecologic"),
    ("BENCH3-H18", "Diabetic person with sweating, confusion, shakiness, and reduced consciousness.", "high", "Possible severe hypoglycaemia", "metabolic"),
    ("BENCH3-H19", "Sudden severe scrotal pain with nausea and a high-riding testicle.", "high", "Possible testicular torsion", "genitourinary"),
    ("BENCH3-H20", "Severe neck swelling with drooling, muffled voice, and breathing difficulty.", "high", "Upper-airway emergency", "ENT"),
    # Medium / needs medical review (20)
    ("BENCH3-M01", "Persistent cough, fever, and chest discomfort for a week without severe breathlessness.", "medium", "Respiratory infection requiring assessment", "respiratory"),
    ("BENCH3-M02", "Repeated migraines becoming more frequent over the last month without neurologic deficit.", "medium", "Changing headache pattern", "neurologic"),
    ("BENCH3-M03", "Persistent fatigue, pallor, and shortness of breath on exertion over several weeks.", "medium", "Possible anaemia pattern", "general"),
    ("BENCH3-M04", "New neck swelling and ongoing hoarseness for several weeks.", "medium", "Persistent neck/voice symptom requiring review", "ENT"),
    ("BENCH3-M05", "Recurrent right upper abdominal pain after fatty meals with nausea.", "medium", "Gallbladder disorder pattern", "gastrointestinal"),
    ("BENCH3-M06", "Burning urination and pelvic discomfort recurring several times this month.", "medium", "Recurrent urinary symptoms", "genitourinary"),
    ("BENCH3-M07", "Persistent thirst, frequent urination, blurred vision, and tiredness.", "medium", "Possible hyperglycaemia", "metabolic"),
    ("BENCH3-M08", "Irregular periods with new excessive hair growth and weight gain over months.", "medium", "Endocrine / menstrual disorder pattern", "endocrine"),
    ("BENCH3-M09", "Persistent numbness and tingling in both hands with reduced grip strength.", "medium", "Neurologic or entrapment neuropathy pattern", "neurologic"),
    ("BENCH3-M10", "Joint swelling, morning stiffness, and pain in several small joints for six weeks.", "medium", "Inflammatory arthritis pattern", "musculoskeletal"),
    ("BENCH3-M11", "A skin mole has changed shape and colour over several months.", "medium", "Changing skin lesion requiring review", "dermatology"),
    ("BENCH3-M12", "Persistent mouth ulcer for more than three weeks.", "medium", "Persistent oral lesion", "dental"),
    ("BENCH3-M13", "Intermittent blood in the stool with a change in bowel habit for several weeks.", "medium", "Persistent bowel symptom requiring assessment", "gastrointestinal"),
    ("BENCH3-M14", "Repeated episodes of ringing in one ear with reduced hearing and spinning dizziness.", "medium", "Inner-ear disorder pattern", "ENT"),
    ("BENCH3-M15", "Low mood, loss of interest, and sleep difficulty lasting several weeks without immediate self-harm risk.", "medium", "Depressive symptoms requiring assessment", "mental_health"),
    ("BENCH3-M16", "Anxiety with recurrent panic-like episodes interfering with study or work.", "medium", "Anxiety / panic symptoms requiring assessment", "mental_health"),
    ("BENCH3-M17", "Persistent lower back pain for six weeks that limits normal activity but has no emergency red flags.", "medium", "Persistent mechanical back pain", "musculoskeletal"),
    ("BENCH3-M18", "Unilateral breast lump noticed recently without acute infection symptoms.", "medium", "New breast lump requiring assessment", "general"),
    ("BENCH3-M19", "Repeated nosebleeds over several weeks without severe active bleeding.", "medium", "Recurrent epistaxis", "ENT"),
    ("BENCH3-M20", "Progressive difficulty swallowing solid food over several weeks.", "medium", "Progressive dysphagia requiring assessment", "gastrointestinal"),
    # Low / self-care appropriate unless worsening (20)
    ("BENCH3-L01", "Mild common-cold symptoms for two days with normal breathing and hydration.", "low", "Mild viral upper respiratory pattern", "respiratory"),
    ("BENCH3-L02", "Mild tension headache after studying for hours, improving after rest.", "low", "Tension-type headache pattern", "neurologic"),
    ("BENCH3-L03", "Occasional mild indigestion after overeating with no alarm symptoms.", "low", "Simple indigestion pattern", "gastrointestinal"),
    ("BENCH3-L04", "Mild ankle soreness after a long walk with no swelling or inability to bear weight.", "low", "Minor overuse soreness", "musculoskeletal"),
    ("BENCH3-L05", "Small localized itchy mosquito bite with no spreading redness or systemic symptoms.", "low", "Local insect-bite reaction", "dermatology"),
    ("BENCH3-L06", "Mild dry cough after throat irritation lasting less than a day.", "low", "Transient throat irritation", "respiratory"),
    ("BENCH3-L07", "Mild eye dryness after prolonged screen time with normal vision and no pain.", "low", "Dry-eye irritation pattern", "eye"),
    ("BENCH3-L08", "Mild constipation after dietary change with normal appetite and no vomiting.", "low", "Short-term constipation", "gastrointestinal"),
    ("BENCH3-L09", "Mild menstrual cramps matching the usual monthly pattern.", "low", "Typical menstrual cramps", "gynecologic"),
    ("BENCH3-L10", "Brief muscle twitch after exercise with no weakness or persistent numbness.", "low", "Transient muscle twitch", "musculoskeletal"),
    ("BENCH3-L11", "Mild seasonal sneezing and itchy nose without breathing difficulty.", "low", "Allergic rhinitis pattern", "allergy"),
    ("BENCH3-L12", "Small uncomplicated mouth ulcer improving over a few days.", "low", "Minor mouth ulcer", "dental"),
    ("BENCH3-L13", "Mild motion-related nausea during a car journey that resolves afterward.", "low", "Motion-related nausea", "general"),
    ("BENCH3-L14", "Mild shoulder muscle soreness after carrying a heavy bag, improving with rest.", "low", "Minor muscular strain", "musculoskeletal"),
    ("BENCH3-L15", "Mild dandruff and scalp flaking without pain, pus, or hair loss patches.", "low", "Mild scalp irritation", "dermatology"),
    ("BENCH3-L16", "Brief ear fullness after a flight with no severe pain, discharge, or hearing loss.", "low", "Pressure-related ear symptom", "ENT"),
    ("BENCH3-L17", "Mild tiredness after several nights of reduced sleep, improving with rest.", "low", "Sleep-related fatigue", "general"),
    ("BENCH3-L18", "Mild gas after beans with no persistent pain, vomiting, or weight loss.", "low", "Diet-related gas", "gastrointestinal"),
    ("BENCH3-L19", "Minor superficial scratch with no redness, swelling, or fever.", "low", "Minor skin injury", "injury"),
    ("BENCH3-L20", "Mild temporary hoarseness after prolonged speaking with normal swallowing and breathing.", "low", "Voice strain", "ENT"),
]


def init_schema() -> None:
    global _SCHEMA_READY
    key = db._database_identity()
    if _SCHEMA_READY == key:
        return
    db.init_db(); conn = db._conn(); c = conn.cursor()
    try:
        c.execute(f"""
            CREATE TABLE IF NOT EXISTS research_validation_cases (
                id {_serial()},
                case_code TEXT UNIQUE NOT NULL,
                case_summary TEXT NOT NULL DEFAULT '',
                reference_risk TEXT NOT NULL,
                system_risk TEXT NOT NULL DEFAULT '',
                reference_condition TEXT NOT NULL DEFAULT '',
                system_condition TEXT NOT NULL DEFAULT '',
                source_reference TEXT NOT NULL DEFAULT '',
                reviewer_role TEXT NOT NULL DEFAULT '',
                notes TEXT NOT NULL DEFAULT '',
                reference_verified INTEGER NOT NULL DEFAULT 0,
                dataset_origin TEXT NOT NULL DEFAULT 'manual',
                scenario_group TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        cols = _cols(c, "research_validation_cases")
        if "reference_verified" not in cols:
            c.execute("ALTER TABLE research_validation_cases ADD COLUMN reference_verified INTEGER NOT NULL DEFAULT 0")
        if "dataset_origin" not in cols:
            c.execute("ALTER TABLE research_validation_cases ADD COLUMN dataset_origin TEXT NOT NULL DEFAULT 'manual'")
        if "scenario_group" not in cols:
            c.execute("ALTER TABLE research_validation_cases ADD COLUMN scenario_group TEXT NOT NULL DEFAULT ''")
        c.execute("CREATE INDEX IF NOT EXISTS idx_research_validation_risk ON research_validation_cases(reference_risk,system_risk)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_research_validation_verified ON research_validation_cases(reference_verified,dataset_origin)")
        # Seed a balanced 60-case starter set once. These rows remain excluded
        # from metrics until an independent reviewer verifies the reference.
        c.execute(f"SELECT COUNT(*) FROM research_validation_cases WHERE dataset_origin={PH}", ("starter_v1",))
        if int((c.fetchone() or [0])[0] or 0) == 0:
            now = _now()
            for code, summary_text, ref_risk, ref_condition, group in _STARTER:
                vals = (code, summary_text, ref_risk, "", ref_condition, "", "", "Pending independent review", "Starter benchmark template. Verify reference risk/condition and cite an independent source before marking as verified.", 0, "starter_v1", group, now, now)
                if db.USE_POSTGRES:
                    c.execute(
                        f"INSERT INTO research_validation_cases(case_code,case_summary,reference_risk,system_risk,reference_condition,system_condition,source_reference,reviewer_role,notes,reference_verified,dataset_origin,scenario_group,created_at,updated_at) VALUES({','.join([PH]*14)}) ON CONFLICT(case_code) DO NOTHING",
                        vals,
                    )
                else:
                    c.execute(
                        f"INSERT OR IGNORE INTO research_validation_cases(case_code,case_summary,reference_risk,system_risk,reference_condition,system_condition,source_reference,reviewer_role,notes,reference_verified,dataset_origin,scenario_group,created_at,updated_at) VALUES({','.join([PH]*14)})",
                        vals,
                    )
            # no-op if some duplicates existed; normal clean install inserts all 60
        c.execute(f"SELECT COUNT(*) FROM research_validation_cases WHERE dataset_origin={PH}", ("starter_v2",))
        if int((c.fetchone() or [0])[0] or 0) == 0:
            now = _now()
            for code, summary_text, ref_risk, ref_condition, group in _STARTER_V2:
                vals = (code, summary_text, ref_risk, "", ref_condition, "", "", "Pending independent review", "Starter benchmark template. Verify reference risk/condition and cite an independent source before marking as verified.", 0, "starter_v2", group, now, now)
                if db.USE_POSTGRES:
                    c.execute(
                        f"INSERT INTO research_validation_cases(case_code,case_summary,reference_risk,system_risk,reference_condition,system_condition,source_reference,reviewer_role,notes,reference_verified,dataset_origin,scenario_group,created_at,updated_at) VALUES({','.join([PH]*14)}) ON CONFLICT(case_code) DO NOTHING",
                        vals,
                    )
                else:
                    c.execute(
                        f"INSERT OR IGNORE INTO research_validation_cases(case_code,case_summary,reference_risk,system_risk,reference_condition,system_condition,source_reference,reviewer_role,notes,reference_verified,dataset_origin,scenario_group,created_at,updated_at) VALUES({','.join([PH]*14)})",
                        vals,
                    )
        c.execute(f"SELECT COUNT(*) FROM research_validation_cases WHERE dataset_origin={PH}", ("starter_v3",))
        if int((c.fetchone() or [0])[0] or 0) == 0:
            now = _now()
            for code, summary_text, ref_risk, ref_condition, group in _STARTER_V3:
                vals = (code, summary_text, ref_risk, "", ref_condition, "", "", "Pending independent review", "Starter benchmark template. Verify reference risk/condition and cite an independent source before marking as verified.", 0, "starter_v3", group, now, now)
                if db.USE_POSTGRES:
                    c.execute(
                        f"INSERT INTO research_validation_cases(case_code,case_summary,reference_risk,system_risk,reference_condition,system_condition,source_reference,reviewer_role,notes,reference_verified,dataset_origin,scenario_group,created_at,updated_at) VALUES({','.join([PH]*14)}) ON CONFLICT(case_code) DO NOTHING",
                        vals,
                    )
                else:
                    c.execute(
                        f"INSERT OR IGNORE INTO research_validation_cases(case_code,case_summary,reference_risk,system_risk,reference_condition,system_condition,source_reference,reviewer_role,notes,reference_verified,dataset_origin,scenario_group,created_at,updated_at) VALUES({','.join([PH]*14)})",
                        vals,
                    )
        conn.commit(); _SCHEMA_READY = key
    finally:
        conn.close()


def _norm_risk(value: str) -> str:
    raw = str(value or "").strip().lower()
    mapping = {
        "low": "low", "منخفض": "low", "low risk": "low",
        "medium": "medium", "moderate": "medium", "review": "medium", "needs review": "medium", "يحتاج مراجعة": "medium", "متوسط": "medium",
        "high": "high", "urgent": "high", "emergency": "high", "عاجل": "high", "طوارئ": "high",
    }
    return mapping.get(raw, raw if raw in {"low", "medium", "high"} else "")


def _norm_text(value: str) -> str:
    value = re.sub(r"\s+", " ", str(value or "").strip().lower())
    return re.sub(r"[^\w\u0600-\u06ff ]+", "", value)


def _select_columns() -> str:
    return "id,case_code,case_summary,reference_risk,system_risk,reference_condition,system_condition,source_reference,reviewer_role,notes,reference_verified,dataset_origin,scenario_group,created_at,updated_at"


def _row_to_dict(row) -> dict:
    keys = ["id", "case_code", "case_summary", "reference_risk", "system_risk", "reference_condition", "system_condition", "source_reference", "reviewer_role", "notes", "reference_verified", "dataset_origin", "scenario_group", "created_at", "updated_at"]
    item = dict(zip(keys, row))
    item["reference_verified"] = bool(item.get("reference_verified"))
    item["risk_agreement"] = bool(_norm_risk(item["reference_risk"]) and _norm_risk(item["system_risk"]) and _norm_risk(item["reference_risk"]) == _norm_risk(item["system_risk"]))
    rc, sc = _norm_text(item["reference_condition"]), _norm_text(item["system_condition"])
    item["condition_agreement"] = None if not rc or not sc else bool(rc == sc or rc in sc or sc in rc)
    return item


def list_cases(limit: int = 300) -> list[dict]:
    init_schema(); limit = max(1, min(1000, int(limit or 300)))
    conn = db._conn(); c = conn.cursor()
    try:
        c.execute(f"SELECT {_select_columns()} FROM research_validation_cases ORDER BY reference_verified DESC,id ASC LIMIT {PH}", (limit,))
        return [_row_to_dict(r) for r in c.fetchall()]
    finally:
        conn.close()


def study_protocol() -> dict:
    """Operational protocol for an independently reviewed validation study.

    This is a workflow description, not an ethics approval or a clinical claim.
    It is designed to keep the reference answer independent from the system
    output and to make the exported study reproducible.
    """
    freeze = research_study.status()
    return {
        "protocol_version": "RV-1.1",
        "study_version": freeze.get("study_version"),
        "app_version": release_candidate.APP_VERSION,
        "version_frozen": bool(freeze.get("frozen")),
        "algorithm_integrity_ok": freeze.get("integrity_ok"),
        "objective": "Evaluate agreement between SymptoSense triage output and an independently established reference for predefined de-identified scenarios.",
        "primary_endpoint": "Three-level risk agreement (low / needs review / urgent).",
        "secondary_endpoints": ["Urgent sensitivity", "Urgent specificity", "Cohen's kappa", "Per-class recall/precision", "Top-condition agreement"],
        "reference_rule": "A case counts only when the reference is independently reviewed, a reviewer role is recorded, and an external source/reference is documented.",
        "blinding_rule": "Use the blinded reviewer export so the reference reviewer does not need to see the system result while establishing the reference.",
        "minimum_verified_cases": 100,
        "minimum_per_risk_class": 20,
        "recommended_domains": 8,
        "limitations": "Starter templates are not clinical ground truth and are excluded from metrics until independently verified.",
    }


def export_rows(blinded: bool = False) -> list[dict]:
    rows = list_cases(1000)
    freeze = research_study.status()
    out = []
    for x in rows:
        item = {
            "study_version": freeze.get("study_version") or "UNFROZEN",
            "app_version": release_candidate.APP_VERSION,
            "algorithm_integrity_ok": freeze.get("integrity_ok"),
            "case_code": x.get("case_code"),
            "scenario_group": x.get("scenario_group"),
            "case_summary": x.get("case_summary"),
            "reference_risk": x.get("reference_risk"),
            "reference_condition": x.get("reference_condition"),
            "reviewer_role": x.get("reviewer_role"),
            "source_reference": x.get("source_reference"),
            "reference_verified": bool(x.get("reference_verified")),
            "dataset_origin": x.get("dataset_origin"),
            "notes": x.get("notes"),
        }
        if not blinded:
            item.update({
                "system_risk": x.get("system_risk"),
                "system_condition": x.get("system_condition"),
                "risk_agreement": x.get("risk_agreement"),
                "condition_agreement": x.get("condition_agreement"),
            })
        out.append(item)
    return out


def summary() -> dict:
    rows = list_cases(1000)
    verified = [x for x in rows if x.get("reference_verified")]
    pending = [x for x in rows if not x.get("reference_verified")]
    risk_rows = [x for x in verified if _norm_risk(x["reference_risk"]) and _norm_risk(x["system_risk"])]
    risk_match = sum(1 for x in risk_rows if x["risk_agreement"])
    cond_rows = [x for x in verified if x["condition_agreement"] is not None]
    cond_match = sum(1 for x in cond_rows if x["condition_agreement"])
    by_risk = {"low": {"n": 0, "match": 0}, "medium": {"n": 0, "match": 0}, "high": {"n": 0, "match": 0}}
    matrix = {r: {s: 0 for s in ("low", "medium", "high")} for r in ("low", "medium", "high")}
    for x in risk_rows:
        ref, sys = _norm_risk(x["reference_risk"]), _norm_risk(x["system_risk"])
        by_risk[ref]["n"] += 1
        if x["risk_agreement"]: by_risk[ref]["match"] += 1
        matrix[ref][sys] += 1
    tp = matrix["high"]["high"]
    fn = matrix["high"]["low"] + matrix["high"]["medium"]
    tn = sum(matrix[r][s] for r in ("low", "medium") for s in ("low", "medium"))
    fp = matrix["low"]["high"] + matrix["medium"]["high"]
    starter = sum(1 for x in rows if str(x.get("dataset_origin") or "").startswith("starter_v"))
    verified_domain_counts = {}
    starter_domain_counts = {}
    for x in rows:
        group = str(x.get("scenario_group") or "unclassified")
        if x.get("reference_verified"):
            verified_domain_counts[group] = verified_domain_counts.get(group, 0) + 1
        if str(x.get("dataset_origin") or "").startswith("starter_v"):
            starter_domain_counts[group] = starter_domain_counts.get(group, 0) + 1
    # A benchmark-size target is a workflow milestone, not a statistical claim.
    protocol = study_protocol()
    target = 100  # workflow milestone; kept aligned with study_protocol()["minimum_verified_cases"]
    observed = sum(sum(v.values()) for v in matrix.values())
    po = (risk_match / observed) if observed else None
    kappa = None
    if observed:
        ref_totals = {r: sum(matrix[r].values()) for r in matrix}
        sys_totals = {c: sum(matrix[r][c] for r in matrix) for c in ("low", "medium", "high")}
        pe = sum(ref_totals[k] * sys_totals[k] for k in ("low", "medium", "high")) / float(observed * observed)
        if pe < 1:
            kappa = round((po - pe) / (1 - pe), 3)
    per_class = {}
    recalls = []; precisions = []; f1s = []
    for cls in ("low", "medium", "high"):
        class_tp = matrix[cls][cls]
        class_fn = sum(matrix[cls][s] for s in ("low", "medium", "high") if s != cls)
        class_fp = sum(matrix[r][cls] for r in ("low", "medium", "high") if r != cls)
        recall = class_tp / (class_tp + class_fn) if (class_tp + class_fn) else None
        precision = class_tp / (class_tp + class_fp) if (class_tp + class_fp) else None
        f1 = (2 * precision * recall / (precision + recall)) if (precision is not None and recall is not None and (precision + recall)) else None
        if recall is not None: recalls.append(recall)
        if precision is not None: precisions.append(precision)
        if f1 is not None: f1s.append(f1)
        per_class[cls] = {
            "n": by_risk[cls]["n"],
            "recall_pct": round(recall * 100, 1) if recall is not None else None,
            "precision_pct": round(precision * 100, 1) if precision is not None else None,
            "f1_pct": round(f1 * 100, 1) if f1 is not None else None,
        }
    distinct_sources = {str(x.get("source_reference") or "").strip() for x in verified if str(x.get("source_reference") or "").strip()}
    minimum_per_class = int(protocol["minimum_per_risk_class"])
    risk_balance_ready = all(by_risk[k]["n"] >= minimum_per_class for k in ("low","medium","high"))
    domain_target = int(protocol["recommended_domains"])
    domain_coverage_ready = len(verified_domain_counts) >= domain_target
    study_ready = len(verified) >= target and risk_balance_ready and domain_coverage_ready
    return {
        "total_cases": len(rows),
        "starter_cases": starter,
        "verified_cases": len(verified),
        "pending_reference_review": len(pending),
        "risk_compared": len(risk_rows),
        "risk_agreement_count": risk_match,
        "risk_agreement_pct": round(100.0 * risk_match / len(risk_rows), 1) if risk_rows else None,
        "urgent_sensitivity_pct": round(100.0 * tp / (tp + fn), 1) if (tp + fn) else None,
        "urgent_specificity_pct": round(100.0 * tn / (tn + fp), 1) if (tn + fp) else None,
        "condition_compared": len(cond_rows),
        "condition_agreement_count": cond_match,
        "condition_agreement_pct": round(100.0 * cond_match / len(cond_rows), 1) if cond_rows else None,
        "cohens_kappa_risk": kappa,
        "balanced_accuracy_pct": round(100.0 * sum(recalls) / len(recalls), 1) if recalls else None,
        "macro_precision_pct": round(100.0 * sum(precisions) / len(precisions), 1) if precisions else None,
        "macro_f1_pct": round(100.0 * sum(f1s) / len(f1s), 1) if f1s else None,
        "per_class": per_class,
        "distinct_reference_sources": len(distinct_sources),
        "risk_balance_ready": risk_balance_ready,
        "domain_coverage_ready": domain_coverage_ready,
        "study_ready": study_ready,
        "protocol": protocol,
        "research_freeze": research_study.status(),
        "by_reference_risk": by_risk,
        "confusion_matrix": matrix,
        "verified_by_domain": verified_domain_counts,
        "starter_by_domain": starter_domain_counts,
        "recommended_min_verified_cases": target,
        "verified_progress_pct": round(min(100.0, 100.0 * len(verified) / target), 1),
        "note": "Only independently verified reference cases are included in validation metrics. Starter benchmark templates are excluded until reviewed and sourced.",
    }


def save_case(data: dict, case_id: int | None = None) -> dict:
    init_schema(); data = data or {}
    code = str(data.get("case_code") or "").strip()[:80]
    summary_text = str(data.get("case_summary") or "").strip()[:1600]
    ref_risk = _norm_risk(data.get("reference_risk"))
    sys_risk = _norm_risk(data.get("system_risk"))
    if not code: raise ValueError("case_code_required")
    if not ref_risk: raise ValueError("valid_reference_risk_required")
    ref_condition = str(data.get("reference_condition") or "").strip()[:300]
    sys_condition = str(data.get("system_condition") or "").strip()[:600]
    source_reference = str(data.get("source_reference") or "").strip()[:1000]
    reviewer_role = str(data.get("reviewer_role") or "").strip()[:160]
    notes = str(data.get("notes") or "").strip()[:1600]
    verified = bool(data.get("reference_verified"))
    if verified and (not reviewer_role or not source_reference):
        raise ValueError("verified_reference_requires_reviewer_and_source")
    scenario_group = str(data.get("scenario_group") or "").strip()[:80]
    now = _now(); conn = db._conn(); c = conn.cursor()
    try:
        if case_id:
            c.execute(f"SELECT dataset_origin FROM research_validation_cases WHERE id={PH}", (int(case_id),))
            old = c.fetchone()
            if not old: raise ValueError("validation_case_not_found")
            origin = old[0] or "manual"
            c.execute(f"UPDATE research_validation_cases SET case_code={PH},case_summary={PH},reference_risk={PH},system_risk={PH},reference_condition={PH},system_condition={PH},source_reference={PH},reviewer_role={PH},notes={PH},reference_verified={PH},scenario_group={PH},updated_at={PH} WHERE id={PH}",
                      (code, summary_text, ref_risk, sys_risk, ref_condition, sys_condition, source_reference, reviewer_role, notes, int(verified), scenario_group, now, int(case_id)))
            cid = int(case_id)
        else:
            origin = "manual"
            c.execute(f"INSERT INTO research_validation_cases(case_code,case_summary,reference_risk,system_risk,reference_condition,system_condition,source_reference,reviewer_role,notes,reference_verified,dataset_origin,scenario_group,created_at,updated_at) VALUES({','.join([PH]*14)})",
                      (code, summary_text, ref_risk, sys_risk, ref_condition, sys_condition, source_reference, reviewer_role, notes, int(verified), origin, scenario_group, now, now))
            if db.USE_POSTGRES:
                c.execute("SELECT lastval()"); cid = int(c.fetchone()[0])
            else:
                cid = int(c.lastrowid)
        conn.commit(); c.execute(f"SELECT {_select_columns()} FROM research_validation_cases WHERE id={PH}", (cid,))
        return _row_to_dict(c.fetchone())
    except Exception:
        conn.rollback(); raise
    finally:
        conn.close()


def delete_case(case_id: int) -> bool:
    init_schema(); conn = db._conn(); c = conn.cursor()
    try:
        c.execute(f"DELETE FROM research_validation_cases WHERE id={PH}", (int(case_id),))
        changed = c.rowcount > 0; conn.commit(); return changed
    finally:
        conn.close()
