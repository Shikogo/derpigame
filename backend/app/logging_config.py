"""One-call logging setup, scoped to the ``app`` logger.

Attaching the handler to ``app`` rather than the root keeps our records apart
from uvicorn's own access/error logging and from third-party noise (httpx,
socketio) — only ``app.*`` loggers flow through it. Propagation stays on so
pytest's ``caplog`` still captures. Clearing handlers first makes it idempotent,
so the repeated ``create_app()`` calls in the test suite don't stack handlers.
"""

import logging
import sys

_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def configure_logging(level: str = "INFO") -> None:
    app_logger = logging.getLogger("app")
    app_logger.setLevel(level)
    app_logger.handlers.clear()
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(_FORMAT))
    app_logger.addHandler(handler)
