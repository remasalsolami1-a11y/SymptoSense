import source_bundle
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WEB = source_bundle.webapp_text()

def test_home_does_not_query_live_stats_synchronously():
    block = source_bundle.function_source("_home_knowledge_snapshot")
    assert "medical_knowledge.statistics()" not in block
    assert "threading.Thread(" in block
    assert "cached or fallback" in block

def test_live_home_stats_refresh_happens_in_background_helper():
    start = WEB.index("def _refresh_home_knowledge_snapshot_background():")
    end = WEB.index("def _home_knowledge_snapshot():", start)
    block = WEB[start:end]
    assert "medical_knowledge.statistics()" in block

def test_optional_schema_storm_is_lazy_by_default():
    start = WEB.index("def _warm_optional_runtime_services():")
    end = WEB.index("def _initialize_core_runtime_services():", start)
    block = WEB[start:end]
    assert 'STARTUP_EAGER_OPTIONAL_SCHEMAS' in block
    assert 'steps = [("owner_admin", db.ensure_owner_admin_by_email)]' in block
    assert 'app.logger.info("STARTUP optional schemas mode=lazy")' in block

def test_optional_startup_is_deferred_after_core_database_ready():
    start = WEB.index("def _initialize_core_runtime_services():")
    block = WEB[start:start+4500]
    assert 'STARTUP_OPTIONAL_DELAY_SECONDS' in block
    assert 'name="symptosense-optional-startup"' in block
    assert 'app.logger.info("STARTUP optional services deferred")' in block
