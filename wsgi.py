"""Gunicorn / `flask` CLI entry point."""

from __future__ import annotations

from app import create_app

app = create_app()
