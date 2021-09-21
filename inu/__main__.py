import os
import asyncio

from dotenv import dotenv_values
import hikari
import lightbulb

from utils import build_logger
from core import Inu

log = build_logger()

conf = dotenv_values()
for key, value in conf.items():
    print(f"key: {key}\nvalue: {value}")
print(os.getcwd())
logs = {
    "version": 1,
    "incremental": True,
    "loggers": {
        "hikari": {"level": "DEBUG"},
        "hikari.ratelimits": {"level": "TRACE_HIKARI"},
        "lightbulb": {"level": "DEBUG"},
    },
}

inu = Inu(
    prefix="inu-",
    token=conf["DISCORD_BOT_TOKEN"],
    intents=hikari.Intents.ALL,
    logs=logs,
)

logger = build_logger(name=None, level=None)
inu.run()