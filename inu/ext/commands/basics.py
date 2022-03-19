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
from lightbulb import OptionModifier as OM
from lightbulb.context import Context
import hikari
from matplotlib.style import available
from numpy import full, isin
from fuzzywuzzy import fuzz

from utils import Colors, Human, Paginator, crumble
from core import getLogger, Inu, Table


log = getLogger(__name__)

basics = lightbulb.Plugin("Basics", "Extends the commands with basic commands", include_datastore=True)
if not isinstance(basics.d, lightbulb_utils.DataStore):
    raise RuntimeError("Plugin don't contain a datastore")
if basics.d is None:
    raise RuntimeError("Plugin don't contain a datastore")

bot: Inu


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

    def ping_to_color_rest(ping: float) -> str:
        if ping >= 1150:
            return "🔴"
        elif ping >= 800:
            return "🟠"
        elif ping >= 450:
            return "🟡"
        else:
            return "🟢"

    def ping_to_color_db(ping: float) -> str:
        if ping >= 80:
            return "🔴"
        elif ping >= 40:
            return "🟠"
        elif ping >= 15:
            return "🟡"
        else:
            return "🟢"

    db_request_start = datetime.now()
    table = Table("bot")
    record = await table.select_row(["key"], ["restart_count"])
    db_delay = datetime.now() - db_request_start
    request_start = datetime.now()
    embed = Embed(
            title="Pong",
            description=(
                f"Bot is alive\n\n"
                f"{ping_to_color(ctx.bot.heartbeat_latency*1000)} Gateway: {ctx.bot.heartbeat_latency*1000:.2f} ms\n\n"
                f"⚫ REST: .... ms\n\n"
                f"{ping_to_color_db(db_delay.total_seconds()*1000)} Database: {db_delay.total_seconds()*1000:.2f} ms"
            ),
    )
    msg = await ctx.respond(embed=embed)
    rest_delay = datetime.now() - request_start


    embed.description = (
        f"Bot is alive\n\n"
        f"{ping_to_color(ctx.bot.heartbeat_latency*1000)} Gateway: {ctx.bot.heartbeat_latency*1000:.2f} ms\n\n"
        f"{ping_to_color_rest(rest_delay.total_seconds()*1000)} REST: {rest_delay.total_seconds()*1000:.2f} ms\n\n"
        f"{ping_to_color_db(db_delay.total_seconds()*1000)} Database: {db_delay.total_seconds()*1000:.2f} ms"
    )
    await msg.edit(embed=embed)

    
@basics.command
@lightbulb.add_cooldown(60*60*10, 15, lightbulb.UserBucket)
@lightbulb.add_checks(
    lightbulb.guild_only, 
    # lightbulb.has_channel_permissions(hikari.Permissions.MANAGE_CHANNELS)
    lightbulb.has_role_permissions(hikari.Permissions.MANAGE_CHANNELS)
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
@lightbulb.command("search", "search different things and get it's ID with the name")
@lightbulb.implements(commands.SlashCommandGroup, commands.PrefixCommandGroup)
async def search(ctx: Context):
    pass

@search.child
@lightbulb.option(
    "guild", 
    "The name/part of the name/id from the guild", 
    modifier=OM.CONSUME_REST,
    type=str,
)
@lightbulb.command(
    "guild", 
    "seach guilds/servers and get it's ID with the name",
    aliases=["server"]
)
@lightbulb.implements(commands.SlashSubCommand, commands.PrefixSubCommand)
async def search_guild(ctx: Context):
    matches = await bot.search.guild(ctx.options.guild)
    if not matches:
        await ctx.respond(f"No guilds with partial ID/name `{ctx.options.guild}` found")
        return
    str_matches = "\n".join(f"name: {g.name:<35} id: {str(g.id):>}" for g in matches)
    result = (
        f"I found {Human.plural_('guild', len(matches), with_number=True)}:\n"
        f"```\n{str_matches}\n```"
    )
    pag = Paginator(page_s=[f"```\n{p.replace('```', '')}```" for p in crumble(result)])
    await pag.start(ctx)

@search.child
@lightbulb.add_checks(lightbulb.guild_only)
@lightbulb.option(
    "member", 
    "A part of the name/id/alias of the member from the guild", 
    modifier=OM.CONSUME_REST,
    type=str,
)
@lightbulb.command(
    "member", 
    "seach a member in this guild",
    aliases=["user", "person"]
)
@lightbulb.implements(commands.SlashSubCommand, commands.PrefixSubCommand)
async def search_member(ctx: Context):
    matches = await bot.search.member(ctx.guild_id, ctx.options.member)
    if not matches:
        await ctx.respond(f"No member with partial name/ID/alias `{ctx.options.member}` found")
        return
    str_matches = "\n".join(f"name: {m.display_name:<35} id: {str(m.id):>}" for m in matches)
    result = (
        f"I found {Human.plural_('member', len(matches), with_number=True)}:\n"
        f"```\n{str_matches}\n```"
    )
    pag = Paginator(page_s=[f"```\n{p.replace('```', '')}```" for p in crumble(result)])
    await pag.start(ctx)




def load(inu: lightbulb.BotApp):
    global bot
    bot = inu
    inu.add_plugin(basics)

