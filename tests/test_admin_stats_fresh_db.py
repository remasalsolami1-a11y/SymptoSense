"""V268: /api/stats must work on a brand-new database (analytics_eligible comes from the lazy privacy migration)."""
import source_bundle

WEB = source_bundle.webapp_text()


def test_api_stats_runs_the_privacy_migration_before_reading_analytics_eligible():
    block = WEB.split('def api_stats():', 1)[1].split('return jsonify', 1)[0]
    assert 'privacy_features.init_schema()' in block
    assert block.index('privacy_features.init_schema()') < block.index('analytics_eligible')
