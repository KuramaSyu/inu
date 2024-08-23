import re
import traceback
import typing
from typing import (
    Optional,
    Union,
    List,
    Dict,
    Any,
    Tuple,
    cast
)

typing.TYPE_CHECKING
import asyncio
import logging
import asyncio
import datetime
import random
from collections import deque
from contextlib import suppress
from pprint import pformat

import hikari
from hikari import ComponentInteraction, Embed, ResponseType, VoiceStateUpdateEvent, ButtonStyle
from hikari.impl import MessageActionRowBuilder
import lightbulb
from lightbulb import SlashContext, commands, context
from lightbulb.commands import OptionModifier as OM
from lightbulb.context import Context
import lavalink_rs
from lavalink_rs.model.search import SearchEngines
from lavalink_rs.model.track import TrackData, PlaylistData, TrackLoadType, Track
from youtubesearchpython.__future__ import VideosSearch  # async variant
from fuzzywuzzy import fuzz
from pytimeparse.timeparse import timeparse
from humanize import naturaldelta
from expiring_dict import ExpiringDict
from tabulate import tabulate
from emoji import replace_emoji

from core import Inu, get_context, InuContext, getLogger, BotResponseError
from utils import (
    Paginator,
    Colors, 
    Human, 
    MusicHistoryHandler, 
    TagManager,
    TagType, 
    crumble
)
from .helpers import YouTubeHelper


log = getLogger(__name__)

bot: Optional[Inu] = None

def setup(inu: Inu):
    global bot
    bot = inu


class Queue:
    """
    Represents the queue message of one player
    """
    def __init__(
        self,
        player: "Player",
    ):
        self.player = player
        self._message: hikari.Message = None
        self._custom_info = ""
        self._custom_info_author: hikari.Member | None = None
        self._custom_footer: hikari.EmbedFooter | None = None
        self.create_footer_info = False
        self.current_track: Track | None = None
        self._last_update = datetime.datetime.now()

    async def fetch_current_track(self, update_node = True) -> Track | None:
        try:
            if update_node:
                await self.player.update_node()
            return self.player.node.queue[0].track
        except IndexError:
            return None

    async def set_message(self, message: hikari.Message):
        """
        Manually set the message used for the queue
        """
        if self._message:
            await self._message.delete()
        self._message = message
    
    def reset(self):
        self._custom_info = ""
        self._create_footer_info = False
        self._custom_info_author = None
        self._custom_footer = None
    
    @property
    def custom_info(self) -> str:
        return self._custom_info
    
    @custom_info.setter
    def custom_info(self, value: str):
        add = "\n" if self._custom_info else ""
        self._custom_info += f"{add}{value}"

    @property
    def custom_info_author(self) -> hikari.Member:
        return self._custom_info_author
    
    @custom_info_author.setter
    def custom_info_author(self, value: hikari.Member):
        self._custom_info_author = value


    def set_footer(
        self, 
        text: str = None, 
        author: hikari.SnowflakeishOr[hikari.Member] = None, 
        override_author: bool = False
    ) -> None:
        """
        Adds a custom footer for the queue message.
        The old footer will remain until the next song

        Args:
        ----
        text : str=None
            The text of the footer
        author : hikari.Member=None
            The author of the footer
        override_author : bool=False
            Wether or not to force set the given author. Otherwise the given author could be ignored
        """
        add = "\n" if self._custom_info else ""
        if text:
            self._custom_info += f"{add}{text}"
        if author and (override_author or not self._custom_info_author):
            self._custom_info_author = author

    def _build_custom_footer(self) -> Dict[str, Any]:
        kwargs = {"text": "", "icon": None}
        last_track: TrackQueue = self.node.queue[-1]
        requester = bot.cache.get_member(
            self.player.guild_id,
            self.custom_info_author 
            or self.player.ctx.author 
            or last_track.requester
        )
        # custom info
        if requester:
            kwargs["icon"] = f'{requester.avatar_url}'
            display_name = f'{requester.display_name}'
        else:
            display_name = last_track.requester

        if self.custom_info:
            kwargs["text"] += f"\n{self.custom_info}"
        elif self.create_footer_info:
            kwargs["text"] += f'\n{last_track.track.info.title} added by {display_name}'

        if not kwargs["text"]:
            kwargs["icon"] = bot.me.avatar_url
            
        # remaining time rounded to seconds
        total_playtime = datetime.timedelta(
            seconds=round(
                datetime.timedelta(
                    milliseconds=sum(
                        min(track.track.info.length, 36_000_000)  # max 10 hours -> prevent OverflowError
                        for track in self.node.queue
                    )
                ).total_seconds()
            )
        )
        queue_len = len(self.node.queue)-1-4  # current playing + 4 upcoming songs
        if not queue_len or queue_len < 0:
            queue_len = 0
        kwargs["text"] += f"\n⤵️{Human.plural_('song', queue_len, with_number=True)} ({total_playtime}) remaining in the queue"

        return kwargs

    @property
    def message(self) -> hikari.Message:
        if not self._message:
            raise TypeError("message is not set")
        return self._message
    
    @message.setter
    def message(self, message: hikari.Message):
        self._message = message

    @property
    def node(self) -> lavalink_rs.Node:
        return self.player.node

    def build_music_components(
        self,
        disable_all: bool = False,
    ) -> List[hikari.impl.MessageActionRowBuilder]:
        """builds the components for the music message
        
        Args:
        ----
        disable_all : bool=False
            If all buttons should be disabled, by default False
        """
        node = None
        paused_or_stopped = False
        if not disable_all:
            node = self.player._node
            if not node:
                disable_all = True

            
        action_rows = [
            (
                MessageActionRowBuilder()
                .add_interactive_button(
                    hikari.ButtonStyle.SECONDARY, 
                    "music_skip_1",
                    is_disabled=disable_all or node.is_paused,
                    emoji="1️⃣",
                )
                .add_interactive_button(
                    hikari.ButtonStyle.SECONDARY,
                    "music_skip_2",
                    emoji="2️⃣",
                    is_disabled=disable_all or node.is_paused,
                )
                .add_interactive_button(
                    hikari.ButtonStyle.SECONDARY,
                    "music_shuffle",
                    emoji="🔀",
                    is_disabled=disable_all,
                )
                .add_interactive_button(
                    hikari.ButtonStyle.SECONDARY,
                    "music_stop",
                    emoji="🛑",
                    is_disabled=disable_all,
                )
            )
        ]
        if not disable_all:
            if self.node.is_paused:
                action_rows[0].add_interactive_button(
                    hikari.ButtonStyle.PRIMARY,
                    "music_resume",
                    emoji="▶",
                )
            else:
                action_rows[0].add_interactive_button(
                    hikari.ButtonStyle.SECONDARY,
                    "music_pause",
                    emoji="⏸",
                )
        return action_rows
    
    @property
    def embed(self) -> hikari.Embed:
        """builds the embed for the music message"""
        AMOUNT_OF_SONGS_IN_QUEUE = 4
        node = self.player._node
        if not node:
            return Embed(
                description=(
                    "Queue is currently empty.\n"
                    "Add some songs with `/play` and the name or URL of the song\n"
                ),
                color=hikari.Color.from_rgb(71, 89, 211),
            )
        numbers = [
            '1️⃣','1️⃣','2️⃣','3️⃣','4️⃣','5️⃣','6️⃣','7️⃣','8️⃣','9️⃣','🔟'
        ] # double 1 to make it 1 based (0 is current playing song)

        upcomping_song_fields: List[hikari.EmbedField] = []
        first_field: hikari.EmbedField = hikari.EmbedField(
            name=" ", 
            value=" ", 
            inline=True
        )
        second_field: hikari.EmbedField = hikari.EmbedField(
            name=" ", 
            value=" ", 
            inline=True
        )
        pre_titles_total_delta = datetime.timedelta()

        # create upcoming song fields
        for i, items in enumerate(zip(node.queue, numbers)):
            _track, num = items
            track = _track.track
            if i == 0:
                # skip current playing song
                try:
                    pre_titles_total_delta += datetime.timedelta(milliseconds=track.info.length)
                except OverflowError:  # Python int too large for C int
                    pre_titles_total_delta += datetime.timedelta(milliseconds=36_000_000)  # 10 hours
                continue
            if i >= AMOUNT_OF_SONGS_IN_QUEUE + 1:
                # only show 4 upcoming songs
                break

            if node.is_paused:
                discord_timestamp = "--:--"
            else:
                discord_timestamp = f"<t:{(datetime.datetime.now() + pre_titles_total_delta).timestamp():.0f}:t>"

            pre_titles_total_delta += datetime.timedelta(milliseconds=track.info.length)
            upcomping_song_fields.append(
                hikari.EmbedField(
                    name=f"{num}{'' if node.is_paused else ' -'} {discord_timestamp}",
                    value=f"```ml\n{Human.short_text(track.info.title, 50, '...')}```",
                    inline=True,
                )
            )

        # split upcomping_song_fields into two EmbedFields
        total_len = len(upcomping_song_fields)
        for i, field in enumerate(upcomping_song_fields):
            # x.5 is first field
            if i < total_len / 2:
                if first_field.name == " ":
                    first_field.name = field.name
                    first_field.value = field.value
                else:
                    first_field.value += f"**{field.name}**\n{field.value}"
            elif i >= total_len / 2:
                if second_field.name == " ":
                    second_field.name = field.name
                    second_field.value = field.value
                else:
                    second_field.value += f"**{field.name}**\n{field.value}"
            else:
                if first_field.name == " ":
                    first_field.name = field.name
                    first_field.value = field.value
                else:
                    first_field.value += f"**{field.name}**\n{field.value}"
        
        upcomping_song_fields = []
        if first_field.name != " ":
            upcomping_song_fields.append(first_field)
        if second_field.name != " ":
            upcomping_song_fields.append(second_field)

        try:
            track = self.player.node.queue[0].track
        except Exception as e:
            return log.warning(f"can't get current playing song: {e}")

        if not node.queue[0].requester:
            log.warning("no requester of current track - returning")

        requester = bot.cache.get_member(self.player.guild_id, node.queue[0].requester)
        try:
            music_over_in = (
                datetime.datetime.now() 
                + datetime.timedelta(
                    milliseconds=track.info.length-track.info.position
                )
            ).timestamp()
        except OverflowError:
            music_over_in = (datetime.datetime.now() + datetime.timedelta(hours=10)).timestamp()
        if node.is_paused:
            paused_at = datetime.datetime.now()
            # min:sec
            music_over_in_str = f"<t:{paused_at.timestamp():.0f}:t>"    
        else:
            music_over_in_str = f'<t:{music_over_in:.0f}:R>'

        # create embed
        music_embed = hikari.Embed(
            colour=hikari.Color.from_rgb(71, 89, 211)
        )
        music_embed.add_field(
            name = "Was played:" if node.is_paused else "Playing:", 
            value=f'[{track.info.title}]({track.info.uri})', 
            inline=True
        )
        music_embed.add_field(
            name="Author:", 
            value=f'{track.info.author}', 
            inline=True
        )
        music_embed.add_field(
            name="Added by:", 
            value=f'{requester.display_name}' , 
            inline=True
        )
        music_embed.add_field(
            name = "Paused at:" if node.is_paused else "Over in:", 
            value=music_over_in_str, 
            inline=False
        )
        music_embed._fields.extend(upcomping_song_fields)
        music_embed.set_footer(**self._build_custom_footer())
        music_embed.set_thumbnail(
            YouTubeHelper.thumbnail_from_url(track.info.uri) 
            or bot.me.avatar_url
        )
        return music_embed
    
    def __len__(self) -> int:
        try:
            return len(self.player.node.queue)
        except RuntimeError:
            return 0
    
    async def send(
        self,
        ctx: InuContext | None = None,
        force_resend: bool = False,
        create_footer_info: bool = False, 
        custom_info: str = "",
        debug_info: str = ""
    ):
        '''
        refreshes the queue of the player
        uses ctx if not None, otherwise it will fetch the last context with the guild_id

        Args:
        -----
        ctx : Optional[InuContext]
            the context to use, by default the player context
        force_resend : bool
            wether to force resend the queue message, by default False
        create_footer_info : bool
            wether to create a footer info (last added song from user), by default False
        custom_info : str
            custom info to add to the footer, by default ""
        '''
        if debug_info:
            log.debug(f"send queue with debug_info: {debug_info}")
        if create_footer_info:
            self.create_footer_info = True
        if custom_info:
            self.custom_info = custom_info
        try:
            if len(self.player.node.queue) == 0:
                raise RuntimeError("queue is empty")
        except Exception:
            # return to prevent sending empty queue embed
            if not self.player.ctx._responded:
                await self.player.ctx.respond("The queue is empty hence I left the channel", delete_after=10)
            self.player._clean_queue = True
            await self.player._leave()
            return

        if ctx:
            self.player.ctx = ctx
        else:
            ctx = self.player.ctx

        if not ctx.guild_id:
            log.debug("guild_id is None in queue command;")
            return
        
        try:
            self.current_track = None 
            if self.player._node:
                try:
                    self.current_track = self.player.node.queue[0].track
                except:
                    pass
            self._last_update = datetime.datetime.now()
            music_embed = self.embed
            await self._send(music_embed, force_resend=force_resend)
        except Exception as e:
            log.error(traceback.format_exc())
        self.reset()

    async def _send(self, music_embed: hikari.Embed, force_resend: bool = False):
        """sends/edits the queue music message
        
        Args:
        -----
        music_embed : hikari.Embed
            the embed to send
        force_resend : bool, optional
            wether to force resend the message, by default False
        """
        old_music_msg = self._message
        music_message = None
        
        # fetch music message from last context
        try:
            resp = await self.player.ctx.message()
            if not resp:
                music_message = None
            else:
                music_message = resp
        except (hikari.NotFoundError, hikari.UnauthorizedError):
            music_message = None
        
        if (
            force_resend 
            or old_music_msg is None   
            or music_message is None 
        ):
            # send new message and override
            kwargs = {"update": False}
            log.debug(f"send new message with {kwargs=}, {music_message=}")
            msg = await self.player.ctx.respond(
                embed=music_embed, 
                content=None,
                components=self.build_music_components(), 
                **kwargs
            )
            new_music_msg = await msg.message()
            log.debug(f"new message: {new_music_msg}")
            # delete, if message was not reused
            try:
                if not old_music_msg is None and not old_music_msg.id == new_music_msg.id:
                    log.debug(f"delete old message {old_music_msg.id}")
                    await old_music_msg.delete()
                else:
                    log.debug(f"old message was reused. old: {old_music_msg}")
            except hikari.NotFoundError:
                log.debug("old message not found")
                pass
            except Exception:
                log.error(traceback.format_exc())
            self.message = new_music_msg
            return

        # edit existing message
        # only possible with component interactions
        try:
            timeout = 4
            ctx_message_id = old_music_msg.id
            async for m in bot.rest.fetch_messages(self.player.ctx.channel_id):
                if m.id == ctx_message_id:
                    # edit existing message if in last messages
                    kwargs = dict(
                        embed=music_embed, 
                        components=self.build_music_components(),
                        content=None, 
                        update=m.id
                    )
                    try:
                        msg = await self.player.ctx.respond(**kwargs)
                        self.message = await msg.message()
                        log.debug("updated old")
                    except hikari.NotFoundError:
                        log.warning(f"Queue._send - using REST fallback: {traceback.format_exc()}")
                        kwargs["channel"] = m.channel_id
                        del kwargs["update"]
                        msg = await self.player.ctx.bot.rest.edit_message(message=m.id, **kwargs)
                    return
                
                timeout -= 1
                if timeout == 0:
                    # resend message (not in last msgs found)
                    log.debug("send new")
                    try:
                        await music_message.delete()
                    except hikari.NotFoundError:
                        pass
                    msg = await self.player.ctx.respond(
                        embed=music_embed, 
                        content=None,
                        components=self.build_music_components(), 
                        update=False
                    )
                    self.message = await msg.message()
                    return
        except Exception:
            log.error(traceback.format_exc())