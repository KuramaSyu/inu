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
from core import Inu, Table
from utils import InvokationStats, Reminders, TagManager
from core import getLogger

log = getLogger(__name__)
log.info(f"hikari version:{hikari.__version__}")
log.info(f"lightbulb version:{lightbulb.__version__}")

def main():
    log.info("Create Inu")
    inu = Inu()

    @inu.listen(hikari.StartingEvent)
    async def on_ready(event : hikari.StartingEvent):
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

    @inu.listen(lightbulb.LightbulbStartedEvent)
    async def on_bot_ready(event : lightbulb.LightbulbStartedEvent):
        table = Table("bot")
        record = await table.select_row(["key"], ["restart_count"])
        await event.bot.update_presence(
            status=hikari.Status.IDLE, 
            activity=hikari.Activity(
                name=record['value'],
            )
        )

    inu.run()

if __name__ == "__main__":
    main()
