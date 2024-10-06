import random

import lightbulb
from lightbulb import Context
import hikari 

from core import Inu
from .music_utils import LavalinkVoice, MusicPlayerManager
from core import getLogger, get_context

log = getLogger(__name__)

plugin = lightbulb.Plugin("Music (advanced) commands")
plugin.add_checks(lightbulb.guild_only)


MENU_CUSTOM_IDS = [
    "music_play", 
    "music_pause", 
    "music_shuffle", 
    "music_skip_1", 
    "music_skip_2", 
    "music_resume", 
    "music_stop"
]
@plugin.listener(hikari.InteractionCreateEvent)
async def on_music_menu_interaction(event: hikari.InteractionCreateEvent):
    if not isinstance(event.interaction, hikari.ComponentInteraction):
        return
    
    ctx = get_context(event)
    if not [custom_id for custom_id in MENU_CUSTOM_IDS if ctx.custom_id == custom_id]:
        # wrong custom id
        return
    
    player = MusicPlayerManager.get_player(ctx)
    if ctx.custom_id == "music_pause":
        await player.pause()
    

@plugin.command
@lightbulb.command("pause", "Pause the currently playing song")
@lightbulb.implements(lightbulb.PrefixCommand, lightbulb.SlashCommand)
async def pause(ctx: Context) -> None:
    """Pause the currently playing song"""
    if not ctx.guild_id:
        return None
    player = MusicPlayerManager.get_player(get_context(ctx.event))
    await player.ctx.defer()
    await player.pause()
    await player.send_queue(True)


@plugin.command
@lightbulb.command("resume", "Resume the currently playing song")
@lightbulb.implements(lightbulb.PrefixCommand, lightbulb.SlashCommand)
async def resume(ctx: Context) -> None:
    """Resume the currently playing song"""
    if not ctx.guild_id:
        return None
    player = MusicPlayerManager.get_player(get_context(ctx.event))
    await player.ctx.defer()
    await player.resume()
    await player.send_queue(True)


@plugin.command
@lightbulb.option(
    "seconds",
    "The position to jump to",
    int,
)
@lightbulb.command("seek", "Seek the currently playing song")
@lightbulb.implements(lightbulb.PrefixCommand, lightbulb.SlashCommand)
async def seek(ctx: Context) -> None:
    """Seek the currently playing song to a specific second"""
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
                f"Seeked: [`{player.track.info.author} - {player.track.info.title}`](<{player.track.info.uri}>)"
            )
        else:
            await ctx.respond(
                f"Seeked: `{player.track.info.author} - {player.track.info.title}`"
            )

        await voice.player.set_position_ms(ctx.options.seconds * 1000)
    else:
        await ctx.respond("Nothing to seek")


@plugin.command
@lightbulb.command("queue", "List the current queue")
@lightbulb.implements(lightbulb.PrefixCommand, lightbulb.SlashCommand)
async def queue(ctx: Context) -> None:
    """List the current queue"""
    ctx = get_context(ctx.event)
    await ctx.defer()
    player = MusicPlayerManager.get_player(ctx)
    await player.send_queue(True)


@plugin.command
@lightbulb.option(
    "index",
    "The index of the song to remove",
    int,
)
@lightbulb.command("remove", "Remove the song at the specified index from the queue")
@lightbulb.implements(lightbulb.PrefixCommand, lightbulb.SlashCommand)
async def remove(ctx: Context) -> None:
    """Remove the song at the specified index from the queue"""
    if not ctx.guild_id:
        return None

    voice = ctx.bot.voice.connections.get(ctx.guild_id)

    if not voice:
        await ctx.respond("Not connected to a voice channel")
        return None

    assert isinstance(voice, LavalinkVoice)

    queue = voice.player.get_queue()

    if ctx.options.index > await queue.get_count():
        await ctx.respond("Index out of range")
        return None

    assert isinstance(ctx.options.index, int)
    track_in_queue = await queue.get_track(ctx.options.index - 1)
    assert track_in_queue
    track = track_in_queue.track

    if track.info.uri:
        await ctx.respond(
            f"Removed: [`{track.info.author} - {track.info.title}`](<{track.info.uri}>)"
        )
    else:
        await ctx.respond(f"Removed: `{track.info.author} - {track.info.title}`")

    queue.remove(ctx.options.index - 1)


@plugin.command
@lightbulb.command("clear", "Clear the entire queue")
@lightbulb.implements(lightbulb.PrefixCommand, lightbulb.SlashCommand)
async def clear(ctx: Context) -> None:
    """Clear the entire queue"""
    if not ctx.guild_id:
        return None

    voice = ctx.bot.voice.connections.get(ctx.guild_id)

    if not voice:
        await ctx.respond("Not connected to a voice channel")
        return None

    assert isinstance(voice, LavalinkVoice)

    queue = voice.player.get_queue()

    if not await queue.get_count():
        await ctx.respond("The queue is already empty")
        return None

    queue.clear()
    await ctx.respond("The queue has been cleared")


@plugin.command
@lightbulb.option(
    "index1",
    "The index of the one of the songs to swap",
    int,
)
@lightbulb.option(
    "index2",
    "The index of the other song to swap",
    int,
)
@lightbulb.command("swap", "Swap the places of two songs in the queue")
@lightbulb.implements(lightbulb.PrefixCommand, lightbulb.SlashCommand)
async def swap(ctx: Context) -> None:
    """Swap the places of two songs in the queue"""
    if not ctx.guild_id:
        return None

    voice = ctx.bot.voice.connections.get(ctx.guild_id)

    if not voice:
        await ctx.respond("Not connected to a voice channel")
        return None

    assert isinstance(voice, LavalinkVoice)

    queue = voice.player.get_queue()
    queue_len = await queue.get_count()

    if ctx.options.index1 > queue_len:
        await ctx.respond("Index 1 out of range")
        return None

    if ctx.options.index2 > queue_len:
        await ctx.respond("Index 2 out of range")
        return None

    if ctx.options.index1 == ctx.options.index2:
        await ctx.respond("Can't swap between the same indexes")
        return None

    assert isinstance(ctx.options.index1, int)
    assert isinstance(ctx.options.index2, int)

    track1 = await queue.get_track(ctx.options.index1 - 1)
    track2 = await queue.get_track(ctx.options.index2 - 1)

    assert track1
    assert track2

    queue.swap(ctx.options.index1 - 1, track2)
    queue.swap(ctx.options.index2 - 1, track1)

    if track1.track.info.uri:
        track1_text = f"[`{track1.track.info.author} - {track1.track.info.title}`](<{track1.track.info.uri}>)"
    else:
        track1_text = f"`{track1.track.info.author} - {track1.track.info.title}`"

    if track2.track.info.uri:
        track2_text = f"[`{track2.track.info.author} - {track2.track.info.title}`](<{track2.track.info.uri}>)"
    else:
        track2_text = f"`{track2.track.info.author} - {track2.track.info.title}`"

    await ctx.respond(f"Swapped {track2_text} with {track1_text}")


@plugin.command
@lightbulb.command("shuffle", "Shuffle the queue")
@lightbulb.implements(lightbulb.PrefixCommand, lightbulb.SlashCommand)
async def shuffle(ctx: Context) -> None:
    """Shuffle the queue"""
    if not ctx.guild_id:
        return None

    voice = ctx.bot.voice.connections.get(ctx.guild_id)

    if not voice:
        await ctx.respond("Not connected to a voice channel")
        return None

    assert isinstance(voice, LavalinkVoice)

    queue_ref = voice.player.get_queue()
    queue = await queue_ref.get_queue()

    random.shuffle(queue)

    queue_ref.replace(queue)

    await ctx.respond("Shuffled the queue")


def load(bot: Inu) -> None:
    log.info("Loading music (advanced) commands", prefix="init")
    bot.add_plugin(plugin)
