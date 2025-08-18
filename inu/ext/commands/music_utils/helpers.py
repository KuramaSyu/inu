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

import lavalink_rs.model
import lavalink_rs.model.track

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
from hikari import ComponentInteraction, Embed
from hikari.impl import MessageActionRowBuilder
import lightbulb
from lightbulb.context import Context
import lavalink_rs
from lavalink_rs.model.search import SearchEngines
from lavalink_rs.model.track import TrackData, PlaylistData, TrackLoadType, Track, TrackError

from core import Inu, getLogger, InuContext


log = getLogger(__name__)
bot: Optional[Inu] = None


def setup(bot_: Inu):
    global bot
    bot = bot_


class MusicDialogs:
    """A class with methods which do some music stuff interactive"""
    def __init__(self, bot: Inu):
        self.bot = bot
        self.lavalink: lavalink_rs.LavalinkClient = self.bot.data.lavalink
        self.queue_msg: Optional[hikari.Message] = None


    async def ask_for_song(
        self,
        ctx: InuContext,
        query: str,
        displayed_song_count: int = 24,
        query_information: Track | None = None,
    ) -> Tuple[Optional[Track], Optional[hikari.InteractionCreateEvent]]:
        """
        Creates an interactive menu for choosing a song

        Args
        ----
        ctx: InuContext 
            the context invoked with
        query: str 
            the query to search; either an url or just a string
        displayed_song_count: int = 24
            the amount of songs which will be showen in the interactive message
        query_information: Optional[Tracks] = None 
            existing information to lower footprint
            
        returns
        -------
        Optional[Track]
            the chosen title (is None if timeout or other errors)
        Optional[hikari.InteractionCreateEvent]

        raises
        ------
        asyncio.TimeoutError:
            When no interaction with the menu was made
        """
        if not ctx.guild_id or not bot:
            return None, None
        query_print = ""
        if not query_information:
            query = SearchEngines.youtube(query)
            query_information = await self.lavalink.load_tracks(ctx.guild_id, query)
            tracks: TrackData | PlaylistData | List[TrackData] | TrackError | None = query_information.data
            if not isinstance(query_information.load_type, TrackLoadType.Search):
                log.critical(f"Query information is not a search type: {query_information.load_type}")
                log.critical(f"{query_information=}")
            cast(List[TrackData], tracks)
            log.debug(f"{tracks=}")
        id_ = bot.id_creator.create_id()
        menu = (
            MessageActionRowBuilder()
            .add_text_menu(f"query_menu-{id_}")
            .set_placeholder("Choose a song")
            .set_max_values(1)
            .set_min_values(1)
        )
        embeds: List[Embed] = []
        # building selection menu
        for x in range(displayed_song_count):
            try:
                track = tracks[x]
            except IndexError:
                break
            query_print = f"{x+1} | {track.info.title}"
            if len(query_print) > 100:
                query_print = query_print[:100]
            menu.add_option(track.info.title[:100], str(x))
            embeds.append(
                Embed(
                    title=f"{x+1} | {track.info.title}"[:100],
                ).set_thumbnail(YouTubeHelper.thumbnail_from_url(track.info.uri))
            )
        menu = menu.parent
        stop_button = (
            MessageActionRowBuilder()
            .add_interactive_button(
                hikari.ButtonStyle.SECONDARY, 
                f"stop_query_menu-{id_}", 
                label=r"I don't find it ¯\_(ツ)_/¯",
                emoji="🗑️"
            )
        )
        msg_proxy = await ctx.respond(components=[menu, stop_button])
        menu_msg = await msg_proxy.message()
        event = None
        try:
            event = await self.bot.wait_for(
                hikari.InteractionCreateEvent,
                60,
                lambda e: (
                    isinstance(e.interaction, ComponentInteraction) 
                    and e.interaction.user.id == ctx.author.id
                    and e.interaction.message.id == menu_msg.id
                    and f"query_menu-{id_}" in e.interaction.custom_id
                )
            )
            if not isinstance(event.interaction, ComponentInteraction):
                return None, None  # to avoid problems with typecheckers
            if len(event.interaction.values) == 0:
                if event.interaction.custom_id.startswith("stop"):
                    await msg_proxy.delete()
                    raise asyncio.TimeoutError("User stopped the query")
            track_num = int(event.interaction.values[0])
        except asyncio.TimeoutError as e:
            with suppress(hikari.NotFoundError):
                await msg_proxy.delete()
            raise e
        # await event.interaction.create_initial_response(
        #     ResponseType.MESSAGE_UPDATE,
        #     content=f"🗑️ Choose the song which should be added"
        # )
        # await event.interaction.delete_initial_response()
        return query_information.tracks[track_num], event


class MusicHelper:
    def __init__(self):
        self.music_logs: Dict[int, MusicLog] = {}
    
    def add_to_log(self, guild_id: int, entry: str):
        """
        adds the <entry> to the `MusicLog` object of the guild with id <guild_id>
        Args:
        -----
            - guild_id: (int) the id of the guild
            - entry: (str) the entry which should be added
        Note:
        -----
            - if there is no log for the guild with id <guild_id>, than a new one will be created
        """

        log = self.music_logs.get(guild_id)
        if log is None:
            log = MusicLog(guild_id)
            self.music_logs[guild_id] = log
        log.add(entry)

    def get_log(self, guild_id: int, max_log_entry_len: int = 1980):
        """
        returns the log of <guild_id>
        
        Args:
        -----
            - guild_id: (int) the id of the guild
            - max_log_entry_len: (int, default=1980) the max len a string (log entry) of the returning list (the log)
        
        Returns:
            - (List[str] | None) the log with its entries or `None`
        """

        raw_log = self.get_raw_log(guild_id)
        if raw_log is None:
            return None
        return raw_log.to_string_list(max_log_entry_len)

    def get_raw_log(self, guild_id):
        """
        returns the raw log of <guild_id>
        
        Args:
        -----
            - guild_id: (int) the id of the guild
        
        Returns:
            - (`MusicLog` | None) the log with its entries or `None`
        """
        return self.music_logs.get(guild_id)




class YouTubeHelper:
    """A YouTube helper to convert some stuff - more like a collection"""
    @staticmethod
    def id_from_url(url: str) -> Optional[str]:
        """Returns the id of a video or None out of th given url"""
        start = url.find("watch?v=")
        if start == -1:
            return None
        start += 7
        end = url[start:].find("&")
        
        if end == -1:
            return url[start+1:]
        return url[start+1:end+start]

    @classmethod
    def thumbnail_from_url(cls, url: str) -> Optional[str]:
        """Returns the thumbnail url of a video or None out of th given url"""
        video_id = cls.id_from_url(url)
        if not video_id:
            return None
        return f"http://img.youtube.com/vi/{video_id}/hqdefault.jpg"

    @staticmethod
    def remove_playlist_info(url: str):
        start = url.find("watch?v=")
        end = url[start:].find("&")
        if end == -1:
            return url
        return url[:end+start]



class MusicLog:
    """
    A class which handels one guild music log.
    The internally the log is a `collections.deque` object
    
    Properties:
    -----------
        - guild_id: (int) the id of the guild the log belongs to
        - music_log: (collections.deque) the list which contains the log entries (most recent first)
    """
    def __init__(self, guild_id: int):
        self.guild_id = guild_id
        self.music_log = deque()

    def add(self, log_entry: str):
        self.music_log.appendleft(f"`{self.format_time_now():<10}:` {log_entry}")

    def format_time_now(self):
        """
        Returns:
        --------
            - (str) `hour`:`minute`:`second` - `month_day_num`. `month`
        """
        time = datetime.datetime.now()
        return f'{time.hour:02d}:{time.minute:02d}:{time.second:02d} - {time.day:02d}. {time.month:02d}'

    def to_string_list(self, max_str_len: int = 1980) -> List[str]:
        """
        converts this to a list with all the log entries. Each entry in the list
        has a max lenth <max_str_len>. Helpfull for sending the log into discord.
        Most recent log entries first
        Args:
        -----
            - max_str_len: (int, default=1980) the maximum length of a string in the return list
        Returns:
        --------
            - (List[str]) the converted list
        """
        str_list = []
        new_entry = ""
        for entry in self.music_log:
            if len(entry) > max_str_len:
                index = 0
                while index < len(entry):
                    str_list.append(entry[index:index + max_str_len])
                    index += max_str_len
            else:
                if len(new_entry) + len(entry) < max_str_len:
                    new_entry += f"{entry}\n"
                else:
                    str_list.append(new_entry)
                    new_entry = entry
        if new_entry:
            str_list.append(new_entry)
        return str_list