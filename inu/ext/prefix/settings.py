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


class BotSettings(lightbulb.Plugin):
    def __init__(self, bot: lightbulb.Bot):
        super().__init__()
        self.bot = bot

    @lightbulb.group()
    async def settings(self, ctx: Context):
        pass

    @lightbulb.check(lightbulb.owner_only)
    @settings.group(aliases=["daily"])
    async def daily_pictures(self, ctx: Context):
        pass

    @lightbulb.check(lightbulb.owner_only)
    @daily_pictures.command()
    async def add_channel(self, ctx: Context, channel_id: Optional[int] = None):
        """
        Adds <channel_id> to channels, where daily reddit stuff will be sent.
        
        Args:
        -----
            - [Optional] channel_id: (int, default: 'channel of this message') The channel you want to add 
        """
        if channel_id is None:
            channel_id = ctx.channel_id