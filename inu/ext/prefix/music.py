import os
import typing
import asyncio

import hikari
from hikari import Embed
import lightbulb
from lightbulb import Context, command, check
import lavasnek_rs


class Music(lightbulb.Plugin):
    def __init__(self, bot: lightbulb.Bot):
        self.bot = bot
        self.os = "Windows"
        super().__init__()

    @check(lightbulb.guild_only())  # type: ignore
    @command()
    async def join(self, ctx: Context) -> None:
        '''
        Let a player join ur channel
        '''
        if self.os == "Windows":
            os.system('start data\\music\\start_lavalink.bat')
            await asyncio.sleep(6)

