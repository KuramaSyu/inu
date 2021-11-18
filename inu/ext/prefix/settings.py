import asyncio
import typing
from typing import (
    List,
    Dict,
    Any,
    Optional
)

import hikari
import lightbulb
from lightbulb import Context
from utils import DailyContentChannels
from core import Inu


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
    async def add_channel(self, ctx: Context, channel_id: Optional[int] = None):
        """
        Adds <channel_id> to channels, where daily reddit stuff will be sent.
        
        Args:
        -----
            - [Optional] channel_id: (int, default: 'channel of this message') The channel you want to add 
        """
        if not ctx.guild_id:
            return
        if channel_id is None:
            channel_id = ctx.channel_id
        await DailyContentChannels.add_channel(channel_id, ctx.guild_id)

    @lightbulb.check(lightbulb.guild_only)
    @daily_pictures.command()
    async def remove_channel(self, ctx: Context, channel_id: Optional[int] = None):
        """
        Removes <channel_id> from channels, where daily reddit stuff will be sent.
        
        Args:
        -----
            - [Optional] channel_id: (int, default: 'channel of this message') The channel you want to remove 
        """
        if not ctx.guild_id:
            return
        if channel_id is None:
            channel_id = ctx.channel_id
        await DailyContentChannels.remove_channel(channel_id, ctx.guild_id)

def load(bot: Inu):
    bot.add_plugin(BotSettings(bot))
        