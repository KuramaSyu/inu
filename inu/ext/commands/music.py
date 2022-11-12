import os
from pickle import HIGHEST_PROTOCOL
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
from pprint import pformat
import random
from collections import deque
import json
from unittest.util import _MAX_LENGTH
from copy import deepcopy

import hikari
from hikari import ComponentInteraction, Embed, ResponseType, ShardReadyEvent, VoiceState, VoiceStateUpdateEvent
from hikari.impl import ActionRowBuilder
import lightbulb
from lightbulb import SlashContext, commands, context
from lightbulb.commands import OptionModifier as OM
from lightbulb.context import Context
import lavasnek_rs
from matplotlib.pyplot import hist
from youtubesearchpython.__future__ import VideosSearch  # async variant

from core import Inu, getLevel
from utils import Paginator, Colors, Human
from utils import method_logger as logger
from core.db import Database
from utils.paginators.music_history import MusicHistoryPaginator

from core import getLogger, BotResponseError, InteractionContext
log = getLogger(__name__)


# If True connect to voice with the hikari gateway instead of lavasnek_rs's
HIKARI_VOICE = True

# to fix bug, when join first time, no music
first_join = False
bot: Inu

# ytdl_format_options = {
#     "format": "bestaudio/best",
#     "restrictfilenames": True,
#     "noplaylist": True,
#     "nocheckcertificate": True,
#     "ignoreerrors": False,
#     "logtostderr": False,
#     "quiet": True,
#     "no_warnings": True,
#     "default_search": "auto",
# }
# ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

class EventHandler:
    """Events from the Lavalink server"""
    def __init__(self):
        pass
    async def track_start(self, lavalink: lavasnek_rs.Lavalink, event: lavasnek_rs.TrackStart) -> None:
        # log.info("Track started on guild: %s", event.guild_id)
        asyncio.create_task(queue(guild_id=event.guild_id, create_footer_info=False))
        node = await lavalink.get_guild_node(event.guild_id)
        if node is None:
            return
        track = node.queue[0].track
        await MusicHistoryHandler.add(event.guild_id, track.info.title, track.info.uri)

    async def track_finish(self, lavalink: lavasnek_rs.Lavalink, event: lavasnek_rs.TrackFinish) -> None:
        node = await lavalink.get_guild_node(event.guild_id)
        if node is None or len(node.queue) == 0:
            await _leave(event.guild_id)

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
        ctx: Context,
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

        raises
        ------
        asyncio.TimeoutError:
            When no interaction with the menu was made
        """
        if not ctx.guild_id:
            return None
        query_print = ""
        if not query_information:
            query_information = await self.lavalink.auto_search_tracks(query)
        id_ = bot.id_creator.create_id()
        menu = (
            ActionRowBuilder()
            .add_select_menu(f"query_menu-{id_}")
        )
        embeds: List[Embed] = []
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
            embeds.append(
                Embed(
                    title=f"{x+1} | {track.info.title}"[:100],
                ).set_thumbnail(YouTubeHelper.thumbnail_from_url(track.info.uri))
            )
        menu = menu.add_to_container()
        msg_proxy = await ctx.respond(f"Choose the song which should be added", component=menu)
        menu_msg = await msg_proxy.message()


        try:
            event = await self.bot.wait_for(
                hikari.InteractionCreateEvent,
                30,
                lambda e: (
                    isinstance(e.interaction, ComponentInteraction) 
                    and e.interaction.user.id == ctx.author.id
                    and e.interaction.message.id == menu_msg.id
                    and e.interaction.custom_id == f"query_menu-{id_}"
                )
            )
            if not isinstance(event.interaction, ComponentInteraction):
                return None  # to avoid problems with typecheckers
            track_num = int(event.interaction.values[0])
        except asyncio.TimeoutError as e:
            raise e
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
            try:
                await cls.db.execute(sql, guild_id, json.dumps({"data": []}))
                return {"data": []}
            except Exception:
                # unique violation error - try again
                return await cls.get(guild_id)



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


music = lightbulb.Plugin(name="Music", include_datastore=True)
lavalink: lavasnek_rs.Lavalink = None


@music.listener(hikari.ShardReadyEvent)
async def on_ready(event: hikari.ShardReadyEvent):
    if music.d is None:
        raise RuntimeError("Plugin has no datastore")
    music.d.log = logging.getLogger(__name__)
    music.d.log.setLevel(logging.DEBUG)
    music.d.interactive = Interactive(music.bot)
    music.d.music_message: Dict[int, Union[hikari.Message, None]] = {}  # guild_id: hikari.Message
    music.d.last_context: Dict[int,Context] = {} # guild_id: lightbulb.Context
    music.d.music_helper = MusicHelper()
    await start_lavalink()


@music.listener(hikari.VoiceStateUpdateEvent)
async def on_voice_state_update(event: VoiceStateUpdateEvent):
    """Clear lavalink after inu leaves a channel"""
    try:
        # check if the user is the bot
        if not event.state.user_id == music.bot.get_me().id: # type: ignore
            return
        # bot connected (No channel -> channel)
        if event.old_state is None and event.state.channel_id:
            pass
        # bot disconnected
        elif event.state.channel_id is None and not event.old_state is None:
            await lavalink.destroy(event.guild_id)
            await lavalink.wait_for_connection_info_remove(event.guild_id)

            # Destroy nor leave remove the node nor the queue loop, you should do this manually.
            await lavalink.remove_guild_node(event.guild_id)
            await lavalink.remove_guild_from_loops(event.guild_id)
            music.d.music_message[event.guild_id] = None
            
    except Exception:
        log.error(traceback.format_exc())


@music.listener(hikari.VoiceStateUpdateEvent)
async def voice_state_update(event: hikari.VoiceStateUpdateEvent) -> None:
    lavalink.raw_handle_event_voice_state_update(
        event.state.guild_id,
        event.state.user_id,
        event.state.session_id,
        event.state.channel_id,
    )


@music.listener(hikari.VoiceServerUpdateEvent)
async def voice_server_update(event: hikari.VoiceServerUpdateEvent) -> None:
    await lavalink.raw_handle_event_voice_server_update(event.guild_id, event.endpoint, event.token)

MENU_CUSTOM_IDS = [
    "music_play", 
    "music_pause", 
    "music_shuffle", 
    "music_skip_1", 
    "music_skip_2", 
    "music_resume", 
    "music_stop"
]
@music.listener(hikari.InteractionCreateEvent)
async def on_music_menu_interaction(event: hikari.InteractionCreateEvent):
    return
    if not isinstance(event.interaction, hikari.ComponentInteraction):
        return
    ctx = InteractionContext(event.interaction, update=True)
    if not any([custom_id for custom_id in MENU_CUSTOM_IDS if ctx.custom_id in custom_id]):
        return
    log = getLogger(__name__, "MUSIC INTERACTION RECEIVE")
    if (message := music.d.music_message.get(ctx.guild_id)) is None:
        log.debug("no music message -> return")
        return
    if not (member := await bot.mrest.fetch_member(ctx.guild_id, ctx.user_id)):
        return

    if ctx.i.message.id != message.id:
        # music message is different from message where interaction comes from
        # disable buttons from that different message
        await ctx.initial_response_update(
            embeds=ctx.i.message.embeds, 
            components=build_music_components(disable_all=True, guild_id=ctx.guild_id)
        )
    music.d.last_context[ctx.guild_id] = ctx   
    guild_id = ctx.guild_id
    custom_id = ctx.custom_id
    if not (node := await lavalink.get_guild_node(guild_id)):
        ctx._ephemeral = True
        return await ctx.respond(
            "How am I supposed to do anything without even an active radio playing music?"
        )
    if custom_id == 'music_shuffle':
        nqueue = node.queue[1:]
        random.shuffle(nqueue)
        nqueue = [node.queue[0], *nqueue]
        node.queue = nqueue
        await lavalink.set_guild_node(guild_id, node)
        music.d.music_helper.add_to_log(guild_id=guild_id, entry=f'🔀 Music was shuffled by {member.display_name}')
    elif custom_id == 'music_resume':
        music.d.music_helper.add_to_log(guild_id = guild_id, entry = f'▶ Music was resumed by {member.display_name}')
        await _resume(guild_id)
    elif custom_id == 'music_skip_1':
        await _skip(guild_id, amount = 1)
        music.d.music_helper.add_to_log(
            guild_id = guild_id, 
            entry = f'1️⃣ Music was skipped by {member.display_name} (once)'
        )
    elif custom_id == 'music_skip_2':
        await _skip(guild_id, amount = 2)
        music.d.music_helper.add_to_log(
            guild_id =guild_id, 
            entry = f'2️⃣ Music was skipped by {member.display_name} (twice)'
        )
    elif custom_id == 'music_pause':
        music.d.music_helper.add_to_log(guild_id =guild_id, entry = f'⏸ Music was paused by {member.display_name}')
        await _pause(guild_id)
    elif custom_id == 'music_stop':
        await message.respond(
            embed=(
                Embed(title="🛑 music stopped")
                .set_footer(text=f"music was stopped by {member.display_name}", icon=member.avatar_url)
            )
        )
        music.d.music_helper.add_to_log(guild_id =guild_id, entry = f'🛑 Music was stopped by {member.display_name}')
        await _leave(guild_id)
        return
    if "music_skip" in custom_id:
        return # skip gets handled from lavalink on_new_track handler
    log.debug("calling queue")
    await queue(ctx)
    

@music.listener(hikari.ReactionAddEvent)
async def on_reaction_add(event: hikari.ReactionAddEvent):
    try:
        if event.user_id == music.bot.get_me().id:
            return
        if not event.message_id in [m.id for m in music.d.music_message.values() if not m is None]:
            return
        try:
            message = music.bot.cache.get_message(event.message_id)
            guild_id = message.guild_id  # type: ignore
            if not isinstance(message, hikari.Message) or guild_id is None:
                return
            member = music.bot.cache.get_member(guild_id, event.user_id)
            if not isinstance(member, hikari.Member):
                return
            if not (ctx := music.d.last_context.get(guild_id)):
                return
        except AttributeError:
            return

        emoji = event.emoji_name
        if emoji == '🔀':
            node = await lavalink.get_guild_node(guild_id)
            if node is None:
                return

            nqueue = node.queue[1:]
            random.shuffle(nqueue)
            nqueue = [node.queue[0], *nqueue]
            node.queue = nqueue
            await lavalink.set_guild_node(guild_id, node)
            await message.remove_reaction(emoji, user=event.user_id)
            music.d.music_helper.add_to_log(guild_id=guild_id, entry=f'🔀 Music was shuffled by {member.display_name}')
        elif emoji == '▶':
            music.d.music_helper.add_to_log(guild_id = guild_id, entry = f'▶ Music was resumed by {member.display_name}')
            await message.remove_reaction(emoji, user=event.user_id)
            await message.remove_reaction(emoji, user=music.bot.me)
            await asyncio.sleep(0.1)
            await message.add_reaction(str('⏸'))
            await _resume(guild_id)
        elif emoji == '1️⃣':
            await _skip(guild_id, amount = 1)
            await message.remove_reaction(emoji, user=event.user_id)
            music.d.music_helper.add_to_log(
                guild_id = guild_id, 
                entry = f'1️⃣ Music was skipped by {member.display_name} (once)'
            )
        elif emoji == '2️⃣':
            await _skip(guild_id, amount = 2)
            await message.remove_reaction(emoji, user=event.user_id)
            music.d.music_helper.add_to_log(
                guild_id =guild_id, 
                entry = f'2️⃣ Music was skipped by {member.display_name} (twice)'
            )
        elif emoji == '3️⃣':
            await _skip(guild_id, amount = 3)
            await message.remove_reaction(emoji, user=event.user_id)
            music.d.music_helper.add_to_log(
                guild_id = guild_id, 
                entry = f'3️⃣ Music was skipped by {member.display_name} (3 times)'
            )
        elif emoji == '4️⃣':
            await _skip(guild_id, amount = 4)
            await message.remove_reaction(emoji, user=event.user_id)
            music.d.music_helper.add_to_log(
                guild_id =guild_id, 
                entry = f'4️⃣ Music was skipped by {member.display_name} (4 times)'
            )
        elif emoji == '⏸':
            music.d.music_helper.add_to_log(guild_id =guild_id, entry = f'⏸ Music was paused by {member.display_name}')
            await message.remove_reaction(emoji, user=event.user_id)
            await message.remove_reaction(emoji, user=music.bot.get_me().id)  # type: ignore
            await asyncio.sleep(0.1)
            await message.add_reaction(str('▶'))
            await _pause(guild_id)
        elif emoji == '🗑':
            await message.remove_reaction(emoji, user=event.user_id)
            await message.respond(
                embed=(
                    Embed(title="🗑 queue cleared")
                    .set_footer(text=f"music queue was cleared by {member.display_name}", icon=member.avatar_url)
                )
            )
            music.d.music_helper.add_to_log(guild_id=guild_id, entry=f'🗑 Queue was cleared by {member.display_name}')
            await _clear(guild_id)
            if not (ctx := music.d.last_context.get(guild_id)):
                return
        elif emoji == '🛑':
            await message.respond(
                embed=(
                    Embed(title="🛑 music stopped")
                    .set_footer(text=f"music was stopped by {member.display_name}", icon=member.avatar_url)
                )
            )
            music.d.music_helper.add_to_log(guild_id =guild_id, entry = f'🛑 Music was stopped by {member.display_name}')
            await _leave(guild_id)
            return
        if emoji in ['🔀','🗑','⏸','▶'] and ctx:
            await queue(ctx)
    except Exception:
        log.error(f"Error reaction_add music:\n{traceback.print_exc()}")

async def _join(ctx: lightbulb.Context) -> Optional[hikari.Snowflake]:
    assert ctx.guild_id is not None

    states = bot.cache.get_voice_states_view_for_guild(ctx.guild_id)
    voice_state = [state async for state in states.iterator().filter(lambda i: i.user_id == ctx.author.id)]

    if not voice_state:
        raise BotResponseError("Connect to a voice channel first, please", ephemeral=True)

    channel_id = voice_state[0].channel_id

    assert ctx.guild_id is not None

    await bot.update_voice_state(ctx.guild_id, channel_id, self_deaf=True)
    connection_info = await lavalink.wait_for_full_connection_info_insert(ctx.guild_id)

    #await lavalink.create_session(connection_info)

    return channel_id

async def start_lavalink() -> None:
    """Event that triggers when the hikari gateway is ready."""
    if not music.bot.conf.lavalink.connect:
        music.d.log.warning(f"Lavalink connection won't be established")
        return
    sleep_time = 10
    log.debug(f"Sleep for {sleep_time} seconds before connecting to Lavalink") 
    await asyncio.sleep(sleep_time)
    for x in range(3):
        try:
            builder = (
                # TOKEN can be an empty string if you don't want to use lavasnek's discord gateway.
                lavasnek_rs.LavalinkBuilder(music.bot.get_me().id, music.bot.conf.bot.DISCORD_TOKEN) #, 
                # This is the default value, so this is redundant, but it's here to show how to set a custom one.
                .set_host(music.bot.conf.lavalink.IP).set_password(music.bot.conf.lavalink.PASSWORD)
            )
            builder.set_start_gateway(False)
            lava_client = await builder.build(EventHandler())
            music.d.interactive.lavalink = lava_client
            global lavalink
            lavalink = lava_client
            break
        except Exception:
            if x == 2:
                music.d.log.error(traceback.format_exc())
                return
            else:
                log.info("retrying lavalink connection in 10 seconds")
                await asyncio.sleep(10)
    log.info("lavalink is connected")


# @music.command
# @lightbulb.add_checks(lightbulb.guild_only)
# @lightbulb.command("join", "I will join into your channel")
# @lightbulb.implements(commands.PrefixCommand, commands.SlashCommand)
# async def join(ctx: context.Context) -> None:
#     """Joins the voice channel you are in."""
#     channel_id = await _join(ctx)
#     await ctx.respond("Radio up and running")

@music.command
@lightbulb.add_checks(lightbulb.guild_only)
@lightbulb.command("fix", "I will kick on my radio, that you will hear music again")
@lightbulb.implements(commands.PrefixCommand, commands.SlashCommand)
async def fix(ctx: context.Context) -> None:
    """I will kick on my radio, that you will hear music again"""
    await _fix(ctx)
    await ctx.respond("Should work now")


async def _fix(ctx: context.Context):
    await _join(ctx)
    await _pause(ctx.guild_id)
    await asyncio.sleep(0.1)
    await _resume(ctx.guild_id)
    

    # if channel_id:
    #     await ctx.respond(f"Joined <#{channel_id}>")


@music.command
@lightbulb.add_checks(lightbulb.guild_only)
@lightbulb.command("leave", "I will leave your channel")
@lightbulb.implements(commands.PrefixCommand, commands.SlashCommand)
async def leave(ctx: context.Context) -> None:
    """Leaves the voice channel the bot is in, clearing the queue."""
    if not ctx.guild_id:
        return  # just for pylance
    await _leave(ctx.guild_id)
    await ctx.respond(
        embed=(
            Embed(title="🛑 music stopped")
                .set_footer(text=f"music was stopped by {ctx.author.display_name}", icon=ctx.author.avatar_url)
        )
    )


async def _leave(guild_id: int):
    await bot.update_voice_state(guild_id, None)

    # this part will be done in the listener
    # await lavalink.destroy(guild_id)
    # await lavalink.wait_for_connection_info_remove(guild_id)

    # # Destroy nor leave remove the node nor the queue loop, you should do this manually.
    # await lavalink.remove_guild_node(guild_id)
    # await lavalink.remove_guild_from_loops(guild_id)
    # music.d.music_message[guild_id] = None


@music.command
@lightbulb.add_cooldown(5, 1, lightbulb.UserBucket)
@lightbulb.add_checks(lightbulb.guild_only)
@lightbulb.option("query", "the title of the track etc.", modifier=OM.CONSUME_REST, type=str)
@lightbulb.command("play-at-position", "Advanced play features", aliases=["pl"])
@lightbulb.implements(commands.PrefixCommandGroup, commands.SlashCommandGroup)
async def pl(ctx: context.Context) -> None:
    """Searches the query on youtube, or adds the URL to the queue."""
    log.debug(lavalink)
    global first_join
    try:
        
        await _play(ctx, ctx.options.query)
        # if first_join:
        #     await _fix(ctx)
        #     first_join = False
    except Exception:
        music.d.log.error(f"Error while trying to play music: {traceback.format_exc()}")

async def _play(ctx: Context, query: str, be_quiet: bool = True, prevent_to_queue: bool = False) -> bool:
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
    be_quiet: bool
        whether to send messages else than queue or not
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
    if not ctx.guild_id or not ctx.member:
        return False # just for pylance
    ictx = InteractionContext(ctx.interaction)
    ictx.responded = ctx._responded
    music.d.last_context[ctx.guild_id] = ictx
    con = lavalink.get_guild_gateway_connection_info(ctx.guild_id) # await?
    # Join the user's voice channel if the bot is not in one.
    if not con:
        await _join(ctx)

    # -> youtube playlist -> load playlist
    if 'youtube' in query and 'playlist?list=' in query:
        node = await lavalink.get_guild_node(ctx.guild_id)
        if len(node.queue) < 1:
            prevent_to_queue = True
        await load_yt_playlist(ctx, query, be_quiet)
    # not a youtube playlist -> something else
    else:
        # -> track from a playlist was added -> remove playlist info
        if (
            "watch?v=" in query
            and "youtube" in query
            and "&list" in query
        ):
            query = YouTubeHelper.remove_playlist_info(query)
        # try to add song
        try:
            track = await search_track(ctx, query, be_quiet)
        except BotResponseError as e:
            raise e
        except asyncio.TimeoutError:
            return False
        if track is None:
            await ctx.respond(f"I only found a lot of empty space for `{query}`")
            return False
        await load_track(ictx, track, be_quiet)

    if prevent_to_queue:
        return True

    await asyncio.sleep(0.2)
    node = await lavalink.get_guild_node(ctx.guild_id)

    if len(node.queue) in [1, 0]:
        return True
    
    await queue(
        ctx, 
        ctx.guild_id, 
        force_resend=True,
        create_footer_info=True,
    )
    return True


@pl.child
@lightbulb.add_cooldown(5, 1, lightbulb.UserBucket)
@lightbulb.add_checks(lightbulb.guild_only)
@lightbulb.option("query", "the name of the track etc.", modifier=OM.CONSUME_REST, type=str)
@lightbulb.command("next", "enqueue a title at the beginning of the queue", aliases=["1st"])
@lightbulb.implements(commands.PrefixSubCommand, commands.SlashSubCommand)
async def now(ctx: Context) -> None:
    """Adds a song infront of the queue. So the track will be played next"""
    await play_at_pos(ctx, 1, ctx.options.query)

@pl.child
@lightbulb.add_cooldown(5, 1, lightbulb.UserBucket)
@lightbulb.add_checks(lightbulb.guild_only)
@lightbulb.option("query", "the name of the track etc.", modifier=OM.CONSUME_REST, type=str)
@lightbulb.command("second", "enqueue a title as the second in the queue", aliases=["2nd"])
@lightbulb.implements(commands.PrefixSubCommand, commands.SlashSubCommand)
async def second(ctx: Context) -> None:
    """Adds a song at the second position of the queue. So the track will be played soon"""
    await play_at_pos(ctx, 2, ctx.options.query)

@pl.child
@lightbulb.add_cooldown(5, 1, lightbulb.UserBucket)
@lightbulb.add_checks(lightbulb.guild_only)
@lightbulb.option("position", "the position in the queue", modifier=OM.CONSUME_REST, type=str)
@lightbulb.option("query", "the name of the track etc.", modifier=commands.OptionModifier.CONSUME_REST)
@lightbulb.command("position", "enqueue a title at a custom position of the queue", aliases=[])
@lightbulb.implements(commands.PrefixSubCommand, commands.SlashSubCommand)
async def position(ctx: SlashContext) -> None:
    """Adds a song at the <position> position of the queue. So the track will be played soon"""
    await play_at_pos(ctx, ctx.options.position, ctx.options.query)

async def play_at_pos(ctx: Context, pos: int, query: str):
    # will be called from event track start
    node = await lavalink.get_guild_node(ctx.guild_id)
    if not node:
        prevent_to_queue = True
    else:
        prevent_to_queue = len(node.queue) == 0
    song_added = await _play(ctx, query, prevent_to_queue=True)
    if not song_added:
        return
    node = await lavalink.get_guild_node(ctx.guild_id)
    if node is None or not ctx.guild_id:
        return
    node_queue = node.queue
    track = node_queue.pop(-1)
    node_queue.insert(pos, track)
    node.queue = node_queue
    await lavalink.set_guild_node(ctx.guild_id, node)
    if not prevent_to_queue:
        await queue(
            ctx, 
            ctx.guild_id, 
            force_resend=True, 
            create_footer_info=True,
            custom_info=f"{track.track.info.title} added by {ctx.author.username}"
        )

async def load_track(ctx: Context, track: lavasnek_rs.Track, be_quiet: bool = False):
    guild_id = ctx.guild_id
    author_id = ctx.author.id
    if not ctx.guild_id or not guild_id:
        raise Exception("guild_id is missing in `lightbulb.Context`")
    try:
        # `.queue()` To add the track to the queue rather than starting to play the track now.
        await lavalink.play(guild_id, track).requester(
            author_id
        ).queue()
    except lavasnek_rs.NoSessionPresent:
        await ctx.respond(f"Use `/join` first")
        return
    
    if not be_quiet:
        embed = Embed(
            title=f'Title added',
            description=f'[{track.info.title}]({track.info.uri})'
        ).set_thumbnail(ctx.member.avatar_url)  # type: ignore
        await ctx.respond(embed=embed)

async def load_yt_playlist(ctx: Context, query: str, be_quiet: bool = False) -> lavasnek_rs.Tracks:
    """
    loads a youtube playlist
    Returns
    -------
        - (lavasnek_rs.Track) the first track of the playlist
    """
    tracks = await lavalink.get_tracks(query)
    for track in tracks.tracks:
        await lavalink.play(ctx.guild_id, track).requester(
            ctx.author.id
        ).queue()
    if tracks.playlist_info:
        embed = Embed(
            title=f'Playlist added',
            description=f'[{tracks.playlist_info.name}]({query})'
        ).set_thumbnail(ctx.member.avatar_url)
        music.d.music_helper.add_to_log(
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

async def search_track(ctx: Context, query: str, be_quiet: bool = False) -> Optional[lavasnek_rs.Track]:
    """
    searches the query and returns the Track or None

    Raises:
    ------
    BotResponseError :
        Given query is not available
    asyncio.TimeoutError :
        User hasn't responded to the menu
    """

    query_information = await lavalink.auto_search_tracks(query)

    if not query_information.tracks:
        log.debug(f"using fallback youtbue search")
        v = VideosSearch(query, limit = 1)
        result = await v.next()

        try:
            query_information = await lavalink.auto_search_tracks(
                result["result"][0]["link"]
            )
        except IndexError:
            return None

    if len(query_information.tracks) > 1:
        try:
            track = await music.d.interactive.ask_for_song(ctx, query, query_information=query_information)
        except asyncio.TimeoutError as e:
            raise e
        except Exception:
            music.d.log.error(traceback.format_exc())
    elif len(query_information.tracks) == 0:
        embed = Embed(title="Title not available")
        url_pattern = "^https?:\\/\\/(?:www\\.)?[-a-zA-Z0-9@:%._\\+~#=]{1,256}\\.[a-zA-Z0-9()]{1,6}\\b(?:[-a-zA-Z0-9()@:%_\\+.~#?&\\/=]*)$"
        if re.match(url_pattern, query):  # Returns Match object
            embed.add_field(name="Typical issues", value=(
                "• Your title has an age limit\n"
                "• Your title is not available in my region\n"
            ))
            embed.add_field(name="What you can do:", value=(
                "• search the name of your title instead of passing in the URL\n"
                "• try other URL's\n"
            ))
            embed.description = f"Your [title]({query}) is not available for me"
        else:
            embed.add_field(name="Typical issues", value=(
                "• You have entered a bunch of shit\n"
            ))
            embed.add_field(name="What you can do:", value=(
                "• Give me shorter queries"
            ))
            embed.description = f"I just found a lot of empty space for `{query}`"
        raise BotResponseError(embed=embed, ephemeral=True)
    else:
        track = query_information.tracks[0]

    if track is None:
        return None
    return track

@music.command
@lightbulb.add_cooldown(5, 1, lightbulb.UserBucket)
@lightbulb.add_checks(lightbulb.guild_only)
@lightbulb.option("query", "the title of the track", modifier=OM.CONSUME_REST, type=str)
@lightbulb.command("play", "play a song", aliases=["pl"])
@lightbulb.implements(commands.SlashCommand)
async def play_normal(ctx: context.Context) -> None:
    #await ctx.interaction.create_initial_response(ResponseType.DEFERRED_MESSAGE_CREATE)
    await _play(ctx, ctx.options.query)

@music.command
@lightbulb.add_checks(lightbulb.guild_only)
@lightbulb.command("stop", "stop the current title")
@lightbulb.implements(commands.PrefixCommand, commands.SlashCommand)
async def stop(ctx: Context) -> None:
    """Stops the current song (skip to continue)."""
    if not await lavalink.get_guild_node(ctx.guild_id):
        return
    await lavalink.stop(ctx.guild_id)
    await ctx.respond("Stopped playings")

@music.command
@lightbulb.add_cooldown(1, 1, lightbulb.UserBucket)
@lightbulb.add_checks(lightbulb.guild_only)
@lightbulb.option("amount", "How many titles do you want to skip?", type=int, default=1)
@lightbulb.command("skip", "skip the current title")
@lightbulb.implements(commands.PrefixCommand, commands.SlashCommand)
async def skip(ctx: Context) -> None:
    """
    Skips the current song.
    
    Args:
    -----
        - [amount]: How many songs you want to skip. Default = 1
    """

    await _skip(ctx.guild_id, ctx.options.amount)


async def _skip(guild_id: int, amount: int) -> bool:
    """
    Returns:
    --------
        - (bool) wether the skip(s) was/where successfull
    """
    for _ in range(amount):
        skip = await lavalink.skip(guild_id)
        
        if not (node := await lavalink.get_guild_node(guild_id)):
            return False

        if not skip:
            return False
        else:
            # If the queue is empty, the next track won't start playing (because there isn't any),
            # so we stop the player.
            if not node.queue and not node.now_playing:
                await lavalink.stop(guild_id)
    return True

@music.command
@lightbulb.add_checks(lightbulb.guild_only)
@lightbulb.command("pause", "pause the music")
@lightbulb.implements(commands.SlashCommand)
async def pause(ctx: SlashContext) -> None:
    """Pauses the current song."""
    if not ctx.guild_id:
        return
    await _pause(ctx.guild_id)
    await queue(InteractionContext(ctx.interaction))

async def _pause(guild_id: int):
    await lavalink.pause(guild_id)


@music.command
@lightbulb.add_checks(lightbulb.guild_only)
@lightbulb.command("resume", "resume the music")
@lightbulb.implements(commands.SlashCommand)
async def resume(ctx: SlashContext) -> None:
    """Resumes playing the current song."""
    if not ctx.guild_id:
        return
    await _resume(ctx.guild_id)
    await queue(InteractionContext(ctx.interaction))

async def _resume(guild_id: int):
    await lavalink.resume(guild_id)


@music.command
@lightbulb.add_cooldown(20, 1, lightbulb.UserBucket)
@lightbulb.add_checks(lightbulb.guild_only)
@lightbulb.command("queue", "Resend the music message")
@lightbulb.implements(commands.PrefixCommand, commands.SlashCommand)
async def _queue(ctx: Context) -> None:
    await queue(ctx, force_resend=True)


@music.command
@lightbulb.add_checks(lightbulb.guild_only)
@lightbulb.command("music", "music related commands", aliases=["m"])
@lightbulb.implements(commands.PrefixCommandGroup, commands.SlashCommandGroup)
async def m(ctx: Context):
    pass


@m.child
@lightbulb.add_checks(lightbulb.guild_only)
@lightbulb.command("log", "get the log for invoked music commands")
@lightbulb.implements(commands.PrefixSubCommand, commands.SlashSubCommand)
async def music_log(ctx: Context):
    """Sends the music log"""
    if not ctx.guild_id or not ctx.member:
        return
    if not (log_sites := music.d.music_helper.get_log(ctx.guild_id, 2000)):
        return
    has_perm = False  
    for role in ctx.member.get_roles():
        if role.name == music.bot.conf.bot.SPECIAL_ROLE_NAME or role.permissions.ADMINISTRATOR:
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
                color=Colors.from_name("maroon")
            )
        )
    pag = Paginator(embeds)
    await pag.start(ctx)


@music.command
@lightbulb.add_checks(lightbulb.guild_only)
@lightbulb.command("clear", "cleans the queue")
@lightbulb.implements(commands.PrefixCommand, commands.SlashCommand)
async def clear(ctx: Context):
    """clears the music queue"""
    if not ctx.guild_id or not ctx.member:
        return

    await _clear(ctx.guild_id)
    music.d.music_helper.add_to_log(
        ctx.guild_id,
        f"music was cleared by {ctx.member.display_name}"
    )
    await music.queue(ctx)

async def _clear(guild_id: int):
    node = await lavalink.get_guild_node(guild_id)
    if not node:
        return
    queue = [node.queue[0]]
    node.queue = queue
    await lavalink.set_guild_node(guild_id, node)


@m.child
@lightbulb.add_checks(lightbulb.guild_only)
@lightbulb.command("history", "Get a list of all the last played titles", aliases=["h"])
@lightbulb.implements(commands.PrefixSubCommand, commands.SlashSubCommand)
async def history(ctx: Context):
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



@m.child
@lightbulb.add_checks(lightbulb.owner_only)
@lightbulb.command("restart", "reconnects to lavalink", hidden=True)
@lightbulb.implements(commands.PrefixSubCommand)
async def restart(ctx: context.Context):
    await start_lavalink()


@m.child
@lightbulb.add_checks(lightbulb.guild_only)
@lightbulb.option("query", "What do you want to search?", modifier=OM.CONSUME_REST)
@lightbulb.command("search", "Searches the queue; every match will be added infront of queue", aliases=["s"])
@lightbulb.implements(commands.PrefixSubCommand, commands.SlashSubCommand)
async def music_search(ctx: context.Context):
    node = await lavalink.get_guild_node(ctx.guild_id)
    if not node:
        return await ctx.respond("You have to play music, that I can search for songs")
    query = ctx.options.query
    query = query.lower()
    response = []
    tracks = []
    for track in node.queue:
        if query in track.track.info.title.lower() or query in track.track.info.author.lower():
            tracks.append(track)
    tracks = list(set(tracks))
    response = [f"\"{track.track.info.title}\" by {track.track.info.author}" for track in tracks]
    if response:
        node_queue = node.queue[1:]
        new_queue = [node.queue[0], *tracks, *node_queue]
        node.queue = new_queue
        await lavalink.set_guild_node(ctx.guild_id, node)
        resp = "Titles added:```py\n" + '\n'.join([f'{i+1}. | {resp}' for i, resp in enumerate(response)]) + "```"
        await ctx.respond(resp) 
        return await queue(ctx)
    else:
        return await ctx.respond("No matches found")


async def queue(
    ctx: InteractionContext = None, 
    guild_id: int = None, 
    force_resend: bool = False,
    create_footer_info: bool = True, 
    custom_info: str = ""
):
    '''
    refreshes the queue of the player
    uses ctx if not None, otherwise it will fetch the last context with the guild_id
    '''
    if guild_id is None:
        guild_id = ctx.guild_id
    if ctx:
        music.d.last_context[guild_id] = ctx
    else:
        ctx = music.d.last_context[guild_id]
    if not ctx.guild_id:
        return
    node = await lavalink.get_guild_node(guild_id)
    if not node:
        music.d.log.warning(f"node is None, in queue command; {guild_id=};")
        music.d.log.info("Try to reconnect to websocket")
        await _join(ctx)
        node = await lavalink.get_guild_node(guild_id)
        return
    numbers = ['1️⃣','2️⃣','3️⃣','4️⃣','5️⃣','6️⃣','7️⃣','8️⃣','9️⃣','🔟']
    upcoming_songs = ''
    for x in range(1,4,1):
        try:
            num = numbers[int(x) - 1]
            upcoming_songs = (
                f'{upcoming_songs}\n' 
                f'{num} {str(datetime.timedelta(milliseconds=node.queue[x].track.info.length))} '
                f'- {node.queue[x].track.info.title}'
            )
        except:
            break
    if upcoming_songs == '':
        upcoming_songs = '/'

    total_playtime = datetime.timedelta(milliseconds=sum(track.track.info.length for track in node.queue)) 

    queue_len = len(node.queue)-3
    if not queue_len or queue_len < 0:
        queue_len = 0
    queue = f"{Human.plural_('song', queue_len, with_number=True)} ({total_playtime}) remaining in the queue"

    try:
        track = node.queue[0].track
    except Exception as e:
        return music.d.log.warning(f"can't get current playing song: {e}")

    if not node.queue[0].requester:
        music.d.log.warning("no requester of current track - returning")

    requester = music.bot.cache.get_member(guild_id, node.queue[0].requester)
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
    kwarg = {"text": f"{queue or '/'}"}
    if create_footer_info:
        last_track: lavasnek_rs.TrackQueue = node.queue[-1]
        requester = music.bot.cache.get_member(ctx.guild_id, last_track.requester)
        if requester:
            kwarg["icon"] = f'{requester.avatar_url}'
            requester_str = f'{requester.display_name}'
        else:
            requester_str = last_track.requester
        if custom_info:
            kwarg["text"] += f"\n{custom_info}"
        else:
            kwarg["text"] += f'\n{last_track.track.info.title} added by {requester_str}'
    music_embed.set_footer(**kwarg)
    music_embed.set_thumbnail(YouTubeHelper.thumbnail_from_url(track.info.uri) or music.bot.me.avatar_url)
    
    # send new message and override
    music_msg = music.d.music_message.get(guild_id, None)
    if music_msg is None or force_resend:
        #await ctx.interaction.execute(embed=music_embed)
        msg = await ctx.respond(embed=music_embed, components=await build_music_components(node=node))
        if not msg:
            msg = await ctx.fetch_response()
        music.d.music_message[ctx.guild_id] = msg
        #asyncio.create_task(add_music_reactions(music.d.music_message[guild_id]))
        return

    #edit existing message
    try:
        timeout = 4
        async for m in music.bot.rest.fetch_messages(music.d.music_message[guild_id].channel_id):
            # edit existing message if in last messages
            if m.id == music.d.music_message[ctx.guild_id].id:
                await ctx.respond(embed=music_embed, components=await build_music_components(node=node), update=True)
                return
            timeout -= 1
            # resend message
            if timeout == 0:
                await ctx.respond(
                    # embed=music_embed, 
                    components=[],
                    update=True
                )
                msg = await ctx.respond(
                    embed=music_embed, 
                    components=await build_music_components(node=node), 
                    update=False
                )
                music.d.music_message[ctx.guild_id] = msg
                return
    except Exception as e:
        log.error(traceback.format_exc())


async def add_music_reactions(message: hikari.Message):
   
    reactions = ['1️⃣', '2️⃣', '🔀', '🛑', '⏸'] # '🗑','3️⃣', '4️⃣',
    for r in reactions:
        await message.add_reaction(str(r))

async def build_music_components(
    guild_id: Optional[int] = None,
    node: Optional[lavasnek_rs.Node] = None,
    disable_all: bool = False,
) -> List[hikari.impl.ActionRowBuilder]:
    if not node and not guild_id:
        raise RuntimeError("Can't build music compoents without guild_id and node. Either one of both needs to be given")
    if not disable_all:
        node = node or await lavalink.get_guild_node(guild_id)
    if not node and not disable_all:
        raise RuntimeError("Can't fetch node")
        
    action_rows = [(
        ActionRowBuilder()
        .add_button(hikari.ButtonStyle.SECONDARY, "music_skip_1")
            .set_emoji("1️⃣")
            .set_is_disabled(disable_all or node.is_paused)
            .add_to_container()
        .add_button(hikari.ButtonStyle.SECONDARY, "music_skip_2")
            .set_emoji("2️⃣")
            .set_is_disabled(disable_all or node.is_paused)
            .add_to_container()
        .add_button(hikari.ButtonStyle.SECONDARY, "music_shuffle")
            .set_emoji("🔀")
            .set_is_disabled(disable_all)
            .add_to_container()
        .add_button(hikari.ButtonStyle.SECONDARY, "music_stop")
            .set_emoji("🛑")
            .set_is_disabled(disable_all)
            .add_to_container()
    )]
    if not disable_all:
        if node.is_paused:
            action_rows[0].add_button(hikari.ButtonStyle.PRIMARY, "music_resume").set_label("▶").add_to_container()
        else:
            action_rows[0].add_button(hikari.ButtonStyle.SECONDARY, "music_pause").set_label("⏸").add_to_container()
    else:
        pass
        #action_rows[0].add_button(hikari.ButtonStyle.SECONDARY, "music_outdated").set_label("outdated").set_is_disabled(disable_all).add_to_container()     
    return action_rows


def load(inu: Inu) -> None:
    global bot
    bot = inu
    inu.add_plugin(music)


def unload(inu: Inu) -> None:
    inu.remove_plugin(music)