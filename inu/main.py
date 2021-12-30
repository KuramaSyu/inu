"""The entrance point of the bot"""

import os
import asyncio
import logging
from asyncpg.exceptions import InsufficientPrivilegeError

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

from dotenv import dotenv_values
import hikari
import lightbulb
from lightbulb import events

from core import Inu
from utils import InvokationStats, Reminders

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

    inu = Inu()

    @inu.listen(hikari.ShardReadyEvent)
    async def on_ready(_: hikari.ShardReadyEvent):
        await inu.init_db()
        log.debug(inu.db.is_connected)
        InvokationStats.set_db(inu.db)
        await Reminders.init_bot(inu)
        

    inu.run()

if __name__ == "__main__":
    main()
