from contextlib import suppress
import random
import asyncio
from typing import *
import traceback

import hikari
from hikari import Embed
import lightbulb
from lightbulb.context import Context

from core import Inu
from utils.language import Human

from core import getLogger, BotResponseError, Inu, InteractionContext

log = getLogger("Error Handler")
pl = lightbulb.Loader()
bot: Inu

MAGIC_ERROR_MONSTER = "https://media.discordapp.net/attachments/818871393369718824/1106177322069012542/error-monster-1.png?width=1308&height=946"
ERROR_JOKES = [
    "Wait, there is a difference between beta and production?",
    "Seems like someone was to lazy to test me -- _again_",
    "Y'know: _my_ ordinary life is generating errors",
    "You expected me to work properly? Oh please ...",
    (
        "Y'know I can smell your disappointment. It's right about here: ```\n"
        "good                  bad\n"
        "  |--------------------|\n"
        "                             ^\n```"
    )

]



# async def on_exception(event: hikari.ExceptionEvent):
#     # not user related error
#     try:
#         log.error(f"{''.join(traceback.format_exception(event.exception))}")
#     except Exception:
#         log.critical(traceback.format_exc())



@pl.error_handler()
async def on_error(exc: lightbulb.exceptions.ExecutionPipelineFailedException) -> bool:
    """
    """
    for cause in exc.causes:
        log.error(f"{''.join(traceback.format_exception(cause))}")
    return True
    # try:
    #     ctx: Context | None = event.context

    #     if not isinstance(ctx, Context):
    #         log.debug(f"Exception uncaught: {event.__class__}")
    #         return
    #     error = event.exception

    #     async def message_dialog(error_embed: hikari.Embed):
    #         error_id = f"{bot.restart_num}-{bot.id_creator.create_id()}-{bot.me.username[0]}"
    #         error_embed.set_image(MAGIC_ERROR_MONSTER)
    #         component=(
    #             hikari.impl.MessageActionRowBuilder()
    #             .add_interactive_button(
    #                 hikari.ButtonStyle.PRIMARY, 
    #                 "error_send_dev_silent",
    #                 label="🍭 Send report silently"
    #             )
    #             .add_interactive_button(
    #                 hikari.ButtonStyle.PRIMARY, 
    #                 "error_send_dev",
    #                 label="🍭 Add note & send"
    #             )
    #         )
    #         try:
    #             message = await (await ctx.respond(
    #                 embed=error_embed,
    #                 component=component,
    #             )).message()
    #         except Exception:
    #             message = await bot.rest.create_message(
    #                 ctx.channel_id,
    #                 embed=error_embed,
    #                 component=component
    #             )

    #         def check(event: hikari.ReactionAddEvent):
    #             if event.user_id != bot.me.id and event.message_id == message.id:
    #                 return True
    #             return False
            
    #         custom_id, _, interaction = await bot.wait_for_interaction(
    #             custom_ids=["error_send_dev", "error_show", "error_send_dev_silent"],
    #             message_id=message.id,
    #             user_ids=ctx.user.id
    #         )
    #         # await interaction.delete_message(message)
    #         embeds: List[Embed] = [Embed(title=f"Bug #{error_id}", description=str(error)[:2000])]
    #         embeds[0].set_author(
    #             name=f'Invoked by: {ctx.user.username}',
    #             icon=ctx.author.avatar_url
    #         )
    #         embeds[0].add_field(
    #             "invoked with", 
    #             value=(
    #                 f"Command: {ctx.invoked_with}\n"
    #                 "\n".join([f"`{k}`: ```\n{v}```" for k, v in ctx.raw_options.items()])
    #             )[:1000]
    #         )
    #         nonlocal event
    #         traceback_list = traceback.format_exception(*event.exc_info)
    #         if len(traceback_list) > 0:
    #             log.warning(str("\n".join(traceback_list)))
    #         error_embed.add_field(
    #             name=f'{str(error.__class__)[8:-2]}',
    #             value=f'Error:\n{error}'[:1024],
    #         )
    #         i = 0
    #         for index, tb in enumerate(traceback_list):
    #             if embeds[-1].total_length() > 6000:
    #                 field = embeds[-1]._fields.pop(-1)
    #                 embeds.append(Embed(description=f"Bug #{error_id}"))
    #                 embeds[-1]._fields.append(field)
    #                 i = 0
    #             if i % 20 == 0 and i != 0:
    #                 embeds.append(Embed(description=f"Bug #{error_id}"))
    #             embeds[-1].add_field(
    #                 name=f'Traceback - layer {index + 1}',
    #                 value=f'```python\n{Human.short_text_from_center(tb, 1000)}```',
    #                 inline=False
    #             )
    #             i += 1
    #         messages: List[List[Embed]] = [[]]
    #         message_len = 0
    #         for e in embeds:
    #             for field in e._fields:
    #                 if not field.value:
    #                     field.value = "-"
    #             if message_len == 0:
    #                 messages[-1].append(e)
    #                 message_len += e.total_length()
    #             else:
    #                 if message_len + e.total_length() > 6000:
    #                     messages.append([e])
    #                     message_len = e.total_length()
    #                 else:
    #                     messages[-1].append(e)
    #                     message_len += e.total_length()

    #         kwargs: Dict[str, Any] = {"embeds": embeds}
    #         answer = ""
    #         if custom_id == "error_show":
    #             await message.edit(embeds=embeds)
                
    #         if custom_id == "error_send_dev":
    #             try:
    #                 answer, interaction, event = await bot.shortcuts.ask_with_modal(
    #                     f"Bug report", 
    #                     question_s="Do you have additional information?", 
    #                     interaction=interaction,
    #                     pre_value_s="/",
    #                 )
    #             except asyncio.TimeoutError:
    #                 answer = "/"
    #             if answer == "/":
    #                 answer = ""

    #         kwargs["content"] = f"**{40*'#'}\nBug #{error_id}\n{40*'#'}**\n\n\n{Human.short_text(answer, 1930)}"
    #         del kwargs["embeds"]
    #         for i, embeds in enumerate(messages):
    #             if i == 0:
    #                 message = await bot.rest.create_message(
    #                     channel=bot.conf.bot.bug_channel_id,
    #                     embeds=embeds,
    #                     **kwargs
    #                 )
    #             else:
    #                 message = await bot.rest.create_message(
    #                     channel=bot.conf.bot.bug_channel_id,
    #                     embeds=embeds,
    #                 )
    #         if interaction:
    #             with suppress():
    #                 await interaction.create_initial_response(
    #                     hikari.ResponseType.MESSAGE_CREATE,
    #                     content=(
    #                         f"**Bug #{error_id}** has been reported.\n"
    #                         f"You can find the bug report [here]({message.make_link(message.guild_id)})\n"
    #                         f"If you can't go to this message, or need additional help,\n"
    #                         f"consider to join the [help server]({bot.conf.bot.guild_invite_url})"

    #                     ),
    #                     flags=hikari.MessageFlag.EPHEMERAL,
    #                 )
    #         return

    #     # errors which will be handled also without prefix
    #     if isinstance(error, errors.NotEnoughArguments):
    #         return await OutsideHelp.search(
    #             obj=ctx.invoked_with,
    #             ctx=ctx,
    #             message=(
    #                 f"to use the `{ctx.invoked.qualname}` command, "
    #                 f"I need {Human.list_([o.name for o in error.missing_options], '`')} to use it"
    #             ),
    #             only_one_entry=True,
    #         )
    #     elif isinstance(error, errors.CommandIsOnCooldown):
    #         return await ctx.respond(
    #             f"You have used `{ctx.invoked.qualname}` to often. Retry it in `{error.retry_after:.01f} seconds` again"
    #         )
    #     elif isinstance(error, errors.ConverterFailure):
    #         return await OutsideHelp.search(
    #             obj=ctx.invoked_with,
    #             ctx=ctx,
    #             message=(
    #                 f"the option `{error.option.name}` has to be {Human.type_(error.option.arg_type, True)}"
    #             ),
    #             only_one_entry=True,
    #         )
    #     elif isinstance(error, errors.MissingRequiredPermission):
    #         return await ctx.respond(
    #             f"You need the `{error.missing_perms.name}` permission, to use `{ctx.invoked_with}`",
    #             flags=hikari.MessageFlag.EPHEMERAL,
    #         )
    #     elif isinstance(error, errors.CheckFailure):
    #         fails = set(
    #             str(error)
    #             .replace("Multiple checks failed: ","")
    #             .replace("This command", f"`{ctx.invoked_with}`")
    #             .split(", ")
    #         )
    #         if len(fails) > 1:
    #             str_fails = [f"{i+1}: {e}"
    #                 for i, e in enumerate(fails)
    #             ]
    #             return await ctx.respond(
    #                 "\n".join(fails)
    #             )
    #         else:
    #             return await ctx.respond(fails.pop())
    #     elif isinstance(error, errors.CommandInvocationError) and isinstance(error.original, BotResponseError):
    #         try:
    #             return await ctx.respond(**error.original.kwargs)
    #         except hikari.BadRequestError:
    #             # interaction probably already acknowledged
    #             # TODO: implement Error handling into InuContext
    #             ctx._responded = True
    #             return await ctx.respond(**error.original.kwargs)

    #     # errors which will only be handled, if the command was invoked with a prefix
    #     if not ctx.prefix:
    #         return # log.debug(f"Suppress error of type: {error.__class__.__name__}")
    #     if isinstance(error, errors.CommandNotFound):
    #         return await OutsideHelp.search(
    #             obj=error.invoked_with, 
    #             ctx=ctx, 
    #             message=f"There is no command called `{error.invoked_with}`\nMaybe you mean one from the following ones?"
    #         )
    #     else:
    #         error_embed = hikari.Embed()
    #         error_embed.title = "Oh no! A bug occurred"
    #         error_embed.description = random.choice(ERROR_JOKES)
    #         if bot.heartbeat_latency > 0.3:
    #             error_embed.description += f"\n\nDiscord sucks at the moment btw (too high latency). This time it's not my fault"
    #         with suppress(hikari.ForbiddenError):
    #             await message_dialog(error_embed)
    # except Exception:
    #     log.critical(traceback.format_exc())



# def load(inu: Inu):
#     global bot
#     bot = inu
#     @bot.listen(hikari.events.ExceptionEvent)
#     async def on_error(event: hikari.events.ExceptionEvent) -> None:
#         try:
#             log.error(f"{''.join(traceback.format_exception(event.exception))}")
#         except Exception:
#             log.critical(traceback.format_exc())
#     inu.add_plugin(pl)
