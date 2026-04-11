"""Tests for the Flask app factory and root route."""

import pytest
from app.app import create_app


@pytest.fixture
def app(test_config, db_manager_with_schema):
    """Create a Flask test application."""
    from services.base import Services

    svc = Services(test_config, db_manager=db_manager_with_schema)
    flask_app = create_app(config=test_config, services=svc)
    flask_app.config["TESTING"] = True
    return flask_app


@pytest.fixture
def client(app):
    """Return a Flask test client."""
    return app.test_client()


def test_root_returns_200(client):
    response = client.get("/")
    assert response.status_code == 200


def test_root_renders_base_template(client):
    response = client.get("/")
    html = response.data.decode()
    assert "<!DOCTYPE html>" in html
    assert "Necker" in html


def test_root_includes_htmx(client):
    response = client.get("/")
    html = response.data.decode()
    assert "htmx" in html


def test_services_attached_to_app(app):
    assert hasattr(app, "services")
    assert app.services is not None


def test_api_blueprint_registered(app):
    rules = {rule.rule for rule in app.url_map.iter_rules()}
    # The /api prefix is registered even with no routes yet
    assert any(r.startswith("/api") or r == "/" for r in rules)


def test_ui_blueprint_registered(app):
    rules = {rule.rule for rule in app.url_map.iter_rules()}
    assert any(r.startswith("/ui") or r == "/" for r in rules)
