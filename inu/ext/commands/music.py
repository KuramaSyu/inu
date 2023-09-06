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

import hikari
from hikari import ComponentInteraction, Embed, ResponseType, VoiceStateUpdateEvent
from hikari.impl import MessageActionRowBuilder
import lightbulb
from lightbulb import SlashContext, commands, context
from lightbulb.commands import OptionModifier as OM
from lightbulb.context import Context
import lavasnek_rs
from youtubesearchpython.__future__ import VideosSearch  # async variant
from fuzzywuzzy import fuzz
from humanize import naturaldelta

from core import Inu, get_context, InuContext, getLogger, BotResponseError
from utils import Paginator, Colors, Human, MusicHistoryHandler, TagManager, TagType
from utils.paginators.music_history import MusicHistoryPaginator
from .tags import get_tag
log = getLogger(__name__)


# If True connect to voice with the hikari gateway instead of lavasnek_rs's
HIKARI_VOICE = True

# prefix for autocomplete history values
HISTORY_PREFIX = "History: "
MEDIA_TAG_PREFIX = "Media Tag: "
# if the bot is alone in a channel, then
DISCONNECT_AFTER = 60 * 10  # seconds

first_join = False
bot: Inu


class EventHandler:
    """Events from the Lavalink server"""
    def __init__(self):
        pass
    async def track_start(self, lavalink: lavasnek_rs.Lavalink, event: lavasnek_rs.TrackStart) -> None:
        try:
            
            node = await lavalink.get_guild_node(event.guild_id)
            if node is None:
                return
            player = await PlayerManager.get_player(event.guild_id)
            await player.update_node(node)
            track = node.queue[0].track
            await MusicHistoryHandler.add(event.guild_id, track.info.title, track.info.uri)
            if (
                player.queue.current_track == track 
                or player.queue._last_update + datetime.timedelta(seconds=5) > datetime.datetime.now()
            ):
                return  # first element added with /play -> play command will call queue 
            await player.queue.send(create_footer_info=False, debug_info="track start")
        except Exception:
            log.error(traceback.format_exc())

    async def track_finish(self, lavalink: lavasnek_rs.Lavalink, event: lavasnek_rs.TrackFinish) -> None:
        node = await lavalink.get_guild_node(event.guild_id)
        if node is None or len(node.queue) == 0:
            player = await PlayerManager.get_player(event.guild_id)
            await player._leave()

    async def track_exception(self, lavalink: lavasnek_rs.Lavalink, event: lavasnek_rs.TrackException) -> None:
        log.warning("Track exception event happened on guild: %d", event.guild_id)
        log.warning(event.exception_message)
        # If a track was unable to be played, skip it
        player = await PlayerManager.get_player(event.guild_id)
        if not player:
            return
        player.queue.set_footer(
            text="Track was unable to be played, skipping...",
            icon=bot.me
        )
        await player._skip(1)
        await player.queue.send(create_footer_info=False, debug_info="track exception")

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
        displayed_song_count: int = 24,
        query_information: lavasnek_rs.Tracks = None,
    ) -> Tuple[Optional[lavasnek_rs.Track], Optional[hikari.InteractionCreateEvent]]:
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
        query_information: Optional[lavasnek_rs.Tracks] = None 
            existing information to lower footprint
            
        returns
        -------
        Optional[lavasnek_rs.Track]
            the chosen title (is None if timeout or other errors)
        Optional[hikari.InteractionCreateEvent]

        raises
        ------
        asyncio.TimeoutError:
            When no interaction with the menu was made
        """
        if not ctx.guild_id:
            return None, None
        query_print = ""
        if not query_information:
            query_information = await self.lavalink.auto_search_tracks(query)
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
                track = query_information.tracks[x]
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

        msg_proxy = await ctx.respond(component=menu)
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
                    and e.interaction.custom_id == f"query_menu-{id_}"
                )
            )
            if not isinstance(event.interaction, ComponentInteraction):
                return None, None  # to avoid problems with typecheckers
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



music = lightbulb.Plugin(name="Music", include_datastore=True)
lavalink: lavasnek_rs.Lavalink = None
interactive: Interactive = None
music_helper: MusicHelper = None
music_messages: Dict[int, Union[hikari.Message, None]] = {}  # guild_id: hikari.Message
last_context: Dict[int, InuContext] = {}

@music.listener(hikari.ShardReadyEvent)
async def on_ready(event: hikari.ShardReadyEvent):
    global interactive, music_helper
    if music.d is None:
        raise RuntimeError("Plugin has no datastore")
    music.d.log = logging.getLogger(__name__)
    interactive = Interactive(music.bot)
    music_helper = MusicHelper()
    await start_lavalink()


@music.listener(hikari.VoiceStateUpdateEvent)
async def on_voice_state_update(event: VoiceStateUpdateEvent):
    """Clear lavalink after inu leaves a channel"""
    try:
        ## USER RELATED VOICE STATES ##
        
        if (
            (
                event.state.user_id != bot.me.id 
                and event.old_state 
                and not event.state.channel_id
            ) # someone left the channel
            or (
                event.state.user_id == bot.me.id 
                and event.old_state
                and event.state.channel_id
            ) # bot changed a channel
        ):
            # someone left channel or bot joined/changed channel
            player = await PlayerManager.get_player(event.state.guild_id)
            is_alone = player.check_if_bot_is_alone()
            if is_alone:
                log.debug(f"Bot is alone in {event.state.guild_id}")
                await player.on_bot_lonely()

        if event.state.channel_id and not event.state.user_id == bot.me.id:
            # someone joined a channel
            player = await PlayerManager.get_player(event.state.guild_id)
            if not player._node:  # ._node can be None, .node can't and raises error
                return
            bot_is_in_channel = player.check_if_bot_in_channel(event.state.channel_id)  
            if bot_is_in_channel:
                log.debug(f"Bot is not alone in {event.state.guild_id}")
                await player.on_human_join()

        ## BOT RELATED VOICE STATES ##
        # check if the user is the bot
        if not event.state.user_id == music.bot.get_me().id: # type: ignore
            return
        # bot connected (No channel -> channel)
        if event.old_state is None and event.state.channel_id:
            pass
        # bot changed room (channel -> channel)
        elif event.old_state and event.state.channel_id:
            # check if room is empty
            user_states = [
                state.user_id for state in 
                bot.cache.get_voice_states_view_for_channel(
                    event.guild_id, event.state.channel_id
                ).values() 
                if state.user_id != bot.me.id
            ]
            player = await PlayerManager.get_player(event.state.guild_id)
            if player.node is None:
                return
            if len(user_states) > 0:
                # resume player if new room is not empty
                log.debug(f"Bot changed room in {event.guild_id} to {event.state.channel_id}")
                await player._resume()
                player.queue.set_footer(
                    f"▶ Music was resumed by {bot.me.username}",
                    author=bot.me,
                )
                await player.queue.send(debug_info="Bot changed room")
            elif len(user_states) == 0 and not player.node.is_paused:
                # pause player if new room is empty
                await player._pause()
                await asyncio.sleep(0.1)
                player.queue.set_footer(
                    f"⏸ Music was paused by {bot.me.username}",
                    author=bot.me,
                )
                await player.queue.send(debug_info="Bot changed room")
                await player.on_bot_lonely()
        # bot disconnected
        elif event.state.channel_id is None and not event.old_state is None:
            player = await PlayerManager.get_player(event.state.guild_id)
            if player.clean_queue:
                with suppress(hikari.NotFoundError, IndexError):
                    music_message = player.queue.message
                    try:
                        await music_message.edit(
                            components=player.queue.build_music_components(
                            disable_all=True)
                        )
                    except hikari.NotFoundError:
                        log.error(traceback.format_exc()) 
            else:
                # add current song again, because the current will be removed
                queue = player.node.queue 
                queue.insert(0, queue[0])
                player._node.queue = queue
                await lavalink.set_guild_node(player.guild_id, player._node)

            await lavalink.destroy(event.guild_id)
            await lavalink.wait_for_connection_info_remove(event.guild_id)
            # Destroy nor leave removes the node or the queue loop, you should do this manually.
            if player.clean_queue:
                log.debug(f"cleaning queue of {event.guild_id}")
                await lavalink.remove_guild_node(event.guild_id)
                await lavalink.remove_guild_from_loops(event.guild_id)
                player.node = None
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
    if not event.endpoint:
        log.warning("Endpoint should never be None!")
        return
    await lavalink.raw_handle_event_voice_server_update(event.guild_id, event.endpoint, event.token)
    player = await PlayerManager.get_player(event.guild_id)
    if player:
        player.queue.set_footer(
            text=f"📡 Voice Server Update: {event.endpoint}",
            author=bot.me
        )
    # await asyncio.sleep(4)
    # if player.queue.custom_info and not player.node.is_paused and len(player.node.queue) > 0:
    #     await player.queue.send(debug_info="Voice Server Update")


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
    if not isinstance(event.interaction, hikari.ComponentInteraction):
        return
    
    ctx = get_context(event)
    if not [custom_id for custom_id in MENU_CUSTOM_IDS if ctx.custom_id == custom_id]:
        # wrong custom id
        return
    player = await PlayerManager.get_player(event.interaction.guild_id, event=event)
    ctx = player.ctx
    guild_id = player.ctx.guild_id
    custom_id = player.ctx.custom_id
    message = player.queue.message
    log = getLogger(__name__, "MUSIC INTERACTION RECEIVE")
    node = await lavalink.get_guild_node(guild_id)
    if not (message and node and len(node.queue) > 0):
        return await ctx.respond(
            "How am I supposed to do anything without even an active radio playing music?",
            ephemeral=True
        )
    if not (member := await bot.mrest.fetch_member(player.ctx.guild_id, player.ctx.author.id)):
        return

    if (await ctx.message()).id != message.id:
        # music message is different from message where interaction comes from
        # disable buttons from that different message
        await ctx.respond(
            embeds=ctx.i.message.embeds, 
            components=player.queue.build_music_components(disable_all=True),
            update=True,
        )
    tasks: List[asyncio.Task] = []
    custom_info = ""

    if custom_id == 'music_shuffle':
        custom_info = f'🔀 Music was shuffled by {member.display_name}'
        music_helper.add_to_log(
            guild_id=guild_id, 
            entry=custom_info
        )
        nqueue = node.queue[1:]
        random.shuffle(nqueue)
        nqueue = [node.queue[0], *nqueue]
        node.queue = nqueue
        await player.update_node(node)
        await lavalink.set_guild_node(guild_id, node)
    elif custom_id == 'music_resume':
        await ctx.defer(update=True)
        custom_info = f'▶ Music was resumed by {member.display_name}'
        music_helper.add_to_log(
            guild_id=guild_id, 
            entry=custom_info
        )
        tasks.append(
            asyncio.create_task(player._resume())
        )

    elif custom_id == 'music_skip_1':
        custom_info = f'1️⃣ Music was skipped by {member.display_name} (once)'
        await asyncio.create_task(player._skip(amount = 1))
        music_helper.add_to_log(
            guild_id=guild_id, 
            entry=custom_info
        )

    elif custom_id == 'music_skip_2':
        custom_info = f'2️⃣ Music was skipped by {member.display_name} (twice)'
        await asyncio.create_task(player._skip(amount = 2))
        music_helper.add_to_log(
            guild_id=guild_id, 
            entry=custom_info
        )
    
    elif custom_id == 'music_pause':
        custom_info = f'⏸ Music was paused by {member.display_name}'
        music_helper.add_to_log(
            guild_id=guild_id, 
            entry=custom_info
        )
        asyncio.create_task(ctx.cache_last_response())
        tasks.append(
            asyncio.create_task(player._pause())
        )

    elif custom_id == 'music_stop':
        custom_info = f'🛑 Music was stopped by {member.display_name}'
        tasks.extend([
            asyncio.create_task(
                ctx.respond(
                    embed=(
                        Embed(title="🛑 music stopped")
                        .set_footer(text=custom_info, icon=member.avatar_url)
                    ),
                    delete_after=30,
                )
            ),
            asyncio.create_task(
                player._leave()
            ),
        ])
        music_helper.add_to_log(
            guild_id=guild_id, 
            entry=custom_info
        )
        return
    
    if tasks:
        done, pending = await asyncio.wait(tasks, return_when=asyncio.ALL_COMPLETED)
        for task in [*done, *pending]:
            task.cancel()
            if isinstance(task.exception(), BotResponseError):
                await ctx.respond(**task.exception().kwargs)
                return

    player.queue.custom_info = custom_info
    if "music_skip" in custom_id:
        player.queue._last_update = datetime.datetime.now()
    await player.queue.send(debug_info=custom_info)



async def start_lavalink() -> None:
    """Event that triggers when the hikari gateway is ready."""
    if not music.bot.conf.lavalink.connect:
        music.d.log.warning(f"Lavalink connection won't be established")
        return
    sleep_time = 3
    log.debug(f"Sleep for {sleep_time} seconds before connecting to Lavalink") 
    await asyncio.sleep(sleep_time)
    for x in range(10):
        try:
            builder = (
                # TOKEN can be an empty string if you don't want to use lavasnek's discord gateway.
                lavasnek_rs.LavalinkBuilder(music.bot.get_me().id, music.bot.conf.bot.DISCORD_TOKEN) #, 
                # This is the default value, so this is redundant, but it's here to show how to set a custom one.
                .set_host(music.bot.conf.lavalink.IP)
                .set_password(music.bot.conf.lavalink.PASSWORD)
            )
            builder.set_start_gateway(False)
            lava_client = await builder.build(EventHandler())
            interactive.lavalink = lava_client
            global lavalink
            lavalink = lava_client
            break
        except Exception:
            if x == 9:
                music.d.log.error(traceback.format_exc())
                return
            else:
                #log.info(f"retrying lavalink connection in {} seconds")
                await asyncio.sleep(sleep_time)
    log.info("lavalink is connected")



@music.command
@lightbulb.add_checks(lightbulb.guild_only)
@lightbulb.command("fix", "I will kick on my radio, that you will hear music again")
@lightbulb.implements(commands.PrefixCommand, commands.SlashCommand)
async def fix(ctx: context.Context) -> None:
    """I will kick on my radio, that you will hear music again"""
    player = await PlayerManager.get_player(ctx.guild_id, ctx.event)
    await player._fix()
    await player.ctx.respond("Should work now")



@music.command
@lightbulb.add_checks(lightbulb.guild_only)
@lightbulb.command("leave", "I will leave your channel")
@lightbulb.implements(commands.PrefixCommand, commands.SlashCommand)
async def leave(ctx: context.Context) -> None:
    """Leaves the voice channel the bot is in, clearing the queue."""
    if not ctx.guild_id:
        return  # just for pylance
    player = await PlayerManager.get_player(ctx.guild_id, ctx.event)
    await player._leave()
    await player.ctx.respond(
        embed=(
            Embed(title="🛑 music stopped")
                .set_footer(text=f"music was stopped by {ctx.member.display_name}", icon=ctx.member.avatar_url)
        )
    )



@music.command
@lightbulb.add_cooldown(5, 1, lightbulb.UserBucket)
@lightbulb.add_checks(lightbulb.guild_only)
@lightbulb.option("query", "the title of the track etc.", modifier=OM.CONSUME_REST, type=str, autocomplete=True)
@lightbulb.command("play-at-position", "Advanced play features", aliases=["pl"])
@lightbulb.implements(commands.PrefixCommandGroup, commands.SlashCommandGroup)
async def pl(ctx: context.Context) -> None:
    """Searches the query on youtube, or adds the URL to the queue."""
    player = await PlayerManager.get_player(ctx.guild_id, event=ctx.event)
    player.query = ctx.options.query
    try:
        await player._play()
    except Exception:
        music.d.log.error(f"Error while trying to play music: {traceback.format_exc()}")



@pl.child
@lightbulb.add_cooldown(5, 1, lightbulb.UserBucket)
@lightbulb.add_checks(lightbulb.guild_only)
@lightbulb.option("query", "the name of the track etc.", modifier=OM.CONSUME_REST, type=str, autocomplete=True)
@lightbulb.command("next", "enqueue a title at the beginning of the queue", aliases=["1st"])
@lightbulb.implements(commands.PrefixSubCommand, commands.SlashSubCommand)
async def now(ctx: Context) -> None:
    """Adds a song infront of the queue. So the track will be played next"""
    player = await PlayerManager.get_player(ctx.guild_id, ctx.event)
    await player.play_at_pos(1, ctx.options.query)



@pl.child
@lightbulb.add_cooldown(5, 1, lightbulb.UserBucket)
@lightbulb.add_checks(lightbulb.guild_only)
@lightbulb.option("query", "the name of the track etc.", modifier=OM.CONSUME_REST, type=str, autocomplete=True)
@lightbulb.command("second", "enqueue a title as the second in the queue", aliases=["2nd"])
@lightbulb.implements(commands.PrefixSubCommand, commands.SlashSubCommand)
async def second(ctx: Context) -> None:
    """Adds a song at the second position of the queue. So the track will be played soon"""
    player = await PlayerManager.get_player(ctx.guild_id, ctx.event)
    await player.play_at_pos(2, ctx.options.query)



@pl.child
@lightbulb.add_cooldown(5, 1, lightbulb.UserBucket)
@lightbulb.add_checks(lightbulb.guild_only)
@lightbulb.option("position", "the position in the queue", modifier=OM.CONSUME_REST, type=int)
@lightbulb.option("query", "the name of the track etc.", modifier=commands.OptionModifier.CONSUME_REST, autocomplete=True)
@lightbulb.command("position", "enqueue a title at a custom position of the queue", aliases=[])
@lightbulb.implements(commands.PrefixSubCommand, commands.SlashSubCommand)
async def position(ctx: SlashContext) -> None:
    """Adds a song at the <position> position of the queue. So the track will be played soon"""
    player = await PlayerManager.get_player(ctx.guild_id, ctx.event)
    await player.play_at_pos(int(ctx.options.position), ctx.options.query)



@music.command
@lightbulb.add_cooldown(5, 1, lightbulb.UserBucket)
@lightbulb.add_checks(lightbulb.guild_only)
@lightbulb.option("query", "the title of the track", modifier=OM.CONSUME_REST, type=str, autocomplete=True)
@lightbulb.command("play", "play a song", aliases=["pl"])
@lightbulb.implements(commands.SlashCommand)
async def play_normal(ctx: context.Context) -> None:
    player = await PlayerManager.get_player(ctx.guild_id, ctx.event)
    await player._play(ctx.options.query)



@music.command
@lightbulb.add_checks(lightbulb.guild_only)
@lightbulb.command("stop", "stop the current title")
@lightbulb.implements(commands.PrefixCommand, commands.SlashCommand)
async def stop(_ctx: Context) -> None:
    """Stops the current song (skip to continue)."""
    player = await PlayerManager.get_player(_ctx.guild_id, _ctx.event)
    await player.ctx.defer()
    await lavalink.stop(player.ctx.guild_id)
    await player.ctx.respond("Stopped playing")
    await player.queue.send()



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
    player = await PlayerManager.get_player(ctx.guild_id, ctx.event)
    successful = await player._skip(ctx.options.amount)
    if not successful:
        return
    await player.queue.send()



@music.command
@lightbulb.add_checks(lightbulb.guild_only)
@lightbulb.command("pause", "pause the music")
@lightbulb.implements(commands.SlashCommand)
async def pause(ctx: SlashContext) -> None:
    """Pauses the current song."""
    if not ctx.guild_id:
        return
    player = await PlayerManager.get_player(ctx.guild_id, ctx.event)
    await player._pause(ctx.guild_id)
    await player.queue.send()



@music.command
@lightbulb.add_checks(lightbulb.guild_only)
@lightbulb.command("resume", "resume the music")
@lightbulb.implements(commands.SlashCommand)
async def resume(_ctx: SlashContext) -> None:
    """Resumes playing the current song."""
    if not _ctx.guild_id:
        return
    player = await PlayerManager.get_player(_ctx.guild_id, _ctx.event)
    await player._resume()
    await player.queue.send()



@music.command
@lightbulb.add_cooldown(20, 1, lightbulb.UserBucket)
@lightbulb.add_checks(lightbulb.guild_only)
@lightbulb.command("queue", "Resend the music message")
@lightbulb.implements(commands.PrefixCommand, commands.SlashCommand)
async def _queue(_ctx: Context) -> None:
    player = await PlayerManager.get_player(_ctx.guild_id, _ctx.event)
    # defer, that it doesn't timeout while loading queue
    await player.ctx.defer()
    await player.queue.send(force_resend=True)



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
    if not (log_sites := music_helper.get_log(ctx.guild_id, 2000)):
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
    player = await PlayerManager.get_player(ctx.guild_id, ctx.event)
    await player.ctx.defer()
    await player._clear()
    music_helper.add_to_log(
        ctx.guild_id,
        f"music was cleared by {ctx.member.display_name}"
    )
    await player.queue.send(force_resend=True)


@music.command
@lightbulb.add_checks(lightbulb.guild_only)
@lightbulb.command("join", "joins the channel")
@lightbulb.implements(commands.PrefixCommand, commands.SlashCommand)
async def clear(ctx: Context):
    """clears the music queue"""
    if not ctx.guild_id or not ctx.member:
        return
    await ctx.defer()
    player = await PlayerManager.get_player(ctx.guild_id, ctx.event)
    await player._join()
    await player.queue.send(force_resend=True)


@m.child
@lightbulb.add_checks(lightbulb.guild_only)
@lightbulb.command("history", "Get a list of all the last played titles", aliases=["h"])
@lightbulb.implements(commands.PrefixSubCommand, commands.SlashSubCommand)
async def history(ctx: Context):
    if not ctx.guild_id:
        return
    history = await MusicHistoryHandler.get(ctx.guild_id)
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
        embed.description += f"{i} | [{record['title']}]({record['url']})\n"
    if embed:
        embeds.append(embed)
    pag = MusicHistoryPaginator(
        history=history,
        pages=embeds,
        items_per_site=20,
    )
    player = await PlayerManager.get_player(ctx.guild_id, ctx.event)
    # TODO params of player._play have changed
    await pag.start(player.ctx, player._play)



@m.child
@lightbulb.add_checks(lightbulb.owner_only)
@lightbulb.command("restart", "reconnects to lavalink", hidden=True)
@lightbulb.implements(commands.PrefixSubCommand)
async def restart(ctx: context.Context):
    await start_lavalink()



@m.child
@lightbulb.add_checks(lightbulb.guild_only)
@lightbulb.option("query", "What do you want to search?", modifier=OM.CONSUME_REST, autocomplete=True)
@lightbulb.command("search", "Searches the queue; every match will be added infront of queue", aliases=["s"])
@lightbulb.implements(commands.PrefixSubCommand, commands.SlashSubCommand)
async def music_search(ctx: context.Context):
    player = await PlayerManager.get_player(ctx.guild_id, ctx.event)
    node = player.node
    query = ctx.options.query
    if not node:
        return await player.ctx.respond("You have to play music, that I can search for songs")
    await player.ctx.defer()
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
        await player.queue.send(
            force_resend=True,
            custom_info=f"🔍 {ctx.member.display_name} searched and added {Human.plural_('title', len(tracks))}"
        )
        await player.ctx.respond(resp, delete_after=100, update=False)
        # this message will be deleted and is not the music message
        await player.ctx._responses.pop(-1)
    else:
        return await player.ctx.respond("No matches found")


@music_search.autocomplete("query")
async def query_auto_complete(
    option: hikari.AutocompleteInteractionOption,
    interaction: hikari.AutocompleteInteraction
) -> List[str]:
    """
    Shows search results in the autocomplete box for music search
    """
    if not (query := option.value):
        return []
    player = await PlayerManager.get_player(interaction.guild_id)
    answers = set()
    if not (node := player.node):
        return answers
    for track in node.queue:
        if query in track.track.info.title.lower() or query in track.track.info.author.lower():
            answers.add(track.track.info.title)
    answers = [a[:100] for a in answers][:22]
    answers.insert(0, query)
    answers.insert(1, "---------- this will be added ----------")
    return answers


@position.autocomplete("query")
@second.autocomplete("query")
@now.autocomplete("query")
@play_normal.autocomplete("query")
async def query_auto_complete(
    option: hikari.AutocompleteInteractionOption,
    interaction: hikari.AutocompleteInteraction
) -> List[str]:
    value = option.value or ""
    records = await MusicHistoryHandler.cached_get(interaction.guild_id)
    if not value:
        records = records[:23]
    else:
        tag_records = await TagManager.cached_find_similar(value, interaction.guild_id, tag_type=TagType.MEDIA)
        new_records = []
        if len(str(value)) > 4:
            # add tags
            records.extend([
                {"title": d["tag_key"], "prefix": MEDIA_TAG_PREFIX} for d in tag_records
            ])
        for r in records:
            r = dict(r)
            if value:
                r["ratio"] = fuzz.partial_token_set_ratio(value, r["title"])
            if not r in new_records:
                new_records.append(r)
        records = new_records
        records.sort(key=lambda r: r["ratio"], reverse=True)

    converted_records = [r.get("prefix", HISTORY_PREFIX) + r["title"] for r in records]
    if len(str(value)) > 3:
        converted_records.insert(0, str(value))
    return [r[:100] for r in converted_records[:23]]



class Player:
    """A Player which represents a guild Node and it's queue message"""
    def __init__(
        self,
        guild_id: int,
        node: lavasnek_rs.Node = None,
    ):
        self.guild_id = guild_id
        self._node = node
        self.ctx = None
        self._query: str = ""
        self.queue: "Queue" = Queue(self)
        self._clean_queue: bool = True
        self._auto_leave_task: Optional[asyncio.Task] = None
    
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
        if len(self.node.queue) > 0:
            await self._pause()
            self.queue.set_footer(
                f"I'll leave the channel in {naturaldelta(DISCONNECT_AFTER)} - the queue will be saved", 
                author=bot.me, 
                override_author=True
            )
            await self.queue.send()

        await asyncio.sleep(DISCONNECT_AFTER)
        if len(self.node.queue) > 0:
            asyncio.create_task(self.set_clean_queue(False))

            self.queue.set_footer(
                "I left the channel, but the queue is saved", 
                author=bot.me, 
                override_author=True
            )
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
    def node(self) -> lavasnek_rs.Node:
        """Returns the node of the player"""
        if not self._node:
            raise RuntimeError("Node is not set")
        return self._node
    
    @node.setter
    def node(self, node: lavasnek_rs.Node):
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

    @property
    def ctx(self) -> InuContext:
        """The currently used context of the player"""
        if not self._ctx:
            raise TypeError("ctx is not set")
        return self._ctx
    
    @ctx.setter
    def ctx(self, ctx: InuContext):
        self._ctx = ctx

    async def update_node(self, node: lavasnek_rs.Node | None = None) -> None:
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
        await self.update_node()
    
    async def _play(self, query: str | None = None, prevent_to_queue: bool = False) -> Tuple[bool, InuContext | None]:
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
        if query:
            self.query = query
        else:
            query = self.query
        if not self.ctx.guild_id or not self.ctx.member:
            return False, None
        ictx = self.ctx
        con = lavalink.get_guild_gateway_connection_info(self.guild_id)
        self.queue._last_update = datetime.datetime.now()
        # Join the user's voice channel if the bot is not in one.
        if not con:
            await self._join()
        await self.update_node()
        await ictx.defer()

        if query.startswith(HISTORY_PREFIX):
            # -> history -> get url from history
            query = query.replace(HISTORY_PREFIX, "")
            history = await MusicHistoryHandler.cached_get(self.guild_id)
            if (alt_query:=[t["url"] for t in history if query in t["title"]]):
                self.query=alt_query[0]

        if query.startswith(MEDIA_TAG_PREFIX):
            # -> media tag -> get url from tag
            query = query.replace(MEDIA_TAG_PREFIX, "")
            tag = await get_tag(ictx, query)
            self.query = tag["tag_value"][0]

        query = self.query
        if 'youtube' in query and 'playlist?list=' in query:
            # -> youtube playlist -> load playlist
            await self.load_yt_playlist()
        # not a youtube playlist -> something else
        else:
            # -> track from a playlist was added -> remove playlist info
            if (
                "watch?v=" in query
                and "youtube" in query
                and "&list" in query
            ):
                self.query = YouTubeHelper.remove_playlist_info(query)
            # try to add song
            event: Optional[hikari.InteractionCreateEvent] = None
            try:
                track, event = await self.search_track(ictx, self.query)
                log.debug(event)
            except BotResponseError as e:
                raise e
            except asyncio.TimeoutError:
                return False, None
            if track is None:
                await ictx.respond(f"I only found a lot of empty space for `{self.query}`")
                return False, None
            if event:
                # asked with menu - update context
                self.ctx = get_context(event=event)
            await self.load_track(track)

        if not prevent_to_queue:
            await self.queue.send(force_resend=True, create_footer_info=False, debug_info="from play"),
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
    ) -> Tuple[Optional[lavasnek_rs.Track], Optional[hikari.InteractionCreateEvent]]:
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
        track = None
        event = None

        if not query_information.tracks:
            query_information = await self.fallback_track_search(query)

        
        if len(query_information.tracks) > 1:
            try:
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
        return track, event
    
    async def load_yt_playlist(self) -> lavasnek_rs.Tracks:
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
        `lavasnek_rs.Track` :
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



    async def load_track(self, track: lavasnek_rs.Track):
        """Loads a track into the queue
        
        Args:
        ----
        ctx : InuContext
            The context to use for sending the message and fetching the node
        track : lavasnek_rs.Track
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
            self.queue.custom_info = f"🎵 {track.info.title} added by {bot.cache.get_member(self.guild_id, self.ctx.author.id).display_name}"
            self.queue.custom_info_author = self.ctx.member
            await self.update_node()
        except lavasnek_rs.NoSessionPresent:
            await self.ctx.respond(f"Use `/join` first")
            return



class Queue:
    """
    Represents the queue message of one player
    """
    def __init__(
        self,
        player: Player,
    ):
        self.player = player
        self._message: hikari.Message = None
        self._custom_info = ""
        self._custom_info_author: hikari.Member | None = None
        self._custom_footer: hikari.EmbedFooter | None = None
        self.create_footer_info = False
        self.current_track: lavasnek_rs.Track | None = None
        self._last_update = datetime.datetime.now()

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
        Sets a custom footer for the queue message

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
        last_track: lavasnek_rs.TrackQueue = self.node.queue[-1]
        requester = music.bot.cache.get_member(
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
            
        # remaining in queue info
        total_playtime = datetime.timedelta(
            milliseconds=sum(
                min(track.track.info.length, 36_000_000)  # max 10 hours -> prevent OverflowError
                for track in self.node.queue
            )
        ) 
        queue_len = len(self.node.queue)-3
        if not queue_len or queue_len < 0:
            queue_len = 0
        kwargs["text"] += f"\n{Human.plural_('song', queue_len, with_number=True)} ({total_playtime}) remaining in the queue"

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
    def node(self) -> lavasnek_rs.Node:
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
        if not disable_all:
            node = self.player.node
            
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
                    pre_titles_total_delta += datetime.timedelta(milliseconds=36000000)  # 10 hours
                continue
            if i >= AMOUNT_OF_SONGS_IN_QUEUE + 1:
                # only show 4 upcoming songs
                break

            if node.is_paused:
                discord_timestamp = "--:--"
            else:
                # <t:{start_timestamp:.0f}:t>
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
            return music.d.log.warning(f"can't get current playing song: {e}")

        if not node.queue[0].requester:
            music.d.log.warning("no requester of current track - returning")

        requester = music.bot.cache.get_member(self.player.guild_id, node.queue[0].requester)
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
            or music.bot.me.avatar_url
        )
        return music_embed
    
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

        if ctx:
            self.player.ctx = ctx
        else:
            ctx = self.player.ctx

        if not ctx.guild_id:
            log.debug("guild_id is None in queue command;")
            return
        
        try:
            self.current_track = None if not self.player._node else self.player.node.queue[0].track
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
            kwargs = {"update": True} if music_message else {}
            log.debug(f"send new message with {kwargs=}, {music_message=}")
            msg = await self.player.ctx.respond(
                embed=music_embed, 
                content=None,
                components=self.build_music_components(), 
                **kwargs
            )
            new_music_msg = await msg.message()

            # delete, if message was not reused
            try:
                if not old_music_msg is None and not old_music_msg.id == new_music_msg.id:
                    await old_music_msg.delete()
            except hikari.NotFoundError:
                pass
            self.message = new_music_msg
            return

        # edit existing message
        # only possible with component interactions
        try:
            timeout = 4
            ctx_message_id = old_music_msg.id
            async for m in music.bot.rest.fetch_messages(self.player.ctx.channel_id):
                if m.id == ctx_message_id:
                    # edit existing message if in last messages
                    msg = await self.player.ctx.respond(
                        embed=music_embed, 
                        components=self.build_music_components(),
                        content=None, 
                        update=True
                    )
                    self.message = await msg.message()
                    log.debug("update old")
                    return
                timeout -= 1
               
                if timeout == 0:
                    # resend message (not in last msgs found)
                    log.debug("send new")
                    await music_message.delete()
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




def load(inu: Inu) -> None:
    global bot
    bot = inu
    inu.add_plugin(music)


def unload(inu: Inu) -> None:
    inu.remove_plugin(music)