"""
Copyright 2021 crazygmr101
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated 
documentation files (the "Software"), to deal in the Software without restriction, including without limitation the 
rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit 
persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the 
Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE 
WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR 
COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR 
OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""
# edited
from typing import *
import logging
import os
import inspect
from pathlib import Path
from datetime import datetime, timedelta
from typing import *
from functools import wraps
import asyncio

from colorama import init, Fore, Style
from . import ConfigProxy, ConfigType
import colorlog



init()
main_log = logging.getLogger("core.logging")
main_log.setLevel(logging.DEBUG)
config = ConfigProxy(ConfigType.YAML)
#print(config.sections)

msg_colors = {
    "TRACE": f"{Fore.WHITE}{Style.DIM}",
    "TRACE_HIKARI": f"{Fore.LIGHTCYAN_EX}{Style.DIM}",
    "DEBUG": f"{Fore.LIGHTBLUE_EX}{Style.NORMAL}",
    "INFO": f"{Fore.LIGHTMAGENTA_EX}{Style.NORMAL}",
    "WARNING": f"{Fore.YELLOW}{Style.BRIGHT}",
    "ERROR": f"{Fore.LIGHTRED_EX}{Style.BRIGHT}",
    "CRITICAL": f"{Fore.RED}{Style.BRIGHT}",
}
level_color = {
    "TRACE": f"{Fore.WHITE}{Style.DIM}",
    "TRACE_HIKARI": f"{Fore.LIGHTCYAN_EX}{Style.DIM}",
    "DEBUG": f"{Fore.LIGHTMAGENTA_EX}{Style.NORMAL}",
    "INFO": Fore.BLUE,
    "WARNING": Fore.YELLOW,
    "ERROR": Fore.LIGHTRED_EX,
    "CRITICAL": Fore.RED,
}
level_style = {
    "TRACE": f"{Fore.WHITE}{Style.DIM}",
    "TRACE_HIKARI": f"{Fore.LIGHTCYAN_EX}{Style.DIM}",
    "DEBUG": f"{Fore.LIGHTGREEN_EX}{Style.DIM}",
    "INFO": f"{Style.BRIGHT}",
    "WARNING": f"{Style.BRIGHT}",
    "ERROR": f"{Style.BRIGHT}",
    "CRITICAL": Style.BRIGHT,
}
color_patterns = {
    "yougan": Fore.GREEN,
    "ptero": Fore.BLUE,
    "hikari.bot": Fore.MAGENTA,
    "hikari.gateway": Fore.MAGENTA,
    "discord.http": Fore.RED,
    "": Fore.BLUE,
    "lightbulb": Fore.BLUE,
}

color_patterns_cache = {
    "": Fore.YELLOW,
    "datetime": f"{Fore.LIGHTBLUE_EX}{Style.NORMAL}"
}

ignored = {
    "yougan-websocket": [
        "Unknown op %s recieved from Node::%s"
    ]
}

class LoggingHandler(logging.Logger):
    def handle(self, record: logging.LogRecord) -> None:
        # if record.msg in ignored.get(record.name, ()):
        #     return
        module = record.name
        level = record.levelno  # noqa F841
        level_name = record.levelname
        try:
            message = record.msg % record.args
        except Exception:
            message = record.msg
        date = datetime.now()
        time_stemp = date.strftime("%b %d %H:%M:%S")
        now = datetime.now()
        print(f"{level_color[level_name]}{level_style[level_name]}{level_name:<8}{Style.RESET_ALL}"
              f" "
              f"{self._get_color('datetime')}[{time_stemp:<8}]{Style.RESET_ALL} "
              f"{Style.BRIGHT}{self._get_color(module)}{module:<20}{Style.RESET_ALL} " +
              f"» "
              f"{msg_colors[level_name]}{message}{Style.RESET_ALL}")

        with open(f"{os.getcwd()}/inu/inu.log", "a", encoding="utf-8") as log_file:
            log_entry = f"{level_name:<8}[{module:<20}] [{time_stemp:<8}] {str(message)}\n"
            log_file.write(log_entry)

    # noinspection PyMethodMayBeStatic
    def _get_color(self, name: str) -> str:
        """get color for the module name"""
        if name in color_patterns_cache:
            return color_patterns_cache[name]
        for nm, color in color_patterns.items():
            if name.startswith(nm):
                color_patterns_cache[name] = color
                return color
        return color_patterns[""]

def stopwatch(
    note: Optional[str | Callable[[], str]] = None, 
    mention_method: bool = False
):
    def decorator(
        func: Callable
    ):
        def log_text(start: datetime):
            log = getLogger(func.__name__)
            text = f"[{(datetime.now() - start).total_seconds()*1000:.0f} ms] "
            if not note or mention_method:
                text += f"({func.__qualname__}) "
            if note:
                if inspect.isfunction(note):
                    text += note()
                else:
                    text += note
            log.warning(text)
        
        if asyncio.iscoroutinefunction(func):
            log.warning("is coro")
            @wraps(func)  # type: ignore
            async def wrapper(*args, **kwargs):
                start = datetime.now()
                val = await func(*args, **kwargs)
                log_text(start)
                return val
        else:
            start = datetime.now()
            @wraps(func)  # type: ignore
            def wrapper(*args, **kwargs):
                log.warning("is not coro")
                val = func(*args, **kwargs)
                log_text(start)
                return val     
        return wrapper
    return decorator
            

logs = set()
def getLogger(*names):
    """
    returns the logger and the level from the corresponding config.ini file

    Priorities:
    -----------
        - func over class
        - class over file
        - file over global
    """
    name = f"{'.'.join(names)}"
    logging.setLoggerClass(LoggingHandler)
    log = logging.getLogger(name)
    level = getLevel(list(name.split(".")))
    log.setLevel(level)
    if name not in logs:
        logs.add(name)
        main_log.debug(f"set level for {name} to {level}")
    return log

def getLevel(name_s: Union[List, str], log4file: bool = False):
    # to implement:
    # level will be min(logging, file_logging)
    # recheck logging level in Logger.handle()
    logging_section = config.file_logging if log4file else config.logging
    if isinstance(name_s, list):
        count = len(name_s)
        name = f"{'.'.join(name_s)}"
    else:
        name = name_s
        name_s = name.split(".")
        count = 1
    level = logging_section.get(name.lower(), None)
    #print(name, level)
    while level is None and count >= 1:
        level = logging_section.get(f"{'.'.join(name_s[:count])}", None)
        count -= 1
        # print(f"{'.'.join(name_s[:count])}", level)
    if level is None:
        level = logging_section.GLOBAL
    return level

colorlog.getLogger = getLogger
log = colorlog.getLogger("colorlog")
log.setLevel("INFO")
log.info("changed colorlog getLogger method")
main_log = colorlog.getLogger("colorlog")
main_log.setLevel("INFO")
# logging.getLogger = getLogger
# log.info("changed logging.getLogger method")
