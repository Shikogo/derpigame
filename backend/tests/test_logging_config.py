"""configure_logging: scoped to the app logger, idempotent, root left alone."""

import logging

import pytest

from app.logging_config import configure_logging


@pytest.fixture(autouse=True)
def restore_app_logger():
    """Keep the global ``app`` logger pristine for the rest of the suite."""
    app_logger = logging.getLogger("app")
    handlers, level = list(app_logger.handlers), app_logger.level
    yield
    app_logger.handlers[:] = handlers
    app_logger.setLevel(level)


def test_configures_the_app_logger_without_touching_root():
    root_handlers = list(logging.getLogger().handlers)

    configure_logging("DEBUG")

    app_logger = logging.getLogger("app")
    assert app_logger.level == logging.DEBUG
    assert len(app_logger.handlers) == 1
    assert logging.getLogger().handlers == root_handlers  # root untouched


def test_repeated_calls_do_not_stack_handlers():
    configure_logging("INFO")
    configure_logging("WARNING")  # e.g. create_app() called again in a test

    app_logger = logging.getLogger("app")
    assert len(app_logger.handlers) == 1  # cleared before re-adding
    assert app_logger.level == logging.WARNING
