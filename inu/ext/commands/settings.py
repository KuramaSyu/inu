import asyncio
import typing
from typing import (
    List,
    Dict,
    Any,
    Optional
)
import logging

import hikari
import lightbulb
from lightbulb.context import Context
from lightbulb import commands
from utils import DailyContentChannels
from core import Inu

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)


plugin = lightbulb.Plugin("Settings", "Commands, to change Inu's behavior to certain things")
    
@plugin.listener(hikari.ShardReadyEvent)
async def on_ready(_: hikari.ShardReadyEvent):
    DailyContentChannels.set_db(plugin.bot.db)

@plugin.command
@lightbulb.add_checks(lightbulb.guild_only)
@lightbulb.command("settings", "Settings to chagne how cretain things are handled")
@lightbulb.implements(commands.PrefixCommandGroup, commands.SlashCommandGroup)
async def settings(ctx: Context):
    pass

@settings.child
@lightbulb.command("daily_pictures", "Settings to the daily pictures I send. By default I don't send pics", aliases=["dp"])
@lightbulb.implements(commands.SlashSubGroup, commands.PrefixSubGroup)
async def daily_pictures(ctx: Context):
    pass

@daily_pictures.child
@lightbulb.add_checks(lightbulb.guild_only)
@lightbulb.command("add_channel", "Adds the channel where you are in, to a channel where I send pictures")
@lightbulb.implements(commands.PrefixSubCommand, commands.SlashSubCommand)
async def add_channel(ctx: Context):
    """
    Adds <channel_id> to channels, where daily reddit stuff will be sent.
    """
    if not ctx.guild_id:
        return
    channel_id = ctx.channel_id
    channel = ctx.get_channel()
    if not channel:
        await ctx.respond("I am not able to add this channel :/", reply=True)
        return
    await DailyContentChannels.add_channel(channel_id, ctx.guild_id)
    await ctx.respond(f"added channel: `{channel.name}` with id `{channel.id}`")

@daily_pictures.child
@lightbulb.add_checks(lightbulb.guild_only)
@lightbulb.command("rm_channel", "Removes the channel you are in form daily content channels", aliases=["remove_channel"])
@lightbulb.implements(commands.SlashSubGroup, commands.PrefixSubGroup)
async def remove_channel(ctx: Context):
    """
    Removes <channel_id> from channels, where daily reddit stuff will be sent.
    """
    if not ctx.guild_id:
        return
    channel_id = ctx.channel_id
    if not (channel := await plugin.bot.rest.fetch_channel(channel_id)):
        await ctx.respond(f"cant remove this channel - channel not found", reply=True)
        return            
    await DailyContentChannels.remove_channel(channel_id, ctx.guild_id)
    await ctx.respond(f"removed channel: `{channel.name}` with id `{channel.id}`")

def load(bot: Inu):
    bot.add_plugin(plugin)
        