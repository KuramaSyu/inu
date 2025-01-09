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

from hikari import (
    Embed,
    ResponseType, 
    TextInputStyle,
    Permissions,
    ButtonStyle
)
import hikari
from hikari.impl import MessageActionRowBuilder
from lightbulb import AutocompleteContext, Choice, Context, Loader, Group, SubGroup, SlashCommand, invoke
from lightbulb.prefab import sliding_window

import lightbulb
from lightbulb.context import Context
from lightbulb import Context, Group, commands
import miru

from core import Inu, Table, BotResponseError, InuContext
from utils import DailyContentChannels, PrefixManager, TimezoneManager, Colors, YES_NO
from utils.db.r_channel_manager import Columns as Col
from utils.db import BoardManager, SettingsManager

from core import getLogger, Inu

log = getLogger(__name__)
EPHEMERAL = {"flags": hikari.MessageFlag.EPHEMERAL}
client = miru.Client(Inu.instance)
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
    async def back_button(self, ctx: miru.ViewContext, button: miru.Button):
        await self.go_back(ctx)
        

    @miru.button(emoji=chr(9209), style=hikari.ButtonStyle.DANGER, row=2)
    async def stop_button(self, ctx: miru.ViewContext, button: miru.Button):
        try:
            self.stop()
        except Exception as e:
            pass
        if self.message:
            await self.message.delete()

        #self.stop() # Stop listening for interactions

    async def go_back(self, ctx: miru.ViewContext) -> None:
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
    async def prefix_add(self, ctx: miru.ViewContext, button: miru.Button) -> None:
        new_prefix, interaction, event = await bot.shortcuts.ask_with_modal(
            self.total_name, 
            "What should be the new prefix?", 
            ctx.interaction,
            max_length_s=15,
            input_style_s=hikari.TextInputStyle.SHORT
        )
        if new_prefix is None:
            return
        # self.lightbulb_ctx._options["new_prefix"] = new_prefix
        # self.lightbulb_ctx._responded = False
        # self.lightbulb_ctx._interaction = interaction
        self._responded = False
        await add.callback(self.lightbulb_ctx)

    @miru.button(label="remove", emoji=chr(128220), style=hikari.ButtonStyle.PRIMARY)
    async def prefix_remove(self, ctx: miru.ViewContext, button: miru.Button) -> None:
        old_prefix, interaction, event = await bot.shortcuts.ask_with_modal(
            self.total_name, 
            "Which prefix should I remove?", 
            ctx.interaction,
            max_length_s=15,
            input_style_s=hikari.TextInputStyle.SHORT
        )
        # self.lightbulb_ctx._options["prefix"] = old_prefix
        # self.lightbulb_ctx._responded = False
        # self.lightbulb_ctx._interaction = interaction
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
                await PrefixManager.fetch_prefixes(self._message.guild_id)  # type: ignore
            )
        )
        return embed

class RedditTopChannelView(SettingsMenuView):
    name = "Top Channels"
    @miru.button(label="add", emoji=chr(129704), style=hikari.ButtonStyle.PRIMARY)
    async def channels(self, ctx: miru.ViewContext, button: miru.Button) -> None:
        await add.callback(self.lightbulb_ctx)

    @miru.button(label="remove", emoji=chr(128220), style=hikari.ButtonStyle.PRIMARY)
    async def prefix_remove(self, ctx: miru.ViewContext, button: miru.Button) -> None:
        await remove.callback(self.lightbulb_ctx)

    async def to_embed(self):
        embed = hikari.Embed(
            title=self.total_name, 
            description="Here u should see the channels which are selected as top channels."
        )
        return embed


class LavalinkView(SettingsMenuView):
    name = "Music"
    
    @miru.button(label="Soundcloud", style=hikari.ButtonStyle.SECONDARY)
    async def soundcloud_button(self, ctx: miru.ViewContext, button: miru.Button) -> None:
        bot.data.preffered_music_search[ctx.guild_id] = "scsearch"
        await ctx.edit_response(embed=await self.to_embed(), components=self.build())

    @miru.button(label="YouTube", style=hikari.ButtonStyle.PRIMARY)
    async def youtube_button(self, ctx: miru.ViewContext, button: miru.Button) -> None:
        bot.data.preffered_music_search[ctx.guild_id] = "ytsearch"
        await ctx.edit_response(embed=await self.to_embed(), components=self.build())

    async def to_embed(self):
        source = "" 
        if bot.data.preffered_music_search.get(self.lightbulb_ctx.guild_id, "ytsearch") == "ytsearch":
            source = "YouTube"
            self.soundcloud_button._style = hikari.ButtonStyle.SECONDARY
            self.youtube_button._style = hikari.ButtonStyle.PRIMARY
        else:
            source = "Soundcloud"
            self.soundcloud_button._style = hikari.ButtonStyle.PRIMARY
            self.youtube_button._style = hikari.ButtonStyle.SECONDARY
        embed = hikari.Embed(
            title=self.total_name, 
            description=f"The currently preferred source for music: **{source}**"
        )
        return embed
    

class RedditChannelView(SettingsMenuView):
    name = "Channels"
    @miru.button(label="add", emoji=chr(129704), style=hikari.ButtonStyle.PRIMARY)
    async def channels(self, ctx: miru.ViewContext, button: miru.Button) -> None:
        await add.callback(self.lightbulb_ctx)

    @miru.button(label="remove", emoji=chr(128220), style=hikari.ButtonStyle.PRIMARY)
    async def prefix_remove(self, ctx: miru.ViewContext, button: miru.Button) -> None:
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
    async def channels(self, ctx: miru.ViewContext, button: miru.Button) -> None:
        await timez_set.callback(self.lightbulb_ctx)

    @miru.button(label="manage top channels", emoji=chr(128220), style=hikari.ButtonStyle.PRIMARY)
    async def prefix_remove(self, ctx: miru.ViewContext, button: miru.Button) -> None:
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
    async def set_timezone(self, ctx: miru.ViewContext, button: miru.Button) -> None:
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
    async def set_true(self, ctx: miru.ViewContext, button: miru.Button) -> None:
        embed = await update_activity_logging(ctx.guild_id, True)
        await ctx.respond(embed=embed)

    @miru.button(label="disable", style=hikari.ButtonStyle.DANGER)
    async def set_false(self, ctx: miru.ViewContext, button: miru.Button) -> None:
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
    @miru.button(label="enable", style=hikari.ButtonStyle.SECONDARY)
    async def set_true(self, ctx: miru.ViewContext, button: miru.Button) -> None:
        assert isinstance(ctx.guild_id, hikari.Snowflake)
        embed = await update_activity_logging(ctx.guild_id, True)
        await ctx.respond(embed=embed)

    @miru.button(label="disable", style=hikari.ButtonStyle.DANGER)
    async def set_false(self, ctx: miru.ViewContext, button: miru.Button) -> None:
        assert isinstance(ctx.guild_id, hikari.Snowflake)
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
    async def prefixes(self, ctx: miru.ViewContext, button: miru.Button) -> None:
        await (PrefixView(old_view=self, ctx=self.lightbulb_ctx)).start(self._message)
        
    @miru.button(label="Reddit", emoji=chr(128220), style=hikari.ButtonStyle.PRIMARY)
    async def reddit_channels(self, ctx: miru.ViewContext, button: miru.Button) -> None:
        await RedditView(old_view=self, ctx=self.lightbulb_ctx).start(self._message)

    @miru.button(label="Music", style=hikari.ButtonStyle.PRIMARY, emoji="🎵")
    async def lavalink_button(self, ctx: miru.ViewContext, button: miru.Button):
        await LavalinkView(old_view=self, ctx=self.lightbulb_ctx).start(self._message)

    @miru.button(label="Timezone", emoji=chr(9986), style=hikari.ButtonStyle.PRIMARY)
    async def timezone_button(self, ctx: miru.ViewContext, button: miru.Button):
        await TimezoneView(old_view=self, ctx=self.lightbulb_ctx).start(self._message)

    @miru.button(label="Activity logging", style=hikari.ButtonStyle.PRIMARY, emoji="🎮")
    async def activity_logging_button(self, ctx: miru.ViewContext, button: miru.Button):
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


loader = lightbulb.Loader()
bot: Inu = Inu.instance


async def board_emoji_autocomplete(
    ctx: AutocompleteContext
) -> None:
    letters = ['🇦', '🇧', '🇨', '🇩', '🇪', '🇫', '🇬', '🇭', '🇮', '🇯', '🇰', '🇱', '🇲', '🇳', '🇴', '🇵', '🇶', '🇷', '🇸', '🇹', '🇺', '🇻', '🇼', '🇽', '🇾', '🇿']
    await ctx.respond(["⭐", "🗑️", "👍", "👎", *letters][:24]) 

@loader.listener(hikari.ShardReadyEvent)
async def on_ready(_: hikari.ShardReadyEvent):
    DailyContentChannels.set_db(bot.db)

settings_group = Group("settings", "Settings to change how certain things are handled", dm_enabled=False)

@settings_group.register
class ActivityTracking(
    SlashCommand,
    name="activity-tracking",
    description="Enable (True) or disable (False) activity logging",
    default_member_permissions=hikari.Permissions.ADMINISTRATOR,
    hooks=[sliding_window(3, 1, "user")]
):
    enable = lightbulb.string("enable", "Whether to enable or disable activity logging", choices=YES_NO)
    @invoke
    async def callback(self, _: Context, ctx: InuContext):
        assert ctx.guild_id is not None
        embed = await update_activity_logging(ctx.guild_id, self.enable == "Yes")
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

@settings_group.register
class SettingsMenu(
    SlashCommand,
    name="menu",
    description="Interactive menu for all settings",
    dm_enabled=False,
    default_member_permissions=None,
    hooks=[sliding_window(3, 1, "user")]
):
    @invoke
    async def callback(self, _: Context, ctx: InuContext):
        main_view = MainView(old_view=None, ctx=ctx)
        message = await ctx.respond("settings")
        await main_view.start(await message.message())

daily_pictures = Group("daily_pictures", "Settings to the daily pictures I send. By default I don't send pics", dm_enabled=False)
#settings_group.register(daily_pictures)

@daily_pictures.register
class AddChannel(
    SlashCommand,
    name="add_channel",
    description="Adds the channel where you are in, to a channel where I send pictures",
    dm_enabled=False
):
    @invoke
    async def callback(self, _: Context, ctx: InuContext):
        if not ctx.guild_id:
            return
        channel_id = ctx.channel_id
        channel = ctx.get_channel()
        if not channel:
            await ctx.respond("I am not able to add this channel :/", reply=True)
            return
        await DailyContentChannels.add_channel(Col.CHANNEL_IDS, channel_id, ctx.guild_id)
        await ctx.respond(f"added channel: `{channel.name}` with id `{channel.id}`")

@daily_pictures.register
class RemoveChannel(
    SlashCommand,
    name="rm_channel",
    description="Removes the channel you are in from daily content channels",
    dm_enabled=False
):
    @invoke
    async def callback(self, _: Context, ctx: InuContext):
        if not ctx.guild_id:
            return
        channel_id = ctx.channel_id
        if not (channel := await bot.rest.fetch_channel(channel_id)):
            await ctx.respond(f"cant remove this channel - channel not found", reply=True)
            return            
        await DailyContentChannels.remove_channel(Col.CHANNEL_IDS, channel_id, ctx.guild_id)
        await ctx.respond(f"removed channel: `{channel.name}` with id `{channel.id}`")

@daily_pictures.register
class AddTopChannel(
    SlashCommand,
    name="add_top_channel",
    description="Adds the channel where you are in, to top channels",
    dm_enabled=False
):
    @invoke
    async def callback(self, _: Context, ctx: InuContext):
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

@daily_pictures.register
class RemoveTopChannel(
    SlashCommand,
    name="rm_top_channel",
    description="Removes the channel from top channels",
    dm_enabled=False
):
    @invoke
    async def callback(self, _: Context, ctx: InuContext):
        if not ctx.guild_id:
            return
        channel_id = ctx.channel_id
        if not (channel := await bot.rest.fetch_channel(channel_id)):
            await ctx.respond(f"cant remove this channel - channel not found", reply=True)
            return
        await DailyContentChannels.remove_channel(Col.TOP_CHANNEL_IDS, channel_id, ctx.guild_id)
        await ctx.respond(f"removed channel: `{channel.name}` with id `{channel.id}`")

prefix_group = Group("prefix", "add/remove custom prefixes", dm_enabled=False)
#settings_group.register(prefix_group)

@prefix_group.register
class AddPrefix(
    SlashCommand,
    name="add",
    description="Add a prefix",
    dm_enabled=False
):
    new_prefix = lightbulb.string("new-prefix", "The prefix you want to add | \"<empty>\" for no prefix")
    @invoke
    async def callback(self, _: Context, ctx: InuContext):
        prefix = self.new_prefix
        if prefix is None:
            raise BotResponseError("Your prefix can't be None", ephemeral=True)
        if prefix == "<empty>":
            prefix = ""
        prefixes = await PrefixManager.add_prefix(ctx.guild_id, prefix)
        await ctx.respond(f"""I added it. For this guild, the prefixes are now: {', '.join([f'`{p or "<empty>"}`' for p in prefixes])}""")

@prefix_group.register
class RemovePrefix(
    SlashCommand,
    name="remove",
    description="Remove a prefix",
    dm_enabled=False
):
    prefix = lightbulb.string("prefix", "The prefix you want to remove | \"<empty>\" for no prefix")
    @invoke
    async def callback(self, _: Context, ctx: InuContext):
        if self.prefix == "<empty>":
            prefix = ""
        elif self.prefix == bot._default_prefix:
            return await ctx.respond(f"I won't do that xD")
        prefixes = await PrefixManager.remove_prefix(ctx.guild_id, prefix)
        await ctx.respond(f"""I removed it. For this guild, the prefixes are now: {', '.join([f'`{p or "<empty>"}`' for p in prefixes])}""")

timezone_group = Group("timezone", "Timezone related commands", dm_enabled=False)
#settings_group.register(timezone_group)

@timezone_group.register
class SetTimezone(
    SlashCommand,
    name="set",
    description="Set the timezone of your guild - interactive",
    dm_enabled=False
):
    @invoke
    async def callback(self, _: Context, ctx: InuContext):
        await set_timezone(ctx)

settings_board_group = Group("board", "group for board commands", dm_enabled=False)
#settings_group.register(settings_board_group)

@settings_board_group.register
class CreateBoard(
    SlashCommand,
    name="create-here",
    description="make this channel to a board",
    dm_enabled=False
):
    emoji = lightbulb.string("emoji", "messages with this emoji will be sent here", autocomplete=board_emoji_autocomplete)
    @invoke
    async def callback(self, _: Context, ctx: InuContext):
        await BoardManager.add_board(
            guild_id=ctx.guild_id,
            channel_id=ctx.channel_id,
            emoji=self.emoji,
        )
        await ctx.respond(
            f"{ctx.get_channel().name} is now a {self.emoji}-Board.\n"
            f"Means all messages with a {self.emoji} reaction will be sent in here."
        )

@settings_board_group.register
class RemoveBoard(
    SlashCommand,
    name="remove-here",
    description="this channel will no longer be a board",
    dm_enabled=False
):
    emoji = lightbulb.string("emoji", "the emoji which the board have", autocomplete=board_emoji_autocomplete)
    @invoke
    async def callback(self, _: Context, ctx: InuContext):
        await BoardManager.remove_board(
            guild_id=ctx.guild_id,
            emoji=self.emoji,
        )
        await ctx.respond(
            f"{ctx.get_channel().name} is not a {self.emoji}-Board anymore.\n"
            f"Means all messages with a {self.emoji} will not be sent here any longer."
        )

async def set_timezone(ctx: InuContext, kwargs: Dict[str, Any] = {"flags": hikari.MessageFlag.EPHEMERAL}):
    """dialog for setting the timezone"""
    time_map: Dict[str, int] = {}
    for x in range(-5,6,1):
        t = timezone(offset=timedelta(hours=x))
        now = datetime.now(tz=t)
        time_map[f"{now.hour}:{now.minute} | {t}"] = x

    selected_time, ctx = await ctx.ask(
        "How late is it in your region?", 
        button_labels=list(time_map.keys()), 
        timeout=600, 
        delete_after_timeout=True, 
        **kwargs
    )
    if not selected_time:
        return
    await ctx.respond("Ok.", ephemeral=True)
    update_author = True
    if ctx.guild_id:
        await TimezoneManager.set_timezone(ctx.guild_id, time_map[selected_time])
        ans, ctx = await ctx.ask(
            "Should I also use it as your personal timezone?",
            button_labels=["Yes", "No"],
            timeout=600, 
            delete_after_timeout=True, 
            ephemeral=True, 
            **kwargs
        )
        if ans is None:
            return

        await ctx.respond("Ok.", ephemeral=True)
        update_author = ans == "Yes"
    if update_author:
        await TimezoneManager.set_timezone(ctx.user.id, time_map[selected_time])

loader.command(settings_group)