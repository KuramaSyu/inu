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

from pyparsing import ParseException
import asyncpraw
import hikari
import lightbulb
from lightbulb.context import Context
from lightbulb import commands
import re


from core import getLogger, Inu, get_context, Bash, InuContext
from utils import Human, calc, evaluation2image

log = getLogger(__name__)


plugin = lightbulb.Plugin("Reddit things", include_datastore=True)

# storing the last answers of users, that it can be used later
last_ans: Dict[int, str] = {}

@plugin.listener(hikari.MessageCreateEvent)
async def on_message_create(event: hikari.MessageCreateEvent):
    await on_message(event)
    
@plugin.listener(hikari.MessageUpdateEvent)
async def on_message_update(event: hikari.MessageUpdateEvent):
    await on_message(event)

async def on_message(event: hikari.MessageCreateEvent | hikari.MessageUpdateEvent):
    message = event.message
    text = str(message.content).lower()
    if "artur ist dumm" in str(message.content).lower():
        return await artur_ist_dumm(message)
    elif "arthur ist dumm" in str(message.content).lower():
        return await message.respond("Artur wird ohne h geschrieben")
    elif text.startswith("="):
        base = None
        content = str(event.message.content)
        #log.debug(content)
        try:
            # extract base 
            base = re.findall(r"-(?:b|base)(?:[ ])?(\d|bin|dec|oct|hex)[ ]", content)[0]
            # remove base option from calculation
            content = re.sub(r"(-(?:b|base)(?:[ ])?(?:\d|bin|dec|oct|hex)[ ])", "", content, count=1)
        except (IndexError, TypeError):
            pass
        return await calc_msg(get_context(event), content, base)

async def artur_ist_dumm(message: hikari.PartialMessage):
    with open("inu//data/other/users/ar_is_stupid.txt", "r", encoding="utf-8") as file_:
        txt = file_.read()
        await message.respond(f"Ich weiß\n{txt}")

@plugin.command
@lightbulb.option("calculation", "e.g. 1+1; 2x + 10 = 40; ...")
@lightbulb.option("base", "base of the number e.g. bin or 2, oct or 8, hex or 16 etc.", default=None)
@lightbulb.command("calculate", "advanced calculator")
@lightbulb.implements(commands.SlashCommand)
async def qalc(ctx: Context):
    await calc_msg(
        ctx=get_context(ctx.event), 
        calculation=ctx.options["calculation"], 
        base=ctx.options["base"]
    )
    


async def calc_msg(ctx: InuContext, calculation: str, base: str | None = None):
    """base method for editing the calculation, calculating it, setting it as `last_ans` and finally sending it"""
    author_id: int = ctx.author.id
    calculation = replace_vars(
        calculation=prepare(calculation),
        author_id=author_id,
    ) 
    result = await calc(calculation, base=base)
        # add result to last_ans
    set_answer(
        result=result,
        author_id=author_id,
    )
    await send_result(ctx, result, calculation, base=base)


def prepare(calculation: str) -> str:
    """removes the equals sign at the beginning of the calculation, if there is one"""
    if calculation.startswith("="):
        calculation = calculation[1:]
    # treats '{string without space} / {string without space}' as one fracion. 
    # e.g. '4*5+4 / 2*3' -> '(4*5+4) / (2*3)'
    calculation = re.sub(r'([^ ]*) \/ ([^ ]*)', r'(\1) / (\2)', calculation)
    return calculation

def replace_vars(calculation: str, author_id: int) -> str:
    """replaces the `ans` word with the last answer of that user, taken from `last_ans[author_id]` """
    query = calculation
    if (last_answer := last_ans.get(author_id)):
        query = query.replace("ans", str(last_answer))
    else:
        query = query.replace("ans", "0")
    return query



async def send_result(ctx: InuContext, result: str, calculation: str, base: str | None):
    """sends the message with the result"""
    def prepare_for_latex(result: str) -> str:
        """prepares the result for latex"""
        result = result.replace("'", "") # remove number things for better readability
        if len(result.splitlines()) > 1 and "warning" in result[0]:
            result = result.split("\n")[-1] # remove warnings

        old_to_new = {
            "¹": "^1",
            "²": "^2",
            "³": "^3",
            "⁴": "^4",
            "⁵": "^5",
            "⁶": "^6",
            "⁷": "^7",
            "⁸": "^8",
            "⁹": "^9",
            "⁰": "^0",
            "−": "-",
            "√": "sqrt",
            "π": "pi",
            "×": "*",
            "÷": "/",
        }
        for old, new in old_to_new.items():
            result = result.replace(old, new)
        return result

    if len(result) > 100:
        embed = hikari.Embed(description=result)
    else:
        embed = hikari.Embed(title=result, description=f"```py\n{(calculation).strip()}```")
    if base:
        embed.set_footer(f"result with base {base}")
    try:
        image = evaluation2image(
            prepare_for_latex(
                result, 
            ),
            multiline= (len(result) > 50)
        )
        embed.set_image(image)
    except ParseException as e:
        log.warning(f"parsing failed:\n{e.explain()}")
    except Exception as e:
        log.warning(f"parsing {prepare_for_latex(result)} failed: {traceback.format_exc()}")
    await ctx.respond(embed=embed)






def set_answer(result: str, author_id) -> None:
    """
    Try to extract number from qalc answer and set it to `last_ans[author_id]`
    """
    if "=" in result:
        results = result.split("=")
        if len(results) > 2:
            # fractional format
            result = results[1]
        else:
            result = results[-1]
        
        if "≈" in result:
            result = result.split("≈")[0]
    if "≈" in result:
        result = result.split("≈")[0]
    try:
        # if (ans := re.findall("(\d+(?:\.\d+)?)", result.replace("'", ""))[0]):
        #     if result.strip().endswith("…"):  # result is periodic
        #         try:
        #             periodic_part = re.findall("\d+\.(\d+)…", result)[0]  # caputre the periodic part -> "1.333…" matches 333
        #             # add periodic part 20 times
        #             ans += str(periodic_part) * 20 
        #         except Exception:
        #             pass
        last_ans[author_id] = result
    except Exception:
        pass

def load(bot: lightbulb.BotApp):
    bot.add_plugin(plugin)
    
    
