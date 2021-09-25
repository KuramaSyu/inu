from contextlib import suppress
import random
import asyncio
from typing import (
    Union,
    Optional,
)
import traceback

import hikari
import lightbulb
from lightbulb import events, plugins, Context, errors

from core import Inu
from utils import build_logger

log = build_logger(__name__)


class ErrorHandler(lightbulb.Plugin):
    def __init__(self, bot: Inu):
        self.bot = bot
        super().__init__(name="ErrorHander")

    @plugins.listener(events.CommandErrorEvent)
    async def on_error(self, event: events.CommandErrorEvent):
        """The event triggered when an error is raised while invoking a command.
        Parameters
        ------------
        ctx: commands.Context
            The context used for command invocation.
        error: commands.CommandError
            The Exception raised.
        """
        ctx: Optional[Context] = event.context

        error = event.exception

        if isinstance(error, errors.CommandNotFound):
            embed = hikari.Embed()
            embed.title = "404 Not Found"
            embed.description = f"No command called '{error.invoked_with}' found"
            return await event.message.respond(embed=embed, reply=True)
            

        if ctx is None:
            log.debug("Exception uncaught")
            return

        def check(event: hikari.ReactionAddEvent):
            if event.user_id != self.bot.me.id and event.message_id == message.id:
                return True
            return False

        error_embed = hikari.Embed()
        error_embed.title = random.choice(['ERROR', '3RR0R'])
        error_embed.description = f'{error}'

        message = await ctx.respond(embed = error_embed)
        for reaction in ['🍭', '❔']:
            await message.add_reaction(reaction)
        try:
            e: hikari.ReactionAddEvent = await self.bot.wait_for(
                hikari.ReactionAddEvent,
                timeout=int(60*10),
                predicate=check,
            )
        except asyncio.TimeoutError:
            await message.remove_all_reactions()
            return
        if str(e.emoji_name) == '🍭':
            error_embed.set_author(
                name=f'Invoked by: {ctx.member.display_name if ctx.member else ctx.author.username}',
                url=str(ctx.author.avatar_url)
            )
            traceback_list = traceback.format_tb(error.__traceback__)
            error_embed.add_field(
                name=f'{str(error.__class__)[8:-2]}',
                value=f'Error:\n{error}',
                )
            for index, tb in enumerate(traceback_list):
                error_embed.add_field(
                    name=f'Traceback - layer {index + 1}',
                    value=f'```python\n{tb}```',
                    inline=False
                )
            await message.edit(embed=error_embed)
            await message.remove_all_reactions()

        elif str(e.emoji_name) == '❔':
            help_cog = self.bot.get_plugin("Help")
            if not help_cog: print("no help"); return;
            for cmd in help_cog.walk_commands():
                if cmd.method_name == "help":
                    await cmd.callback(help_cog, ctx, ctx.invoked_with) #type: ignore
                    await message.remove_all_reactions()


def load(bot: Inu):
    bot.add_plugin(ErrorHandler(bot))
