from contextlib import suppress
import logging
import random
import asyncio
from typing import (
    Union,
    Optional,
)
import traceback

import hikari
import lightbulb
from lightbulb import events, errors
from lightbulb.context import Context

from core import Inu
from .inu_help import OutsideHelp

from core import getLogger

log = getLogger(__name__)


pl = lightbulb.Plugin("Error Handler")


@pl.listener(events.CommandErrorEvent)
async def on_error(event: events.CommandErrorEvent):
    """
    The event triggered when an error is raised while invoking a command.
    Parameters
    ------------
    error: commands.CommandError
        The Exception raised.
    """

    ctx: Optional[Context] = event.context

    if ctx is None:
        log.debug("Exception uncaught: {event}")
        return

    if ctx.prefix == "":
        return

    error = event.exception
    channel_id = event.context.get_channel()
    rest = pl.bot.rest
    if isinstance(event, events.PrefixCommandErrorEvent):
        message_id = event.context.event.message_id


    async def message_dialog(error_embed: hikari.Embed):
        message = await (await ctx.respond(embed = error_embed)).message()

        def check(event: hikari.ReactionAddEvent):
            if event.user_id != pl.bot.me.id and event.message_id == message.id:
                return True
            return False
        
        for reaction in ['❔']:
            await message.add_reaction(reaction)
        if int(pl.bot.conf.bot.owner_id) == ctx.user.id:
            await message.add_reaction("🍭")
        try:
            e: hikari.ReactionAddEvent = await pl.bot.wait_for(
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
            traceback_list = traceback.format_exception(*event.exc_info)
            if len(traceback_list) > 0:
                log.warning(str("\n".join(traceback_list)))
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
            await OutsideHelp.search(ctx.invoked_with, ctx)
            await message.remove_all_reactions()
        return

    if isinstance(error, errors.CommandNotFound):
        embed = hikari.Embed()
        embed.title = "Not Found"
        embed.description = f"No command called '{error.invoked_with}' found"
        return await message_dialog(embed)
        

    else:
        error_embed = hikari.Embed()
        error_embed.title = random.choice(['ERROR', '3RR0R'])
        error_embed.description = f'{str(error) if len(str(error)) < 2000 else str(error)[:2000]}'
        await message_dialog(error_embed)


def load(bot: Inu):
    bot.add_plugin(pl)
