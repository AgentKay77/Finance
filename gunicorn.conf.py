"""Gunicorn config for Raspberry Pi 5 (4 cores, 4GB).

The Pi handles a household-scale workload, so 2 sync workers with 4 threads
each is generous. Bump `workers` if you ever expose this beyond LAN/VPN.
"""

from __future__ import annotations

import multiprocessing
import os

bind = os.environ.get("GUNICORN_BIND", "127.0.0.1:8000")
workers = int(os.environ.get("GUNICORN_WORKERS", max(2, multiprocessing.cpu_count() // 2)))
threads = int(os.environ.get("GUNICORN_THREADS", 4))
worker_class = "gthread"
timeout = 60
graceful_timeout = 30
keepalive = 5
accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("GUNICORN_LOG_LEVEL", "info")
forwarded_allow_ips = "127.0.0.1"
proxy_protocol = False
