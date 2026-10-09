import source_bundle
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def test_admin_data_pulse_endpoint_is_protected_and_aggregate_only():
    src=source_bundle.webapp_text()
    assert '@app.route("/api/admin/data-pulse", methods=["GET"])' in src
    assert '@admin_api_required("analytics")' in src
    assert 'registered_users' in src
    assert 'stored_data_records' in src
    assert 'knowledge_items' in src
    block=src.split('@app.route("/api/admin/data-pulse"',1)[1].split('@app.route("/api/admin/system-health"',1)[0]
    assert 'SELECT email' not in block
    assert 'SELECT content' not in block
    assert 'SELECT name' not in block


def test_admin_dashboard_keeps_primary_overview_compact():
    src=(ROOT/'dashboard.py').read_text(encoding='utf-8')
    assert 'projectStrengthStats' in src
    assert 'قوة SymptoSense بالأرقام' in src
    assert 'Platform & Data Pulse' not in src
    assert 'نبض المنصة والبيانات' not in src
