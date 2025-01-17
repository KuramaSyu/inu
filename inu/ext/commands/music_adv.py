import random
from contextlib import suppress

from typing import *
import asyncio
import lightbulb
from lightbulb import Context, SlashCommand, invoke
import hikari 
from hikari import Embed

from core import Inu
from .music_utils import (
    LavalinkVoice, MusicPlayerManager, HISTORY_PREFIX, 
    MEDIA_TAG_PREFIX, MARKDOWN_URL_REGEX, DISCONNECT_AFTER
)
from core import getLogger, get_context, BotResponseError, InuContext

log = getLogger(__name__)

loader = lightbulb.Loader()
bot: Inu

MENU_CUSTOM_IDS = [
    "music_play", 
    "music_pause", 
    "music_shuffle", 
    "music_skip_1", 
    "music_skip_2", 
    "music_resume", 
    "music_stop"
]
@loader.listener(hikari.InteractionCreateEvent)
async def on_music_menu_interaction(event: hikari.InteractionCreateEvent) -> None:
    if not isinstance(event.interaction, hikari.ComponentInteraction):
        return
    
    ctx = get_context(event)
    if not [custom_id for custom_id in MENU_CUSTOM_IDS if ctx.custom_id == custom_id]:
        # wrong custom id
        return
    tasks: List[asyncio.Task] = []
    add_task = lambda coro: tasks.append(asyncio.create_task(coro))

    await ctx.defer(update=True)
    member: hikari.Member = ctx.member  # type: ignore
    custom_id = ctx.custom_id
    player = MusicPlayerManager.get_player(ctx)
    player.set_context(ctx)

    if custom_id == "music_pause":
        add_task(player.pause())
    elif custom_id == "music_shuffle":
        add_task(player.shuffle())
    elif custom_id == "music_skip_1":
        add_task(player.skip())
    elif custom_id == "music_skip_2":
        add_task(player.skip(2))
    elif custom_id == "music_resume":
        add_task(player.resume())
    elif custom_id == "music_pause":
        add_task(player.pause())
    elif custom_id == "music_stop":
        await player.pre_leave(force_resend=False)
        add_task(player.leave())

    if tasks:
        done, pending = await asyncio.wait(tasks, return_when=asyncio.ALL_COMPLETED)
        for task in [*done, *pending]:
            task.cancel()
            if isinstance(task.exception(), BotResponseError):
                await ctx.respond(**task.exception().kwargs)  # type: ignore
                return

    if "stop" in custom_id:
        return
    await player.send_queue(force_resend=False, force_lock=True)



@loader.command
class PauseCommand(
    lightbulb.SlashCommand,
    name="pause",
    description="Pause the currently playing song",
):
    @invoke
    async def callback(self, _: lightbulb.Context, ctx: InuContext) -> None:
        if not ctx.guild_id:
            return None
        player = MusicPlayerManager.get_player(ctx)
        await player.ctx.defer()
        await player.pause()
        await player.send_queue(True)



@loader.command
class ResumeCommand(
    lightbulb.SlashCommand,
    name="resume",
    description="Resume the currently playing song",
):
    @invoke
    async def callback(self, _: lightbulb.Context, ctx: InuContext) -> None:
        if not ctx.guild_id:
            return None
        player = MusicPlayerManager.get_player(ctx)
        await player.ctx.defer()
        await player.resume()
        await player.send_queue(True)



@loader.command
class SeekCommand(
    lightbulb.SlashCommand,
    name="seek",
    description="Seek the currently playing song",
):
    seconds = lightbulb.number("seconds", "The position to jump to")

    @invoke
    async def callback(self, _: lightbulb.Context, ctx: InuContext) -> None:
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
            await voice.player.set_position_ms(int(self.seconds * 1000))
        else:
            await ctx.respond("Nothing to seek")

@loader.command
class QueueCommand(
    lightbulb.SlashCommand,
    name="queue",
    description="List the current queue",
):
    @invoke
    async def callback(self, _: lightbulb.Context, ctx: InuContext) -> None:
        await ctx.defer()
        player = MusicPlayerManager.get_player(ctx)
        await player.send_queue(True)

@loader.command
class RemoveCommand(
    lightbulb.SlashCommand,
    name="remove",
    description="Remove the song at the specified index from the queue",
):
    index = lightbulb.integer("index", "The index of the song to remove")

    @invoke
    async def callback(self, _: lightbulb.Context, ctx: InuContext) -> None:
        if not ctx.guild_id:
            return None

        voice = ctx.bot.voice.connections.get(ctx.guild_id)

        if not voice:
            await ctx.respond("Not connected to a voice channel")
            return None

        assert isinstance(voice, LavalinkVoice)

        queue = voice.player.get_queue()

        if self.index > await queue.get_count():
            await ctx.respond("Index out of range")
            return None

        assert isinstance(self.index, int)
        track_in_queue = await queue.get_track(self.index - 1)
        assert track_in_queue
        track = track_in_queue.track

        if track.info.uri:
            await ctx.respond(
                f"Removed: [`{track.info.author} - {track.info.title}`](<{track.info.uri}>)"
            )
        else:
            await ctx.respond(f"Removed: `{track.info.author} - {track.info.title}`")

        queue.remove(self.index - 1)



@loader.command
class ClearCommand(
    lightbulb.SlashCommand,
    name="clear",
    description="Clear the entire queue",
):
    @invoke
    async def callback(self, _: lightbulb.Context, ctx: InuContext) -> None:
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

@loader.command
class SwapCommand(
    lightbulb.SlashCommand,
    name="swap",
    description="Swap the places of two songs in the queue",
):
    index1 = lightbulb.number("pos-1",  "The index of the one of the songs to swap")
    index2 = lightbulb.number("pos-2", "The index of the other song to swap")

    @invoke
    async def callback(self, _: lightbulb.Context, ctx: InuContext) -> None:
        if not ctx.guild_id:
            return None

        voice = ctx.bot.voice.connections.get(ctx.guild_id)

        if not voice:
            await ctx.respond("Not connected to a voice channel")
            return None

        assert isinstance(voice, LavalinkVoice)

        queue = voice.player.get_queue()
        queue_len = await queue.get_count()

        if self.index1 > queue_len:
            await ctx.respond("Index 1 out of range")
            return None

        if self.index2 > queue_len:
            await ctx.respond("Index 2 out of range")
            return None

        if self.index1 == self.index2:
            await ctx.respond("Can't swap between the same indexes")
            return None

        assert isinstance(self.index1, int)
        assert isinstance(self.index2, int)

        track1 = await queue.get_track(self.index1 - 1)
        track2 = await queue.get_track(self.index2 - 1)

        assert track1
        assert track2

        queue.swap(self.index1 - 1, track2)
        queue.swap(self.index2 - 1, track1)

        if track1.track.info.uri:
            track1_text = f"[`{track1.track.info.author} - {track1.track.info.title}`](<{track1.track.info.uri}>)"
        else:
            track1_text = f"`{track1.track.info.author} - {track1.track.info.title}`"

        if track2.track.info.uri:
            track2_text = f"[`{track2.track.info.author} - {track2.track.info.title}`](<{track2.track.info.uri}>)"
        else:
            track2_text = f"`{track2.track.info.author} - {track2.track.info.title}`"

        await ctx.respond(f"Swapped {track2_text} with {track1_text}")



@loader.command
class ShuffleCommand(
    lightbulb.SlashCommand,
    name="shuffle",
    description="Shuffle the queue",
):
    @invoke
    async def callback(self, _: lightbulb.Context, ctx: InuContext) -> None:
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