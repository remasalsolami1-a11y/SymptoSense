import mental_support


def test_direct_crisis_arabic():
    assert mental_support.safety_level('أبي أموت') == 'direct'
    msg = mental_support.supportive_answer('أبي أموت', 'ar')
    assert '997' in msg and '911' in msg and '937' in msg


def test_passive_risk_arabic():
    assert mental_support.safety_level('أتمنى ما أصحى') == 'passive'
    msg = mental_support.supportive_answer('أتمنى ما أصحى', 'ar')
    assert 'هل تفكر الآن' in msg
    assert '997' in msg and '911' in msg and '937' in msg


def test_medical_red_flag_not_assumed_panic():
    assert mental_support.safety_level('عندي ألم صدر شديد وأنا خايف') == 'medical_red_flag'
    msg = mental_support.supportive_answer('عندي ألم صدر شديد وأنا خايف', 'ar')
    assert '997' in msg


def test_common_topics_are_tailored():
    assert 'الوحدة' in mental_support.supportive_answer('أشعر بالوحدة وما عندي أحد', 'ar')
    assert 'الغضب' in mental_support.supportive_answer('أنا معصب وعندي غضب', 'ar')
    assert 'sleep' in mental_support.supportive_answer("I can't sleep at night", 'en').lower()


def test_grounding_and_breathing_are_available():
    assert '5-4-3-2-1' in mental_support.grounding_54321('ar')
    breath = mental_support.calm_breathing('ar')
    assert '4' in breath and '6' in breath
    assert 'تحبس' in breath


def test_quick_tools_include_urgent_support():
    tools = mental_support.quick_tools('ar')
    keys = {item['key'] for item in tools}
    assert keys == {'calm', 'ground', 'urgent'}


def test_more_direct_crisis_phrases_are_caught():
    phrases = (
        'أفكر بالانتحار',
        'أبغى أنتحر',
        'ما أقدر أضمن نفسي',
        'أخاف أؤذي نفسي',
        'I am suicidal',
        'I cannot keep myself safe',
    )
    for phrase in phrases:
        assert mental_support.safety_level(phrase) == 'direct', phrase


def test_explicit_safe_denials_do_not_false_trigger():
    assert mental_support.safety_level('ما أبي أموت، أنا بس خايف') == 'none'
    assert mental_support.safety_level('ما أفكر بالانتحار') == 'none'
    assert mental_support.safety_level("I don't want to die") == 'none'
    assert mental_support.safety_level('I am not suicidal') == 'none'
    assert mental_support.safety_level('I am reading about suicide for a class') == 'none'


def test_standalone_crisis_keyword_prompts_safety_check():
    assert mental_support.safety_level('انتحار') == 'passive'
    assert mental_support.safety_level('suicide') == 'passive'


def test_affirmative_reply_to_safety_question_escalates():
    ar_messages = [
        {'role': 'assistant', 'content': 'هل تفكر الآن في إيذاء نفسك أو إنهاء حياتك؟'},
        {'role': 'user', 'content': 'نعم'},
    ]
    en_messages = [
        {'role': 'assistant', 'content': 'Are you thinking about hurting yourself or ending your life right now?'},
        {'role': 'user', 'content': 'yes'},
    ]
    assert mental_support.is_affirmative_crisis_followup(ar_messages)
    assert mental_support.is_affirmative_crisis_followup(en_messages)


def test_other_harm_uses_unified_emergency_number():
    assert mental_support.safety_level('أبي أقتل أحد') == 'other_harm'
    msg = mental_support.supportive_answer('أبي أقتل أحد', 'ar')
    assert '911' in msg and '997' in msg


def test_urgent_support_lists_saudi_numbers():
    ar = mental_support.urgent_support('ar')
    en = mental_support.urgent_support('en')
    for msg in (ar, en):
        assert '997' in msg and '911' in msg and '937' in msg
