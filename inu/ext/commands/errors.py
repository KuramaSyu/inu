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
from utils.language import Human
from .help import OutsideHelp

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
    try:
        ctx: Optional[Context] = event.context

        if ctx is None:
            log.debug(f"Exception uncaught: {event.__class__}")
            return



        error = event.exception
        # channel_id = event.context.get_channel()
        # rest = pl.bot.rest
        # if isinstance(event, events.PrefixCommandErrorEvent):
        #     message_id = event.context.event.message_id


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

        # errors which will be handled also without prefix
        if isinstance(error, errors.NotEnoughArguments):
            return await OutsideHelp.search(
                obj=ctx.invoked_with,
                ctx=ctx,
                message=(
                    f"to use the `{ctx.invoked.qualname}` command, "
                    f"I need {Human.list_([o.name for o in error.missing_options], '`')} to use it"
                ),
                only_one_entry=True,
            )
        elif isinstance(error, errors.CommandIsOnCooldown):
            return await ctx.respond(
                f"You have used `{ctx.invoked.qualname}` to often. Retry it in `{error.retry_after:.01f} seconds` again"
            )
        elif isinstance(error, errors.ConverterFailure):
            return await OutsideHelp.search(
                obj=ctx.invoked_with,
                ctx=ctx,
                message=(
                    f"the option `{error.option.name}` has to be {Human.type_(error.option.arg_type, True)}"
                ),
                only_one_entry=True,
            )
        elif isinstance(error, errors.MissingRequiredPermission):
            error: errors.MissingRequiredPermission = error
            return await ctx.respond(
                f"You need the `{error.missing_perms.name}` permission, to use `{ctx.invoked_with}`"
            )

        # errors which will only be handled, if the command was invoked with a prefix
        if not ctx.prefix:
            return # log.debug(f"Suppress error of type: {error.__class__.__name__}")
        if isinstance(error, errors.CommandNotFound):
            return await OutsideHelp.search(
                obj=error.invoked_with, 
                ctx=ctx, 
                message=f"There is no command called `{error.invoked_with}`\nMaybe you mean one from the following ones?"
            )
        else:
            error_embed = hikari.Embed()
            error_embed.title = random.choice(['ERROR', '3RR0R'])
            error_embed.description = f'{str(error) if len(str(error)) < 2000 else str(error)[:2000]}'
            with suppress(hikari.ForbiddenError):
                await message_dialog(error_embed)
    except Exception:
        log.error(traceback.format_exc())

def load(bot: Inu):
    bot.add_plugin(pl)
