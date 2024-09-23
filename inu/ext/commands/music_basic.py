import os
import logging
import typing as t

import hikari
import lightbulb
from lightbulb import Context
import lavalink_rs
from lavalink_rs.model import events

from lavalink_rs.model.search import SearchEngines
from lavalink_rs.model.track import TrackData, PlaylistData, TrackLoadType

from .music_utils import LavalinkVoice, MusicPlayerManager, MusicPlayer
from core import Inu, getLogger

log = getLogger(__name__)

plugin =lightbulb.Plugin("Music (base) events")
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

        logging.info(
            f"Started track {event.track.info.author} - {event.track.info.title} in {event.guild_id.inner}"
        )

        player_ctx = client.get_player_context(event.guild_id.inner)

        assert player_ctx
        assert player_ctx.data

        data = t.cast(t.Tuple[hikari.Snowflake, hikari.api.RESTClient], player_ctx.data)

        assert event.track.user_data and isinstance(event.track.user_data, dict)

        if event.track.info.uri:
            await data[1].create_message(
                data[0],
                f"Started playing [`{event.track.info.author} - {event.track.info.title}`](<{event.track.info.uri}>) | Requested by <@!{event.track.user_data['requester_id']}>",
            )
        else:
            await data[1].create_message(
                data[0],
                f"Started playing `{event.track.info.author} - {event.track.info.title}` | Requested by <@!{event.track.user_data['requester_id']}>",
            )


# async def custom_node(
#    client: lavalink_rs.LavalinkClient, guild_id: lavalink_rs.GuildId | int
# ) -> lavalink_rs.Node:
#    node = client.get_node_by_index(0)
#    assert node
#    return node


@plugin.listener(hikari.ShardReadyEvent, bind=True)
async def start_lavalink(plug: lightbulb.Plugin, event: hikari.ShardReadyEvent) -> None:
    """Event that triggers when the hikari gateway is ready."""
    MusicPlayerManager.set_bot(plug.bot)

    node = lavalink_rs.NodeBuilder(
        f"{plug.bot.conf.lavalink.IP}:2333",
        False,  # is the server SSL?
        plug.bot.conf.lavalink.PASSWORD,
        event.my_user.id,
    )

    lavalink_client = await lavalink_rs.LavalinkClient.new(
        Events(),
        [node],
        lavalink_rs.NodeDistributionStrategy.sharded(),
        # lavalink_rs.NodeDistributionStrategy.custom(custom_node),
    )

    plug.bot.lavalink = lavalink_client
    log.info("Lavalink client started", prefix="init")

async def _join(ctx: Context) -> t.Optional[hikari.Snowflake]:
    if not ctx.guild_id:
        return None

    channel_id = None

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
            ctx.bot,
            ctx.bot.lavalink,
            (ctx.channel_id, ctx.bot.rest),
        )
    else:
        assert isinstance(voice, LavalinkVoice)

        await LavalinkVoice.connect(
            ctx.guild_id,
            channel_id,
            ctx.bot,
            ctx.bot.lavalink,
            (ctx.channel_id, ctx.bot.rest),
            old_voice=voice,
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
async def leave(ctx: Context) -> None:
    """Leaves the voice channel"""
    if not ctx.guild_id:
        return None

    voice = ctx.bot.voice.connections.get(ctx.guild_id)

    if not voice:
        await ctx.respond("Not in a voice channel")
        return None

    await voice.disconnect()

    await ctx.respond("Left the voice channel")


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
    auto_defer=True,
)
@lightbulb.implements(
    lightbulb.PrefixCommand,
    lightbulb.SlashCommand,
)
async def play(ctx: Context) -> None:
    if not ctx.guild_id:
        return None

    player = MusicPlayerManager.get_player(ctx.guild_id)
    player.set_context(ctx)
    await player.play(ctx.options.query)


@plugin.command()
@lightbulb.command("skip", "Skip the currently playing song")
@lightbulb.implements(lightbulb.PrefixCommand, lightbulb.SlashCommand)
async def skip(ctx: Context) -> None:
    """Skip the currently playing song"""
    if not ctx.guild_id:
        return None

    voice = ctx.bot.voice.connections.get(ctx.guild_id)

    if not voice:
        await ctx.respond("Not connected to a voice channel")
        return None

    assert isinstance(voice, LavalinkVoice)

    player = await voice.player.get_player()

    if player.track:
        if player.track.info.uri:
            await ctx.respond(
                f"Skipped: [`{player.track.info.author} - {player.track.info.title}`](<{player.track.info.uri}>)"
            )
        else:
            await ctx.respond(
                f"Skipped: `{player.track.info.author} - {player.track.info.title}`"
            )

        voice.player.skip()
    else:
        await ctx.respond("Nothing to skip")


@plugin.command()
@lightbulb.command("stop", "Stop the currently playing song")
@lightbulb.implements(lightbulb.PrefixCommand, lightbulb.SlashCommand)
async def stop(ctx: Context) -> None:
    """Stop the currently playing song"""
    if not ctx.guild_id:
        return None

    voice = ctx.bot.voice.connections.get(ctx.guild_id)

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


def load(bot: Inu) -> None:
    bot.add_plugin(plugin)
