from __future__ import annotations

import os


bind = os.getenv("GUNICORN_BIND", "unix:/run/wedding/wedding.sock")
workers = int(os.getenv("GUNICORN_WORKERS", "3"))
worker_class = "gthread"
threads = int(os.getenv("GUNICORN_THREADS", "2"))
timeout = int(os.getenv("GUNICORN_TIMEOUT", "45"))
graceful_timeout = 30
keepalive = 5
max_requests = 1000
max_requests_jitter = 100
preload_app = False
worker_tmp_dir = "/dev/shm"
umask = 0o007

# Access logging is intentionally disabled because private invite tokens appear
# in /invite/<token>. Nginx logs normal requests and suppresses /invite/ logs.
accesslog = None
errorlog = "-"
loglevel = os.getenv("LOG_LEVEL", "info").lower()
capture_output = True
