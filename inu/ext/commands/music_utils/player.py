from email import message
from typing import *
from datetime import datetime, timedelta
from dataclasses import dataclass
import asyncio
import random 
from contextlib import suppress

import hikari
from hikari.api import VoiceConnection
from hikari import Embed, Snowflake
from hikari.impl import MessageActionRowBuilder
from lavalink_rs import PlayerContext, TrackInQueue
import lightbulb
from lavalink_rs.model.search import SearchEngines
from lavalink_rs.model.track import Track, TrackData, PlaylistData, TrackLoadType, PlaylistInfo
from lavalink_rs.model.player import Player
from sortedcontainers.sortedlist import traceback
from tabulate import tabulate

from utils.shortcuts import display_name_or_id
from .query_strategies import *
from core import BotResponseError, ResponseProxy


from . import (
    LavalinkVoice, YouTubeHelper, TrackUserData, 
    ResponseLock, MusicMessageComponents, HISTORY_PREFIX,
    MEDIA_TAG_PREFIX, MARKDOWN_URL_REGEX, BotIsActiveState,
    VoiceState
)
from ..tags import get_tag
from utils import Human, MusicHistoryHandler
from core import Inu, get_context, InuContext, getLogger, InuContextBase

log = getLogger(__name__)

class MusicPlayerManager:
    _instances: Dict[int, "MusicPlayer"] = {}
    _bot: Inu
    _ctx: InuContext

    @classmethod
    def player_factory(cls, ctx_or_guild_id: int | InuContext) -> "MusicPlayer":
        """
        Creates or retrieves a MusicPlayer for the given guild
        
        Args:
        -----
        `ctx_or_guild_id`: (`int` | `InuContext`)
            The guild id or the context of the command.
            If it's the context, then it will be automatically set as player ctx.
        """
        guild_id = None
        ctx = None

        if isinstance(ctx_or_guild_id, InuContextBase):
            ctx_or_guild_id = cast(InuContext, ctx_or_guild_id)
            guild_id = ctx_or_guild_id.guild_id
            ctx = ctx_or_guild_id
        else:
            guild_id = ctx_or_guild_id
        guild_id = cast(int, guild_id)

        player = None
        player = cls._instances.get(guild_id)

        if not player:
            player = MusicPlayer(cls._bot, guild_id)
            cls._instances[guild_id] = player
        
        if ctx:
            player.set_context(ctx)

        return player

    @classmethod
    def set_bot(cls, bot: Inu) -> None:
        cls._bot = bot


    

class MusicPlayer:
    def __init__(self, bot: Inu, guild_id: Snowflake) -> None:
        self.bot: Inu = bot
        self._guild_id = guild_id
        self._ctx: InuContext | None = None
        self._queue: QueueMessage = QueueMessage(self)
        self.response_lock = ResponseLock(timedelta(seconds=6))
        self._join_channel: hikari.PartialChannel | None = None
        self.voice_state: VoiceState = BotIsActiveState(self)  # Default state
        
    def with_join_channel(self, channel: hikari.PartialChannel) -> "MusicPlayer":
        """
        Sets the channel for /join
        """
        self._join_channel = channel
        return self
        
    @property
    def guild(self) -> hikari.Guild:
        guild = self.bot.cache.get_guild(self.guild_id)
        assert guild
        return guild

    def _get_voice(self) -> LavalinkVoice | None:
        """
        Returns:
        --------
        `LavalinkVoice | None`:
            The voice connection of the bot in the guild
            (`self.bot.voice.connections.get(self.guild_id)`)
        """
        return self.bot.voice.connections.get(self.guild_id)  # type: ignore
    
    async def _fetch_voice_player(self) -> Player | None:
        """
        Returns:
        --------
        `lavalink_rs.model.player.Player`:
            The player of the voice connection
        """
        voice = self._get_voice()
        if not voice:
            return None
        assert isinstance(voice, LavalinkVoice)
        return await voice.player.get_player()
    
    @property
    def queue(self) -> "QueueMessage":
        return self._queue
    
    @property   
    def ctx(self) -> InuContext:
        if self._ctx is None:
            raise RuntimeError("Context is not set")
        return self._ctx
    
    @property
    def is_active(self) -> bool:
        """Whether or not the player is currently in use. Note: _ctx is checked for that"""
        return self._ctx is not None
    
    @property
    def guild_id(self) -> Snowflake:
        return self._guild_id
    
    @property
    def ctx_avatar_url(self) -> str:
        url = self.ctx.author.avatar_url or self.bot.me.avatar_url
        assert isinstance(url, str)
        return url

    # Add voice state methods that delegate to the current state
    async def check_if_bot_is_alone(self):
        """Check if the bot is alone in the voice channel, delegates to current state."""
        #if hasattr(self, 'voice_client') and self.voice_client:
        log.debug(f"Check for is alone with {type(self.voice_state)}")
        return await self.voice_state.check_if_bot_is_alone()
    
    async def on_bot_lonely(self):
        """Handle the event when bot becomes lonely, delegates to current state."""
        await self.voice_state.on_bot_lonely()
        await self.voice_state.update_message()
    
    async def on_human_join(self):
        """Handle the event when a human joins the voice channel, delegates to current state."""
        await self.voice_state.on_human_join()
        await self.voice_state.update_message()

    
    async def is_paused(self) -> bool:
        """
        https://docs.rs/lavalink-rs/latest/lavalink_rs/player_context/struct.PlayerContext.html

        Returns:
            bool: whether the player is paused or not
        """
        voice = self._get_voice()
        if not voice:
            return True
        return (await voice.player.get_player()).paused  # type: ignore
    
    def set_context(self, ctx: InuContext) -> None:
        self._ctx = ctx

    async def _join(self, channel: Optional[hikari.PartialChannel] = None) -> Optional[int]:
        if not self.guild_id:
            return None

        channel_id = None

        if channel:
            channel_id = channel.id

        if not channel_id:
            voice_state = self.bot.cache.get_voice_state(self.guild_id, self.ctx.author.id)

            if not voice_state or not voice_state.channel_id:
                return None

            channel_id = voice_state.channel_id

        voice = self._get_voice()


        # set state to active, to not directly leave
        self.voice_state = BotIsActiveState(self)

        if not voice:
            await LavalinkVoice.connect(
                Snowflake(self.guild_id),
                channel_id,
                self.bot,
                self.bot.lavalink,
                (self.ctx.channel_id, self.bot.rest),
            )
        else:
            assert isinstance(voice, LavalinkVoice)

            await LavalinkVoice.connect(
                Snowflake(self.guild_id),
                channel_id,
                self.bot,
                self.bot.lavalink,
                (self.ctx.channel_id, self.ctx.bot.rest),
                #old_voice=voice,
            )

        return channel_id
    
    async def pause(self, suppress_info: bool = False, paused_by: hikari.User | None = None) -> None:
        """Pauses a player and adds a footer info"""
        user = paused_by or self.ctx.author
        if not suppress_info:
            self._queue.add_footer_info(
                f"⏸️ Music paused by {user.username}", 
                user.avatar_url  # type: ignore
            )
        await self._set_pause(True)
        
    async def resume(self, resumed_from: hikari.User | None = None) -> None:
        """Resumes the player and adds a footer info"""
        user = resumed_from or self.ctx.author
        self._queue.add_footer_info(
            f"▶️ Music resumed by {user.username}", 
            user.avatar_url  # type: ignore
        )
        await self._set_pause(False)

    async def _set_pause(self, pause: bool) -> None:
        """
        Pauses or resumes the MusicPlayer
        """

        ctx = self.ctx
        voice = self._get_voice()

        if not voice:
            return

        assert isinstance(voice, LavalinkVoice)

        player = await voice.player.get_player()

        if player.track:
            await voice.player.set_pause(pause)
        else:
            return
        
        
    async def skip(self, amount: int = 1) -> None:
        ctx = self.ctx
        if not ctx.guild_id:
            return None

        voice = self._get_voice()

        if not voice:
            await ctx.respond("Not connected to a voice channel")
            return None

        assert isinstance(voice, LavalinkVoice)

        player = await voice.player.get_player()
        
        if amount > 1:
            self._queue.add_footer_info(
                f"🎵 Skipped {Human.plural_('song', amount, True)}", 
                self.ctx.author.avatar_url  # type: ignore
            )
        else:
            self._queue.add_footer_info(
                f"🎵 Skipped {player.track.info.author} - {player.track.info.title}",   
                self.ctx.author.avatar_url  # type: ignore
            )

        if not player.track:
            await ctx.respond("No song is playing")
            return None
        
        for _ in range(amount):
            voice.player.skip()

    async def stop(self) -> None:
        ctx = self.ctx
        if not ctx.guild_id:
            return None

        voice = self._get_voice()

        if not voice:
            await ctx.respond("Not connected to a voice channel")
            return None

        assert isinstance(voice, LavalinkVoice)

        player = await voice.player.get_player()

        if player.track:
            if player.track.info.uri:
                await ctx.respond(
                    f"Stopped: [`{player.track.info.author} - {player.track.info.title}`](<{player.track.info.uri}>)"
                )
            else:
                await ctx.respond(
                    f"Stopped: `{player.track.info.author} - {player.track.info.title}`"
                )

            await voice.player.stop_now()
        else:
            await ctx.respond("Nothing to stop")
                
        
    async def leave(self, silent: bool = False) -> None:
        ctx = self.ctx
        if not ctx.guild_id:
            return None

        voice = self._get_voice()
        if not voice and not silent:
            await ctx.respond("I can't leave without beeing in a voice channel in the first place, y'know?")
            return None
        if voice:
            await voice.disconnect()

    def _make_user_data(self, ctx: Optional[InuContext] = None) -> TrackUserData:
        """
        User data which will be added to lavalinks track (`track.track.user_data`)
        """
        if not ctx:
            ctx = self.ctx
        return {"requester_id": ctx.author.id}
    
    async def fetch_current_track(self) -> TrackData | None:
        voice_player = await self._fetch_voice_player()
        if not voice_player:
            return None
        return voice_player.track
    

    async def _process_query(self, query: str, search_engine: Optional[str] = None) -> List[str]:
        """
        Process the query (one line) and return the modified query.

        Parameters
        ----------
        query : str
            The search query or URL for the track or playlist.
        user_data : TrackUserData
            The user data associated with the track.

        Returns
        -------
        str
            The processed query.

        Raises
        ------
        BotResponseError
            If no query strategy matches the query.

        Notes
        -----
        - Changes MEDIA TAGS and HISTORY PREFIXES to the actual URL or name.
        - is for one line queries
        """
        if len(query.splitlines()) > 1:
            results = []
            for line in query.splitlines():
                results.extend(await self._process_query(line, search_engine))
            return results

        for strategy in QUERY_STRATEGIES:
            if not strategy.matches_query(query):
                continue
            result = await strategy.process_query(self.ctx, query, self.guild_id, search_engine)
            log.trace(f"process {query} with {type(strategy).__name__} -> {result}; {len(result.splitlines())}")
            if len(result.splitlines()) > 1:
                # return each line as a separate query
                return [line for q in await self._process_query(result, search_engine) for line in q.splitlines()]
            else:
                return [result]
        raise BotResponseError(f"No QueryStrategy for: {query}")

    def _get_player_ctx(self) -> PlayerContext:
        voice = self.bot.voice.connections.get(self.guild_id)
        if not voice:
            raise RuntimeError("Not connected to a voice channel")
        return voice.player

    async def play(self, query: str, position: int | None = None, search_engine: str = "soundcloud") -> bool:
        """
        Plays a track or playlist based on the provided query.

        Parameters
        ----------
        query : str
            The search query or URL for the track or playlist to play.

        Returns
        -------
        _ : bool
            Whether the track was successfully added to the queue.

        Raises
        ------
        BotResponseError
            If there is an error processing the query.
        TimeoutError
            If no track is selected from the search results.

        Notes
        -----
        - If no query is provided, it will attempt to play the next track in the queue.
        - If a track is already playing, it will notify the user.
        - If the queue is empty, it will notify the user.
        - Supports loading a single track, a search result, or a playlist.
        - Adds track or playlist information to the queue and updates the music history.
        """
        log.debug(f"play: {query = }")
        voice, has_joined = await self._connect()
        if not has_joined:
            return False
        player_ctx = voice.player  # type: ignore

        # process query and add track(s) line by line
        lines = await self._process_query(query, search_engine)
        silent = len(lines) > 1
        proxy = None
        progress: List[Tuple[int, str]] = []
        for i, query in enumerate(lines):
            try:
                message, was_successfull = await self._add_track(player_ctx, query, silent, position)
                progress.append((i+1, str(message)[:50]))
                proxy = await self._communicate_parsing_progress(progress, proxy, silent)
            except BotResponseError as e:
                await self.ctx.respond(**e.context_kwargs)
            except TimeoutError:
                return False
            
        if len(lines) > 1:
            # when multiple tracks are added, the listener will trigger,
            # when first track is added. Hence we need to resend the queue
            # to show all the tracks instead of the first one.
            await self.send_queue()
            
        if has_joined:
            return True

        player_data = await player_ctx.get_player()
        queue = player_ctx.get_queue()

        if player_data:
            if not player_data.track and await queue.get_track(0):
                player_ctx.skip()
        return True

    async def _communicate_parsing_progress(self, progress: List[Tuple[int, str]], proxy: None | ResponseProxy, silent: bool) -> None | ResponseProxy:
        """
        silent means in this case, that this message will be send und updated. Not silent means that this will be done 
        in another part of the code, hence here it will be ignored.
        """
        if not silent:
            return None
        table = tabulate(progress, headers=["Line", "Title"], tablefmt="rounded_outline")
        if not proxy:
            proxy = await self.ctx.respond(f"Searching Tracks...\n```{table}```")
        else:
            await proxy.edit(f"Searching Tracks...\n```{table}```")
        return proxy
    
    async def _choose_track(self, tracks: List[TrackData], silent: bool) -> TrackData | None:
        """
        Creates a selection menu for the user to choose a track from a list of tracks.
        
        Parameters
        ----------
        tracks : List[TrackData]
            List of track data objects to choose from
        silent : bool
            Don't ask the user, just return the first track
            
        Returns
        -------
        TrackData or None
            The selected track if user makes a selection, None if user cancels or timeout occurs
            
        Notes
        -----
        Creates an interactive message with:
        - A dropdown menu listing up to 25 tracks
        - A cancel button
        - 60 second timeout for user interaction
        - Updates context after selection
        The tracks are displayed in format: "<index> | <title> (<author>)"
        """
        if silent:
            return tracks[0]

        id_ = self.bot.id_creator.create_id()
        # create component
        menu: hikari.impl.TextSelectMenuBuilder = (
            MessageActionRowBuilder()
            .add_text_menu(f"query_menu-{id_}")
            .set_min_values(1)
            .set_max_values(1)
            .set_placeholder("Choose a song")
        ) # type: ignore

        stop_button = (
            MessageActionRowBuilder()
            .add_interactive_button(
                hikari.ButtonStyle.SECONDARY, 
                f"stop_query_menu-{id_}", 
                label="I don't find it ¯\_(ツ)_/¯",
                emoji="🗑️"
            )
        )
        # add songs to menu with index as ID
        for i, track in enumerate(tracks):
            if i >= 24:
                break
            query_display = f"{i+1} | {track.info.title} ({track.info.author})"[:100]
            menu.add_option(query_display, str(i))
        
        # ask the user
        log.debug(f"Song Selection: {menu.parent}")
        proxy = await self.ctx.respond(components=[menu.parent, stop_button])
        menu_msg = await proxy.message()
        
        # wait for interaction
        value_or_custom_id, event, _ = await self.bot.wait_for_interaction(
            custom_ids=[f"query_menu-{id_}", f"stop_query_menu-{id_}"],
            message_id=menu_msg.id,
            timeout=60
        )
        if value_or_custom_id in [None, f"stop_query_menu-{id_}"]:
            # probably timeout -> delete message
            with suppress(hikari.NotFoundError):
                await proxy.delete()
            return None
        
        # set new context and return
        assert event is not None
        assert isinstance(event.interaction, hikari.ComponentInteraction)
        assert isinstance(value_or_custom_id, str)
        
        ctx = get_context(event.interaction)
        await ctx.defer(update=True)
        self.set_context(ctx)

        return tracks[int(value_or_custom_id)]
    
    
    async def _add_track(self, player_ctx: PlayerContext, query: str, silent: bool, position: int | None = None) -> Tuple[Optional[str], bool]:
        """Add a track or playlist to the queue based on the query.

        Parameters
        ----------
        player_ctx : PlayerContext
            The player context managing the queue
        query : str
            The search query or URL to load tracks from
        silent : bool
            Whether or not to supress responses to the user (e.g. track selection)

        Returns
        -------
        Optional[str]
            The title of the track/playlist or the error message
        bool
            True if track(s) were successfully added, False if there was an error

        Notes
        -----
        This method handles three types of track loading:

        1. Single Track: Directly adds the track to queue
        2. Search Results: Shows selection menu and adds chosen track
        3. Playlist: Adds all tracks from playlist to queue

        For playlists with a selected track, only that track is added.
        Otherwise all tracks in the playlist are added.

        Raises
        ------
        TimeoutError
            If no track is selected from search results
        """
        # search for tracks with the query
        ctx = self.ctx
        user_data: TrackUserData = self._make_user_data(ctx)
        track_title: str | None = None
        try:
            log.debug(f"Search {query=}")
            tracks: Track = await ctx.bot.lavalink.load_tracks(self.guild_id, query)
            loaded_tracks = tracks.data
        except Exception as e:
            log.error(traceback.format_exc())
            if not silent:
                await ctx.respond("Error")
            return "Interal Error", False

        if tracks.load_type == TrackLoadType.Track:
            assert isinstance(loaded_tracks, TrackData)
            loaded_tracks.user_data = user_data  # type: ignore
            self.add_to_queue(loaded_tracks, player_ctx, position=position)  # adds the track
            self._queue.add_footer_info(make_track_message(loaded_tracks), self.ctx_avatar_url)
            track_title = loaded_tracks.info.title
            
        elif tracks.load_type == TrackLoadType.Search:
            assert isinstance(loaded_tracks, list)
            track = await self._choose_track(loaded_tracks, silent)
            if not track:
                raise TimeoutError("No track selected")
            track.user_data = user_data  # type: ignore
            self.add_to_queue(track, player_ctx, position=position)
            self._queue.add_footer_info(make_track_message(track), self.ctx_avatar_url)
            track_title = track.info.title

        elif tracks.load_type == TrackLoadType.Playlist:
            assert isinstance(loaded_tracks, PlaylistData)
            if loaded_tracks.info.selected_track:
                track = loaded_tracks.tracks[loaded_tracks.info.selected_track]
                track.user_data = user_data  # type: ignore
                self.add_to_queue(track, player_ctx, position=position)
                self._queue.add_footer_info(make_track_message(track), self.ctx_avatar_url)
                track_title = track.info.title
            else:
                log.debug(f"load playlist without selected track")
                tracks: List[TrackData] = loaded_tracks.tracks
                for i in tracks:
                    i.user_data = user_data

                queue = player_ctx.get_queue()
                queue.append(tracks)
                self._queue.add_footer_info(
                    f"🎵 Added playlist to queue: `{loaded_tracks.info.name}`", 
                    self.ctx_avatar_url
                )
                # query should be the playlist URL
                await MusicHistoryHandler.add(self.guild_id, loaded_tracks.info.name, query)
                track_title = loaded_tracks.info.name

        # Error or no search results
        else:
            if not silent:
                await ctx.respond("No tracks found")
            return "Not Found", False
        return track_title, True
        
    def add_to_queue(
        self, 
        track: TrackInQueue | TrackData, 
        player_ctx: PlayerContext, 
        position: int | None = None
    ):
        """Add a track to the queue.

        Parameters
        ----------
        track : Union[TrackInQueue, TrackData]
            The track to add to the queue. Can be either a TrackInQueue or TrackData object.
        player_ctx : PlayerContext
            The player context managing the queue.
        position : Optional[int], default=None
            The position to insert the track in the queue. If None, appends to the end.

        Notes
        -----
        If position is None, the track is added to the end of the queue.
        If position is specified, the track is inserted at that position.
        """

        if not position:
            player_ctx.queue(track)
        else:
            queue = player_ctx.get_queue()
            queue.insert(position, track)

    async def _connect(self) -> Tuple[VoiceConnection | None, bool]:
        voice = self._get_voice()
        has_joined = False

        if not voice:
            if not await self._join():
                await self.ctx.respond("Please join a voice channel first.")
                return None, False
            voice = self.bot.voice.connections.get(self.guild_id)  # type: ignore
            has_joined = True
        else:
            has_joined = True
        assert isinstance(voice, LavalinkVoice)

        return voice, has_joined
    
    
    async def send_queue(self, force_resend: bool = False, disable_components: bool = False, force_lock: bool = False) -> bool:
        """Sends or updates the queue message in the text channel.
        This method manages the queue display in Discord, handling message updates and component states.
        
        Parameters
        ----------
        force_resend : bool, optional
            If True, forces a new message to be sent instead of updating existing one.
            Defaults to False.
        disable_components : bool, optional
            If True, disables interactive components in the message.
            Defaults to False.
        force_lock : bool, optional
            If True, bypasses the response lock check.
            Defaults to False.
        
        Returns
        -------
        bool
            True if the message was successfully sent/updated, False if locked and force_lock is False.
        
        Notes
        -----
        Uses a response lock to prevent concurrent message updates.
        Automatically resets the queue footer after sending.
        """
        if not self.response_lock.is_available() and not force_lock:
            return False
        self.response_lock.lock()
        await self._queue._send_or_update_message(
            force_resend=force_resend, 
            disable_components=disable_components
        )
        self._queue.reset_footer()
        
        return True

    async def shuffle(self) -> None:
        if not self.ctx.guild_id:
            return None

        voice = self._get_voice()

        if not voice:
            # not connected to a voice channel
            return None

        assert isinstance(voice, LavalinkVoice)

        queue_ref = voice.player.get_queue()
        queue = await queue_ref.get_queue()

        random.shuffle(queue)

        queue_ref.replace(queue)
        self._queue.add_footer_info(
            f"🔀 Queue shuffled by {self.ctx.author.username}", 
            self.ctx.author.avatar_url  # type: ignore
        )

    @staticmethod
    def create_leave_embed(author: hikari.Member) -> Embed:
        return (
                Embed(title="🛑 Music stopped")
                .set_footer(text=f"Music stopped by {author.display_name}", icon=author.avatar_url)
        )
    
    async def pre_leave(self, force_resend: bool) -> None:
        """
        Pauses the player, updates the queue message and sends the leave embed
        """
        await self.pause(suppress_info=True)
        self._queue.add_footer_info(f"🛑 stopped by {self.ctx.display_name}", icon=self.ctx.author.avatar_url)  # type: ignore
        await self.send_queue(force_resend=force_resend, disable_components=True, force_lock=True)
        assert(self.ctx.member is not None)
        await self.ctx.execute(embed=self.create_leave_embed(self.ctx.member), delete_after=30)

@dataclass
class MessageData:
    id: int
    proxy: ResponseProxy


@dataclass
class Footer:
    icon: str | None
    infos: List[str]


class QueueMessage:
    """
    Represents the queue message of one player
    """

    def __init__(
        self,
        player: MusicPlayer,
    ):
        self._player: MusicPlayer = player
        self._message: MessageData | None = None
        self._footer = Footer(None, [])

    @property
    def message_id(self) -> int | None:
        if self._message:
            return self._message.id
        return None
        
    @property
    def player(self) -> MusicPlayer:
        return self._player

    @property
    def bot(self) -> Inu:
        return self.player.bot

    def reset_footer(self) -> None:
        self._footer = Footer(None, [])
    
    def add_footer_info(self, info: str, icon: str | None = None) -> None:
        self._footer.infos.append(info)
        if icon is not None:
            self._footer.icon = icon
        
    async def _build_footer(self) -> Dict[str, str]:
        """
        Joins the footer infos into 'text' and adds 'icon' if set. Amount of in queue is 
        """
        d = {}
        queue = await self._player._get_voice().player.get_queue().get_queue()  # type: ignore
        upcoming_songs = max(len(queue) - 4, 0)
        time_amount_milis = sum([x.track.info.length for i, x in enumerate(queue)] or [0])
        time_amount = timedelta(seconds=time_amount_milis // 1000)
        self._footer.infos = [f for f in self._footer.infos if "remaining in queue" not in f]
        self.add_footer_info(f"⤵️ {Human.plural_('song', upcoming_songs, True)} ({time_amount}) remaining in queue ")
        d["text"] = Human.short_text("\n".join(self._footer.infos), 1024, "...")
        if self._footer.icon:
            d["icon"] = self._footer.icon
        return d

    def error_embed(self, info: str | None = None) -> Embed:
        return Embed(
            title="Error",
            description=info or "An error occured",
            # color=self.bot.error_color
        )

    async def build_embed(self) -> hikari.Embed:
        """builds the embed for the music message"""
        AMOUNT_OF_SONGS_IN_QUEUE = 4
        
        voice = self._player._get_voice()

        if not voice:
            return self.error_embed("Not connected to a voice channel")

        queue = await voice.player.get_queue().get_queue()
        voice_player = await self._player._fetch_voice_player()
        is_paused = await self._player.is_paused()
        
        numbers = ['1️⃣','2️⃣','3️⃣','4️⃣','5️⃣','6️⃣','7️⃣','8️⃣','9️⃣','🔟']

        upcomping_song_fields: List[hikari.EmbedField] = []
        
        pre_titles_total_delta = timedelta()
        if title := await self.player.fetch_current_track():
            pre_titles_total_delta = timedelta(milliseconds=title.info.length)
        # create upcoming song fields
        # pre_titles_total_delta += timedelta(milliseconds=36_000_000)  # 10 hours
        log.debug(f"create upcoming song fields")
        for i, items in enumerate(zip(queue, numbers)):
            _track, num = items
            track = _track.track
            if i >= AMOUNT_OF_SONGS_IN_QUEUE:
                # only show 4 upcoming songs
                break

            if is_paused:
                discord_timestamp = "--:--"
            else:
                discord_timestamp = f"<t:{(datetime.now() + pre_titles_total_delta).timestamp():.0f}:t>"

            pre_titles_total_delta += timedelta(milliseconds=track.info.length)
            upcomping_song_fields.append(
                hikari.EmbedField(
                    name=f"{num}{'' if is_paused else '  -'} {discord_timestamp}:",
                    value=f"```ml\n{Human.short_text(track.info.title, 50, '...')}```",
                    inline=False,
                )
            )

        try:
            track = voice_player.track
        except Exception as e:
            log.warning(f"can't get current playing song: {e}")

        if not voice_player.track or not voice_player.track.user_data:
            log.warning("no requester of current track - returning")

        if voice_player.track is None:
            return Embed(title="Queue is empty", description="or broken", color=self.bot.accent_color)
        
        requester = self.bot.cache.get_member(
            self.player.guild_id, 
            voice_player.track.user_data["requester_id"]
        )
        try:
            music_over_in = (
                datetime.now() 
                + timedelta(
                    milliseconds=track.info.length-track.info.position
                )
            ).timestamp()
        except OverflowError:
            music_over_in = (datetime.now() + timedelta(hours=10)).timestamp()
        if is_paused:
            paused_at = datetime.now()
            # min:sec
            music_over_in_str = f"<t:{paused_at.timestamp():.0f}:t>"    
        else:
            music_over_in_str = f'<t:{music_over_in:.0f}:R>'

        # create embed
        music_embed = hikari.Embed(
            color=self.bot.accent_color
        )
        music_embed.add_field(
            name = "Was played:" if is_paused else "Playing:", 
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
            name = "Paused at:" if is_paused else "Over in:", 
            value=music_over_in_str, 
            inline=False
        )
        music_embed._fields.extend(upcomping_song_fields)
        footer = await self._build_footer()
        music_embed.set_footer(footer["text"], icon=footer.get("icon"))
        music_embed.set_thumbnail(track.info.artwork_url or self.bot.me.avatar_url)
        return music_embed
    
    
    async def _send_or_update_message(
        self, 
        force_resend: bool,
        disable_components: bool
    ) -> None:
        """
        Sends the message or updates it if it already exists
        """
        log.debug(f"send or update message")	
        embed = await self.build_embed()
        components = (
            MusicMessageComponents()
            .disable(disable_components)
            .pause(await self._player.is_paused())
            .build()
        )
        ctx = self._player.ctx

        if force_resend:
            edit_history = False
        else:
            assert self.message_id is not None
            edit_history = await is_in_history(self.player.ctx.channel_id, self.message_id)
        
        # edit history message
        failed = False
        if edit_history:
            log.debug(f"edit history: ")
            if ctx.needs_response or self._message:
                try:
                    log.debug(f"ctx respond edit history; {self.message_id = } == {ctx.message_id = }")
                    await ctx.respond(embeds=[embed], components=components, update=self.message_id or True)
                except Exception:
                    log.debug(f"failed to ctx respond edit history")
                    failed = True
            if failed:
                # this should never occur; maybe remove this branch
                failed = False
                try:
                    log.debug(f"edit message with rest")
                    assert self.message_id is not None
                    await self.bot.rest.edit_message(
                        self.player.ctx.channel_id, 
                        self.message_id, embeds=[embed], components=components
                    )
                except:
                    log.debug(f"failed to edit message with rest")
                    failed = True
        
        if edit_history and not failed:
            return

        # delete old message
        if self.message_id:
            # delete old message
            if ctx.needs_response and ctx.message_id == self.message_id:
                # Case: button was pressed on older then last 4 messages
                # -> make deferred response -> delete this response -> resend
                log.debug(f"Make deferred response to delete it {self.message_id = }")
                proxy = await ctx.respond(components=components)
                await proxy.delete()
                self._message = None
            else:
                # Case: normal message
                log.debug(f"delete old message {self.message_id = }")
                task = asyncio.create_task(self._delete_old_message())
        # send new message
        log.debug(f"create music message with ctx respond")
        proxy = await ctx.respond(embeds=[embed], components=components, update=False)
        message_id = (await proxy.message()).id
        self._message = MessageData(id=message_id, proxy=proxy)
    
    async def _delete_old_message(self) -> None:
        if self.message_id:
            try:
                await self.bot.rest.delete_message(self._player.ctx.channel_id, self.message_id)
            except:
                pass
        self._message = None
    
        
        
        
async def is_in_history(channel_id: int, message_id: int, amount: int = 3) -> bool:
    """
    Checks whether a message_id is in channel_id in the last <amount> messages
    """
    async for m in MusicPlayerManager._bot.rest.fetch_messages(channel_id):
        amount -= 1
        if m.id == message_id:
            return True
        if amount < 0:
            break
    return False

def make_track_message(track: TrackData) -> str:
    """
    track needs info field which as author and title
    """
    return  f"➕ Added to queue: {track.info.author} - {track.info.title}"