"""The entrance point of the bot"""

import os
import asyncio

from dotenv import dotenv_values
import hikari
import lightbulb

from utils import build_logger
from core import Inu

def main():
    log = build_logger()

    conf = dotenv_values()
    for key, value in conf.items():
        print(f"key: {key}\nvalue: {value}")
    print(os.getcwd())
    logs = {
        "version": 1,
        "incremental": True,
        "loggers": {
            "hikari": {"level": 0},
            "hikari.ratelimits": {"level": 0}, # TRACE_HIKARI
            "lightbulb": {"level": 0},
        },
    }

    inu = Inu(
        prefix="inu-",
        token=conf["DISCORD_BOT_TOKEN"],
        intents=hikari.Intents.ALL,
        logs=logs,
    )

    inu.run()

if __name__ == "__main__":
    main()
