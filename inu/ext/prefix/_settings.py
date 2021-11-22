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
from lightbulb import Context
from utils import DailyContentChannels
from core import Inu

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)


class BotSettings(lightbulb.Plugin):
    def __init__(self, bot: Inu):
        super().__init__()
        self.bot = bot
    
    @lightbulb.listener(hikari.ShardReadyEvent)
    async def on_ready(self, _: hikari.ShardReadyEvent):
        DailyContentChannels.set_db(self.bot.db)

    @lightbulb.group()
    async def settings(self, ctx: Context):
        pass

    @lightbulb.check(lightbulb.guild_only)
    @settings.group(aliases=["daily"])
    async def daily_pictures(self, ctx: Context):
        pass

    @lightbulb.check(lightbulb.guild_only)
    @daily_pictures.command()
    async def add_channel(self, ctx: Context):
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

    @lightbulb.check(lightbulb.guild_only)
    @daily_pictures.command()
    async def remove_channel(self, ctx: Context):
        """
        Removes <channel_id> from channels, where daily reddit stuff will be sent.
        """
        if not ctx.guild_id:
            return
        channel_id = ctx.channel_id
        if not (channel := await self.bot.rest.fetch_channel(channel_id)):
            await ctx.respond(f"cant remove this channel - channel not found", reply=True)
            return            
        await DailyContentChannels.remove_channel(channel_id, ctx.guild_id)
        await ctx.respond(f"removed channel: `{channel.name}` with id `{channel.id}`")

def load(bot: Inu):
    bot.add_plugin(BotSettings(bot))
        