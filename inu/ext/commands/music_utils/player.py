from typing import *

import hikari
from hikari.api import VoiceConnection
import lightbulb
from lavalink_rs.model.search import SearchEngines
from lavalink_rs.model.track import TrackData, PlaylistData, TrackLoadType

from . import LavalinkVoice
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