"""The entrance point of the bot"""
import logging
import traceback
import time
import os
import re
from pprint import pprint 

import aiohttp
from core import LoggingHandler
logging.setLoggerClass(LoggingHandler)

import miru
import hikari
import lightbulb
from lightbulb.ext import tasks
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
from utils import Human


log = getLogger(__name__)
log.info(f"hikari version:{hikari.__version__}")
log.info(f"lightbulb version:{lightbulb.__version__}")
log.info(f"lavasnek-rs version:{lavasnek_rs.__version__}")
log.info(f"hikari-miru version:{miru.__version__}")

def main():
    log.info("Create Inu")
    inu = Inu()
    tasks.load(inu)
    inu.conf.pprint()

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
        log.debug("Synced Prefixes", prefix="init")

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
            await table.upsert(where={"key": "restart_count", "value": str(count)})
            log.info(f'Number: {(await table.select_row(["key"], ["restart_count"]))["value"]}', prefix="init")
        except Exception:
            log.error(traceback.format_exc())


    @inu.listen(lightbulb.LightbulbStartedEvent)
    async def on_bot_ready(event : lightbulb.LightbulbStartedEvent):
        async def fetch_response(number: int):
            """Fetches a response from the numbersapi.com API"""
            async with aiohttp.ClientSession() as session:
                async with session.get(f"http://numbersapi.com/{number}") as resp:
                    return (await resp.read()).decode("utf-8")
                

        table = Table("bot")
        record = await table.select_row(["key"], ["restart_count"])
        activity = str(record["value"]) if record else 0
        bot_description = ""
        try:
            negative_answers = ["an uninteresting number", "a boring number", "we're missing a fact", "an unremarkable number"]
            number_fact = await fetch_response(int(activity))
            if any(answer in number_fact for answer in negative_answers):
                new_number = int(activity) % 100
                number_fact = (await fetch_response(new_number)).replace(str(new_number), "")
                pattern = re.compile(str(new_number) + r"\b")
                sub_number = pattern.sub(f"-{new_number}-", activity)
                bot_description = f"{sub_number}{' Well its looking empty this time' if len(activity) > len(number_fact) else number_fact}"
            else:
                bot_description = f"{number_fact}"
        except Exception:
            log.error(traceback.format_exc())
        log.info(f"Bot is online: {bot_description}", prefix="init")
        try:
            await event.bot.update_presence(
                status=hikari.Status.IDLE, 
                activity=hikari.Activity(
                    name=f"Restart Nr {activity}",
                    state=Human.short_text(bot_description, 128),
                    type=hikari.ActivityType.CUSTOM
                )
            )
        except Exception:
            log.error(f"failed to set presence: {traceback.format_exc()}", prefix="start")

    
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
