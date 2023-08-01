"""The entrance point of the bot"""
import logging
import traceback
import time
import os

import aiohttp
from core import LoggingHandler
logging.setLoggerClass(LoggingHandler)

import miru
import hikari
import lightbulb
from core import Inu, Table
from utils import (
    InvokationStats, 
    Reminders, 
    TagManager, 
    PollManager, 
    Urban, 
    MyAnimeListAIOClient,
    CurrentGamesManager,
    BoardManager,
    set_bot,
    AutoroleManager
)
import lavasnek_rs
from core import getLogger


log = getLogger(__name__)
log.info(f"hikari version:{hikari.__version__}")
log.info(f"lightbulb version:{lightbulb.__version__}")
log.info(f"lavasnek-rs version:{lavasnek_rs.__version__}")
log.info(f"hikari-miru version:{miru.__version__}")

def main():
    log.info("Create Inu")
    inu = Inu()
    print(inu.conf)

    @inu.listen(lightbulb.LightbulbStartedEvent)
    async def sync_prefixes(event: hikari.ShardReadyEvent):
        await inu.db.execute_many(
            "INSERT INTO guilds (guild_id, prefixes) VALUES ($1, $2) ON CONFLICT DO NOTHING",
            [(guild, [inu._default_prefix]) for guild in inu.db.bot.cache.get_available_guilds_view()],
        )
        
        # remove guilds where the bot is no longer in
        stored = [guild_id for guild_id in await inu.db.column("SELECT guild_id FROM guilds")]
        member_of = inu.db.bot.cache.get_available_guilds_view()
        to_remove = [(guild_id,) for guild_id in set(stored) - set(member_of)]
        await inu.db.execute_many("DELETE FROM guilds WHERE guild_id = $1;", to_remove)
        records = await inu.db.fetch("SELECT * FROM guilds")
        for record in records:
            inu.db.bot._prefixes[record["guild_id"]] = record["prefixes"]
        log.debug("Synced Prefixes")

    @inu.listen(hikari.StartingEvent)
    async def on_ready(event : hikari.StartingEvent):
        try:
            await inu.init_db()
            InvokationStats.init_db(inu)
            await Reminders.init_bot(inu)
            TagManager.init_db(inu)
            await PollManager.init_bot(inu)
            Urban.init_bot(inu)
            await BoardManager.init_bot(inu)
            MyAnimeListAIOClient.set_credentials(inu.db.bot.conf.MAL.id)
            set_bot(inu)
            AutoroleManager.set_bot(inu)
            log.info("initialized Invokationstats, Reminders and TagManager")
        except Exception:
            log.critical(f"Can't connect Database to classes: {traceback.format_exc()}")

        # update bot start value
        try:
            table = Table("bot")
            record = await table.select_row(["key"], ["restart_count"])
            if not record:
                count = 0
            else:
                count = int(record["value"])
            count += 1
            inu.restart_num = count
            await table.upsert(["key", "value"], ["restart_count", str(count)])
            log.info(f'RESTART NUMBER: {(await table.select_row(["key"], ["restart_count"]))["value"]}')
        except Exception:
            log.error(traceback.format_exc())


    @inu.listen(lightbulb.LightbulbStartedEvent)
    async def on_bot_ready(event : lightbulb.LightbulbStartedEvent):
        table = Table("bot")
        record = await table.select_row(["key"], ["restart_count"])
        activity = str(record["value"])
        try:
            async with aiohttp.ClientSession() as session:
                resp = await session.get(f"http://numbersapi.com/{activity}")
                new_activity = (await resp.read()).decode("utf-8")
                activity = activity if len(activity) > len(new_activity) else new_activity
        except Exception:
            log.error(traceback.format_exc())
        await event.bot.update_presence(
            status=hikari.Status.IDLE, 
            activity=hikari.Activity(
                name=activity,
            )
        )


    # @inu.listen(lightbulb.events.CommandInvocationEvent)
    # async def on_event(event: lightbulb.events.CommandInvocationEvent):
    #     log.debug(
    #         (
    #             f"[{event.context.user.id}] {event.context.author.username} called {event.command.name}"
    #         )
    #     )
    
    stop = False
    while not stop:
        try:
            inu.run()
            print(f"Press Strl C again to exit")
            time.sleep(3)
        except KeyboardInterrupt:
            stop = True
            log.waring(f"Keyboard interrupt - stop session")
            break
        except Exception:
            log.critical(f"Bot crashed with critical Error:")
            log.critical(traceback.format_exc())
        finally:
            if not inu.conf.bot.reboot:
                stop = True
            else:
                log.info(f"Rebooting bot")
    log.info(f"Bot shutted down!")

if __name__ == "__main__":
    if os.name != "nt":
        import uvloop
        uvloop.install()
    main()
