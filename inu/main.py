"""The entrance point of the bot"""

import os
import asyncio
import logging

from utils.logging import LoggingHandler
logging.setLoggerClass(LoggingHandler)
log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

from dotenv import dotenv_values
import hikari
import lightbulb

from core import Inu

def main():

    conf = dotenv_values()
    for key, value in conf.items():
        print(f"name: {key}\nvalue: {value}")
    print(os.getcwd())
    logs = {
        "version": 1,
        "incremental": True,
        "loggers": {
            "hikari": {"level": "DEBUG"},
            "hikari.gateway": {"level": "DEBUG"},
            "hikari.ratelimits": {"level": "INFO"}, #TRACE_HIKARI
            "lightbulb": {"level": "DEBUG"},
        },
    }

    inu = Inu(
        prefix="inu-",
        token=conf["DISCORD_TOKEN"],
        intents=hikari.Intents.ALL,
        logs=logs,
    )
    logging.setLoggerClass(LoggingHandler)
    inu.run()

if __name__ == "__main__":
    main()
