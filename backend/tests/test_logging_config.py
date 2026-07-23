"""configure_logging: scoped to the app logger, idempotent, root left alone,
plus a health-check filter on uvicorn.access."""

import logging

import pytest

from app.logging_config import HealthCheckFilter, configure_logging


@pytest.fixture(autouse=True)
def restore_loggers():
    """Keep the global ``app`` and ``uvicorn.access`` loggers pristine."""
    app_logger = logging.getLogger("app")
    access_logger = logging.getLogger("uvicorn.access")
    app_state = (list(app_logger.handlers), app_logger.level)
    access_filters = list(access_logger.filters)
    yield
    app_logger.handlers[:], app_logger.level = app_state[0], app_state[1]
    access_logger.filters[:] = access_filters


def _access_record(path: str) -> logging.LogRecord:
    return logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname=__file__,
        lineno=0,
        msg='%s - "%s %s HTTP/%s" %d',
        args=("127.0.0.1:52111", "GET", path, "1.1", 200),
        exc_info=None,
    )


def test_configures_the_app_logger_without_touching_root():
    root_handlers = list(logging.getLogger().handlers)

    configure_logging("DEBUG")

    app_logger = logging.getLogger("app")
    assert app_logger.level == logging.DEBUG
    assert len(app_logger.handlers) == 1
    assert logging.getLogger().handlers == root_handlers  # root untouched


def test_repeated_calls_do_not_stack_handlers_or_filters():
    configure_logging("INFO")
    configure_logging("WARNING")  # e.g. create_app() called again in a test

    app_logger = logging.getLogger("app")
    assert len(app_logger.handlers) == 1  # cleared before re-adding
    assert app_logger.level == logging.WARNING

    access_filters = logging.getLogger("uvicorn.access").filters
    assert sum(isinstance(f, HealthCheckFilter) for f in access_filters) == 1


def test_health_filter_drops_only_the_health_path():
    filt = HealthCheckFilter()

    assert filt.filter(_access_record("/health")) is False
    assert filt.filter(_access_record("/rooms")) is True
