"""The entrance point of the bot"""

from distutils import command
from inspect import trace
import os
import asyncio
import logging
import traceback

import aiohttp
from core import LoggingHandler
logging.setLoggerClass(LoggingHandler)

from dotenv import dotenv_values
import hikari
import lightbulb
from core import Inu, Table
from utils import InvokationStats, Reminders, TagManager, MyAnimeList
from core import getLogger

log = getLogger(__name__)
log.info(f"hikari version:{hikari.__version__}")
log.info(f"lightbulb version:{lightbulb.__version__}")

def main():
    log.info("Create Inu")
    inu = Inu()

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
        activity = record["value"]
        try:
            async with aiohttp.ClientSession() as session:
                resp = await session.get(f"http://numbersapi.com/{activity}")
                activity = (await resp.read()).decode("utf-8")
        except Exception:
            traceback.print_exc()
        await event.bot.update_presence(
            status=hikari.Status.IDLE, 
            activity=hikari.Activity(
                name=activity,
            )
        )
        # await event.bot.update_presence(
        #     status=hikari.Status.IDLE, 
        #     afk=True,
        # )
        # log.debug("start test")
        # try:
        #     anime = await MyAnimeList.fetch_anime_by_id(1)
        #     for k,v in anime.__dict__.items():
        #         log.debug(f"{k}={v}: {type(v)}")
        # except Exception:
        #     log.error(traceback.format_exc())

    # @inu.listen(hikari.PresenceUpdateEvent)
    # async def on_bot_ready(event : hikari.PresenceUpdateEvent):
    #     if event.user_id != inu.get_me().id:
    #         return
    #     else:
    #         await event.bot.update_presence(
    #             status=hikari.Status.IDLE, 
    #             afk=True,
    #         )

    @inu.listen(lightbulb.events.CommandInvocationEvent)
    async def on_event(event: lightbulb.events.CommandInvocationEvent):
        log.debug(
            (
                f"[{event.context.user.id}] {event.context.author.username} called {event.command.name}"
            )
        )

    inu.run()

if __name__ == "__main__":
    main()
