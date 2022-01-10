"""The entrance point of the bot"""

import os
import asyncio
import logging

from core._logging import LoggingHandler
logging.setLoggerClass(LoggingHandler)

from dotenv import dotenv_values
import hikari
import lightbulb
from lightbulb import events
logging.setLoggerClass(LoggingHandler)
from core import Inu
from utils import InvokationStats, Reminders, Table
from core import getLogger

log = getLogger(__name__)

def main():

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
        # init all db classes
        logging.setLoggerClass(LoggingHandler)
        await inu.init_db()
        InvokationStats.set_db(inu.db)
        await Reminders.init_bot(inu)

        # update bot start value
        table = Table("bot", do_log=False)
        record = await table.select_row(["key"], ["restart_count"])
        if not record:
            count = 1
        else:
            count = int(record["value"])
            count += 1
        await table.upsert(["key", "value"], ["restart_count", str(count)])
        log.info(f'RESTART NUMBER: {(await table.select_row(["key"], ["restart_count"]))["value"]}')
        

        

    inu.run()

if __name__ == "__main__":
    main()
