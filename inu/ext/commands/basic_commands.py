import typing
from typing import (
    Union,
    Optional,
    List,
)
import asyncio
import logging
from datetime import datetime

from hikari import ActionRowComponent, Embed, MessageCreateEvent, embeds
from hikari.messages import ButtonStyle
from hikari.impl.special_endpoints import ActionRowBuilder, LinkButtonBuilder
from hikari.events import InteractionCreateEvent
import lightbulb
import lightbulb.utils as lightbulb_utils
from lightbulb import commands, context
import hikari
from numpy import isin

from utils import Colors
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
    def ping_to_color(ping: float) -> str:
        if ping >= 500:
            return "🔴"
        elif ping >= 340:
            return "🟠"
        elif ping >= 150:
            return "🟡"
        else:
            return "🟢"

    request_start = datetime.now()
    embed = Embed(
            title="Pong",
            description=(
                f"Bot is alive\n\n"
                f"{ping_to_color(ctx.bot.heartbeat_latency*1000)} Gateway: {ctx.bot.heartbeat_latency*1000:.2f} ms\n\n"
                f"⚫ REST: .... ms"
            ),
    )
    msg = await ctx.respond(embed=embed)
    rest_delay = datetime.now() - request_start
    embed.description = (
        f"Bot is alive\n\n"
        f"{ping_to_color(ctx.bot.heartbeat_latency*1000)} Gateway: {ctx.bot.heartbeat_latency*1000:.2f} ms\n\n"
        f"{ping_to_color(rest_delay.total_seconds()*1000)} REST: {rest_delay.total_seconds()*1000:.2f} ms"
    )
    await msg.edit(embed=embed)

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
    await ctx.respond(
        embed=Embed(
            title="Invite me",
            description=f"[Click here]({ctx.bot.conf.bot.DISCORD_INVITE_LINK}) _or click the button_",
            color=Colors.from_name("mediumslateblue"),
        ).set_thumbnail(ctx.bot.get_me().avatar_url),
        component=(
            ActionRowBuilder()
            .add_button(
                ButtonStyle.LINK, 
                ctx.bot.conf.bot.DISCORD_INVITE_LINK
            ).set_label("my invite link").add_to_container()
        )
    )

@basics.command
@lightbulb.command("test", "test")
@lightbulb.implements(commands.UserCommand)
async def test_(ctx: context.Context):
    await ctx.respond("test")

def load(bot: lightbulb.BotApp):
    bot.add_plugin(basics)
