# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright © 2017 ANSSI. All rights reserved.

"""Logging utility functions and helpers."""

import logging
import re
import sys
from typing import Any


# Logging helpers
def debug(msg: str) -> None:
    """Log a message as :py:data:`logging.DEBUG` level.

    :param msg: the message to log

    """

    from . import logger
    logger.debug(msg)

def info(msg: str) -> None:
    """Log a message as :py:data:`logging.INFO` level.

    :param msg: the message to log

    """
    from . import logger
    logger.info(msg)

def warn(msg: str) -> None:
    """Log a message as :py:data:`logging.WARNING` level.

    :param msg: the message to log

    """
    from . import logger
    logger.warn(msg)

def error(msg: str) -> None:
    """Log a message as :py:data:`logging.ERROR` level.

    :param msg: the message to log

    """
    from . import logger
    logger.error(msg)

def critical(msg: str) -> None:
    """Log a message as :py:data:`logging.CRITICAL` level.

    :param msg: the message to log

    """
    from . import logger
    logger.critical(msg)


def _create_logger(name: str) -> logging.Logger:
    """Create the logging.Logger intended to be used for the whole cosmk
    package and created in __init__."""

    logger = logging.getLogger(name)
    # consider all log messages at logger level, leaving filtering to handlers
    logger.setLevel(logging.DEBUG)

    # console handler:
    ch = logging.StreamHandler(sys.stderr)
    ch.setLevel(logging.INFO)
    cf = _FancyConsoleFormatter("%(msg)s", colorized=bool(sys.stderr.isatty()))
    ch.setFormatter(cf)
    logger.addHandler(ch)

    return logger

def _enable_debug_console() -> None:
    from . import logger
    for hdlr in logger.handlers:
        if isinstance(hdlr, logging.StreamHandler):
            hdlr.setLevel(logging.DEBUG)
            break

class _FancyConsoleFormatter(logging.Formatter):
    """Console formatter that use fancy prefixes on the standard output streams
    depending on the level of the message it processes."""

    prefixes = {
        logging.DEBUG: {
            False: " [-] ",
            True: " \x1b[32;1m[-]\x1b[0m ",
        },
        logging.INFO: {
            False: " [*] ",
            True: " \x1b[34;1m[*]\x1b[0m ",
        },
        logging.WARNING: {
            False: " [!] ",
            True: " \x1b[33;1m[!]\x1b[0m ",
        },
        logging.ERROR: {
            False: " [X] ",
            True: " \x1b[31;1m[X]\x1b[0m ",
        },
        logging.CRITICAL: {
            False: " [#] ",
            True: " \x1b[31;1m[#]\x1b[0m ",
        },
    }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        try:
            self.colorized = bool(kwargs["colorized"])
            kwargs.pop("colorized")
        except KeyError:
            self.colorized = False
        super().__init__(*args, **kwargs)

    def format(self, record: logging.LogRecord) -> str:
        try:
            prefix = self.prefixes[record.levelno][self.colorized]
        except KeyError:
            prefix = ''

        msg = super().format(record)
        if self.colorized and prefix:
            # get length of prefix without counting ANSI escape codes
            prefix_len = len(
                re.sub("\x1b"r"\[([0-9]{1,2}(;[0-9]{1,2})*)?[m|K]",
                       "", prefix))
            # Set everything in bold to differtiate visually what's coming from
            # cosmk or the SDKs scripts and the output of the commands launched
            # within SDKs:
            msg = "\x1b[1m" + msg.replace("\n", "\x1b[0m\n\x1b[1m") + "\x1b[0m"
            # and align with indentation created by prefix
            msg = msg.replace("\n", "\n" + " "*prefix_len)

        return prefix + msg
