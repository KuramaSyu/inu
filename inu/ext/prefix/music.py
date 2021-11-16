import os
from pickle import HIGHEST_PROTOCOL
import traceback
import typing
from typing import (
    Optional,
    Union,
    List,
    Dict,
    Any,
    Tuple
)
import asyncio
import logging
import asyncio
import datetime
from pprint import pformat
import random
from collections import deque
import json
from unittest.util import _MAX_LENGTH

import hikari
from hikari import ComponentInteraction, Embed, ResponseType, ShardReadyEvent, VoiceState, VoiceStateUpdateEvent
from hikari.impl import ActionRowBuilder
import lightbulb
from lightbulb import Context, command, check
import lavasnek_rs
from matplotlib.pyplot import hist

from core import Inu
from utils import Paginator
from utils import Color
from utils.db import Database
from utils.paginators.specific_paginators import MusicHistoryPaginator

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)


# If True connect to voice with the hikari gateway instead of lavasnek_rs's
HIKARI_VOICE = False


class EventHandler:
    """Events from the Lavalink server"""
    def __init__(self, ext: "Music"):
        self.ext = ext
    async def track_start(self, lavalink: lavasnek_rs.Lavalink, event: lavasnek_rs.TrackStart) -> None:
        # log.info("Track started on guild: %s", event.guild_id)
        await self.ext.queue(guild_id=event.guild_id)
        node = await lavalink.get_guild_node(event.guild_id)
        if node is None:
            return
        track = node.queue[0].track
        await MusicHistoryHandler.add(event.guild_id, track.info.title, track.info.uri)

    async def track_finish(self, _: lavasnek_rs.Lavalink, event: lavasnek_rs.TrackFinish) -> None:
        log.info("Track finished on guild: %s", event.guild_id)

    async def track_exception(self, lavalink: lavasnek_rs.Lavalink, event: lavasnek_rs.TrackException) -> None:
        log.warning("Track exception event happened on guild: %d", event.guild_id)
        log.warning(event.exception_message)
        # If a track was unable to be played, skip it
        skip = await lavalink.skip(event.guild_id)
        node = await lavalink.get_guild_node(event.guild_id)

        if skip and not node is None:
            if not node.queue and not node.now_playing:
                await lavalink.stop(event.guild_id)

class Interactive:
    """A class with methods which do some music stuff interactive"""
    def __init__(self, bot: Inu):
        self.bot = bot
        self.lavalink = self.bot.data.lavalink
        self.queue_msg: Optional[hikari.Message] = None


    async def ask_for_song(
        self,
        ctx: lightbulb.Context,
        query: str,
        displayed_song_count: int = 30,
        query_information: lavasnek_rs.Tracks = None,
    ) -> Optional[lavasnek_rs.Track]:
        """
        Creates an interactive menu for choosing a song

        Args
        ----
            - ctx: (Context) the context invoked with
            - query: (str) the query to search; either an url or just a string
            - displayed_song_count: (int, default=30) the amount of songs which will be showen in the interactive message
            - query_information: (lavasnek_rs.Tracks, default=None) existing information to lower footprint
            
        returns
        -------
            - (lavasnek_rs.Track | None) the chosen title (is None if timeout or other errors)
        """
        if not ctx.guild_id:
            return
        query_print = ""
        if not query_information:
            query_information = await self.lavalink.auto_search_tracks(query)
        menu = (
            ActionRowBuilder()
            .add_select_menu("query_menu")
        )
        # building selection menu
        for x in range(displayed_song_count):
            try:
                track = query_information.tracks[x]
            except IndexError:
                break
            query_print = f"{x+1} | {track.info.title}"
            if len(query_print) > 100:
                query_print = query_print[:100]
            menu.add_option(query_print, str(x)).add_to_menu()
        menu = menu.add_to_container()
        menu_msg = await ctx.respond(f"Choose the song which should be added", component=menu)

        try:
            event = await self.bot.wait_for(
                hikari.InteractionCreateEvent,
                30,
                lambda e: (
                    isinstance(e.interaction, ComponentInteraction) 
                    and e.interaction.user.id == ctx.author.id
                    and e.interaction.message.id == menu_msg.id
                )
            )
            if not isinstance(event.interaction, ComponentInteraction):
                return  # to avoid problems with typecheckers
            track_num = int(event.interaction.values[0])
        except asyncio.TimeoutError as e:
            return None
        await event.interaction.create_initial_response(
            ResponseType.DEFERRED_MESSAGE_UPDATE
        )
        return query_information.tracks[track_num]


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

    @staticmethod
    def thumbnail_from_url(url: str) -> Optional[str]:
        """Returns the thumbnail url of a video or None out of th given url"""
        video_id = __class__.id_from_url(url)
        if not video_id:
            return
        return f"http://img.youtube.com/vi/{video_id}/hqdefault.jpg"

    @staticmethod
    def remove_playlist_info(url: str):
        start = url.find("watch?v=")
        end = url[start:].find("&")
        if end == -1:
            return url
        return url[:end+start]


class MusicHistoryHandler:
    """A class which handles music history stuff and syncs it with postgre"""
    db: Database = Database()
    max_length: int = 200  # max length of music history list¡

    @classmethod
    async def add(cls, guild_id: int, title: str, url: str):

        json_ = await cls.get(guild_id)
        history: List[Dict] = json_["data"]  # type: ignore
        history.append(                
            {
                "uri": url,
                "title": title,
            }
        )
        if len(history) > cls.max_length:
            history.pop(0)
        json_ = json.dumps({"data": history})
        sql = """
            UPDATE music_history
            SET history = $1
            WHERE guild_id = $2
        """
        await cls.db.execute(sql, json_, guild_id)

    @classmethod
    async def get(cls, guild_id: int) -> Dict[str, Union[str, List[Dict]]]:
        """"""
        sql = """
            SELECT * FROM music_history
            WHERE guild_id = $1
        """
        record = await cls.db.row(sql, guild_id)

        if record:
            json_ = record["history"]
            return json.loads(json_)
        else:
            sql = """
                INSERT INTO music_history(guild_id, history)
                VALUES ($1, $2)
            """
            # create new entry for this guild
            await cls.db.execute(sql, guild_id, json.dumps({"data": []}))
            return {"data": []}



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
        self.music_log.appendleft(f"{self.format_time_now()}: {log_entry}")

    def format_time_now(self):
        """
        Returns:
        --------
            - (str) `hour`:`minute`:`second` - `month_day_num`. `month`
        """
        time = datetime.datetime.now()
        return f'{time.hour}:{time.minute}:{time.second} - {time.day}. {time.month}'

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




class Music(lightbulb.Plugin):
    def __init__(self, bot: Inu) -> None:
        super().__init__()
        self.bot = bot
        self.log = logging.getLogger(__name__)
        self.log.setLevel(logging.DEBUG)
        self.interactive = Interactive(self.bot)
        self.music_message: Dict[int, hikari.Message] = {}  # guild_id: hikari.Message
        self.last_context: Dict[int, lightbulb.Context] = {} # guild_id: lightbulb.Context
        self.music_helper = MusicHelper()

    @lightbulb.listener(hikari.ShardReadyEvent)
    async def on_ready(self, event: hikari.ShardReadyEvent):
        pass
        # await asyncio.sleep(6)
        # await MusicHistoryHandler.add(
        #     538398443006066728,
        #     "test",
        #     "test uri"
        # )
        # self.log.debug(await MusicHistoryHandler.get(538398443006066728))

    @lightbulb.listener(hikari.VoiceStateUpdateEvent)
    async def on_voice_state_update(self, event: VoiceStateUpdateEvent):
        # check if the user is the bot
        if not event.state.user_id == self.bot.get_me().id: # type: ignore
            return
        # bot connected (No channel -> channel)
        if event.old_state is None and event.state.channel_id:
            pass
        elif event.state.channel_id is None and not event.old_state is None:
            await self._leave(event.guild_id)

    @lightbulb.listener(hikari.ReactionAddEvent)
    async def on_reaction_add(self, event: hikari.ReactionAddEvent):
        if event.user_id == self.bot.get_me().id:
            return
        if event.message_id not in [m.id for m in self.music_message.values()]:
            return
        try:
            message = self.bot.cache.get_message(event.message_id)
            guild_id = message.guild_id  # type: ignore
            if not isinstance(message, hikari.Message) or guild_id is None:
                return
            member = self.bot.cache.get_member(guild_id, event.user_id)
            if not isinstance(member, hikari.Member):
                return
            if not (ctx := self.last_context.get(guild_id)):
                return
        except AttributeError:
            return

        emoji = event.emoji_name
        if emoji == '🔀':
            node = await self.lavalink.get_guild_node(guild_id)
            if node is None:
                return

            queue = node.queue[1:]
            random.shuffle(queue)
            queue = [node.queue[0], *queue]
            node.queue = queue
            await self.lavalink.set_guild_node(guild_id, node)
            await message.remove_reaction(emoji, user=event.user_id)
            self.music_helper.add_to_log(guild_id=guild_id, entry=f'🔀 Music was shuffled by {member.display_name}')
        elif emoji == '▶':
            self.music_helper.add_to_log(guild_id = guild_id, entry = f'▶ Music was resumed by {member.display_name}')
            await message.remove_reaction(emoji, user=event.user_id)
            await message.remove_reaction(emoji, user=self.bot.me)
            await asyncio.sleep(0.1)
            await message.add_reaction(str('⏸'))
            await self._resume(guild_id)
        elif emoji == '1️⃣':
            await self._skip(guild_id, amount = 1)
            await message.remove_reaction(emoji, user=event.user_id)
            self.music_helper.add_to_log(
                guild_id = guild_id, 
                entry = f'1️⃣ Music was skipped by {member.display_name} (once)'
            )
        elif emoji == '2️⃣':
            await self._skip(guild_id, amount = 2)
            await message.remove_reaction(emoji, user=event.user_id)
            self.music_helper.add_to_log(
                guild_id =guild_id, 
                entry = f'2️⃣ Music was skipped by {member.display_name} (twice)'
            )
        elif emoji == '3️⃣':
            await self._skip(guild_id, amount = 3)
            await message.remove_reaction(emoji, user=event.user_id)
            self.music_helper.add_to_log(
                guild_id = guild_id, 
                entry = f'3️⃣ Music was skipped by {member.display_name} (3 times)'
            )
        elif emoji == '4️⃣':
            await self._skip(guild_id, amount = 4)
            await message.remove_reaction(emoji, user=event.user_id)
            self.music_helper.add_to_log(
                guild_id =guild_id, 
                entry = f'4️⃣ Music was skipped by {member.display_name} (4 times)'
            )
        elif emoji == '⏸':
            self.music_helper.add_to_log(guild_id =guild_id, entry = f'⏸ Music was paused by {member.display_name}')
            await message.remove_reaction(emoji, user=event.user_id)
            await message.remove_reaction(emoji, user=self.bot.get_me().id)  # type: ignore
            await asyncio.sleep(0.1)
            await message.add_reaction(str('▶'))
            await self._pause(guild_id)
        elif emoji == '🗑':
            await message.remove_reaction(emoji, user=event.user_id)
            await message.respond(
                embed=(
                    Embed(title="🗑 queue cleared")
                    .set_footer(text=f"music queue was cleared by {member.display_name}", icon=member.avatar_url)
                )
            )
            self.music_helper.add_to_log(guild_id=guild_id, entry=f'🗑 Queue was cleared by {member.display_name}')
            await self._clear(guild_id)
            if not (ctx := self.last_context.get(guild_id)):
                return
        elif emoji == '🛑':
            await message.respond(
                embed=(
                    Embed(title="🛑 music stopped")
                    .set_footer(text=f"music was stopped by {member.display_name}", icon=member.avatar_url)
                )
            )
            self.music_helper.add_to_log(guild_id =guild_id, entry = f'🛑 Music was stopped by {member.display_name}')
            await self._leave(guild_id)
        if emoji in ['🔀','🛑','🗑','⏸','▶','4️⃣','3️⃣','2️⃣','1️⃣'] and ctx:
            await self.queue(ctx)

    async def _join(self, ctx: lightbulb.Context) -> Optional[hikari.Snowflake]:
        if not (guild := ctx.get_guild()) or not ctx.guild_id:
            return
        states = self.bot.cache.get_voice_states_view_for_guild(guild)
        voice_state = [state async for state in states.iterator().filter(lambda i: i.user_id == ctx.author.id)]

        if not voice_state:
            await ctx.respond("Connect to a voice channel first")
            return None

        channel_id = voice_state[0].channel_id

        if HIKARI_VOICE:
            await self.bot.update_voice_state(ctx.guild_id, channel_id, self_deaf=True)
            connection_info = await self.bot.data.lavalink.wait_for_full_connection_info_insert(ctx.guild_id)
        else:
            try:
                connection_info = await self.bot.data.lavalink.join(ctx.guild_id, channel_id)
            except TimeoutError:
                await ctx.respond(
                    "I was unable to connect to the voice channel, maybe missing permissions? or some internal issue."
                )
                return None

        await self.bot.data.lavalink.create_session(connection_info)

        return channel_id

    @lightbulb.listener(hikari.ShardReadyEvent)
    async def start_lavalink(self, _: hikari.ShardReadyEvent) -> None:
        """Event that triggers when the hikari gateway is ready."""
        builder = (
            # TOKEN can be an empty string if you don't want to use lavasnek's discord gateway.
            lavasnek_rs.LavalinkBuilder(self.bot.me.id, self.bot.conf.DISCORD_TOKEN) #, 
            # This is the default value, so this is redundant, but it's here to show how to set a custom one.
            .set_host(self.bot.conf.LAVALINK_IP).set_password(self.bot.conf.LAVALINK_PASSWORD)
        )

        if HIKARI_VOICE:
            builder.set_start_gateway(False)

        lava_client = await builder.build(EventHandler(self))
        self.bot.data.lavalink = lava_client
        self.lavalink = self.interactive.lavalink = self.bot.data.lavalink
        logging.info("lavalink is connected")

    @lightbulb.check(lightbulb.guild_only)
    @lightbulb.command()
    async def join(self, ctx: lightbulb.Context) -> None:
        """Joins the voice channel you are in."""
        channel_id = await self._join(ctx)

        if channel_id:
            await ctx.respond(f"Joined <#{channel_id}>")

    @lightbulb.check(lightbulb.guild_only)
    @lightbulb.command()
    async def leave(self, ctx: lightbulb.Context) -> None:
        """Leaves the voice channel the bot is in, clearing the queue."""
        if not ctx.guild_id:
            return  # just for pylance
        await self._leave(ctx.guild_id)
        await ctx.respond("Left voice channel")

    async def _leave(self, guild_id: int):
        await self.bot.data.lavalink.destroy(guild_id)

        if HIKARI_VOICE:
            await self.bot.update_voice_state(guild_id, None)
            await self.bot.data.lavalink.wait_for_connection_info_remove(guild_id)
        else:
            await self.bot.data.lavalink.leave(guild_id)

        # Destroy nor leave remove the node nor the queue loop, you should do this manually.
        await self.bot.data.lavalink.remove_guild_node(guild_id)
        await self.bot.data.lavalink.remove_guild_from_loops(guild_id)
        
    # @lightbulb.check(lightbulb.guild_only)
    @lightbulb.group()
    async def play(self, ctx: lightbulb.Context, *, query: str) -> None:
        """Searches the query on youtube, or adds the URL to the queue."""
        await self._play(ctx, query)

    async def _play(self, ctx: Context, query: str, be_quiet: bool = False) -> None:
        if not ctx.guild_id or not ctx.member:
            return  # just for pylance
        con = await self.bot.data.lavalink.get_guild_gateway_connection_info(ctx.guild_id)
        # Join the user's voice channel if the bot is not in one.
        if not con:
            await self._join(ctx)

        # check for youtube playlist
        if 'youtube' in query and 'playlist?list=' in query:
            await self.load_yt_playlist(ctx, query, be_quiet)
        else:
            if (
                "watch?v=" in query
                and "youtube" in query
                and "&list" in query
            ):
                query = YouTubeHelper.remove_playlist_info(query)
            track = await self.search_track(ctx, query, be_quiet)
            if track is None:
                return
            await self.load_track(ctx, track, be_quiet)
        await self.queue(ctx)

    @play.command(aliases=["1st", "st"])
    async def now(self, ctx: Context, *, query: str) -> None:
        """Adds a song infront of the queue. So the track will be played next"""
        await self.play_at_pos(ctx, 1, query)

    @play.command(aliases=["nd", "2nd"])
    async def second(self, ctx: Context, *, query: str) -> None:
        """Adds a song at the second position of the queue. So the track will be played soon"""
        await self.play_at_pos(ctx, 2, query)

    @play.command(aliases=["pos"])
    async def position(self, ctx: Context, position: int, *, query: str) -> None:
        """Adds a song at the <position> position of the queue. So the track will be played soon"""
        await self.play_at_pos(ctx, position, query)

    async def play_at_pos(self, ctx: Context, pos: int, query: str):
        await self._play(ctx, query)
        node = await self.lavalink.get_guild_node(ctx.guild_id)
        if node is None or not ctx.guild_id:
            return
        track = node.queue.pop()
        queue = node.queue
        queue.insert(pos, track)
        node.queue = queue
        await self.lavalink.set_guild_node(ctx.guild_id, node)
        await self.queue(ctx)

    async def load_track(self, ctx: Context, track: lavasnek_rs.Track, be_quiet: bool = False):
        guild_id = ctx.guild_id
        author_id = ctx.author.id
        if not ctx.guild_id or not guild_id:
            raise Exception("guild_id is missing in `lightbulb.Context`")
        try:
            # `.queue()` To add the track to the queue rather than starting to play the track now.
            await self.bot.data.lavalink.play(guild_id, track).requester(
                author_id
            ).queue()
            await MusicHistoryHandler.add(
                ctx.guild_id,
                track.info.title,
                track.info.uri
            )
        except lavasnek_rs.NoSessionPresent:
            await ctx.respond(f"Use `{self.bot.conf.DEFAULT_PREFIX}join` first")
            return
        
        if not be_quiet:
            embed = Embed(
                title=f'Title added',
                description=f'[{track.info.title}]({track.info.uri})'
            ).set_thumbnail(ctx.member.avatar_url)  # type: ignore
            await ctx.respond(embed=embed)
        await MusicHistoryHandler.add(
            ctx.guild_id, 
            str(track.info.title), 
            track.info.uri
        )

    async def load_yt_playlist(self, ctx: Context, query: str, be_quiet: bool = False) -> lavasnek_rs.Tracks:
        """
        loads a youtube playlist

        Returns
        -------
            - (lavasnek_rs.Track) the first track of the playlist
        """
        tracks = await self.lavalink.get_tracks(query)
        for track in tracks.tracks:
            await self.bot.data.lavalink.play(ctx.guild_id, track).requester(
                ctx.author.id
            ).queue()
        if tracks.playlist_info:
            embed = Embed(
                title=f'Playlist added',
                description=f'[{tracks.playlist_info.name}]({query})'
            ).set_thumbnail(ctx.member.avatar_url)
            self.music_helper.add_to_log(
                ctx.guild_id, 
                str(tracks.playlist_info.name), 
            )
            await MusicHistoryHandler.add(
                ctx.guild_id, 
                str(tracks.playlist_info.name),
                query,
            )
            if not be_quiet:
                await ctx.respond(embed=embed)
        return tracks

    async def search_track(self, ctx: Context, query: str, be_quiet: bool = False) -> Optional[lavasnek_rs.Track]:
        """
        searches the query and returns the Track or None
        """
        query_information = await self.bot.data.lavalink.auto_search_tracks(query)
        track = None
        if not query_information.tracks and not be_quiet:  # tracks is empty
            await ctx.respond("Could not find any video of the search query.")
            return None

        if len(query_information.tracks) > 1:
            try:
                track = await self.interactive.ask_for_song(ctx, query, query_information=query_information)
                if track is None:
                    return
            except Exception:
                self.log.error(traceback.print_exc())

        else:
            track = query_information.tracks[0]

        if track is None:
            return None
        return track

    @lightbulb.check(lightbulb.guild_only)
    @lightbulb.command()
    async def stop(self, ctx: lightbulb.Context) -> None:
        """Stops the current song (skip to continue)."""

        await self.bot.data.lavalink.stop(ctx.guild_id)
        await ctx.respond("Stopped playing")

    @lightbulb.check(lightbulb.guild_only)
    @lightbulb.command()
    async def skip(self, ctx: lightbulb.Context, amount: int = 1) -> None:
        """
        Skips the current song.
        
        Args:
        -----
            - [amount]: How many songs you want to skip. Default = 1
        """

        await self._skip(ctx.guild_id, amount)
        await self.queue(ctx)


    async def _skip(self, guild_id: int, amount: int) -> bool:
        """
        Returns:
        --------
            - (bool) wether the skip(s) was/where successfull
        """
        for _ in range(amount):
            skip = await self.bot.data.lavalink.skip(guild_id)
            
            if not (node := await self.bot.data.lavalink.get_guild_node(guild_id)):
                return False

            if not skip:
                return False
            else:
                # If the queue is empty, the next track won't start playing (because there isn't any),
                # so we stop the player.
                if not node.queue and not node.now_playing:
                    await self.bot.data.lavalink.stop(guild_id)
        return True

    @lightbulb.check(lightbulb.guild_only)
    @lightbulb.command()
    async def pause(self, ctx: lightbulb.Context) -> None:
        """Pauses the current song."""
        if not ctx.guild_id:
            return
        await self._pause(ctx.guild_id)
        message = self.music_message[ctx.guild_id]
        await message.remove_reaction(str('▶'), user=ctx.author)
        await message.remove_reaction(str('▶'), user=self.bot.me)
        await asyncio.sleep(0.1)
        await message.add_reaction(str('⏸'))

    async def _pause(self, guild_id: int):
        await self.bot.data.lavalink.pause(guild_id)

    @lightbulb.check(lightbulb.guild_only)
    @lightbulb.command()
    async def resume(self, ctx: lightbulb.Context) -> None:
        """Resumes playing the current song."""
        if not ctx.guild_id:
            return
        await self._resume(ctx.guild_id)
        message = self.music_message[ctx.guild_id]
        await message.remove_reaction(str('▶'), user=ctx.author)
        await message.remove_reaction(str('▶'), user=self.bot.me)
        await asyncio.sleep(0.1)
        await message.add_reaction(str('⏸'))

    async def _resume(self, guild_id: int):
        await self.bot.data.lavalink.resume(guild_id)
        
    @lightbulb.check(lightbulb.guild_only)
    @lightbulb.command(aliases=["np"])
    async def now_playing(self, ctx: lightbulb.Context) -> None:
        """Gets the song that's currently playing."""

        node = await self.bot.data.lavalink.get_guild_node(ctx.guild_id)

        if not node or not node.now_playing:
            await ctx.respond("Nothing is playing at the moment.")
            return

        # for queue, iterate over `node.queue`, where index 0 is now_playing.
        await ctx.respond(f"Now Playing: {node.now_playing.track.info.title}")

    @lightbulb.check(lightbulb.guild_only)
    @lightbulb.check(lightbulb.owner_only)  # Optional
    @lightbulb.command()
    async def data(self, ctx: lightbulb.Context, *args: Any) -> None:
        """Load or read data from the node.
        If just `data` is ran, it will show the current data, but if `data <key> <value>` is ran, it
        will insert that data to the node and display it."""

        node = await self.bot.data.lavalink.get_guild_node(ctx.guild_id)

        if not args:
            await ctx.respond(await node.get_data())
        else:
            if len(args) == 1:
                await node.set_data({args[0]: args[0]})
            else:
                await node.set_data({args[0]: args[1]})
            await ctx.respond(await node.get_data())

    if HIKARI_VOICE:

        @lightbulb.listener(hikari.VoiceStateUpdateEvent)
        async def voice_state_update(self, event: hikari.VoiceStateUpdateEvent) -> None:
            await self.bot.data.lavalink.raw_handle_event_voice_state_update(
                event.state.guild_id,
                event.state.user_id,
                event.state.session_id,
                event.state.channel_id,
            )

        @lightbulb.listener(hikari.VoiceServerUpdateEvent)
        async def voice_server_update(self, event: hikari.VoiceServerUpdateEvent) -> None:
            await self.bot.data.lavalink.raw_handle_event_voice_server_update(
                event.guild_id, event.endpoint, event.token
            )

    #  @lightbulb.check(lightbulb.guild_only)
    @lightbulb.group()
    async def music(self, ctx: Context):
        pass

    @lightbulb.check(lightbulb.guild_only)
    @music.command(name="log")
    async def events(self, ctx: Context):
        """Sends the music log"""
        if not ctx.guild_id or not ctx.member:
            return
        if not (log_sites := self.music_helper.get_log(ctx.guild_id, 2000)):
            return
        has_perm = False  
        for role in ctx.member.get_roles():
            if role.name == self.bot.conf.SPECIAL_ROLE_NAME or role.permissions.ADMINISTRATOR:
                has_perm = True
                break
        if not has_perm:
            return
        embeds = []
        for i, log_site in enumerate(log_sites):
            embeds.append(
                Embed(
                    title=f"log {i+1}/{len(log_sites)}", 
                    description=log_site, 
                    color=Color.from_name("maroon")
                )
            )
        pag = Paginator(embeds)
        await pag.start(ctx)


    @lightbulb.check(lightbulb.guild_only)
    @lightbulb.command()
    async def clear(self, ctx: Context):
        """clears the music queue"""
        if not ctx.guild_id or not ctx.member:
            return

        await self._clear(ctx.guild_id)
        self.music_helper.add_to_log(
            ctx.guild_id,
            f"music was cleared by {ctx.member.display_name}"
        )
        await self.queue(ctx)

    async def _clear(self, guild_id: int):
        node = await self.lavalink.get_guild_node(guild_id)
        if not node:
            return
        queue = [node.queue[0]]
        node.queue = queue
        await self.lavalink.set_guild_node(guild_id, node)

    @lightbulb.check(lightbulb.guild_only)
    @music.command(aliases=['h'])
    async def history(self, ctx: Context):
        if not ctx.guild_id:
            return
        json_ = await MusicHistoryHandler.get(ctx.guild_id)
        history: List[Dict] = json_["data"]  # type: ignore
        history.reverse()  # now recent first
        embeds = []
        embed = None
        for i, record in enumerate(history):
            if i % 20 == 0:
                if not embed == None:
                    embeds.append(embed)
                embed = Embed(
                    title=f"Music history {i} - {i+19}",
                    description="",
                )
            embed.description += f"{i} | [{record['title']}]({record['uri']})\n"
        if embed:
            embeds.append(embed)
        pag = MusicHistoryPaginator(
            history=history,
            pages=embeds,
            items_per_site=20,
        )
        await pag.start(ctx)
        
            


    async def queue(self, ctx: Context = None, guild_id: int = None):
        '''
        refreshes the queue of the player
        uses ctx if not None, otherwise it will fetch the last context with the guild_id
        '''
        if ctx is None and isinstance(guild_id, int):
            ctx = self.last_context.get(guild_id) #  type: ignore
        if not ctx:
            return
        if not ctx.guild_id:
            return
        self.last_context[ctx.guild_id] = ctx
        if not ctx.guild_id:
            return
        channel = ctx.get_channel()
        node = await self.bot.data.lavalink.get_guild_node(ctx.guild_id)
        if not node:
            self.log.warning("node is None, in queue command")
            return
        numbers = ['1️⃣','2️⃣','3️⃣','4️⃣','5️⃣','6️⃣','7️⃣','8️⃣','9️⃣','🔟']
        upcoming_songs = ''
        for x in range(1,5,1):
            try:
                num = numbers[int(x) - 1]
                upcoming_songs = (
                    f'{upcoming_songs}\n' 
                    f'{num} {str(datetime.timedelta(milliseconds=int(int(node.queue[x].track.info.length))))} '
                    f'- {node.queue[x].track.info.title}'
                )
            except:
                break
        queue = None
        if upcoming_songs == '':
            upcoming_songs = '/'
        elif int(len(node.queue)) > 4:
            queue_len = int(len(node.queue))-4
            if queue_len > 1:
                queue = f'waiting in Queue: ---{queue_len}--- songs'
            else:
                try:
                    queue = f'waiting in Queue: ---{queue_len}--- song'
                except:
                    queue = f'waiting in Queue: ---N0TH1NG---'
        if queue is None:
            queue = f'Queue: ---N0TH1NG---'
        try:
            track = node.queue[0].track
        except Exception as e:
            return self.log.warning(f"can't get current playing song: {e}")

        if not node.queue[0].requester:
            self.log.warning("no requester of current track - returning")
        #get thumbnail of the video

        requester = ctx.get_guild().get_member(int(node.queue[0].requester))
        current_duration = str(datetime.timedelta(milliseconds=int(int(track.info.length))))
        music_embed = hikari.Embed(
            colour=hikari.Color.from_rgb(71, 89, 211)
        )
        music_embed.add_field(name = "Playing Song:", value=f'[{track.info.title}]({track.info.uri})', inline=True)#{"🔂 " if player.repeat else ""}
        music_embed.add_field(name = "Author:", value=f'{track.info.author}', inline=True)
        music_embed.add_field(name="Added from:", value=f'{requester.display_name}' , inline=True)
        music_embed.add_field(name = "Duration:", value=f'{current_duration}', inline=False)
        
        
        
        # music_embed.set_thumbnail(url=f'{video_thumbnail}')
        music_embed.add_field(name = "——————————Queue—————————————————", value=f'```ml\n{upcoming_songs}\n```', inline=False)
        music_embed.set_footer(text = f'{queue or "/"}')
        music_embed.set_thumbnail(YouTubeHelper.thumbnail_from_url(track.info.uri) or self.bot.me.avatar_url)
        try:
            self.music_message[ctx.guild_id]
        except:
            self.music_message[ctx.guild_id] = None

        #edit existing message
        resume = True
        if self.music_message[ctx.guild_id] != None:
            try:
                timeout = 4
                async for m in self.bot.rest.fetch_messages(ctx.channel_id):
                    if m.id == self.music_message[ctx.guild_id].id:
                        await self.music_message[ctx.guild_id].edit(embed=music_embed)
                        resume = False
                    timeout -= 1
                    if timeout == 0:
                        break
            except Exception as e:
                traceback.print_exc()
        try:
            if resume:
                #last message not among the last 3. Del and re send
                if self.music_message[ctx.guild_id] != None:
                    await self.music_message[ctx.guild_id].delete()
                    self.music_message[ctx.guild_id] = None#edit(embed=music_embed)
                    self.music_message[ctx.guild_id] = await ctx.respond(embed=music_embed)
                    message = self.music_message[ctx.guild_id]
                    await self.add_music_reactions(message)
                else: #self.music_message[str(ctx.guild)] == None:
                    self.music_message[ctx.guild_id] = await ctx.respond(embed=music_embed)
                    message = self.music_message[ctx.guild_id]
                    await self.add_music_reactions(message)
        except Exception as e:
            traceback.print_exc()
            try:
                self.music_message[ctx.guild_id] = await ctx.respond(embed=music_embed)
                message = self.music_message[ctx.guild_id]
                await self.add_music_reactions(message)
            except Exception as e:
                traceback.print_exc()
        return

    async def add_music_reactions(self, message: hikari.Message):
        await message.add_reaction(str('1️⃣'))
        await message.add_reaction(str('2️⃣'))
        await message.add_reaction(str('3️⃣'))
        await message.add_reaction(str('4️⃣'))
        await message.add_reaction(str('🔀'))
        await message.add_reaction(str('🗑'))
        await message.add_reaction(str('🛑'))
        await message.add_reaction(str('⏸'))


def load(bot: Inu) -> None:
    bot.add_plugin(Music(bot))


def unload(bot: lightbulb.Bot) -> None:
    bot.remove_plugin("Music")

