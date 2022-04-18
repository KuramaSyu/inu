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
    # text = str(message.content)
    # try:
    #     text = (
    #         text
    #         .lower()
    #         .replace("x", "*")
    #         .replace(" ", "")
    #         .replace(":", "/")
    #         .replace(",", ".")
    #     )
    #     if text.startswith("="):
    #         text = text[1:]
    #     calculator = NumericStringParser()
    #     result = Human.number(str(calculator.eval(text)))
    #     result = result[:-2] if result.endswith(".0") and not "," in result else result
    try:
        result = await calc(message.content)
        if len(result) > 100:
            await message.respond(
                hikari.Embed(description=result)
            )
        else:
            await message.respond(
                hikari.Embed(title=result)
            )
    except:
        return
        

def load(bot: lightbulb.BotApp):
    bot.add_plugin(plugin)
    
    
