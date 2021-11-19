"""The entrance point of the bot"""

import os
import asyncio
import logging

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

from dotenv import dotenv_values
import hikari
import lightbulb

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

    inu = lightbulb.BotApp(
        prefix="inu-",
        token=str(conf["DISCORD_TOKEN"]),
        intents=hikari.Intents.ALL,
        logs=logs,
    )
    
    inu.load_extensions("ext.prefix.basic_commands")
    inu.run()

if __name__ == "__main__":
    main()
