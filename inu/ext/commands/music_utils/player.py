from typing import *
from datetime import datetime, timedelta

import hikari
from hikari.api import VoiceConnection
from hikari import Embed
import lightbulb
from lavalink_rs.model.search import SearchEngines
from lavalink_rs.model.track import TrackData, PlaylistData, TrackLoadType

from . import LavalinkVoice
from utils import Human, YouTubeHelper
from core import Inu, get_context, InuContext, getLogger

log = getLogger(__name__)

class MusicPlayerManager:
    _instances: Dict[int, "MusicPlayer"] = {}
    _bot: lightbulb.BotApp
    _ctx: InuContext

    @classmethod
    def get_player(cls, guild_id: int) -> "MusicPlayer":
        if player := cls._instances.get(guild_id):
            return player
        else:
            player = MusicPlayer(cls._bot, guild_id)
            cls._instances[guild_id] = player
            return player

    @classmethod
    def set_bot(cls, bot: lightbulb.BotApp) -> None:
        cls._bot = bot


    

class MusicPlayer:
    def __init__(self, bot: lightbulb.BotApp, guild_id: int) -> None:
        self.bot = bot
        self._guild_id = guild_id
        self._ctx: InuContext | None = None

    def _get_voice(self) -> VoiceConnection | None:
        return self.bot.voice.connections.get(self.guild_id)
    
    @property   
    def ctx(self) -> InuContext:
        if self._ctx is None:
            raise RuntimeError("Context is not set")
        return self._ctx
    
    @property
    def guild_id(self) -> int:
        return self._guild_id
    
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

        voice = self.bot.voice.connections.get(self.guild_id)

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

    async def play(self, query: str) -> None:
        voice, has_joined = await self._connect()
        if not has_joined:
            return
        player_ctx = voice.player
        ctx = self.ctx

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

            loaded_tracks.user_data = {"requester_id": int(ctx.author.id)}

            player_ctx.queue(loaded_tracks)

            if loaded_tracks.info.uri:
                await ctx.respond(
                    f"Added to queue: [`{loaded_tracks.info.author} - {loaded_tracks.info.title}`](<{loaded_tracks.info.uri}>)"
                )
            else:
                await ctx.respond(
                    f"Added to queue: `{loaded_tracks.info.author} - {loaded_tracks.info.title}`"
                )

        elif tracks.load_type == TrackLoadType.Search:
            assert isinstance(loaded_tracks, list)

            loaded_tracks[0].user_data = {"requester_id": int(ctx.author.id)}

            player_ctx.queue(loaded_tracks[0])

            if loaded_tracks[0].info.uri:
                await ctx.respond(
                    f"Added to queue: [`{loaded_tracks[0].info.author} - {loaded_tracks[0].info.title}`](<{loaded_tracks[0].info.uri}>)"
                )
            else:
                await ctx.respond(
                    f"Added to queue: `{loaded_tracks[0].info.author} - {loaded_tracks[0].info.title}`"
                )

        elif tracks.load_type == TrackLoadType.Playlist:
            assert isinstance(loaded_tracks, PlaylistData)

            if loaded_tracks.info.selected_track:
                track = loaded_tracks.tracks[loaded_tracks.info.selected_track]

                track.user_data = {"requester_id": int(ctx.author.id)}

                player_ctx.queue(track)

                if track.info.uri:
                    await ctx.respond(
                        f"Added to queue: [`{track.info.author} - {track.info.title}`](<{track.info.uri}>)"
                    )
                else:
                    await ctx.respond(
                        f"Added to queue: `{track.info.author} - {track.info.title}`"
                    )
            else:
                tracks = loaded_tracks.tracks

                for i in tracks:
                    i.user_data = {"requester_id": int(ctx.author.id)}

                queue = player_ctx.get_queue()
                queue.append(tracks)

                await ctx.respond(f"Added playlist to queue: `{loaded_tracks.info.name}`")

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

        assert isinstance(voice, LavalinkVoice)
        return voice, has_joined
    

class QueueMessage:
    """
    Represents the queue message of one player
    """

    def __init__(
        self,
        player: MusicPlayer,
    ):
        self.palyer = player

    @property
    def bot(self) -> Inu:
        return self.player.bot
    
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
                color=hikari.Color.from_hex_code(self.bot.conf.bot.color),
            )
        numbers = [
            '1️⃣','1️⃣','2️⃣','3️⃣','4️⃣','5️⃣','6️⃣','7️⃣','8️⃣','9️⃣','🔟'
        ] # double 1 to make it start at 1 (0 is current playing song)

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
                    pre_titles_total_delta += timedelta(milliseconds=track.info.length)
                except OverflowError:  # Python int too large for C int
                    pre_titles_total_delta += timedelta(milliseconds=36_000_000)  # 10 hours
                continue
            if i >= AMOUNT_OF_SONGS_IN_QUEUE + 1:
                # only show 4 upcoming songs
                break

            if node.is_paused:
                discord_timestamp = "--:--"
            else:
                discord_timestamp = f"<t:{(datetime.now() + pre_titles_total_delta).timestamp():.0f}:t>"

            pre_titles_total_delta += timedelta(milliseconds=track.info.length)
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

        requester = self.bot.cache.get_member(self.player.guild_id, node.queue[0].requester)
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
            or self.bot.me.avatar_url
        )
        return music_embed