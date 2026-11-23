"""Run the independent worker with the same lifecycle as the local HTTPS server."""

from contextlib import contextmanager
import os
import subprocess
import sys

from backend.data.database import ROOT


@contextmanager
def worker_process(url, enabled=True):
    if not enabled:
        yield
        return
    environment = dict(os.environ, ATES_DATABASE_URL=url, ATES_WORKER_STDIN="1", PYTHONUNBUFFERED="1")
    process = subprocess.Popen([sys.executable, "-m", "backend.worker"], stdin=subprocess.PIPE,
                               cwd=ROOT, env=environment)
    try:
        yield
    finally:
        process.stdin.close()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.terminate()
            process.wait(timeout=5)

