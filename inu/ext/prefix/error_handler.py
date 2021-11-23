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

log = logging.getLogger(__name__)


pl = lightbulb.Plugin("Error Handler")


@pl.listener(events.CommandErrorEvent)
async def on_error(event: events.CommandErrorEvent):
    log.warning("error")
    """
    The event triggered when an error is raised while invoking a command.
    Parameters
    ------------
    error: commands.CommandError
        The Exception raised.
    """
    ctx: Optional[Context] = event.context

    error = event.exception
    channel_id = event.context.get_channel()
    rest = pl.bot.rest
    if isinstance(event, events.PrefixCommandErrorEvent):
        message_id = event.context.event.message_id

    if isinstance(error, errors.CommandNotFound):
        embed = hikari.Embed()
        embed.title = "404 Not Found"
        embed.description = f"No command called '{error.invoked_with}' found"
        return await rest.create_message(embed=embed, channel=channel_id)
        

    if ctx is None:
        log.debug("Exception uncaught")
        return

    
    def check(event: hikari.ReactionAddEvent):
        if event.user_id != pl.bot.me.id and event.message_id == message.id:
            return True
        return False

    error_embed = hikari.Embed()
    error_embed.title = random.choice(['ERROR', '3RR0R'])
    error_embed.description = f'{str(error) if len(str(error)) < 2000 else str(error)[:2000]}'

    message = await (await ctx.respond(embed = error_embed)).message()
    for reaction in ['🍭', '❔']:
        await message.add_reaction(reaction)
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
        help_cog = pl.bot.get_plugin("Help")
        if not help_cog: print("no help"); return;
        for cmd in help_cog.walk_commands():
            if cmd.method_name == "help":
                await cmd.callback(help_cog, ctx, ctx.invoked_with) #type: ignore
                await message.remove_all_reactions()


def load(bot: Inu):
    bot.add_plugin(pl)
