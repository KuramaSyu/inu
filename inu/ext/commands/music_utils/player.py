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
from utils.paginators.music_history import MusicHistoryPaginator
from ..tags import get_tag, _tag_add

from .helpers import YouTubeHelper, MusicHelper, MusicDialogs
from .queue import Queue
from .constants import *

log = getLogger(__name__)




lavalink: lavalink_rs.Lavalink = None
first_join = False
bot: Inu
music_helper = MusicHelper()
message_id_to_queue_cache: ExpiringDict = None
interactive: MusicDialogs = None



def setup(
        inu: Inu = None, 
        lavalink_: lavalink_rs.Lavalink = None,
        message_id_to_queue_cache_: ExpiringDict = None,
):
    global lavalink, bot, interactive, message_id_to_queue_cache
    if inu:
        bot = inu
        interactive = MusicDialogs(inu)
    if message_id_to_queue_cache_ is not None:
        message_id_to_queue_cache = message_id_to_queue_cache_
        
    if lavalink_:
        lavalink = lavalink_
    log.debug(f"message_id cache set to: {message_id_to_queue_cache_}")
    



class Player:
    """A Player which represents a guild Node and it's queue message"""
    def __init__(
        self,
        guild_id: int,
        node: lavalink_rs.Node = None,
    ):
        self.guild_id = guild_id
        self._node = node
        self.ctx = None
        self._query: str = ""
        self.queue: "Queue" = Queue(self)
        self._clean_queue: bool = True
        self._auto_leave_task: Optional[asyncio.Task] = None
        self.auto_parse = False
        self.last_added_track = None

    def track_to_md(self, track: lavalink_rs.Track) -> str:
        """Converts a track to markdown"""
        return f"[{track.info.title}]({track.info.uri})"
    
    async def prepare(self):
        """Prepares the player for usage and fetches the node"""
        if self._node is None:
            if not self.guild_id:
                raise RuntimeError("guild_id is not set")
            node = await lavalink.get_guild_node(self.guild_id)
            self.node = node

    def reset(self):
        self.query = ""

    @property
    def clean_queue(self) -> bool:
        """Wether the queue should be cleaned after the player left the channel"""
        return self._clean_queue
    
    async def set_clean_queue(
        self, 
        value: bool, 
        interval: datetime.timedelta = datetime.timedelta(minutes=1)
    ):
        """Sets the clean_queue value and starts the auto leave task"""
        old_value = self._clean_queue
        self._clean_queue = value
        await asyncio.sleep(interval.total_seconds())
        self._clean_queue = old_value

    def check_if_bot_is_alone(self) -> bool:
        """
        Checks if the bot is alone in the voice channel.
        """
        if not self.guild_id:
            # theoretically this should never happen
            return
        if not (voice_state := bot.cache.get_voice_state(self.guild_id, bot.me.id)):
            # not in a channel
            return
        if not (channel_id := voice_state.channel_id):
            # not in a channel
            return
        other_states = [
            state 
            for state 
            in bot.cache.get_voice_states_view_for_channel(
                self.guild_id, channel_id
            ).values() 
            if state.user_id != bot.get_me().id
        ]
        if not other_states:
            return True
        return False
    
    def check_if_bot_in_channel(self, channel_id: int) -> bool:
        """Checks if the bot is in the channel"""
        if not self.guild_id:
            # theoretically this should never happen
            return
        if not (voice_state := bot.cache.get_voice_state(self.guild_id, self.ctx.author.id)):
            # not in a channel
            return
        if not (channel_id := voice_state.channel_id):
            # not in a channel
            return
        if channel_id == channel_id:
            return True
        return False

    
    async def auto_leave(self):
        log.debug("auto leave - start")
        if len(self.node.queue) > 0:
            await self._pause()
            self.queue.set_footer(
                f"I'll leave the channel in {naturaldelta(DISCONNECT_AFTER)} - the queue will be saved", 
                author=bot.me, 
                override_author=True
            )
            await self.queue.send()

        await asyncio.sleep(DISCONNECT_AFTER)
        log.debug(f"auto leave - leave now")
        if len(self.node.queue) > 0:
            asyncio.create_task(self.set_clean_queue(False))

            self.queue.set_footer(
                "I left the channel, but the queue is saved", 
                author=bot.me, 
                override_author=True
            )
        # queue will be sent on leave in voice state listener
        await self._leave()
        self._auto_leave_task = None

    async def on_bot_lonely(self):
        """
        gets called, when only the player is left in the voice channel. 
        Leaving 10 Minutes later, if no one joins
        """
        if not self._auto_leave_task:
            self._auto_leave_task = asyncio.create_task(self.auto_leave())

    async def on_human_join(self):
        """gets called, when a human joins the voice channel. This cancels the leave timer"""
        if self._auto_leave_task:
            self._auto_leave_task.cancel()
            self._auto_leave_task = None

    @property
    def node(self) -> lavalink_rs.Node:
        """Returns the node of the player"""
        if not self._node:
            raise RuntimeError("Node is not set")
        return self._node
    
    @node.setter
    def node(self, node: lavalink_rs.Node):
        self._node = node
    
    @property
    def query(self):
        """The query of the searched title"""
        return self._query
    
    @query.setter
    def query(self, query: str):
        self._query = query

    async def play(
        self,
        query: str,
    ):
        ...

    async def _skip(self, amount: int) -> bool:
        """
        Returns:
        --------
            - (bool) wether the skip(s) was/where successfull
        """
        for _ in range(amount):
            skip = await lavalink.skip(self.guild_id)
            if not skip:
                return False
            if not (node := await lavalink.get_guild_node(self.guild_id)):
                return False
            await self.update_node(node)
            if not skip:
                return False
            # else:
            #     # If the queue is empty, the next track won't start playing (because there isn't any),
            #     # so we stop the player.
            #     if not node.queue and not node.now_playing:
            #         await lavalink.stop(self.guild_id)
        return True
    
    async def _clear(self):
        """Clears the node queue"""
        queue = [self.node.queue[0]]
        self.node.queue = queue
        await lavalink.set_guild_node(self.guild_id, self.node)

    async def seek(self, time_str: str) -> int | None:
        """Seeks to a specific position in the track
        
        Args:
            time_str (str): The time string representing the position to seek to
        
        Returns:
            int | None: The number of seconds the track was seeked to
        """
        seconds = await self._seek(time_str)
        if seconds is None:
            return None
        custom_info = f"⏩ {self.ctx.author.username} jumped to {str(datetime.timedelta(seconds=seconds))}"
        self.queue.set_footer(custom_info)
        music_helper.add_to_log(
            guild_id=self.guild_id, 
            entry=custom_info
        )
        return seconds
    
    async def _seek(self, time_str: str) -> int | None:
            """Seeks to a specific position in the track
            
            Args:
                time_str (str): The time string representing the position to seek to
            
            Returns:
                int | None: The number of seconds the track was seeked to
            """
            try:
                seconds = timeparse(time_str)
            except Exception:
                return None
            if seconds < 0:
                # current time - seconds
                track = await self.queue.fetch_current_track()
                if track is None:
                    return None
                seconds = max(track.info.position - seconds, 0)
            await lavalink.seek_secs(self.guild_id, seconds)
            await self.update_node()
            return seconds
    
    @property
    def ctx(self) -> InuContext:
        """The currently used context of the player"""
        if not self._ctx:
            raise TypeError("ctx is not set")
        return self._ctx
    
    @ctx.setter
    def ctx(self, ctx: InuContext):
        self._ctx = ctx

    async def update_node(self, node: lavalink_rs.Node | None = None) -> None:
        """this re-fetches the node. This should be called, when the node changed"""
        if node is None:
            node = await lavalink.get_guild_node(self.guild_id)
        self.node = node

    async def _join(self) -> Optional[hikari.Snowflake]:
        """Joins the voice channel of the author"""
        assert self.ctx.guild_id is not None
        if not (voice_state := bot.cache.get_voice_state(self.guild_id, self.ctx.author.id)):
            raise BotResponseError("Connect to a voice channel first, please", ephemeral=True)

        channel_id = voice_state.channel_id
        await bot.update_voice_state(self.guild_id, channel_id, self_deaf=True)
        connection_info = await lavalink.wait_for_full_connection_info_insert(self.ctx.guild_id)
        # the follwoing line causes an issue, where lavalink plays faster then normal
        # await lavalink.create_session(connection_info)
        return channel_id

    async def _leave(self):
        """Leaves the voice channel"""
        await bot.update_voice_state(self.guild_id, None)

    async def _fix(self):
        if not (voice_state := bot.cache.get_voice_state(self.guild_id, self.ctx.author.id)):
            return None

        channel_id = voice_state.channel_id

        await bot.update_voice_state(self.guild_id, channel_id, self_deaf=True)
        connection_info = await lavalink.wait_for_full_connection_info_insert(self.ctx.guild_id)
        await lavalink.create_session(connection_info) # <-- possible issue

        await self._pause()
        await asyncio.sleep(0.1)
        await self._resume()

    async def _pause(self):
        await lavalink.pause(self.guild_id)
        await self.update_node()

    async def _resume(self):
        if not bot.cache.get_voice_state(self.guild_id, bot.me.id):
            await self._join()
            await lavalink.resume(self.ctx.guild_id)
            await self._lavalink_rejoin_workaround()
        else:
            await lavalink.resume(self.ctx.guild_id)
        await self.update_node()

    async def re_add_current_track(self):
        queue = self.player.node.queue 
        queue.insert(0, queue[0])
        self.player._node.queue = queue
        await self.update_node(node=self.player._node)
    
    async def _play(
        self, 
        query: str | None = None, 
        prevent_to_queue: bool = False,
        recursive: bool = False,
    ) -> Tuple[bool, InuContext | None]:
        """
        - Will search the query
        - if more than one track found, ask which track to use
        - queue the track(s)
        - if no track found, tell the user
        - send queue if not prevented

        Args:
        -----
        ctx: lightbulb.Context
            the context of the command
        query: str
            the query to search for
        recursive: bool
            whether the function is called recursively
        prevent_to_queue: bool
            whether to prevent sending the queue
            - needed when queue have to be called afterwards

        Returns:
        -------
        bool : 
            wether or not it fails to add a title

        Note
        ----
        sending the queue will be automatically prevented, 
        when only one song is in the node, hence the 
        track start event will trigger the queue.
        sending the queue will be also prevented, when a 
        playlist is added and the playlist is the 
        first element in the queue.
        """
        
        if query:
            self.query = query
        else:
            query = self.query
        if not self.ctx.guild_id or not self.ctx.member:
            return False, None
        ictx = self.ctx
        resolved = False  # bool wether the query was resolved - mainly used for multi line queries
        force_resend = True  # Whether or not the queue message will be new or will reuse the old one

        if not recursive:
            con = lavalink.get_guild_gateway_connection_info(self.guild_id)
            self.queue._last_update = datetime.datetime.now()
            # Join the user's voice channel if the bot is not in one.
            if not con:
                await self._join()
            await self.update_node()
            await ictx.defer()

        # -> multiple lines -> play every line
        if len(lines := query.splitlines()) > 1:
            self.auto_parse = True
            msg = ""
            songs: List[Dict[str, str]] = []
            rate_limit = 0
            msg_id = None
            for i, line in enumerate(lines):
                if not line:
                    continue
                if matches := MARKDOWN_URL_REGEX.findall(line):
                    _, line = matches[0]
                await self._play(line, prevent_to_queue=True, recursive=True)

                line_content = Human.short_text(
                    replace_emoji(self.last_added_track.info.title, ''), 
                    50, 
                    intelligent=False
                ) if self.last_added_track else 'Not found -> apply rate limit'
                
                msg += f"{line_content}\n"
                table = tabulate(
                    [[i+1, line] for i, line in enumerate(msg.splitlines())],
                    headers=["#", "Title"],
                    tablefmt="simple_outline"
                )
                send_message_task = asyncio.Task(
                    ictx.respond(
                        Human.short_text_from_center(f"Looking up titles:\n```\n{table}```", 2000), 
                        update=msg_id or True
                ))
                if not msg_id:
                    done, _ = await asyncio.wait([send_message_task], return_when=asyncio.FIRST_COMPLETED)
                    msg_id = (await (done.pop().result()).message()).id
                if self.last_added_track is None:
                    rate_limit = 1
                else:
                    songs.append({
                        "title": self.last_added_track.info.title,
                        "url": self.last_added_track.info.uri
                    })
                await asyncio.sleep(rate_limit)
            self.auto_parse = False
            # check if this is the `top level _play` call
            if not prevent_to_queue:
                # is top level call -> add save as tag component
                await ictx.respond(
                    components=[
                        MessageActionRowBuilder()
                        .add_interactive_button(ButtonStyle.PRIMARY, f"queue_to_tag_{msg_id}", label="Save as Tag", emoji="➕")
                    ],
                    update = msg_id or True
                )
            message_id_to_queue_cache[msg_id] = songs
            self.queue.reset()
            self.queue.set_footer(text=f"🎵 multiple titles added by {ictx.author.username}", author=ictx.author.id)
            resolved = True

        elif query.startswith(HISTORY_PREFIX):
            # -> history -> get url from history
            # only edits the query
            query = query.replace(HISTORY_PREFIX, "")
            history = await MusicHistoryHandler.cached_get(self.guild_id)
            if (alt_query:=[t["url"] for t in history if query in t["title"]]):
                await self._play(query=alt_query[0], prevent_to_queue=True, recursive=True)
            else:
                await ictx.respond(f"Couldn't find the title `{query}` in the history")
                return False, None
            resolved = True

        elif query.startswith(MEDIA_TAG_PREFIX):
            # -> media tag -> get url from tag
            # only edits the query
            query = query.replace(MEDIA_TAG_PREFIX, "")
            tag = await get_tag(ictx, query)
            await self._play(query=tag["tag_value"][0], prevent_to_queue=True, recursive=True) 
            self.queue.reset()
            self.queue.set_footer(text=f"🎵 {tag['tag_key']} added by {ictx.author.username}", author=ictx.author.id)
            resolved = True

        query = self.query
        if 'youtube' in query and 'playlist?list=' in query and not resolved:
            # -> youtube playlist -> load playlist
            await self.load_playlist()
        elif 'soundcloud' in query and 'sets/' in query and not resolved:
            # -> soundcloud playlist -> load playlist
            await self.load_playlist()
        # not a youtube playlist nor soundcloud playlist -> something else
        elif not resolved:
            # check if yt track contains playlist info
            if (
                "watch?v=" in query
                and "youtube" in query
                and "&list" in query
            ):
                # -> track from a playlist was added -> remove playlist info
                query = YouTubeHelper.remove_playlist_info(query)
            if (
                not (re.match(r"^https?:\/\/", query)) 
                and not ("ytsearch:" in query or "scsearch:" in query)
            ):
                # nor 'ytsearch:' nor 'scsearch:' in query -> add the guild-default
                query = f"{bot.data.preffered_music_search.get(ictx.guild_id, 'ytsearch')}:{query}"
            log.debug(f"{query=}")
            # try to add song
            event: Optional[hikari.InteractionCreateEvent] = None
            try:
                # ask interactive for song
                track, event = await self.search_track(ictx, query)
                force_resend = False  # queue can reuse this message
            except BotResponseError as e:
                raise e
            except asyncio.TimeoutError:
                return False, None
            except Exception:
                log.error(traceback.format_exc())
                raise BotResponseError(
                    "Something went wrong while searching for the title", 
                    ephemeral=True
                )
            if track is None:
                if not recursive:
                    await ictx.respond(f"I only found a lot of empty space for `{query}`")
                return False, None
            if event:
                # asked with menu - update context
                self.ctx = get_context(event=event)
                await self.ctx.defer(update=True, background=True)
                # set the queue message to the 'ask-user' message
                await self.queue.set_message(await ictx.message())
            await self.load_track(track)

        if not prevent_to_queue and not recursive:
            await self.queue.send(force_resend=force_resend, create_footer_info=False, debug_info="from play"),
        return True, ictx

    async def fallback_track_search(self, query: str):
            log.warning(f"using fallback youtbue search")
            v = VideosSearch(query, limit = 1)
            result = await v.next()

            try:
                query_information = await lavalink.auto_search_tracks(
                    result["result"][0]["link"]
                )
                return query_information
            except IndexError:
                return None

    async def search_track(
            self,
            ctx: Context, 
            query: str, 
    ) -> Tuple[Optional[lavalink_rs.Track], Optional[hikari.InteractionCreateEvent]]:
        """
        searches the query and returns the Track or None

        Raises:
        ------
        BotResponseError :
            Given query is not available
        asyncio.TimeoutError :
            User hasn't responded to the menu
        """
        log.debug(f"search with query: {query}")
        query_information = await lavalink.get_tracks(query)
        track = None
        event = None

        if not query_information.tracks:
            query_information = await self.fallback_track_search(query)

        if not query_information:
            self.last_added_track = None
            return None, None
        
        if len(query_information.tracks) > 1:
            try:
                if self.auto_parse:
                    # dont use official music videos
                    PREVENT = ["official video", "official music video", "official audio"]
                    for track in query_information.tracks:
                        if not any([p in track.info.title.lower() for p in PREVENT]):
                            return track, None
                    return query_information.tracks[0], None
                else:
                    track, event = await interactive.ask_for_song(ctx, query, query_information=query_information)
                if event is None:
                    # no interaction was done - delete selection menu
                    return None, None
            except asyncio.TimeoutError as e:
                raise e
            except Exception:
                log.error(traceback.format_exc())
        elif len(query_information.tracks) == 0:
            embed = Embed(title="Title not available")
            url_pattern = "^https?:\\/\\/(?:www\\.)?[-a-zA-Z0-9@:%._\\+~#=]{1,256}\\.[a-zA-Z0-9()]{1,6}\\b(?:[-a-zA-Z0-9()@:%_\\+.~#?&\\/=]*)$"
            if re.match(url_pattern, query):  # Returns Match object
                embed.add_field(name="Typical issues", value=(
                    "• Your title has an age limit\n"
                    "• Your title is not available in my region\n"
                    "• I could have problems with YouTube or Soundcloud.\n"
                    "If this problem persists with popular titles, then it's my issue\n"
                ))
                embed.add_field(name="What you can do:", value=(
                    "• Do `/settings menu`, go to `Music` and change from YouTube to Soundcloud or vice versa\n"
                    "• search by name instead of URL\n"
                    "• try other URL's\n"
                    "• Report problem: [GitHub Issues - zp33dy/inu](https://github.com/zp33dy/inu/issues)"
                ))
                embed.description = f"Your [title]({query}) is not available for me"
            else:
                embed.add_field(name="Typical issues", value=(
                    "• You have entered a bunch of shit\n"
                    "• I could have problems with connecting to YouTube or SoundCloud. \n"
                    "If this problem persists with popular titles, then it's my issue\n"
                ))
                embed.add_field(name="What you can do:", value=(
                    "• Give me shorter queries\n"
                    "• Do `/settings menu`, go to `Music` and change from YouTube to Soundcloud or vice versa\n"
                    "• Report problem: [GitHub Issues - zp33dy/inu](https://github.com/zp33dy/inu/issues)"
                ))
                embed.description = f"I just found a lot of empty space for `{query}`"
            raise BotResponseError(embed=embed, ephemeral=True)
        else:
            track = query_information.tracks[0]
        return track, event
    
    async def load_playlist(self) -> lavalink_rs.Tracks:
        """
        loads a youtube playlist

        Parameters
        ----------
        ctx : InuContext
            The context to use for sending the message and fetching the node
        query : str
            The query to search for
        be_quiet : bool, optional
            If the track should be loaded without any response, by default False
        
        Returns
        -------
        `lavalink_rs.Track` :
            the first track of the playlist
        """
        tracks = await lavalink.get_tracks(self.query)
        for track in tracks.tracks:
            await (
                lavalink
                   .play(self.ctx.guild_id, track)
                   .requester(self.ctx.author.id)
                   .queue()
            )
        if tracks.playlist_info:
            embed = Embed(
                title=f'Playlist added',
                description=f'[{tracks.playlist_info.name}]({self.query})'
            ).set_thumbnail(self.ctx.member.avatar_url)

            playlist_name = str(tracks.playlist_info.name)
            self.queue.custom_info = f"🎵 {playlist_name} Playlist added by {self.ctx.member.display_name}"
            self.queue.custom_info_author = self.ctx.member
            music_helper.add_to_log(
                self.ctx.guild_id, 
                self.queue.custom_info, 
            )
            await MusicHistoryHandler.add(
                self.ctx.guild_id, 
                str(tracks.playlist_info.name),
                self.query,
            )
            await self.update_node()
        return tracks

    async def play_at_pos(self, pos: int, query: str | None = None):
        """Adds a song at the <position> position of the queue. So the track will be played soon
        
        Args:
        ----
        ctx : InuContext
            The context to use for sending the message and fetching the node
        pos : int
            The position where the song should be added
        query : str
            The query to search for
        """
        if query:
            self.query = query
        try:
            ctx = self.ctx
            await ctx.defer()
            prevent_to_queue = False
            song_added, ctx = await self._play(prevent_to_queue=True)

            if not song_added:
                return
            await self.update_node()
            if not (node := self.node):
                return
            node_queue = node.queue
            track = node_queue.pop(-1)
            node_queue.insert(pos, track)
            node.queue = node_queue
            await lavalink.set_guild_node(ctx.guild_id, node)
            await self.update_node(node)
            if not prevent_to_queue:
                await self.queue.send(
                    force_resend=True, 
                    create_footer_info=False,
                    debug_info="play_at_pos"
                )
        except BotResponseError as e:
            raise e
        except Exception as e:
            log.error(traceback.format_exc())



    async def load_track(self, track: lavalink_rs.Track):
        """Loads a track into the queue
        
        Args:
        ----
        ctx : InuContext
            The context to use for sending the message and fetching the node
        track : lavalink_rs.Track
            The track to load
        be_quiet : bool, optional
            If the track should be loaded without any response, by default False
        """
        guild_id = self.guild_id
        author_id = self.ctx.author.id
        if not self.guild_id or not guild_id:
            raise Exception("guild_id is missing in `lightbulb.Context`")
        try:
            # `.queue()` To add the track to the queue rather than starting to play the track now.
            await (
                lavalink
                .play(guild_id, track)
                .requester(author_id)
                .queue()
            )
            self.last_added_track = track
            self.queue.custom_info = f"🎵 {track.info.title} added by {bot.cache.get_member(self.guild_id, self.ctx.author.id).display_name}"
            self.queue.custom_info_author = self.ctx.member
            await self.update_node()
        except lavalink_rs.NoSessionPresent:
            await self.ctx.respond(f"Use `/join` first")
            return

    async def _lavalink_rejoin_workaround(self):
        """
        Readds the first song and skips the current playing.
        Only when skipping, audio will be heard again.
        This seems to be a lavalink issue
        """
        await self.re_add_current_track()
        await self._skip(1)


class PlayerManager:
    _players: Dict[int, "Player"] = {}

    @classmethod
    async def get_player(
        cls, 
        guild_id: int, 
        event: hikari.InteractionCreateEvent | None = None, 
        ctx: InuContext | None = None
    ) -> "Player":
        if not guild_id in cls._players:
            cls._players[guild_id] = Player(guild_id)
        player = cls._players[guild_id]
        if event:
            ctx = get_context(event)
        if ctx:
            player.ctx = ctx
        await player.prepare()
        return player
        
    @classmethod
    def remove_player(cls, guild_id: int) -> None:
        if guild_id in cls._players:
            del cls._players[guild_id]