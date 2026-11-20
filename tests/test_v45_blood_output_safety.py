import blood_test


def test_unknown_cbc_units_are_not_reflected_from_ocr_or_model_output():
    malicious = '<img src=x onerror=alert(1)>'
    assert blood_test._normalize_unit(malicious) == ''
    entries, _ = blood_test.parse_blood_text('HGB | 13.2 | ' + malicious + ' | 12 | 16')
    assert entries and entries[0]['unit'] == ''


def test_blood_report_builder_emits_no_application_html_markup():
    results, notes, dangers, _level, child = blood_test.analyze_blood([
        {'key':'hgb','value':13.2,'unit':'g/dL','reference_low':12,'reference_high':16}
    ], gender='f', age=25)
    text = blood_test.build_text(results, 'f', 'en', notes, dangers, child)
    assert '<b>' not in text and '</b>' not in text
    assert 'Blood Test Report' in text
