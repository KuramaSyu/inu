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

import logging
import os
from pathlib import Path
import datetime

from colorama import init, Fore, Style

init()

msg_colors = {
    "TRACE": f"{Fore.WHITE}{Style.DIM}",
    "TRACE_HIKARI": f"{Fore.WHITE}{Style.DIM}",
    "DEBUG": f"{Fore.LIGHTBLUE_EX}{Style.NORMAL}",
    "INFO": f"{Fore.LIGHTMAGENTA_EX}{Style.NORMAL}",
    "WARNING": f"{Fore.YELLOW}{Style.BRIGHT}",
    "ERROR": f"{Fore.LIGHTRED_EX}{Style.BRIGHT}",
    "CRITICAL": f"{Fore.RED}{Style.BRIGHT}",
}
level_color = {
    "TRACE": f"{Fore.WHITE}{Style.DIM}",
    "TRACE_HIKARI": f"{Fore.WHITE}{Style.DIM}",
    "DEBUG": f"{Fore.LIGHTMAGENTA_EX}{Style.NORMAL}",
    "INFO": Fore.BLUE,
    "WARNING": Fore.YELLOW,
    "ERROR": Fore.LIGHTRED_EX,
    "CRITICAL": Fore.RED,
}
level_style = {
    "TRACE": f"{Fore.WHITE}{Style.DIM}",
    "TRACE_HIKARI": f"{Fore.WHITE}{Style.DIM}",
    "DEBUG": f"{Fore.LIGHTGREEN_EX}{Style.DIM}",
    "INFO": "",
    "WARNING": "",
    "ERROR": "",
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
    "": Fore.YELLOW
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
        date = datetime.datetime.now()
        time_stemp = date.strftime("%b %d %H:%M:%S")
        print(f"{level_color[level_name]}{level_style[level_name]}{level_name:<8}{Style.RESET_ALL}"
              f" "
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