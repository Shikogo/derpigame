"""One-call logging setup.

Attaching our handler to ``app`` rather than the root keeps our records apart
from uvicorn's own access/error logging and from third-party noise (httpx,
socketio) — only ``app.*`` loggers flow through it. Propagation stays on so
pytest's ``caplog`` still captures. Clearing handlers first makes it idempotent,
so the repeated ``create_app()`` calls in the test suite don't stack handlers.

We also mute uvicorn's per-request access log for ``/health``: platform health
checks hit it constantly and carry no signal, and uvicorn logs every request
through one INFO-level logger with no per-path level, so a filter is the only
surgical way to silence just that path.
"""

import logging
import sys

_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
_HEALTH_PATH = "/health"


class HealthCheckFilter(logging.Filter):
    """Drop uvicorn access records for the health endpoint."""

    def filter(self, record: logging.LogRecord) -> bool:
        # uvicorn.access args: (client_addr, method, path, http_version, status)
        args = record.args
        return not (isinstance(args, tuple) and len(args) >= 3 and args[2] == _HEALTH_PATH)


def configure_logging(level: str = "INFO") -> None:
    app_logger = logging.getLogger("app")
    app_logger.setLevel(level)
    app_logger.handlers.clear()
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(_FORMAT))
    app_logger.addHandler(handler)

    # Idempotent: drop any prior instance before re-adding, so repeated
    # create_app() calls don't stack duplicate filters.
    access_logger = logging.getLogger("uvicorn.access")
    access_logger.filters = [
        f for f in access_logger.filters if not isinstance(f, HealthCheckFilter)
    ]
    access_logger.addFilter(HealthCheckFilter())
