from __future__ import division
import asyncio
import traceback
import typing
from typing import (
    List,
    Dict,
    Any,
    Optional,
    Union
)
import time as tm
import random
import logging

import asyncpraw
import hikari
import lightbulb
from lightbulb.context import Context
from lightbulb import commands
import re


from core import getLogger
from utils import Human, calc

log = getLogger(__name__)


plugin = lightbulb.Plugin("Reddit things", include_datastore=True)

# storing the last answers of users, that it can be used later
last_ans = {}

@plugin.listener(hikari.MessageCreateEvent)
async def on_message_create(event: hikari.MessageCreateEvent):
    await on_message(event.message)
    
@plugin.listener(hikari.MessageUpdateEvent)
async def on_message_update(event: hikari.MessageUpdateEvent):
    await on_message(event.message)

async def on_message(message: hikari.PartialMessage):
    text = str(message.content).lower()
    if "artur ist dumm" in str(message.content).lower():
        return await artur_ist_dumm(message)
    elif "arthur ist dumm" in str(message.content).lower():
        return await message.respond("Artur wird ohne h geschrieben")
    elif text.startswith("="):
        return await calc_msg(message)

async def artur_ist_dumm(message: hikari.PartialMessage):
    with open("inu//data/other/users/ar_is_stupid.txt", "r", encoding="utf-8") as file_:
        txt = file_.read()
        await message.respond(f"Ich weiß\n{txt}")

async def calc_msg(message: hikari.PartialMessage):
    if not message.content.startswith("="):
        return
    try:
        query = message.content
        if (last_answer := last_ans.get(message.author.id)):
            query = query.replace("ans", str(last_answer))
        else:
            query = query.replace("ans", "0")
            
        result = await calc(query)
        # add result to last_ans
        if (ans := re.findall("(\d+(?:\.\d+)?)", result.replace("'", ""))[0]):
            if result.strip().endswith("…"):  # result is periodic
                try:
                    periodic_part = re.findall("\d+\.(\d+)…", result)[0]  # caputre the periodic part -> "1.333…" matches 333
                    # add periodic part 20 times
                    ans += str(periodic_part) * 20 
                except:
                    pass
            last_ans[message.author.id] = ans
        if len(result) > 100:
            await message.respond(
                hikari.Embed(description=result)
            )
        else:
            await message.respond(
                hikari.Embed(title=result, description=f"```py\n{(message.content[1:]).strip()}```"),
            )
    except:
        log.debug(traceback.format_exc())
        

def load(bot: lightbulb.BotApp):
    bot.add_plugin(plugin)
    
    
