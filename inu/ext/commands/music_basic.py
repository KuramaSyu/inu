import os
import logging
import typing as t

import asyncio
import hikari
import lightbulb
from lightbulb import Context
import lavalink_rs
from lavalink_rs.model import events

from lavalink_rs.model.search import SearchEngines
from lavalink_rs.model.track import TrackData, PlaylistData, TrackLoadType

from .music_utils import LavalinkVoice, MusicPlayerManager, MusicPlayer
from core import Inu, getLogger, get_context

log = getLogger(__name__)

plugin = lightbulb.Plugin("Music (base) events")
t.cast(Inu, plugin.bot)
plugin.add_checks(lightbulb.guild_only)


class Events(lavalink_rs.EventHandler):
    async def ready(
        self,
        client: lavalink_rs.LavalinkClient,
        session_id: str,
        event: events.Ready,
    ) -> None:
        del client, session_id, event
        logging.info("HOLY READY")

    async def track_start(
        self,
        client: lavalink_rs.LavalinkClient,
        session_id: str,
        event: events.TrackStart,
    ) -> None:
        del session_id

        log.info(
            f"Started track {event.track.info.author} - {event.track.info.title} in {event.guild_id.inner}"
        )

        player = MusicPlayerManager.get_player(event.guild_id.inner)
        log.debug(f"Send play message from track_start event")
        await player.send_queue()


@plugin.listener(hikari.ShardReadyEvent, bind=True)
async def start_lavalink(plug: lightbulb.Plugin, event: hikari.ShardReadyEvent) -> None:
    """Event that triggers when the hikari gateway is ready."""
    MusicPlayerManager.set_bot(plug.bot)
    bot: Inu = plug.bot
    node = lavalink_rs.NodeBuilder(
        f"{bot.conf.lavalink.IP}:2333",
        False,  # is the server SSL?
        bot.conf.lavalink.PASSWORD,
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

async def _join(ctx: Context) -> t.Optional[hikari.Snowflake]:
    if not ctx.guild_id:
        return None

    channel_id = None
    bot: Inu = ctx.bot  # type: ignore

    for i in ctx.options.items():
        if i[0] == "channel" and i[1]:
            channel_id = i[1].id
            break

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


@plugin.command()
@lightbulb.option(
    "channel",
    "The channel you want me to join",
    hikari.GuildVoiceChannel,
    required=False,
    channel_types=[hikari.ChannelType.GUILD_VOICE],
)
@lightbulb.command(
    "join", "Enters the voice channel you are connected to, or the one specified"
)
@lightbulb.implements(lightbulb.PrefixCommand, lightbulb.SlashCommand)
async def join(ctx: Context) -> None:
    """Joins the voice channel you are in"""
    channel_id = await _join(ctx)

    if channel_id:
        await ctx.respond(f"Joined <#{channel_id}>")
    else:
        await ctx.respond(
            "Please, join a voice channel, or specify a specific channel to join in"
        )


@plugin.command()
@lightbulb.command("leave", "Leaves the voice channel")
@lightbulb.implements(lightbulb.PrefixCommand, lightbulb.SlashCommand)
async def leave(_ctx: Context) -> None:
    """Leaves the voice channel"""
    ctx = get_context(_ctx.event)
    await ctx.defer()
    player = MusicPlayerManager.get_player(ctx)
    player._queue.add_footer_info(f"🛑 Stopped by {ctx.author.username}", str(ctx.author.avatar_url))
    await player.send_queue(True)
    await player.leave()


@plugin.command()
@lightbulb.option(
    "query",
    "The spotify search query, or any URL",
    modifier=lightbulb.OptionModifier.CONSUME_REST,
    required=False,
)
@lightbulb.command(
    "play",
    "Searches the query on Soundcloud",
)
@lightbulb.implements(
    lightbulb.PrefixCommand,
    lightbulb.SlashCommand,
)
async def play(_ctx: Context) -> None:
    if not _ctx.guild_id:
        return None
    ctx = get_context(_ctx.event)
    await ctx.defer()
    player = MusicPlayerManager.get_player(ctx)
    was_playing = not (await player.is_paused())
    log.debug(f"{was_playing = }")
    await player.play(_ctx.options.query)
    await asyncio.sleep(0.15)  # without this, it does not start playing
    await player.send_queue(True)

@plugin.command()
@lightbulb.command("skip", "Skip the currently playing song")
@lightbulb.implements(lightbulb.PrefixCommand, lightbulb.SlashCommand)
async def skip(_ctx: Context) -> None:
    """Skip the currently playing song"""
    ctx = get_context(_ctx.event)
    await ctx.defer()
    player = MusicPlayerManager.get_player(ctx)
    await player.skip()
    await player.send_queue(True)


# @plugin.command()
# @lightbulb.command("stop", "Stop the currently playing song")
# @lightbulb.implements(lightbulb.PrefixCommand, lightbulb.SlashCommand)
# async def stop(ctx: Context) -> None:
#     """Stop the currently playing song"""
#     player = MusicPlayerManager.get_player(get_context(ctx.event))
#     await player.stop()
#     await player.send_queue(True)


def load(bot: Inu) -> None:
    bot.add_plugin(plugin)
