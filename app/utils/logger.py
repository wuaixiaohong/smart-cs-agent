from __future__ import annotations

import logging
import sys


def setup_logger(name: str = "smart_cs_agent") -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    if not logger.handlers:
        fmt = logging.Formatter(
            "[%(asctime)s] %(levelname)-5s [%(name)s.%(funcName)s] %(message)s",
            datefmt="%m-%d %H:%M:%S",
        )
        h = logging.StreamHandler(sys.stdout)
        h.setLevel(logging.DEBUG)
        h.setFormatter(fmt)
        logger.addHandler(h)
    return logger


logger = setup_logger()
