import logging
import typing
from typing import (
    Mapping,
    Union,
)

LOG_LEVEL: Union[logging._Level, int, None] = logging.DEBUG
LOGFORMAT: str = "%(log_color)s%(levelname)-8s%(reset)s[%(name)-20s] %(log_color)s%(message)s%(reset)s"
LOG_COLORS: Mapping[str, str] = {
		'DEBUG':    'cyan',
		'INFO':     'green',
		'WARNING':  'yellow',
		'ERROR':    'red',
		'CRITICAL': 'purple',#,bg_white',
	}

from colorlog import ColoredFormatter


def build_logger(
    name: str=__name__,
    level: Union[logging._Level, int, None]=logging.DEBUG
    ) -> logging.Logger:
    """Returns a custom logger"""
    logger = logging.getLogger(name)
    if level:
        logger.setLevel(level)
    console_handler = logging.StreamHandler()
    if level:
        console_handler.setLevel(level)
    file_handler = logging.FileHandler("inu.log", mode="a")
    if level:
        file_handler.setLevel(level)

    # formatter = logging.Formatter(
    #     fmt="{levelname} - {asctime} in {name}:\n{message}",
    #     datefmt="%b %d %H:%M:%S",
    #     style="{"
    # )

    formatter = logging.Formatter(
        fmt="%(levelname)-8s [%(name)-20s] %(asctime)s: %(message)s",
        datefmt="%b %d %H:%M:%S",
    )
    file_handler.setFormatter(formatter)
    #console_handler.setFormatter(formatter)

    console_handler.setFormatter(ColoredFormatter(LOGFORMAT, log_colors=LOG_COLORS,))

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    return logger

