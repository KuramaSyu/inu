import os
import logging
import traceback
from typing import *

import asyncio
import hikari
from hikari import VoiceStateUpdateEvent
import lightbulb
from lightbulb import AutocompleteContext, Context, SlashCommand, invoke, Choice
from fuzzywuzzy import fuzz
import lavalink_rs
from lavalink_rs.model import events
from lavalink_rs.model.search import SearchEngines
from lavalink_rs.model.track import TrackData, PlaylistData, TrackLoadType

from .music_utils import (
    LavalinkVoice, MusicPlayerManager, HISTORY_PREFIX, 
    MEDIA_TAG_PREFIX, MARKDOWN_URL_REGEX, DISCONNECT_AFTER
)
from utils import TagManager, TagType, MusicHistoryHandler
from core import Inu, getLogger, get_context, InuContext

log = getLogger(__name__)

loader = lightbulb.Loader()
bot = Inu.instance


@loader.listener(hikari.VoiceStateUpdateEvent)
async def on_voice_state_update(event: VoiceStateUpdateEvent):
    """Listener, to let the bot leave or pause"""
    try:
        ## USER RELATED VOICE STATES ##
        if (
            (
                event.state.user_id != bot.me.id 
                and not (
                    event.old_state
                    and event.old_state.channel_id == event.state.channel_id
                )
            ) # someone left/joined/changed the channel
            or (
                event.state.user_id == bot.me.id 
                and event.old_state
                and event.state.channel_id
            ) # bot changed a channel
            or (
                event.state.user_id != bot.me.id
                and event.old_state
                and event.state.channel_id != event.old_state.channel_id
            ) # user changed room
        ):
            # someone left channel or bot joined/changed channel
            await asyncio.sleep(3)
            player = MusicPlayerManager.player_factory(event.state.guild_id)
            is_alone = await player.check_if_bot_is_alone()
            if is_alone:
                log.debug(f"Bot is alone in {event.state.guild_id}")
                await player.on_bot_lonely()
            else:
                log.debug(f"Bot is not alone in {event.state.guild_id}")
                await player.on_human_join()

        ## BOT RELATED VOICE STATES ##
        if not event.state.user_id == bot.me.id:
            # check if the user is the bot
            return
        if event.old_state is None and event.state.channel_id:
            # bot connected (No channel -> channel)
            pass
        elif event.old_state and event.state.channel_id:
            # bot changed room (channel -> channel)
            # check if room is empty
            user_states = [
                state.user_id for state in 
                bot.cache.get_voice_states_view_for_channel(
                    event.guild_id, event.state.channel_id
                ).values() 
                if state.user_id != bot.me.id
            ]
            player = MusicPlayerManager.player_factory(event.state.guild_id)
            if len(user_states) > 0:
                # resume player if new room is not empty
                log.debug(f"Bot changed room in {event.guild_id} to {event.state.channel_id}")
                await player.pause(False)
                player.queue.add_footer_info(
                    f"▶ Music was resumed by {bot.me.username}",
                    str(bot.me.avatar_url)
                )
                log.debug("Resend queue from on_voice_state_update, resume player if new room not empty")
                await player.send_queue()
            elif len(user_states) == 0 and not player.is_paused():
                # pause player if new room is empty
                await player.pause()
                await asyncio.sleep(0.1)
                player.queue.add_footer_info(
                    f"⏸ Music was paused by {bot.me.username}",
                    str(bot.me.avatar_url),
                )
                log.debug("Resend queue because bot is lonely")
                await player.send_queue()
                await player.on_bot_lonely()
        elif event.state.channel_id is None and not event.old_state is None:
            # bot disconnected
            player = MusicPlayerManager.player_factory(event.state.guild_id)
            
            # add current song again, because the current will be removed
            current_track = await player.fetch_current_track() # TODO: current_track always None because of disconnect
            if current_track: 
                player.add_to_queue(current_track, player._get_player_ctx(), position=0)
    except Exception:
        log.error(traceback.format_exc())


async def query_auto_complete(ctx: AutocompleteContext) -> None:
    """
    Autocomplete function for search queries.

    Parameters
    ----------
    ctx : AutocompleteContext
        The context of the autocomplete interaction.

    Returns
    -------
    None
    """
    try:
        assert ctx.interaction.guild_id
        query = str(ctx.focused.value) or ""
        records = [
            {"title": record["title"], "prefix": HISTORY_PREFIX} 
            for record in await MusicHistoryHandler.cached_get(ctx.interaction.guild_id)
        ]
        if not query:
            records = records[:23]
        else:
            if len(str(query)) > 1:
                tag_records = await TagManager.cached_find_similar(query, ctx.interaction.guild_id, tag_type=TagType.MEDIA)
                # add tags
                records.extend([
                    {"title": d["tag_key"], "prefix": MEDIA_TAG_PREFIX} for d in tag_records
                ])
            new_records = []

            for r in records:
                r = dict(r)
                if query:
                    r["ratio"] = fuzz.partial_token_sort_ratio(query, r["title"])
                if not r in new_records:
                    new_records.append(r)
            records = new_records
            
            # prefer top 2 media tags
            tag_records = [ 
                r for r in records 
                if r["prefix"] == MEDIA_TAG_PREFIX
                and r["ratio"] > 65
            ]
            tag_records.sort(key=lambda r: r["ratio"], reverse=True)

            for r in tag_records[:2]:
                r["ratio"] += 40

            records.sort(key=lambda r: r["ratio"], reverse=True)

        # add prefixes
        converted_records = [r.get("prefix", HISTORY_PREFIX) + r["title"] for r in records]
        if len(str(query)) > 3:
            converted_records.insert(0, str(query))
        await ctx.respond([r[:100] for r in converted_records[:23]]) 
    except Exception as e:
        log.error(f"Error in query_auto_complete: {traceback.format_exc()}")
        raise e



class Events(lavalink_rs.EventHandler):
    """
    Handler for incoming Lavalink Events
    """
    async def ready(
        self,
        client: lavalink_rs.LavalinkClient,
        session_id: str,
        event: events.Ready,
    ) -> None:
        del client, session_id, event
        log.info("Lavalink_rs is ready", prefix="init")

    async def track_start(
        self,
        client: lavalink_rs.LavalinkClient,
        session_id: str,
        event: events.TrackStart,
    ) -> None:
        del session_id
        log = getLogger(__name__, "Lavalink Event Handler")
        log.info(f"Started track {event.track.info.author} - {event.track.info.title} in {event.guild_id.inner}")

        player = MusicPlayerManager.player_factory(event.guild_id.inner)
        track = await player.fetch_current_track()
        if track:
            await MusicHistoryHandler.add(event.guild_id.inner, track.info.title, track.info.uri)  # type: ignore
        if not player.response_lock.is_available():
            log.debug(f"message locked - dont send")
            return
        log.debug(f"message not locked - send")
        try:
            await player.send_queue()
        except Exception as e:
            log.error(f"Error sending queue: {traceback.format_exc()}")



@loader.listener(hikari.ShardReadyEvent)
async def start_lavalink(event: hikari.ShardReadyEvent) -> None:
    """Event that triggers when the hikari gateway is ready."""
    MusicPlayerManager.set_bot(bot)
    try:
        ip = bot.conf.lavalink.IP  # type: ignore
        password = bot.conf.lavalink.PASSWORD  # type: ignore
    except AttributeError:
        log.error("Lavalink IP or PASSWORD not set in config.yaml", prefix="init")
        return

    node = lavalink_rs.NodeBuilder(
        f"{ip}:2333",
        False,  # is the server SSL?
        password,
        event.my_user.id,
    )

    lavalink_client = await lavalink_rs.LavalinkClient.new(
        Events(),
        [node],
        lavalink_rs.NodeDistributionStrategy.sharded(),
        # lavalink_rs.NodeDistributionStrategy.custom(custom_node),
    )

    bot.lavalink = lavalink_client
    log.info("Lavalink client started", prefix="init")



async def _join(ctx: InuContext, channel: Optional[hikari.PartialChannel]) -> Optional[hikari.Snowflake]:
    """Joins a voice channel. 
    
    Args:
    -----
    ctx: InuContext
        The context of the command.
    channel: Optional[hikari.PartialChannel]
        The channel to join. If None, the channel of the author is used.
        
    Returns:
    --------
    Optional[hikari.Snowflake]
        The channel id of the channel joined.
        
    Notes:
    ------
    - If the bot is already connected to a voice channel, it will disconnect and reconnect to the new channel.
    - If channel is None, the bot's channel is used.
    """
    if not ctx.guild_id:
        return None

    channel_id = None

    if channel:
        channel_id = channel.id

    if not channel_id:
        voice_state = ctx.bot.cache.get_voice_state(ctx.guild_id, ctx.author.id)

        if not voice_state or not voice_state.channel_id:
            return None

        channel_id = voice_state.channel_id

    voice = ctx.bot.voice.connections.get(ctx.guild_id)

    if not voice:
        await LavalinkVoice.connect(
            ctx.guild_id,
            channel_id,
            bot,
            bot.lavalink,  # type: ignore
            (ctx.channel_id, ctx.bot.rest),
        )
    else:
        assert isinstance(voice, LavalinkVoice)

        await LavalinkVoice.connect(
            ctx.guild_id,
            channel_id,
            bot,
            bot.lavalink,  # type: ignore
            (ctx.channel_id, bot.rest),
            # old_voice=voice,
        )

    return channel_id

YOUTUBE_SEARCH = Choice("YouTube: not reliable, all songs", "youtube")
SOUNDCLOUD_SEARCH = Choice("Soundcloud: reliable, less songs", "soundcloud")
SEARCH_ENGINE_CHOICES = [YOUTUBE_SEARCH, SOUNDCLOUD_SEARCH]

@loader.command
class JoinCommand(
    lightbulb.SlashCommand,
    name="join",
    description="Enters the voice channel you are connected to, or the one specified",
    dm_enabled=False,
    default_member_permissions=None,
):
    channel = lightbulb.channel(
        "channel",
        "The channel you want me to join",
        channel_types=[hikari.ChannelType.GUILD_VOICE],
        default=None,
    )

    @lightbulb.invoke
    async def callback(self, _: lightbulb.Context, ctx: InuContext):
        channel_id = await _join(ctx, self.channel)
        if channel_id:
            await ctx.respond(f"Joined <#{channel_id}>")
        else:
            await ctx.respond(
                "Please, join a voice channel, or specify a specific channel to join in"
            )


@loader.command
class LeaveCommand(
    lightbulb.SlashCommand,
    name="leave",
    description="Leaves the voice channel",
    dm_enabled=False,
    default_member_permissions=None,
):
    @lightbulb.invoke
    async def callback(self, _: lightbulb.Context, ctx: InuContext):
        await ctx.defer()
        player = MusicPlayerManager.player_factory(ctx)
        player._queue.add_footer_info(f"🛑 Stopped by {ctx.author.username}", str(ctx.author.avatar_url))
        await player.send_queue(True)
        await player.leave()

@loader.command
class PlayCommand(
    SlashCommand,
    name="play",
    description="Searches the query on Soundcloud",
    dm_enabled=False,
):
    query = lightbulb.string(
        "query",
        "The spotify search query, or any URL",
        autocomplete=query_auto_complete,
        default=None,
    )
    search_engine = lightbulb.string(
        "search-engine", "the website to search with",
        choices=SEARCH_ENGINE_CHOICES,
        default=SOUNDCLOUD_SEARCH
    )

    @lightbulb.invoke
    async def callback(self, _: lightbulb.Context, ctx: InuContext):
        if not ctx.guild_id:
            return None
        if not self.query:
            self.query, new_ctx = await ctx.ask_with_modal(
                "Search a title", "What do you search for?", 
                placeholder_s="Title / URL / Playlist\nTitle2 / URL2 / Playlist2\n..."
            )
            ctx = new_ctx or ctx
        assert self.query
        await ctx.defer()
        player = MusicPlayerManager.player_factory(ctx)
        was_playing = not (await player.is_paused())
        log.debug(f"{was_playing = }")
        try:
            successfull_play = await player.play(self.query, search_engine=str(self.search_engine))
            if not successfull_play:
                return
        except TimeoutError:
            # triggered, when no song was selected
            return
        
        await asyncio.sleep(0.15)  # without this, it does not start playing
        await player.send_queue(True)


play_at_group = lightbulb.Group("play-at-position", "Play a song at a specific position", dm_enabled=False)

@play_at_group.register
class PlayAtPositionCommand(
    SlashCommand,
    name="now",
    description="Searches the query on Soundcloud",
    dm_enabled=False,
):
    query = lightbulb.string(
        "query",
        "The spotify search query, or any URL",
        autocomplete=query_auto_complete,
        default=None,
    )

    @lightbulb.invoke
    async def callback(self, _: lightbulb.Context, ctx: InuContext):
        if not ctx.guild_id:
            return None
        if not self.query:
            self.query, new_ctx = await ctx.ask_with_modal(
                "Search a title", "What do you search for?", 
                placeholder_s="Title / URL / Playlist\nTitle2 / URL2 / Playlist2\n..."
            )
            ctx = new_ctx or ctx
        assert self.query
        await ctx.defer()
        player = MusicPlayerManager.player_factory(ctx)
        was_playing = not (await player.is_paused())
        log.debug(f"{was_playing = }")
        try:
            successfull_play = await player.play(self.query)
            if not successfull_play:
                return
        except TimeoutError:
            # triggered, when no song was selected
            return
        
        await asyncio.sleep(0.15)  # without this, it does not start playing
        await player.send_queue(True)
        
        
@loader.command
class SkipCommand(
    lightbulb.SlashCommand,
    name="skip",
    description="Skip the currently playing song",
    dm_enabled=False,
    default_member_permissions=None,
):
    @lightbulb.invoke
    async def callback(self, _: lightbulb.Context, ctx: InuContext):
        await ctx.defer()
        player = MusicPlayerManager.player_factory(ctx)
        await player.skip()
        await player.send_queue(True)


play_at_group = lightbulb.Group("play-at-position", "Play a song at a specific position", dm_enabled=False)


@play_at_group.register
class PlayAtPositionNowCommand(
    SlashCommand,
    name="now",
    description="Play a song next",
):
    query = lightbulb.string(
        "query",
        "The spotify search query, or any URL",
        autocomplete=query_auto_complete,
        default=None,
    )

    @invoke
    async def callback(self, _: lightbulb.Context, ctx: InuContext) -> None:
        await play(self.query, ctx, 0)



@play_at_group.register
class PlayAtPositionSecondCommand(
    SlashCommand,
    name="second",
    description="Play a song next-next",
):
    query = lightbulb.string(
        "query",
        "The spotify search query, or any URL",
        autocomplete=query_auto_complete,
        default=None,
    )

    @invoke
    async def callback(self, _: lightbulb.Context, ctx: InuContext) -> None:
        await play(self.query, ctx, 1)


@play_at_group.register
class PlayAtPositionAnyCommand(
    SlashCommand,
    name="position",
    description="Play a song next-next",
):
    query = lightbulb.string(
        "query",
        "The spotify search query, or any URL",
        autocomplete=query_auto_complete,
        default=None,
    )
    position = lightbulb.integer(
        "position",
        "The position in the queue to insert the song",
        default=0,
    )
    

    @invoke
    async def callback(self, _: lightbulb.Context, ctx: InuContext) -> None:
        await play(self.query, ctx, self.position)



async def play(
    query: Optional[str], 
    ctx: InuContext, 
    position: Optional[int],
    search_engine: str = "soundcloud"
) -> None:
    """
    Play a song in a voice channel.

    Parameters
    ----------
    query : str
        The search query or URL to play.
    ctx : InuContext
        The command context.
    position : Optional[int]
        The position in the queue to insert the song. If None, appends to end.
    """
    if not ctx.guild_id:
        return None
    if not query:
        query, new_ctx = await ctx.ask_with_modal(
            "Search a title", "What do you search for?", 
            placeholder_s="Title / URL / Playlist\nTitle2 / URL2 / Playlist2\n..."
        )
        ctx = new_ctx or ctx
    assert query
    await ctx.defer()
    player = MusicPlayerManager.player_factory(ctx)
    was_playing = not (await player.is_paused())
    log.debug(f"{was_playing = }")
    try:
        successfull_play = await player.play(query, search_engine=search_engine)
        if not successfull_play:
            return
    except TimeoutError:
        # triggered, when no song was selected
        return
    
    await asyncio.sleep(0.15)  # without this, it does not start playing
    await player.send_queue(True)