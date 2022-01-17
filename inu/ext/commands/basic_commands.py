import typing
from typing import (
    Union,
    Optional,
    List,
)
import asyncio
import logging

from hikari import ActionRowComponent, Embed, MessageCreateEvent, embeds
from hikari.messages import ButtonStyle
from hikari.impl.special_endpoints import ActionRowBuilder
from hikari.events import InteractionCreateEvent
import lightbulb
import lightbulb.utils as lightbulb_utils
from lightbulb import commands, context
import hikari
from numpy import isin


from core import getLogger

log = getLogger(__name__)

basics = lightbulb.Plugin("Basics", "Extends the commands with basic commands", include_datastore=True)
if not isinstance(basics.d, lightbulb_utils.DataStore):
    raise RuntimeError("Plugin don't contain a datastore")
if basics.d is None:
    raise RuntimeError("Plugin don't contain a datastore")


@basics.command
@lightbulb.command("ping", "is the bot alive?")
@lightbulb.implements(commands.PrefixCommand, commands.SlashCommand)
async def ping(ctx: context.Context):
    await ctx.respond(f"Bot is alive with a delay of {ctx.bot.heartbeat_latency*1000:.2f}ms")


@basics.command
@lightbulb.option("to_echo", "the text I should echo", modifier=commands.OptionModifier.CONSUME_REST)
@lightbulb.command("echo", "echo your input")
@lightbulb.implements(commands.PrefixCommandGroup, commands.SlashCommandGroup)
async def echo(ctx: context.Context):
    await ctx.respond(ctx.options.to_echo)

@echo.child
@lightbulb.option("to_echo", "the text I should echo", modifier=commands.OptionModifier.CONSUME_REST)
@lightbulb.option("multiplier", "How often should I repeat?", type=int)
@lightbulb.command("multiple", "echo your input multiple times")
@lightbulb.implements(commands.PrefixSubCommand, commands.SlashSubCommand)
async def multiple(ctx):
    await ctx.respond(str(ctx.options.multiplier * ctx.options.to_echo))

@basics.command
@lightbulb.command("test", "/")
@lightbulb.implements(commands.PrefixCommand, commands.SlashCommand)
async def test(ctx):
    embed = hikari.Embed()
    embed.title = "test"
    embed.add_field("```test```", "test")
    await ctx.respond(embed=embed)
    
@basics.command
@lightbulb.add_cooldown(60*60, 4, lightbulb.UserBucket)
@lightbulb.add_checks(
    lightbulb.guild_only, 
    #lightbulb.has_channel_permissions(hikari.Permissions.MANAGE_CHANNELS)
)
@lightbulb.option(
    "ammount", 
    "The ammount of messages you want to delete, Default: 5", 
    default=5, 
    type=int,
)
@lightbulb.command("purge", "Delete the last messages from a channel", aliases=["clean"])
@lightbulb.implements(commands.PrefixCommand, commands.SlashCommand)
async def purge(ctx: context.Context):
    if not (channel := ctx.get_channel()):
        return
    if not isinstance(channel, hikari.TextableGuildChannel):
        return
    if (ammount := ctx.options.ammount) > 50:
        await ctx.respond("I can't delete that much messages!")
    messages = []
    ammount += 2
    await ctx.respond("I'll do it. Let me some time. I'll include your message and this message")
    async for m in channel.fetch_history():
        messages.append(m)
        ammount -= 1
        if ammount <= 0:
            break
    await channel.delete_messages(messages)

@basics.command
@lightbulb.command("invite", "Invite this bot to your server")
@lightbulb.implements(commands.PrefixCommand, commands.SlashCommand)
async def invite(ctx: context.Context):
    await ctx.respond(ctx.bot.conf.bot.DISCORD_INVITE_LINK)


def load(bot: lightbulb.BotApp):
    bot.add_plugin(basics)
