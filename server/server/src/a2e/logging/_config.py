import atexit
import logging
import logging.config
import logging.handlers
import queue
from sys import stderr, stdout

from typing_extensions import assert_never

from a2e.config import LoggingMode
from a2e.logging._filter import NonErrorFilter
from a2e.settings import Settings

from ._formatter import A2EJSONFormatter


def setup_logging() -> None:
    """
    Configures logging for the specified logging mode.
    """
    logging_mode = Settings.logging_mode
    if logging_mode is LoggingMode.DEFAULT:
        _setup_library_logging()
    elif logging_mode is LoggingMode.STRUCTURED:
        _setup_application_logging()
    else:
        assert_never(logging_mode)


def _setup_library_logging() -> None:
    """
    Configures logging if A2E is used as a library
    """
    logger = logging.getLogger("a2e")
    logger.setLevel(Settings.logging_level)
    db_logger = logging.getLogger("sqlalchemy")
    db_logger.setLevel(Settings.db_logging_level)
    logger.info("Default logging ready")


def _setup_application_logging() -> None:
    """
    Configures logging if A2E is used as an application
    """
    sql_engine_logger = logging.getLogger("sqlalchemy.engine.Engine")
    # Remove all existing handlers
    for handler in sql_engine_logger.handlers[:]:
        sql_engine_logger.removeHandler(handler)
        handler.close()

    a2e_logger = logging.getLogger("a2e")
    a2e_logger.setLevel(Settings.logging_level)
    a2e_logger.propagate = False  # Do not pass records to the root logger
    sql_logger = logging.getLogger("sqlalchemy")
    sql_logger.setLevel(Settings.db_logging_level)
    sql_logger.propagate = False  # Do not pass records to the root logger

    log_queue = queue.Queue()  # type:ignore
    queue_handler = logging.handlers.QueueHandler(log_queue)
    a2e_logger.addHandler(queue_handler)
    sql_logger.addHandler(queue_handler)

    fmt_keys = {
        "level": "levelname",
        "message": "message",
        "timestamp": "timestamp",
        "logger": "name",
        "module": "module",
        "function": "funcName",
        "line": "lineno",
        "thread_name": "threadName",
    }
    formatter = A2EJSONFormatter(fmt_keys=fmt_keys)

    # stdout handler
    stdout_handler = logging.StreamHandler(stdout)
    stdout_handler.setFormatter(formatter)
    stdout_handler.setLevel(Settings.logging_level)
    stdout_handler.addFilter(NonErrorFilter())

    # stderr handler
    stderr_handler = logging.StreamHandler(stderr)
    stderr_handler.setFormatter(formatter)
    stderr_handler.setLevel(logging.WARNING)

    queue_listener = logging.handlers.QueueListener(log_queue, stdout_handler, stderr_handler)
    if queue_listener is not None:
        queue_listener.start()
        atexit.register(queue_listener.stop)
    a2e_logger.info("Structured logging ready")
