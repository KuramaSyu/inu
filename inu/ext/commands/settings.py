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
import miru.context
from typing_extensions import Self

from hikari import (
    Embed,
    ResponseType, 
    TextInputStyle,
    Permissions,
    ButtonStyle,
    ComponentInteraction
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
from utils import DailyContentChannels, PrefixManager, TimezoneManager, Colors, YES_NO, Paginator, button
from utils.db.r_channel_manager import Columns as Col
from utils.db import BoardManager, SettingsManager

from core import getLogger, Inu, get_context

log = getLogger(__name__)
EPHEMERAL = {"flags": hikari.MessageFlag.EPHEMERAL}
################################################################################
# Start - View for Settings
################################################################################
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

class SettingsMenuView(Paginator[Embed]):
    name = "Settings"
    
    def __init__(self, old_view: Optional["SettingsMenuView"], guild_id: int):
        super().__init__([], disable_paginator_when_one_site=False)
        self.old_view: Optional["SettingsMenuView"] = old_view
        if self.old_view is not None:
            # stop, that interactions are not received by the old view
            self.old_view.silent_stop()
        self.guild_id = guild_id

    @abstractmethod
    async def to_embed(self) -> hikari.Embed:
        raise NotImplementedError()

    @button(emoji="◀", label="back", style=hikari.ButtonStyle.DANGER)
    async def back_button(self, ctx: InuContext, _: ComponentInteraction) -> None:
        await self.go_back(ctx)

    async def go_back(self, ctx: InuContext) -> None:
        if self.old_view is not None:
            self._stopped = True
            await ctx.defer(update=True)
            # recreate class because old view was stopped
            pag = self.old_view.__class__(self.old_view.old_view, self.guild_id)
            await pag.start(ctx)
        else:
            await ctx.respond("You can't go back from here.")

    @property
    def total_name(self) -> str:
        if self.old_view is not None:
            if hasattr(self.old_view, "total_name"):
                return f"{self.old_view.total_name} > {self.__class__.name}"  # type: ignore
            else:
                return self.__class__.name
        else:
            return self.__class__.name
    
    async def start(self, ctx: InuContext, **kwargs) -> hikari.Message:  # type: ignore
        log.debug(f"get embed")
        if self.old_view is not None:
            # to assure, that new view uses the same message
            await ctx.defer(update=True)
        self._pages = [await self.to_embed()]
        log.debug(f"start paginator")
        return await super().start(ctx, **kwargs)

class PrefixView(SettingsMenuView):
    name = "Prefixes"

    @button(emoji="◀", label="back", style=hikari.ButtonStyle.DANGER)
    async def back_button(self, ctx: InuContext, _: ComponentInteraction) -> None:
        await self.go_back(ctx)

    @button(label="add", emoji=chr(129704), style=hikari.ButtonStyle.PRIMARY)
    async def prefix_add(self, ctx: InuContext, _: ComponentInteraction) -> None:
        new_prefix, new_ctx = await ctx.ask_with_modal(
            self.total_name, 
            "What should be the new prefix?", 
            max_length_s=15,
            input_style_s=hikari.TextInputStyle.SHORT
        )
        if new_prefix is None or new_ctx is None:
            return
        await AddPrefix._callback(new_ctx, new_prefix=new_prefix)

    @button(label="remove", emoji=chr(128220), style=hikari.ButtonStyle.PRIMARY)
    async def prefix_remove(self, ctx: InuContext, _: ComponentInteraction) -> None:
        old_prefix, new_ctx = await ctx.ask_with_modal(
            self.total_name, 
            "Which prefix should I remove?", 
            max_length_s=15,
            input_style_s=hikari.TextInputStyle.SHORT
        )
        if not old_prefix or not new_ctx:
            return
        await RemovePrefix._callback(new_ctx, prefix=old_prefix)

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
                await PrefixManager.fetch_prefixes(self.guild_id)
            )
        )
        return embed

# class RedditTopChannelView(SettingsMenuView):
#     name = "Top Channels"

#     @button(emoji="◀", label="back", style=hikari.ButtonStyle.DANGER)
#     async def back_button(self, ctx: InuContext, _: ComponentInteraction) -> None:
#         await self.go_back(ctx)

#     @button(label="add", emoji=chr(129704), style=hikari.ButtonStyle.PRIMARY)
#     async def channels(self, ctx: InuContext, _: ComponentInteraction) -> None:
#         inu_ctx = get_context(ctx.interaction)
#         await AddTopChannel._callback(inu_ctx)

#     @button(label="remove", emoji=chr(128220), style=hikari.ButtonStyle.PRIMARY)
#     async def prefix_remove(self, ctx: InuContext, _: ComponentInteraction) -> None:
#         inu_ctx = get_context(ctx.interaction)
#         await RemoveTopChannel._callback(inu_ctx)

#     async def to_embed(self):
#         embed = hikari.Embed(
#             title=self.total_name, 
#             description="Here u should see the channels which are selected as top channels."
#         )
#         return embed

class LavalinkView(SettingsMenuView):
    name = "Music"

    @button(emoji="◀", label="back", style=hikari.ButtonStyle.DANGER)
    async def back_button(self, ctx: InuContext, _: ComponentInteraction) -> None:
        await self.go_back(ctx)

    @button(label="Soundcloud", style=hikari.ButtonStyle.SECONDARY)
    async def soundcloud_button(self, ctx: InuContext, _: ComponentInteraction) -> None:
        log.debug(f"Context: {ctx}")
        guild_id = ctx.guild_id
        assert guild_id is not None
        bot.data.preffered_music_search[guild_id] = "scsearch"
        log.debug(f"Context: {ctx}")
        await ctx.respond(embed=await self.to_embed(), components=self.components, update=True)

    @button(label="YouTube", style=hikari.ButtonStyle.PRIMARY)
    async def youtube_button(self, ctx: InuContext, _: ComponentInteraction) -> None:
        guild_id = ctx.guild_id
        assert guild_id is not None
        bot.data.preffered_music_search[guild_id] = "ytsearch"
        await ctx.respond(embed=await self.to_embed(), components=self.components, update=True)

    async def to_embed(self):
        source = "" 
        guild_id = self.guild_id
        assert guild_id is not None
        if bot.data.preffered_music_search.get(guild_id, "ytsearch") == "ytsearch":
            source = "YouTube"
            self.soundcloud_button._style = hikari.ButtonStyle.SECONDARY  # type: ignore
            self.soundcloud_button._style = hikari.ButtonStyle.SECONDARY  # type: ignore
            self.youtube_button._style = hikari.ButtonStyle.PRIMARY   # type: ignore
        else:
            source = "Soundcloud"
            self.soundcloud_button._style = hikari.ButtonStyle.PRIMARY  # type: ignore
            self.youtube_button._style = hikari.ButtonStyle.SECONDARY # type: ignore
        embed = hikari.Embed(
            title=self.total_name, 
            description=f"The currently preferred source for music: **{source}**"
        )
        return embed

# class RedditChannelView(SettingsMenuView):
#     name = "Channels"
#     @button(emoji="◀", label="back", style=hikari.ButtonStyle.DANGER)
#     async def back_button(self, ctx: InuContext, _: ComponentInteraction) -> None:
#         await self.go_back(ctx)

#     @button(label="add", emoji=chr(129704), style=hikari.ButtonStyle.PRIMARY)
#     async def channels(self, ctx: InuContext, _: ComponentInteraction) -> None:
#         inu_ctx = get_context(ctx.interaction)
#         await AddChannel._callback(inu_ctx)

#     @button(label="remove", emoji=chr(128220), style=hikari.ButtonStyle.PRIMARY)
#     async def prefix_remove(self, ctx: InuContext, _: ComponentInteraction) -> None:
#         inu_ctx = get_context(ctx.interaction)
#         await RemoveChannel._callback(inu_ctx)

#     async def to_embed(self):
#         embed = hikari.Embed(
#             title=self.total_name, 
#             description="Here u should see the channels that are used to post content from reddit."
#         )
#         return embed

# class RedditView(SettingsMenuView):
#     name = "Reddit"

#     @button(emoji="◀", label="back", style=hikari.ButtonStyle.DANGER, row=0)
#     async def back_button(self, ctx: InuContext, _: ComponentInteraction) -> None:
#         await self.go_back(ctx)

#     @button(label="manage channels", emoji=chr(129704), style=hikari.ButtonStyle.PRIMARY)
#     async def channels(self, ctx: InuContext, _: ComponentInteraction) -> None:
#         await SetTimezone._callback(get_context(ctx.interaction))

#     @button(label="manage top channels", emoji=chr(128220), style=hikari.ButtonStyle.PRIMARY)
#     async def prefix_remove(self, ctx: InuContext, _: ComponentInteraction) -> None:
#         await RedditTopChannelView(old_view=self, guild_id=self.guild_id).start(ctx)

#     async def to_embed(self):
#         embed = hikari.Embed(
#             title=self.total_name, 
#             description=(
#                 "Manage the channels that the bot will post content from Reddit to.\n" 
#                 "Here u should see the channels that the bot is currently posting to."
#             )
#         )
#         return embed

class TimezoneView(SettingsMenuView):
    name = "Timezone"

    @button(emoji="◀", label="back", style=hikari.ButtonStyle.DANGER)
    async def back_button(self, ctx: InuContext, _: ComponentInteraction) -> None:
        await self.go_back(ctx)

    @button(label="set", emoji=chr(129704), style=hikari.ButtonStyle.PRIMARY)
    async def set_timezone(self, ctx: InuContext, _: ComponentInteraction) -> None:
        await SetTimezone._callback(ctx)

    async def to_embed(self):
        t_zone = await TimezoneManager.fetch_timezone(self.guild_id)
        now = datetime.now(t_zone)
        embed = hikari.Embed(
            title=self.total_name,
            description=f"Your current time is: {now.strftime('%Y-%m-%d %H:%M')}" 
        )
        return embed

class ActivityLoggingView(SettingsMenuView):
    name = "Guild activity statistics"
    @button(emoji="◀", label="back", style=hikari.ButtonStyle.DANGER)
    async def back_button(self, ctx: InuContext, _: ComponentInteraction) -> None:
        await self.go_back(ctx)

    @button(label="enable", style=hikari.ButtonStyle.SUCCESS)
    async def set_true(self, ctx: InuContext, _: ComponentInteraction) -> None:
        embed = await update_activity_logging(ctx.guild_id, True)  # type: ignore
        await ctx.respond(embed=embed)

    @button(label="disable", style=hikari.ButtonStyle.DANGER)
    async def set_false(self, ctx: InuContext, _: ComponentInteraction) -> None:
        embed = await update_activity_logging(ctx.guild_id, False)  # type: ignore
        await ctx.respond(embed=embed)

    async def to_embed(self):
        embed = hikari.Embed(
            title=self.total_name, 
            description=(
                "Here you can enable or disable activity logging\n"
                "So if you want to use commands like `/current-games` or `/week-activity` "
                "than you need to enable it. WHEN **ENABLED** ALL THIS GUILDS **ACTIVITIES WILL BE TRACKED**! (but anonymously)\n\n"
                f"Currently: {'ENABLED' if await SettingsManager.fetch_activity_tracking(self.guild_id) else 'DISABLED'}"
            )
        )
        return embed

class AutorolesView(SettingsMenuView):
    name = "Autoroles"
    @button(emoji="◀", label="back", style=hikari.ButtonStyle.DANGER)
    async def back_button(self, ctx: InuContext, _: ComponentInteraction) -> None:
        await self.go_back(ctx)

    @button(label="enable", style=hikari.ButtonStyle.SECONDARY)
    async def set_true(self, ctx: InuContext, _: ComponentInteraction) -> None:
        assert isinstance(ctx.guild_id, hikari.Snowflake)
        embed = await update_activity_logging(ctx.guild_id, True)
        await ctx.respond(embed=embed)

    @button(label="disable", style=hikari.ButtonStyle.DANGER)
    async def set_false(self, ctx: InuContext, _: ComponentInteraction) -> None:
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
                f"Currently: {'ENABLED' if await SettingsManager.fetch_activity_tracking(self.guild_id) else 'DISABLED'}"
            )
        )
        return embed

class MainView(SettingsMenuView):
    name = "Settings"
    @button(emoji="◀", label="back", style=hikari.ButtonStyle.DANGER)
    async def back_button(self, ctx: InuContext, _: ComponentInteraction) -> None:
        await self.go_back(ctx)

    @button(label="Prefixes", emoji=chr(129704), style=hikari.ButtonStyle.PRIMARY)
    async def prefixes(self, ctx: InuContext, _: ComponentInteraction) -> None:
        await PrefixView(old_view=self, guild_id=self.guild_id).start(ctx)

    # TODO: this needs to be rewritten, that second arg is button to change Style if want
    @button(label="Music", style=hikari.ButtonStyle.PRIMARY, emoji="🎵")
    async def lavalink_button(self, ctx: InuContext, _: ComponentInteraction) -> None:
        await LavalinkView(old_view=self, guild_id=self.guild_id).start(ctx)

    @button(label="Timezone", emoji=chr(9986), style=hikari.ButtonStyle.PRIMARY)
    async def timezone_button(self, ctx: InuContext, _: ComponentInteraction) -> None:
        await TimezoneView(old_view=self, guild_id=self.guild_id).start(ctx)

    @button(label="Activity logging", style=hikari.ButtonStyle.PRIMARY, emoji="🎮")
    async def activity_logging_button(self, ctx: InuContext, _: ComponentInteraction) -> None:
        await ActivityLoggingView(old_view=self, guild_id=self.guild_id).start(ctx)

    async def to_embed(self) -> hikari.Embed:
        embed = hikari.Embed(
            title=self.total_name,
            description="Here you can configure the bot.",
        )
        return embed
    @button(label="Autoroles", style=hikari.ButtonStyle.PRIMARY, emoji="🤖")
    async def autoroles_button(self, ctx: InuContext, _: ComponentInteraction) -> None:
        await AutorolesView(old_view=self, guild_id=self.guild_id).start(ctx)



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

settings_group = Group(
    "settings", 
    "Settings to change how certain things are handled", 
    dm_enabled=False,
    default_member_permissions=hikari.Permissions.ADMINISTRATOR,
)

@settings_group.register
class ActivityTracking(
    SlashCommand,
    name="activity-tracking",
    description="Enable (True) or disable (False) activity logging",
    hooks=[sliding_window(3, 1, "user")]
):
    enable = lightbulb.string("enable", "Whether to enable or disable activity logging", choices=YES_NO)
    
    @invoke
    async def callback(self, _: Context, ctx: InuContext):
        await self._callback(ctx, enable=self.enable)
        
    @staticmethod
    async def _callback(ctx: InuContext, *, enable: str):
        assert ctx.guild_id is not None
        embed = await update_activity_logging(ctx.guild_id, enable == "Yes")
        await ctx.respond(embed=embed)

@settings_group.register
class SettingsMenu(
    SlashCommand,
    name="menu",
    description="Interactive menu for all settings",
    hooks=[sliding_window(3, 1, "user")]
):
    @invoke
    async def callback(self, _: Context, ctx: InuContext):
        await self._callback(ctx)
        
    async def _callback(self, ctx: InuContext):
        #main_view = MainView(old_view=None, ctx=ctx)
        #message = await ctx.respond("settings")
        #await main_view.start_view(await message.message())
        pag = MainView(old_view=None, guild_id=ctx.guild_id)  # type: ignore
        await pag.start(ctx)

daily_pictures = settings_group.subgroup("daily-pictures", "Commands for daily pictures")

@daily_pictures.register
class AddChannel(
    SlashCommand,
    name="add_channel",
    description="Adds the channel where you are in, to a channel where I send pictures",
):
    @invoke
    async def callback(self, _: Context, ctx: InuContext):
        await self._callback(ctx)
        
    @staticmethod
    async def _callback(ctx: InuContext):
        if not ctx.guild_id:
            return
        channel_id = ctx.channel_id
        channel = ctx.get_channel()
        if not channel:
            await ctx.respond("I am not able to add this channel :/")
            return
        await DailyContentChannels.add_channel(Col.CHANNEL_IDS, channel_id, ctx.guild_id)
        await ctx.respond(f"added channel: `{channel.name}` with id `{channel.id}`")

@daily_pictures.register
class RemoveChannel(
    SlashCommand,
    name="rm_channel",
    description="Removes the channel you are in from daily content channels",
):
    @invoke
    async def callback(self, _: Context, ctx: InuContext):
        await self._callback(ctx)
        
    @staticmethod
    async def _callback(ctx: InuContext):
        if not ctx.guild_id:
            return
        channel_id = ctx.channel_id
        if not (channel := await bot.rest.fetch_channel(channel_id)):
            await ctx.respond(f"cant remove this channel - channel not found")
            return            
        await DailyContentChannels.remove_channel(Col.CHANNEL_IDS, channel_id, ctx.guild_id)
        await ctx.respond(f"removed channel: `{channel.name}` with id `{channel.id}`")

@daily_pictures.register
class AddTopChannel(
    SlashCommand,
    name="add_top_channel",
    description="Adds the channel where you are in, to top channels",
):
    @invoke
    async def callback(self, _: Context, ctx: InuContext):
        await self._callback(ctx)
        
    @staticmethod
    async def _callback(ctx: InuContext):
        if not ctx.guild_id:
            return
        channel_id = ctx.channel_id
        channel = ctx.get_channel()
        assert(isinstance(channel, hikari.GuildChannel))
        if not channel:
            await ctx.respond("I am not able to add this channel :/")
            return
        await DailyContentChannels.add_channel(Col.TOP_CHANNEL_IDS, channel_id, ctx.guild_id)
        await ctx.respond(f"added channel: `{channel.name}` with id `{channel.id}`")

@daily_pictures.register
class RemoveTopChannel(
    SlashCommand,
    name="rm_top_channel",
    description="Removes the channel from top channels",
):
    @invoke
    async def callback(self, _: Context, ctx: InuContext):
        await self._callback(ctx)
        
    @staticmethod
    async def _callback(ctx: InuContext):
        if not ctx.guild_id:
            return
        channel_id = ctx.channel_id
        if not (channel := await bot.rest.fetch_channel(channel_id)):
            await ctx.respond(f"cant remove this channel - channel not found")
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
):
    new_prefix = lightbulb.string("new-prefix", "The prefix you want to add | \"<empty>\" for no prefix")
    @invoke
    async def callback(self, _: Context, ctx: InuContext):
        await self._callback(ctx, new_prefix=self.new_prefix)
        
    @staticmethod
    async def _callback(ctx: InuContext, *, new_prefix: Optional[str]):
        if new_prefix is None:
            raise BotResponseError("Your prefix can't be None", ephemeral=True)
        if new_prefix == "<empty>":
            new_prefix = ""
        prefixes = await PrefixManager.add_prefix(ctx.guild_id, new_prefix)  # type: ignore
        await ctx.respond(f"""I added it. For this guild, the prefixes are now: {', '.join([f'`{p or "<empty>"}`' for p in prefixes])}""")

@prefix_group.register
class RemovePrefix(
    SlashCommand,
    name="remove",
    description="Remove a prefix",
):
    prefix = lightbulb.string("prefix", "The prefix you want to remove | \"<empty>\" for no prefix")
    
    @invoke
    async def callback(self, _: Context, ctx: InuContext):
        await self._callback(ctx, prefix=self.prefix)
        
    @staticmethod
    async def _callback(ctx: InuContext, *, prefix: str):
        if prefix == "<empty>":
            prefix = ""
        elif prefix == bot._default_prefix:
            return await ctx.respond(f"I won't do that xD")
        prefixes = await PrefixManager.remove_prefix(ctx.guild_id, prefix)  # type: ignore
        await ctx.respond(f"""I removed it. For this guild, the prefixes are now: {', '.join([f'`{p or "<empty>"}`' for p in prefixes])}""")

timezone_group = Group("timezone", "Timezone related commands", dm_enabled=False)
#settings_group.register(timezone_group)

@timezone_group.register
class SetTimezone(
    SlashCommand,
    name="set",
    description="Set the timezone of your guild - interactive",
):
    @invoke
    async def callback(self, _: Context, ctx: InuContext):
        await self._callback(ctx)
        
    @staticmethod
    async def _callback(ctx: InuContext):
        await set_timezone(ctx)

settings_board_group = Group("board", "group for board commands", dm_enabled=False)
#settings_group.register(settings_board_group)

@settings_board_group.register
class CreateBoard(
    SlashCommand,
    name="create-here",
    description="make this channel to a board",
):
    emoji = lightbulb.string("emoji", "messages with this emoji will be sent here", autocomplete=board_emoji_autocomplete)
    
    @invoke
    async def callback(self, _: Context, ctx: InuContext):
        await self._callback(ctx, emoji=self.emoji)
        
    @staticmethod
    async def _callback(ctx: InuContext, *, emoji: str):
        await BoardManager.add_board(
            guild_id=ctx.guild_id,  # type: ignore
            channel_id=ctx.channel_id,
            emoji=emoji,
        )
        channel = ctx.get_channel()
        if not channel:
            return await ctx.respond("I am not able to add this channel :/")
        await ctx.respond(
            f"{channel.name} is now a {emoji}-Board.\n"
            f"Means all messages with a {emoji} reaction will be sent in here."
        )

@settings_board_group.register
class RemoveBoard(
    SlashCommand,
    name="remove-here",
    description="this channel will no longer be a board",
):
    emoji = lightbulb.string("emoji", "the emoji which the board have", autocomplete=board_emoji_autocomplete)
    
    @invoke
    async def callback(self, _: Context, ctx: InuContext):
        await self._callback(ctx, emoji=self.emoji)
        
    @staticmethod
    async def _callback(ctx: InuContext, *, emoji: str):
        await BoardManager.remove_board(
            guild_id=ctx.guild_id,  # type: ignore
            emoji=emoji,
        )
        channel = ctx.get_channel()
        if not channel:
            return await ctx.respond("I am not able to remove this channel :/")
        await ctx.respond(
            f"{channel.name} is not a {emoji}-Board anymore.\n"
            f"Means all messages with a {emoji} will not be sent here any longer."
        )

async def set_timezone(ctx: InuContext, ephemeral: bool = True, **kwargs):
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
        ephemeral=ephemeral,
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