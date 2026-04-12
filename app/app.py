"""Flask application factory."""

from flask import Flask, render_template
from flask_wtf.csrf import CSRFProtect

from config import load_config
from services.base import Services

csrf = CSRFProtect()


def create_app(config=None, services=None):
    """Create and configure the Flask application.

    Args:
        config: Config object. If None, loads from the default config file.
        services: Services container. If None, creates one from config.

    Returns:
        Configured Flask application instance.
    """
    app = Flask(__name__)

    # Initialize config and services
    if config is None:
        config = load_config()
    if services is None:
        services = Services(config)

    app.config["NECKER_CONFIG"] = config
    app.config["SECRET_KEY"] = config.secret_key
    app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5 MB upload limit
    app.services = services

    csrf.init_app(app)

    # Register blueprints
    from app.api import api_bp
    from app.ui import ui_bp

    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(ui_bp, url_prefix="/ui")

    @app.route("/")
    def index():
        return render_template("base.html")

    @app.errorhandler(413)
    def request_entity_too_large(e):
        return (
            render_template(
                "fragments/import_form.html",
                accounts=[],
                error="File too large. Maximum upload size is 5 MB.",
                selected_account_id=None,
            ),
            413,
        )

    return app
