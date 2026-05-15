"""Flask application factory.

`create_app` wires extensions, blueprints, logging, and SQLite WAL pragmas.
Imported by both Gunicorn (production) and pytest (testing).
"""

from __future__ import annotations

import logging
import sys
from typing import Any

from flask import Flask
from sqlalchemy import event
from sqlalchemy.engine import Engine

from app.config import BaseConfig, resolve_config
from app.extensions import csrf, db, login_manager, migrate


def _configure_logging(app: Flask) -> None:
    level = getattr(logging, app.config.get("LOG_LEVEL", "INFO").upper(), logging.INFO)
    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
    app.logger.setLevel(level)


def _enable_sqlite_pragmas(app: Flask) -> None:
    """Force WAL + foreign keys on every SQLite connection."""

    @event.listens_for(Engine, "connect")
    def _set_sqlite_pragma(dbapi_connection: Any, _conn_record: Any) -> None:
        if app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite"):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.close()


def create_app(config: type[BaseConfig] | str | None = None) -> Flask:
    app = Flask(
        __name__,
        instance_path=None,
        instance_relative_config=False,
        static_folder="static",
        template_folder="templates",
    )

    if isinstance(config, type):
        app.config.from_object(config)
    else:
        app.config.from_object(resolve_config(config))

    _configure_logging(app)
    _enable_sqlite_pragmas(app)

    # Extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    from app.models import User

    @login_manager.user_loader
    def _load_user(user_id: str) -> User | None:
        return db.session.get(User, int(user_id))

    # Blueprints
    from app.blueprints.auth import bp as auth_bp
    from app.blueprints.bills import bp as bills_bp
    from app.blueprints.budget import bp as budget_bp
    from app.blueprints.dashboard import bp as dashboard_bp
    from app.blueprints.goals import bp as goals_bp
    from app.blueprints.loans import bp as loans_bp
    from app.blueprints.networth import bp as networth_bp
    from app.blueprints.subscriptions import bp as subscriptions_bp
    from app.blueprints.whatif import bp as whatif_bp
    from app.pwa import bp as pwa_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(loans_bp)
    app.register_blueprint(networth_bp)
    app.register_blueprint(bills_bp)
    app.register_blueprint(budget_bp)
    app.register_blueprint(whatif_bp)
    app.register_blueprint(goals_bp)
    app.register_blueprint(subscriptions_bp)
    app.register_blueprint(pwa_bp)

    @app.context_processor
    def inject_globals() -> dict[str, Any]:
        return {"app_name": "Finance Hub"}

    return app
