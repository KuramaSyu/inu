from abc import abstractmethod
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
from datetime import datetime, timedelta, timezone
from typing_extensions import Self

import hikari
from hikari.impl import MessageActionRowBuilder
from hikari.interactions.base_interactions import ResponseType
from hikari.interactions.component_interactions import ComponentInteraction
from hikari import ButtonStyle, ComponentType
import lightbulb
from lightbulb.context import Context
from lightbulb import SlashContext, commands
import miru

from core import Inu, Table, BotResponseError
from utils import DailyContentChannels, PrefixManager, TimezoneManager, Colors
from utils.db.r_channel_manager import Columns as Col
from utils.db import BoardManager, SettingsManager

from core import getLogger, Inu

log = getLogger(__name__)
EPHEMERAL = {"flags": hikari.MessageFlag.EPHEMERAL}

################################################################################
# Start - View for Settings
################################################################################


class SettingsMenuView(miru.View):
    name: str
    def __init__(
        self, 
        *,
        old_view: Optional["SettingsMenuView"], 
        timeout: Optional[float] = 14*15, 
        autodefer: bool = True,
        ctx: lightbulb.Context,
    ) -> None:
        super().__init__(timeout=timeout, autodefer=autodefer)
        self.old_view = old_view
        self.lightbulb_ctx = ctx

    @abstractmethod
    async def to_embed(self) -> hikari.Embed:
        raise NotImplementedError()

    @miru.button(emoji="◀", label="back", style=hikari.ButtonStyle.DANGER, row=2)
    async def back_button(self, button: miru.Button, ctx: miru.Context):
        await self.go_back(ctx)
        

    @miru.button(emoji=chr(9209), style=hikari.ButtonStyle.DANGER, row=2)
    async def stop_button(self, button: miru.Button, ctx: miru.Context):
        try:
            self.stop()
        except Exception as e:
            pass
        if self.message:
            await self.message.delete()

        #self.stop() # Stop listening for interactions

    async def go_back(self, ctx: miru.Context) -> None:
        if self.old_view is not None:
            self.stop()
            await self.old_view.start(self.message)
        else:
            await ctx.respond("You can't go back from here.")

    @property
    def total_name(self) -> str:
        if self.old_view is not None:
           return f"{self.old_view.total_name} > {self.__class__.name}" 
        else:
            return self.__class__.name

    async def start(self, message: hikari.Message) -> None:

        await super().start(message)
        await message.edit(
            embed=await self.to_embed(),
            components=self.build()
        )


class PrefixView(SettingsMenuView):
    name = "Prefixes"
    @miru.button(label="add", emoji=chr(129704), style=hikari.ButtonStyle.PRIMARY)
    async def prefix_add(self, button: miru.Button, ctx: miru.Context) -> None:
        new_prefix, interaction, event = await bot.shortcuts.ask_with_modal(
            self.total_name, 
            "What should be the new prefix?", 
            ctx.interaction,
            max_length_s=15,
            input_style_s=hikari.TextInputStyle.SHORT
        )
        if new_prefix is None:
            return
        self.lightbulb_ctx._options["new_prefix"] = new_prefix
        self.lightbulb_ctx._responded = False
        self.lightbulb_ctx._interaction = interaction
        self._responded = False
        await add.callback(self.lightbulb_ctx)

    @miru.button(label="remove", emoji=chr(128220), style=hikari.ButtonStyle.PRIMARY)
    async def prefix_remove(self, button: miru.Button, ctx: miru.Context) -> None:
        old_prefix, interaction, event = await bot.shortcuts.ask_with_modal(
            self.total_name, 
            "Which prefix should I remove?", 
            ctx.interaction,
            max_length_s=15,
            input_style_s=hikari.TextInputStyle.SHORT
        )
        self.lightbulb_ctx._options["prefix"] = old_prefix
        self.lightbulb_ctx._responded = False
        self.lightbulb_ctx._interaction = interaction
        self._responded = False
        await remove.callback(self.lightbulb_ctx)

    async def to_embed(self):
        embed = hikari.Embed(
            title=self.total_name, 
            description=(
                "Prefixes are used to call commands in the bot.\n"
                "You can add and remove prefixes here."
            ),
        )
        embed.add_field(
            name="Current Prefixes:", 
            value="\n".join(
                await PrefixManager.fetch_prefixes(
                    self._message.guild_id
                )
            )
        )
        return embed

class RedditTopChannelView(SettingsMenuView):
    name = "Top Channels"
    @miru.button(label="add", emoji=chr(129704), style=hikari.ButtonStyle.PRIMARY)
    async def channels(self, button: miru.Button, ctx: miru.Context) -> None:
        await add.callback(self.lightbulb_ctx)

    @miru.button(label="remove", emoji=chr(128220), style=hikari.ButtonStyle.PRIMARY)
    async def prefix_remove(self, button: miru.Button, ctx: miru.Context) -> None:
        await remove.callback(self.lightbulb_ctx)

    async def to_embed(self):
        embed = hikari.Embed(
            title=self.total_name, 
            description="Here u should see the channels which are selected as top channels."
        )
        return embed

class RedditChannelView(SettingsMenuView):
    name = "Channels"
    @miru.button(label="add", emoji=chr(129704), style=hikari.ButtonStyle.PRIMARY)
    async def channels(self, button: miru.Button, ctx: miru.Context) -> None:
        await add.callback(self.lightbulb_ctx)

    @miru.button(label="remove", emoji=chr(128220), style=hikari.ButtonStyle.PRIMARY)
    async def prefix_remove(self, button: miru.Button, ctx: miru.Context) -> None:
        await remove.callback(self.lightbulb_ctx)

    async def to_embed(self):
        embed = hikari.Embed(
            title=self.total_name, 
            description="Here u should see the channels that are used to post content from reddit."
        )
        return embed


class RedditView(SettingsMenuView):
    name = "Reddit"
    @miru.button(label="manage channels", emoji=chr(129704), style=hikari.ButtonStyle.PRIMARY)
    async def channels(self, button: miru.Button, ctx: miru.Context) -> None:
        await timez_set.callback(self.lightbulb_ctx)

    @miru.button(label="manage top channels", emoji=chr(128220), style=hikari.ButtonStyle.PRIMARY)
    async def prefix_remove(self, button: miru.Button, ctx: miru.Context) -> None:
        await RedditTopChannelView(old_view=self, ctx=self.lightbulb_ctx).start(self.message)

    async def to_embed(self):
        embed = hikari.Embed(
            title=self.total_name, 
            description=(
                "Manage the channels that the bot will post content from Reddit to.\n" 
                "Here u should see the channels that the bot is currently posting to."
            )
        )
        return embed

class TimezoneView(SettingsMenuView):
    name = "Timezone"
    @miru.button(label="set", emoji=chr(129704), style=hikari.ButtonStyle.PRIMARY)
    async def set_timezone(self, button: miru.Button, ctx: miru.Context) -> None:
        await set_timezone(ctx)

    async def to_embed(self):
        t_zone = await TimezoneManager.fetch_timezone(self.lightbulb_ctx.guild_id)
        now = datetime.now(t_zone)
        embed = hikari.Embed(
            title=self.total_name,
            description=f"Your current time is: {now.strftime('%Y-%m-%d %H:%M')}" 
        )
        return embed

class ActivityLoggingView(SettingsMenuView):
    name = "Guild activity statistics"
    @miru.button(label="enable", style=hikari.ButtonStyle.SUCCESS)
    async def set_true(self, button: miru.Button, ctx: miru.Context) -> None:
        embed = await update_activity_logging(ctx.guild_id, True)
        await ctx.respond(embed=embed)

    @miru.button(label="disable", style=hikari.ButtonStyle.DANGER)
    async def set_false(self, button: miru.Button, ctx: miru.Context) -> None:
        embed = await update_activity_logging(ctx.guild_id, False)
        await ctx.respond(embed=embed)

    async def to_embed(self):
        embed = hikari.Embed(
            title=self.total_name, 
            description=(
                "Here you can enable or disable activity logging\n"
                "So if you want to use commands like `/current-games` or `/week-activity` "
                "than you need to enable it. WHEN **ENABLED** ALL THIS GUILDS **ACTIVITIES WILL BE TRACKED**! (but anonymously)\n\n"
                f"Currently: {'ENABLED' if await SettingsManager.fetch_activity_tracking(self.lightbulb_ctx.guild_id) else 'DISABLED'}"
            )
        )
        return embed

class AutorolesView(SettingsMenuView):
    name = "Autoroles"
    @miru.button(label="enable", style=hikari.ButtonStyle.SUCCESS)
    async def set_true(self, button: miru.Button, ctx: miru.Context) -> None:
        embed = await update_activity_logging(ctx.guild_id, True)
        await ctx.respond(embed=embed)

    @miru.button(label="disable", style=hikari.ButtonStyle.DANGER)
    async def set_false(self, button: miru.Button, ctx: miru.Context) -> None:
        embed = await update_activity_logging(ctx.guild_id, False)
        await ctx.respond(embed=embed)

    async def to_embed(self):
        embed = hikari.Embed(
            title=self.total_name, 
            description=(
                "Here you can enable or disable activity logging\n"
                "So if you want to use commands like `/current-games` or `/week-activity` "
                "than you need to enable it. WHEN **ENABLED** ALL THIS GUILDS **ACTIVITIES WILL BE TRACKED**! (but anonymously)\n\n"
                f"Currently: {'ENABLED' if await SettingsManager.fetch_activity_tracking(self.lightbulb_ctx.guild_id) else 'DISABLED'}"
            )
        )
        return embed




class MainView(SettingsMenuView):
    name = "Settings"
    @miru.button(label="Prefixes", emoji=chr(129704), style=hikari.ButtonStyle.PRIMARY)
    async def prefixes(self, button: miru.Button, ctx: miru.Context) -> None:
        await (PrefixView(old_view=self, ctx=self.lightbulb_ctx)).start(self._message)
        
    @miru.button(label="Reddit", emoji=chr(128220), style=hikari.ButtonStyle.PRIMARY)
    async def reddit_channels(self, button: miru.Button, ctx: miru.Context) -> None:
        await RedditView(old_view=self, ctx=self.lightbulb_ctx).start(self._message)

    @miru.button(label="Timezone", emoji=chr(9986), style=hikari.ButtonStyle.PRIMARY)
    async def timezone_button(self, button: miru.Button, ctx: miru.Context):
        await TimezoneView(old_view=self, ctx=self.lightbulb_ctx).start(self._message)

    @miru.button(label="Activity logging", style=hikari.ButtonStyle.PRIMARY)
    async def activity_logging_button(self, button: miru.Button, ctx: miru.Context):
        await ActivityLoggingView(old_view=self, ctx=self.lightbulb_ctx).start(self._message)

    async def to_embed(self) -> hikari.Embed:
        embed = hikari.Embed(
            title=self.total_name,
            description="Here you can configure the bot.",
        )
        return embed

################################################################################
# End - View for Settings
################################################################################


plugin = lightbulb.Plugin("Settings", "Commands, to change Inu's behavior to certain things")
bot: Inu = None


@plugin.listener(hikari.ShardReadyEvent)
async def on_ready(_: hikari.ShardReadyEvent):
    DailyContentChannels.set_db(plugin.bot.db)

@plugin.command
@lightbulb.add_checks(lightbulb.guild_only)
@lightbulb.command("settings", "Settings to chagne how cretain things are handled")
@lightbulb.implements(commands.PrefixCommandGroup, commands.SlashCommandGroup)
async def settings(ctx: Context):
    pass
    # main_view = MainView(old_view=None, ctx=ctx)
    # message = await ctx.respond("settings")
    # await main_view.start(await message.message())

@settings.child
@lightbulb.add_checks(lightbulb.guild_only)
@lightbulb.option("enable", "True = Yes; False = No", type=bool)
@lightbulb.command("activity-tracking", "Enable (True) or disable (False) activity logging")
@lightbulb.implements(commands.SlashSubCommand)
async def set_activity_logging(ctx: SlashContext):
    embed = await update_activity_logging(ctx.guild_id, ctx.options.enable)
    await ctx.respond(embed=embed)



async def update_activity_logging(guild_id: int, enable: bool) -> hikari.Embed:
    await SettingsManager.update_activity_tracking(guild_id, enable)
    embed = hikari.Embed(title="Activity tracking for statistics")
    if enable:
        embed.description = "Is now enabled"
        embed.color = Colors.from_name("green")
    else:
        embed.description = "Is now disabled"
        embed.color = Colors.from_name("red")
    return embed



@settings.child
@lightbulb.add_checks(lightbulb.guild_only)
@lightbulb.command("menu", "Interacive menu for all settings")
@lightbulb.implements(commands.SlashSubCommand, commands.PrefixSubCommand)
async def settings_menu(ctx: Context):
    main_view = MainView(old_view=None, ctx=ctx)
    message = await ctx.respond("settings")
    await main_view.start(await message.message())


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
    assert(isinstance(channel, hikari.GuildChannel))
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
@lightbulb.option("new_prefix", "The prefix you want to add | \"<empty>\" for no prefix", type=str, default="")
@lightbulb.command("add", "Add a prefix")
@lightbulb.implements(commands.SlashSubCommand, commands.PrefixSubCommand)
async def add(ctx: Context):
    prefix = ctx.options.new_prefix
    if prefix is None:
        raise BotResponseError("Your prefix can't be None", ephemeral=True)
    if prefix == "<empty>":
        prefix = ""
    prefixes = await PrefixManager.add_prefix(ctx.guild_id, prefix)
    await ctx.respond(f"""I added it. For this guild, the prefixes are now: {', '.join([f'`{p or "<empty>"}`' for p in prefixes])}""")

@prefix.child
@lightbulb.add_checks(lightbulb.guild_only)
@lightbulb.option("prefix", "The prefix you want to remove | \"<empty>\" for no prefix", type=str, default="")
@lightbulb.command("remove", "Remove a prefix")
@lightbulb.implements(commands.SlashSubCommand, commands.PrefixSubCommand)
async def remove(ctx: Context):
    prefix = ctx.options.prefix
    if prefix == "<empty>":
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
    await set_timezone(ctx)

async def set_timezone(ctx: Context, kwargs: Dict[str, Any] = {"flags": hikari.MessageFlag.EPHEMERAL}):
    """dialog for setting the timezone"""
    menu = (
        MessageActionRowBuilder()
        .add_select_menu("timezone_menu")
    )
    for x in range(-5,6,1):
        t = timezone(offset=timedelta(hours=x))
        now = datetime.now(tz=t)
        menu.add_option(
            f"{now.hour}:{now.minute} | {t}",
            str(x)
        ).add_to_menu()
    component = menu.add_to_container()
    await ctx.respond("How late is it in your region?", component=component, **kwargs)
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
        await event.interaction.create_initial_response(ResponseType.MESSAGE_CREATE, f"ok", **kwargs)
        update_author = True
        if ctx.guild_id:
            await TimezoneManager.set_timezone(ctx.guild_id, int(event.interaction.values[0]))
            try:
                btns = (
                    MessageActionRowBuilder()
                    .add_button(ButtonStyle.PRIMARY, "1").set_emoji("✔️").add_to_container()
                    .add_button(ButtonStyle.DANGER, "0").set_emoji("✖").add_to_container()
                )
                await event.interaction.execute(
                    "Should I also use it as your private time?",
                    component=btns,
                    **EPHEMERAL
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
                await event2.interaction.create_initial_response(ResponseType.MESSAGE_CREATE, f"ok", **EPHEMERAL)
                # await event.interaction.create_initial_response(ResponseType.DEFERRED_MESSAGE_CREATE)
            except Exception:
                log.error(f"settings timezone set: {traceback.format_exc()}")
        if update_author:
            await TimezoneManager.set_timezone(event2.interaction.user.id, int(event.interaction.values[0]))
        
    except asyncio.TimeoutError:
        pass

@settings.child
@lightbulb.command("board", "group for board commands")
@lightbulb.implements(commands.SlashSubGroup)
async def settings_board(ctx: SlashContext):
    pass

@settings_board.child
@lightbulb.option("emoji", "messages with this emoji will be sent here", autocomplete=True)
@lightbulb.command("create-here", "make this channel to a board")
@lightbulb.implements(commands.SlashSubCommand)
async def settings_board_add(ctx: SlashContext):
    await BoardManager.add_board(
        guild_id=ctx.guild_id,
        channel_id=ctx.channel_id,
        emoji=ctx.options.emoji,
    )
    await ctx.respond(
        (
            f"{ctx.get_channel().name} is now a {ctx.options.emoji}-Board.\n"
            f"Means all messages with a {ctx.options.emoji} reaction will be sent in here."
        )
    )

@settings_board.child
@lightbulb.option("emoji", "the emoji which the board have", autocomplete=True)
@lightbulb.command("remove-here", "this channel will no longer be a board")
@lightbulb.implements(commands.SlashSubCommand)
async def settings_board_remove(ctx: SlashContext):
    await BoardManager.remove_board(
        guild_id=ctx.guild_id,
        emoji=ctx.options.emoji,
    )
    await ctx.respond(
        (
            f"{ctx.get_channel().name} is not a {ctx.options.emoji}-Board anymore.\n"
            f"Means all messages with a {ctx.options.emoji} will not be sent here any longer."
        )
    )

# @settings.child()
# @lightbulb.command("autoroles", "automatically role asignment")
# @lightbulb.implements(commands.SlashSubCommand)
# async def autoroles(ctx: SlashContext):
#     ...

@settings_board_add.autocomplete("emoji")
@settings_board_remove.autocomplete("emoji")
async def board_emoji_autocomplete(    
    option: hikari.AutocompleteInteractionOption, 
    interaction: hikari.AutocompleteInteraction
) -> List[str]:
    letters = ['🇦', '🇧', '🇨', '🇩', '🇪', '🇫', '🇬', '🇭', '🇮', '🇯', '🇰', '🇱', '🇲', '🇳', '🇴', '🇵', '🇶', '🇷', '🇸', '🇹', '🇺', '🇻', '🇼', '🇽', '🇾', '🇿']
    return ["⭐", "🗑️", "👍", "👎", *letters][:24]


def load(inu: Inu):
    inu.add_plugin(plugin)
    global bot
    bot = inu
    miru.load(bot)
        