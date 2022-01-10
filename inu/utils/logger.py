import logging
import typing
from typing import (
    Mapping,
    Union,
)
from functools import wraps

LOG_LEVEL: Union[int, None] = logging.DEBUG
LOGFORMAT: str = "%(log_color)s%(levelname)-8s%(reset)s[%(name)-20s] %(log_color)s%(message)s%(reset)s"
LOG_COLORS: Mapping[str, str] = {
		'DEBUG':    'cyan',
		'INFO':     'green',
		'WARNING':  'yellow',
		'ERROR':    'red',
		'CRITICAL': 'purple',#,bg_white',
	}

from colorlog import ColoredFormatter
import traceback
import inspect
import logging

from core import getLogger

log = getLogger(__name__)


def build_logger(
    name: Union[str, None] = __name__,
    level: Union[int, None] = logging.DEBUG
    ) -> logging.Logger:
    """
    Returns a custom logger.
    If level is None: level wont be overridden
    """
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

def method_logger(reraise_exc: bool = True, only_log_on_error: bool = True):
    def decorator(*args):
        args = [*args]
        func = None
        for arg in args:
            if inspect.isfunction(arg) or inspect.ismethod(arg):
                func = arg
                args.remove(func)
        if func is None:
            raise RuntimeError(f"logging decorator didn't found a function in args")
        @wraps(func)
        def wrapper(*args, **kwargs):
            log = logging.getLogger(f"{__name__}.{func.__qualname__}")
            if not only_log_on_error:
                log.debug(f"{args =}; {kwargs =}")
            try:
                return_value = func(*args, **kwargs)
                if not only_log_on_error:
                    log.debug(f"returns: {return_value}")
                return return_value
            except Exception as e:
                if only_log_on_error:
                    log.debug(f"{args =}; {kwargs =}")
                log.exception(f"{traceback.format_exc()}")
                if reraise_exc:
                    raise e
                return None
        return wrapper
    return decorator
