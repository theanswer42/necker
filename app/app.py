"""Flask application factory."""

from flask import Flask, render_template
from flask_wtf.csrf import CSRFProtect

from config import load_config
from db.manager import DatabaseManager

csrf = CSRFProtect()


def create_app(config=None, db_manager=None):
    """Create and configure the Flask application.

    Args:
        config: Config object. If None, loads from the default config file.
        db_manager: Database manager. If None, creates one from config.

    Returns:
        Configured Flask application instance.
    """
    app = Flask(__name__)

    # Initialize config and db_manager
    if config is None:
        config = load_config()
    if db_manager is None:
        db_manager = DatabaseManager(config)

    app.config["NECKER_CONFIG"] = config
    app.config["SECRET_KEY"] = config.secret_key
    app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5 MB upload limit
    app.db_manager = db_manager

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
