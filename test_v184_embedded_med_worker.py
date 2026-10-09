import source_bundle
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WEBAPP = source_bundle.webapp_text()


def test_embedded_worker_starts_after_core_db_ready():
    assert 'def _medication_reminder_delivery_loop()' in WEBAPP
    assert '_start_medication_reminder_worker_once()' in WEBAPP
    assert 'MED_REMINDER_WORKER_INTERVAL_SECONDS' in WEBAPP
    marker = 'app.logger.info("STARTUP core database ready elapsed_ms=%s attempts=%s", elapsed_ms, attempt)'
    start = WEBAPP.index(marker)
    assert '_start_medication_reminder_worker_once()' in WEBAPP[start:start+500]


def test_save_and_edit_trigger_immediate_delivery_check():
    plan_route = WEBAPP[WEBAPP.index('def api_meds_plan():'):WEBAPP.index('def api_meds_plan_item(pid):')]
    item_route = WEBAPP[WEBAPP.index('def api_meds_plan_item(pid):'):WEBAPP.index('@app.route("/api/meds/today"')]
    assert '_kick_medication_delivery_now()' in plan_route
    assert '_kick_medication_delivery_now()' in item_route


def test_delivery_status_endpoint_present():
    assert '@app.route("/api/meds/delivery-status", methods=["GET"])' in WEBAPP
    assert 'email_configured' in WEBAPP
    assert 'worker_started' in WEBAPP
