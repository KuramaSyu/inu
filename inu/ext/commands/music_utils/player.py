from typing import *
from datetime import datetime, timedelta
from dataclasses import dataclass
import asyncio

import hikari
from hikari.api import VoiceConnection
from hikari import Embed
import lightbulb
from lavalink_rs.model.search import SearchEngines
from lavalink_rs.model.track import TrackData, PlaylistData, TrackLoadType
from lavalink_rs.model.player import Player

from . import LavalinkVoice, YouTubeHelper, TrackUserData, ResponseLock
from utils import Human
from core import Inu, get_context, InuContext, getLogger

log = getLogger(__name__)

class MusicPlayerManager:
    _instances: Dict[int, "MusicPlayer"] = {}
    _bot: lightbulb.BotApp
    _ctx: InuContext

    @classmethod
    def get_player(cls, ctx_or_guild_id: int | InuContext) -> "MusicPlayer":
        """
        Args:
        -----
        `ctx_or_guild_id` (`int` | `InuContext`):
            The guild id or the context of the command.
            If it's the context, then it will be automatically set as player ctx.
        """
        guild_id = None
        ctx = None

        if isinstance(ctx_or_guild_id, InuContext):
            guild_id = ctx_or_guild_id.guild_id
            ctx = ctx_or_guild_id
        else:
            guild_id = ctx_or_guild_id

        player = None
        player = cls._instances.get(guild_id)

        if not player:
            player = MusicPlayer(cls._bot, guild_id)
            cls._instances[guild_id] = player
        
        if ctx:
            player.set_context(ctx)

        return player

    @classmethod
    def set_bot(cls, bot: lightbulb.BotApp) -> None:
        cls._bot = bot


    

class MusicPlayer:
    def __init__(self, bot: lightbulb.BotApp, guild_id: int) -> None:
        self.bot = bot
        self._guild_id = guild_id
        self._ctx: InuContext | None = None
        self._queue: QueueMessage = QueueMessage(self)
        self.response_lock = ResponseLock(timedelta(seconds=3))

    def _get_voice(self) -> VoiceConnection | None:
        """
        Returns:
        --------
        `VoiceConnection | None`:
            The voice connection of the bot in the guild
            (`self.bot.voice.connections.get(self.guild_id)`)
        """
        return self.bot.voice.connections.get(self.guild_id)
    
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
    def ctx(self) -> InuContext:
        if self._ctx is None:
            raise RuntimeError("Context is not set")
        return self._ctx
    
    @property
    def guild_id(self) -> int:
        return self._guild_id
    
    async def is_paused(self) -> bool:
        """
        https://docs.rs/lavalink-rs/latest/lavalink_rs/player_context/struct.PlayerContext.html

        Returns:
            bool: whether the player is paused or not
        """
        voice = self._get_voice()
        if not voice:
            return True
        return (await voice.player.get_player()).paused
    
    def set_context(self, ctx: InuContext) -> None:
        self._ctx = ctx

    async def _join(self) -> Optional[int]:
        if not self.guild_id:
            return None

        channel_id = None

        for i in self.ctx.options.items():
            if i[0] == "channel" and i[1]:
                channel_id = i[1].id
                break

        if not channel_id:
            voice_state = self.bot.cache.get_voice_state(self.guild_id, self.ctx.author.id)

            if not voice_state or not voice_state.channel_id:
                return None

            channel_id = voice_state.channel_id

        voice = self._get_voice()

        if not voice:
            await LavalinkVoice.connect(
                self.guild_id,
                channel_id,
                self.bot,
                self.bot.lavalink,
                (self.ctx.channel_id, self.bot.rest),
            )
        else:
            assert isinstance(voice, LavalinkVoice)

            await LavalinkVoice.connect(
                self.guild_id,
                channel_id,
                self.bot,
                self.bot.lavalink,
                (self.ctx.channel_id, self.ctx.bot.rest),
                old_voice=voice,
            )

        return channel_id
    
    async def pause(self) -> None:
        """Pauses a player and adds a footer info"""
        self._queue.add_footer_info(
            f"⏸️ Music paused by {self.ctx.author.username}", 
            self.ctx.author.avatar_url
        )
        await self._set_pause(True)
        
    async def resume(self) -> None:
        """Resumes the player and adds a footer info"""
        self._queue.add_footer_info(
            f"▶️ Music resumed by {self.ctx.author.username}", 
            self.ctx.author.avatar_url
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
                self.ctx.author.avatar_url
            )
        else:
            self._queue.add_footer_info(
                f"🎵 Skipped {player.track.info.author} - {player.track.info.title}", 
                self.ctx.author.avatar_url
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
                
        
    async def leave(self) -> None:
        ctx = self.ctx
        if not ctx.guild_id:
            return None

        voice = self._get_voice()
        if not voice:
            await ctx.respond("I can't leave without beeing in a voice channel in the first place, y'know?")
            return None

        await voice.disconnect()

    def _make_user_data(self, ctx: Optional[InuContext] = None) -> TrackUserData:
        """
        User data which will be added to lavalinks track (`track.track.user_data`)
        """
        if not ctx:
            ctx = self.ctx
        return {"requester_id": int(ctx.author.id)}
    
    async def fetch_current_track(self) -> Any | None:
        voice_player = await self._fetch_voice_player()
        return voice_player.track
    
    async def play(self, query: str) -> None:
        log.debug(f"play: {query = }")
        voice, has_joined = await self._connect()
        log.debug(f"{voice = }; {has_joined = }")
        if not has_joined:
            return
        player_ctx = voice.player
        ctx = self.ctx
        user_data: TrackUserData = self._make_user_data(ctx)

        if not query:
            player = await player_ctx.get_player()
            queue = player_ctx.get_queue()

            if not player.track and await queue.get_count() > 0:
                player_ctx.skip()
            else:
                if player.track:
                    await ctx.respond("A song is already playing")
                else:
                    await ctx.respond("The queue is empty")

            return None

        if not query.startswith("http"):
            # add scsearch: to the query
            query = SearchEngines.soundcloud(query)
        try:
            tracks = await ctx.bot.lavalink.load_tracks(ctx.guild_id, query)
            loaded_tracks = tracks.data

        except Exception as e:
            log.error(e)
            await ctx.respond("Error")
            return None

        if tracks.load_type == TrackLoadType.Track:
            assert isinstance(loaded_tracks, TrackData)
            loaded_tracks.user_data = user_data
            player_ctx.queue(loaded_tracks)
            self._queue.add_footer_info(make_track_message(loaded_tracks), ctx.author.avatar_url)

        elif tracks.load_type == TrackLoadType.Search:
            assert isinstance(loaded_tracks, list)
            loaded_tracks[0].user_data = user_data
            player_ctx.queue(loaded_tracks[0])
            self._queue.add_footer_info(make_track_message(loaded_tracks[0]), ctx.author.avatar_url)

        elif tracks.load_type == TrackLoadType.Playlist:
            assert isinstance(loaded_tracks, PlaylistData)

            if loaded_tracks.info.selected_track:
                track = loaded_tracks.tracks[loaded_tracks.info.selected_track]
                track.user_data = user_data
                player_ctx.queue(track)
                self._queue.add_footer_info(make_track_message(track), ctx.author.avatar_url)
            else:
                tracks = loaded_tracks.tracks
                
                for i in tracks:
                    i.user_data = user_data

                queue = player_ctx.get_queue()
                queue.append(tracks)
                self._queue.add_footer_info(
                    f"🎵 Added playlist to queue: `{loaded_tracks.info.name}`", 
                    ctx.author.avatar_url
                )


        # Error or no search results
        else:
            await ctx.respond("No songs found")
            return None

        if has_joined:
            return None

        player_data = await player_ctx.get_player()
        queue = player_ctx.get_queue()

        if player_data:
            if not player_data.track and await queue.get_track(0):
                player_ctx.skip()


    async def _connect(self) -> Tuple[VoiceConnection, bool]:
        voice = self._get_voice()
        has_joined = False

        if not voice:
            if not await self._join():
                await self.ctx.respond("Please join a voice channel first.")
                return None, False
            voice = self.bot.voice.connections.get(self.guild_id)
            has_joined = True
        else:
            has_joined = True
        assert isinstance(voice, LavalinkVoice)
        return voice, has_joined
    
    def _make_queue_message(self) -> None:
        if not self._queue:
            self._queue = QueueMessage(self)
    
    async def send_queue(self, force_resend: bool = False) -> bool:
        """
        Returns:
        --------
        `bool`:
            Whether the message was sent
        """
        is_locked = self.response_lock.lock()
        if not is_locked:
            return False
        self._make_queue_message()
        await self._queue._send_or_update_message(force_resend)
        return True


@dataclass
class MessageData:
    id: int
    proxy: lightbulb.ResponseProxy


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
        if icon:
            self._footer.icon_url = icon
        
    async def _build_footer(self) -> Dict[str, str]:
        """
        Joins the footer infos into 'text' and adds 'icon' if set. Amount of in queue is 
        """
        d = {}
        queue = await self._player._get_voice().player.get_queue().get_queue()
        upcoming_songs = max(len(queue) - 4, 0)
        time_amount_milis = sum([x.track.info.length for i, x in enumerate(queue) if i > 4] or [0])
        time_amount = timedelta(milliseconds=time_amount_milis)
        self.add_footer_info(f"🎵 {Human.plural_('other song', upcoming_songs, True)} remaining [{time_amount}]")
        d["text"] = Human.short_text("\n".join(self._footer.infos), 1024, "...")
        if self._footer.icon:
            d["icon"] = self._footer.icon
        return d

    async def build_embed(self) -> hikari.Embed:
        """builds the embed for the music message"""
        AMOUNT_OF_SONGS_IN_QUEUE = 4
        
        voice = self._player._get_voice()
        queue = await voice.player.get_queue().get_queue()
        voice_player = await self._player._fetch_voice_player()
        is_paused = await self._player.is_paused()
        
        numbers = ['1️⃣','2️⃣','3️⃣','4️⃣','5️⃣','6️⃣','7️⃣','8️⃣','9️⃣','🔟']

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
        pre_titles_total_delta = timedelta()

        # create upcoming song fields
        # pre_titles_total_delta += timedelta(milliseconds=36_000_000)  # 10 hours
        log.debug(f"create upcoming song fields")
        for i, items in enumerate(zip(queue, numbers)):
            _track, num = items
            track = _track.track
            if i >= AMOUNT_OF_SONGS_IN_QUEUE + 1:
                # only show 4 upcoming songs
                break

            if is_paused:
                discord_timestamp = "--:--"
            else:
                discord_timestamp = f"<t:{(datetime.now() + pre_titles_total_delta).timestamp():.0f}:t>"

            pre_titles_total_delta += timedelta(milliseconds=track.info.length)
            upcomping_song_fields.append(
                hikari.EmbedField(
                    name=f"{num}{'' if is_paused else ' -'} {discord_timestamp}",
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
            track = voice_player.track
        except Exception as e:
            # TODO: currently always out of range
            return log.warning(f"can't get current playing song: {e}")

        if not voice_player.track.user_data:
            log.warning("no requester of current track - returning")

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
            # colour=hikari.Color.from_rgb(71, 89, 211)
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
        music_embed.set_footer(**(await self._build_footer()))
        music_embed.set_thumbnail(
            YouTubeHelper.thumbnail_from_url(track.info.uri) 
            or self.bot.me.avatar_url
        )
        return music_embed
    
    async def _send_or_update_message(self, force_resend: bool) -> None:
        """
        Sends the message or updates it if it already exists
        """
        log.debug(f"send or update message")	
        embed = await self.build_embed()

        if force_resend:
            edit_history = False
        else:
            edit_history = await is_in_history(self.player.ctx.channel_id, self.message_id)
        
        # edit history message
        if edit_history:
            failed = False
            if self._message:
                try:
                    log.debug(f"edit message with proxy")
                    await self._message.proxy.edit(embed=embed)
                except Exception as e:
                    failed = True
            if not self._message or failed:
                failed = False
                try:
                    log.debug(f"edit message with rest")
                    await self.bot.rest.edit_message(
                        self.player.ctx.channel_id, 
                        self._message_id, embed=embed
                    )
                except:
                    failed = True
        
        # send new message
        if not edit_history or failed:
            if self.message_id:
                # delete old message
                log.debug(f"delete message: {self.message_id}")
                task = asyncio.create_task(
                    self.bot.rest.delete_message(self._player.ctx.channel_id, self.message_id)
                )
            log.debug(f"create music message with rest")
            message_proxy = await self._player.ctx.respond(embeds=[embed])
            message_id = (await message_proxy.message()).id
            self._message = MessageData(id=message_id, proxy=message_proxy)
    
        self.reset_footer()
        
        

async def is_in_history(channel_id: int, message_id: int, amount: int = 4) -> bool:
    """
    Checks whether a message_id is in channel_id in the last <amount> messages
    """
    async for m in MusicPlayerManager._bot.rest.fetch_messages(channel_id):
        if m.id == message_id:
            return True
    return False

def make_track_message(track) -> str:
    """
    track needs info field which as author and title
    """
    return  f"🎵 Added to queue: {track.info.author} - {track.info.title}"