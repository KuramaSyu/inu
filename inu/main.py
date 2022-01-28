"""The entrance point of the bot"""

from inspect import trace
import os
import asyncio
import logging
import traceback

from core import LoggingHandler
logging.setLoggerClass(LoggingHandler)

from dotenv import dotenv_values
import hikari
import lightbulb
from lightbulb import events
from core import Inu, Table
from utils import InvokationStats, Reminders, TagManager
from core import getLogger

log = getLogger(__name__)

def main():
    log.info("Create Inu")
    inu = Inu()

    @inu.listen(hikari.StartingEvent)
    async def on_ready(_: hikari.StartingEvent):
        try:
            await inu.init_db()
            InvokationStats.set_db(inu.db)
            await Reminders.init_bot(inu)
            TagManager.set_db(inu.db)
            log.info("initialized Invokationstats, Reminders and TagManager")
        except Exception:
            log.critical(f"Can't connect Database to classes: {traceback.format_exc()}")

        # update bot start value
        try:
            table = Table("bot")
            record = await table.select_row(["key"], ["restart_count"])
            if not record:
                count = 1
            else:
                count = int(record["value"])
                count += 1
            await table.upsert(["key", "value"], ["restart_count", str(count)])
            log.info(f'RESTART NUMBER: {(await table.select_row(["key"], ["restart_count"]))["value"]}')
        except Exception:
            log.error(traceback.format_exc())

        

    inu.run()

if __name__ == "__main__":
    main()
