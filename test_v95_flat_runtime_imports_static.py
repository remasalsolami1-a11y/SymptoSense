import source_bundle
import versioning
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def test_production_view_imports_are_flat_and_self_contained():
    webapp = source_bundle.webapp_text()
    chat = source_bundle.chat_view_text()
    site = (ROOT / 'site_info_view.py').read_text(encoding='utf-8')
    assert 'from chat_view import render_chat_page' in webapp
    assert 'from site_info_view import render_site_info_page' in webapp
    assert 'from views.' not in webapp
    assert 'from views.' not in chat
    assert 'import views' not in chat
    assert 'def render_chat_page' in chat
    assert 'def render_site_info_page' in site


def test_docker_validates_flat_runtime_modules():
    docker = (ROOT / 'Dockerfile').read_text(encoding='utf-8')
    assert "SymptoSense Railway build profile: " + versioning.REVISION in docker
    assert 'chat_view.py' in docker
    assert 'site_info_view.py' in docker
    assert 'production runtime still depends on the optional views/ package' in docker
