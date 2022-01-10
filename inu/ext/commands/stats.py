import typing
from typing import (
    Union,
    Optional,
    List,
)
import asyncio
import logging

from hikari import ActionRowComponent, Embed, MessageCreateEvent, embeds
from hikari.messages import ButtonStyle
from hikari.impl.special_endpoints import ActionRowBuilder
from hikari.events import InteractionCreateEvent
import lightbulb
import lightbulb.utils as lightbulb_utils
from lightbulb import events, commands, context
import hikari
from numpy import isin

from utils import InvokationStats
from utils import Colors

# from utils.logging import LoggingHandler
# logging.setLoggerClass(LoggingHandler)

from core import getLogger

log = getLogger(__name__)

plugin = lightbulb.Plugin("Stats", "Extends the commands with statistic commands", include_datastore=True)

@plugin.listener(lightbulb.events.CommandCompletionEvent)
async def on_cmd_invoce(event: events.CommandInvocationEvent):
    log.debug(f"{event.command.name} invoked by {event.context.author.username}")
    await InvokationStats.add_or_sub(event.command.qualname, event.context.guild_id, 1)

@plugin.command
@lightbulb.command("stats", "Command invokation infos")
@lightbulb.implements(commands.SlashCommandGroup, commands.PrefixCommandGroup)
async def stats(ctx: context.Context):
    await guild_stats.callback(ctx)

@stats.child
@lightbulb.command("global", "the command stats for all guilds where I am in")
@lightbulb.implements(commands.PrefixSubCommand, commands.SlashSubCommand)
async def global_stats(ctx: context.Context):
    json_ = await InvokationStats.fetch_global_json()
    await send_formated_json(ctx, json_)

@stats.child
@lightbulb.command("guild", "the command stats for this guild")
@lightbulb.implements(commands.PrefixSubCommand, commands.SlashSubCommand)
async def guild_stats(ctx: context.Context):
    json_ = await InvokationStats.fetch_json(ctx.guild_id)
    await send_formated_json(ctx, json_)

async def send_formated_json(ctx: context.Context, json_: dict):
    embed = hikari.Embed(title="Command stats", description="")
    embed.color = Colors.random_color()
    cmd_list = []
    for command, value in json_.items():
        cmd_list.append({command: value})
    cmd_list.sort(key=lambda d: [*d.values()][0], reverse=True)
    for d in cmd_list:
        for command, value in d.items():
            embed.description += f"**{command}**: {value}x\n"
    await ctx.respond(embed=embed)

def load(bot: lightbulb.BotApp):
    bot.add_plugin(plugin)
