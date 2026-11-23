"""HTTPS server process for browser tests. Closing its stdin requests shutdown."""

import os
from pathlib import Path
import sys
from threading import Thread

import uvicorn

from backend.cli import tls_pair
from backend.worker_process import worker_process


def main():
    cert, key = tls_pair(Path(sys.argv[2]))
    server = uvicorn.Server(uvicorn.Config(
        "backend.api.app:create_app", factory=True, host="127.0.0.1", port=int(sys.argv[1]),
        ssl_certfile=str(cert), ssl_keyfile=str(key),
    ))
    def stop_on_eof():
        sys.stdin.buffer.read()
        server.should_exit = True

    Thread(target=stop_on_eof, daemon=True).start()
    with worker_process(os.environ["ATES_DATABASE_URL"], enabled=os.environ["ATES_TEST_START_WORKER"] == "1"):
        server.run()


if __name__ == "__main__":
    main()
