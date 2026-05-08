"""Routes that serve the PWA shell: manifest and service worker.

Keeping these on the root path is required so the service worker can claim
clients across the entire site.
"""

from __future__ import annotations

from flask import Blueprint, Response, current_app, send_from_directory

bp = Blueprint("pwa", __name__)


@bp.route("/manifest.webmanifest")
def manifest() -> Response:
    response = send_from_directory(
        current_app.static_folder, "manifest.json", mimetype="application/manifest+json"
    )
    response.headers["Cache-Control"] = "no-cache"
    return response


@bp.route("/sw.js")
def service_worker() -> Response:
    response = send_from_directory(
        current_app.static_folder, "sw.js", mimetype="application/javascript"
    )
    # Service workers must not be cached by intermediaries — browsers re-fetch
    # this on every navigation to detect updates.
    response.headers["Cache-Control"] = "no-cache"
    response.headers["Service-Worker-Allowed"] = "/"
    return response


@bp.route("/offline")
def offline() -> str:
    from flask import render_template

    return render_template("offline.html")
