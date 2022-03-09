import asyncio
from email.policy import default
import traceback
import typing
from typing import (
    List,
    Dict,
    Any,
    Optional
)
import logging
import datetime
from datetime import datetime, timedelta, timezone

import hikari
from hikari.impl import ActionRowBuilder
from hikari.interactions.base_interactions import ResponseType
from hikari.interactions.component_interactions import ComponentInteraction
from hikari.messages import ButtonStyle, ComponentType
import lightbulb
from lightbulb.context import Context
from lightbulb import commands

from utils import DailyContentChannels, PrefixManager
from core import Inu, Table
from utils.db.r_channel_manager import Columns as Col

from core import getLogger, Inu

log = getLogger(__name__)


plugin = lightbulb.Plugin("Settings", "Commands, to change Inu's behavior to certain things")
bot: Inu

@plugin.listener(hikari.ShardReadyEvent)
async def on_ready(_: hikari.ShardReadyEvent):
    DailyContentChannels.set_db(plugin.bot.db)

@plugin.command
@lightbulb.add_checks(lightbulb.guild_only)
@lightbulb.command("settings", "Settings to chagne how cretain things are handled")
@lightbulb.implements(commands.PrefixCommandGroup, commands.SlashCommandGroup)
async def settings(ctx: Context):
    pass

@settings.child
@lightbulb.command("daily_pictures", "Settings to the daily pictures I send. By default I don't send pics", aliases=["dp"])
@lightbulb.implements(commands.SlashSubGroup, commands.PrefixSubGroup)
async def daily_pictures(ctx: Context):
    pass

@daily_pictures.child
@lightbulb.add_checks(lightbulb.guild_only)
@lightbulb.command("add_channel", "Adds the channel where you are in, to a channel where I send pictures")
@lightbulb.implements(commands.PrefixSubCommand, commands.SlashSubCommand)
async def add_channel(ctx: Context):
    """
    Adds <channel_id> to channels, where daily reddit stuff will be sent.
    """
    if not ctx.guild_id:
        return
    channel_id = ctx.channel_id
    channel = ctx.get_channel()
    if not channel:
        await ctx.respond("I am not able to add this channel :/", reply=True)
        return
    await DailyContentChannels.add_channel(Col.CHANNEL_IDS, channel_id, ctx.guild_id)
    await ctx.respond(f"added channel: `{channel.name}` with id `{channel.id}`")

@daily_pictures.child
@lightbulb.add_checks(lightbulb.guild_only)
@lightbulb.command("rm_channel", "Removes the channel you are in form daily content channels", aliases=["remove_channel"])
@lightbulb.implements(commands.SlashSubCommand, commands.PrefixSubCommand)
async def remove_channel(ctx: Context):
    """
    Removes <channel_id> from channels, where daily reddit stuff will be sent.
    """
    if not ctx.guild_id:
        return
    channel_id = ctx.channel_id
    if not (channel := await plugin.bot.rest.fetch_channel(channel_id)):
        await ctx.respond(f"cant remove this channel - channel not found", reply=True)
        return            
    await DailyContentChannels.remove_channel(Col.CHANNEL_IDS, channel_id, ctx.guild_id)
    await ctx.respond(f"removed channel: `{channel.name}` with id `{channel.id}`")
    
@daily_pictures.child
@lightbulb.add_checks(lightbulb.guild_only)
@lightbulb.command("add_top_channel", "Adds the channel where you are in, to a channel where I send pictures")
@lightbulb.implements(commands.PrefixSubCommand, commands.SlashSubCommand)
async def add_top_channel(ctx: Context):
    """
    Adds <channel_id> to channels, where daily reddit stuff will be sent.
    """
    if not ctx.guild_id:
        return
    channel_id = ctx.channel_id
    channel = ctx.get_channel()
    if not channel:
        await ctx.respond("I am not able to add this channel :/", reply=True)
        return
    await DailyContentChannels.add_channel(Col.TOP_CHANNEL_IDS, channel_id, ctx.guild_id)
    await ctx.respond(f"added channel: `{channel.name}` with id `{channel.id}`")

@daily_pictures.child
@lightbulb.add_checks(lightbulb.guild_only)
@lightbulb.command("rm_top_channel", "Removes the channel you are in form daily content channels", aliases=["remove_top_channel"])
@lightbulb.implements(commands.SlashSubCommand, commands.PrefixSubCommand)
async def remove_top_channel(ctx: Context):
    """
    Removes <channel_id> from channels, where daily reddit stuff will be sent.
    """
    if not ctx.guild_id:
        return
    channel_id = ctx.channel_id
    if not (channel := await plugin.bot.rest.fetch_channel(channel_id)):
        await ctx.respond(f"cant remove this channel - channel not found", reply=True)
        return
    await DailyContentChannels.remove_channel(Col.TOP_CHANNEL_IDS, channel_id, ctx.guild_id)
    await ctx.respond(f"removed channel: `{channel.name}` with id `{channel.id}`")

@settings.child
@lightbulb.command("prefix", "add/remove custom prefixes", aliases=["p"])
@lightbulb.implements(commands.SlashSubGroup, commands.PrefixSubGroup)
async def prefix(ctx: Context):
    pass

@prefix.child
@lightbulb.add_checks(lightbulb.guild_only)
@lightbulb.option("new_prefix", "The prefix you want to add", type=str, default="")
@lightbulb.command("add", "Add a prefix")
@lightbulb.implements(commands.SlashSubCommand, commands.PrefixSubCommand)
async def add(ctx: Context):
    prefix = ctx.options.new_prefix
    if prefix == "empty":
        prefix = ""
    prefixes = await PrefixManager.add_prefix(ctx.guild_id, prefix)
    await ctx.respond(f"""I added it. For this guild, the prefixes are now: {', '.join([f'`{p or "<empty>"}`' for p in prefixes])}""")

@prefix.child
@lightbulb.add_checks(lightbulb.guild_only)
@lightbulb.option("prefix", "The prefix you want to add", type=str, default="")
@lightbulb.command("remove", "Remove a prefix")
@lightbulb.implements(commands.SlashSubCommand, commands.PrefixSubCommand)
async def remove(ctx: Context):
    prefix = ctx.options.prefix
    if prefix == "empty":
        prefix = ""
    elif prefix == bot._default_prefix:
        return await ctx.respond(f"I won't do that xD")
    prefixes = await PrefixManager.remove_prefix(ctx.guild_id, prefix)
    await ctx.respond(f"""I removed it. For this guild, the prefixes are now: {', '.join([f'`{p or "<empty>"}`' for p in prefixes])}""")

@settings.child
@lightbulb.command("timezone", "Timezone related commands")
@lightbulb.implements(commands.SlashSubGroup, commands.PrefixSubGroup)
async def timez(ctx: Context):
    pass

@timez.child
@lightbulb.command("set", "Set the timezone of your guild - interactive")
@lightbulb.implements(commands.SlashSubCommand, commands.PrefixSubCommand)
async def timez_set(ctx: Context):
    menu = (
        ActionRowBuilder()
        .add_select_menu("timezone_menu")
    )
    for x in range(-5,6,1):
        t = timezone(offset=timedelta(hours=x))
        now = datetime.now(tz=t)
        menu.add_option(
            f"{now.hour}:{now.minute} | {t}",
            str(x)
        ).add_to_menu()
    menu = menu.add_to_container()
    await ctx.respond("How late is it in your region?", component=menu)
    try:
        event = await plugin.bot.wait_for(
            hikari.InteractionCreateEvent,
            timeout=10*60,
            predicate=lambda e: (
                isinstance(e.interaction, ComponentInteraction)
                and e.interaction.user.id == ctx.author.id
                and e.interaction.custom_id == "timezone_menu"
                and e.interaction.channel_id == ctx.channel_id
            )
        )
        if not isinstance(event.interaction, ComponentInteraction):
            return
        await event.interaction.create_initial_response(ResponseType.MESSAGE_CREATE, f"_successfully stored in my mind_")
        update_author = True
        table = Table("guild_timezones")
        if ctx.guild_id:
            await table.upsert(["guild_or_author_id", "offset_hours"], [ctx.guild_id, int(event.interaction.values[0])])
            try:
                btns = (
                    ActionRowBuilder()
                    .add_button(ButtonStyle.PRIMARY, "1").set_emoji("✔️").add_to_container()
                    .add_button(ButtonStyle.DANGER, "0").set_emoji("❌").add_to_container()
                )
                await ctx.bot.rest.create_message(
                    ctx.channel_id, 
                    "Should I also use it as your private time?",
                    component=btns
                )
                event2 = await ctx.bot.wait_for(
                    hikari.InteractionCreateEvent,
                    timeout=10*60,
                    predicate=lambda e: (
                        isinstance(e.interaction, ComponentInteraction)
                        and e.interaction.user.id == ctx.author.id
                        and e.interaction.channel_id == ctx.channel_id
                    )
                )
                if not isinstance(event2.interaction, ComponentInteraction):
                    pass
                values = event.interaction.values
                update_author = bool(int(event2.interaction.custom_id))
                await event2.interaction.create_initial_response(ResponseType.MESSAGE_CREATE, f"_also successfully stored in my mind_")
                # await event.interaction.create_initial_response(ResponseType.DEFERRED_MESSAGE_CREATE)
            except Exception:
                log.error(f"settings timezone set: {traceback.format_exc()}")
        if update_author:
            await table.upsert(["guild_or_author_id", "offset_hours"], [ctx.author.id, int(event.interaction.values[0])])
        
    except asyncio.TimeoutError:
        pass


def load(inu: Inu):
    inu.add_plugin(plugin)
    global bot
    bot = inu
        