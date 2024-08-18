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
from pprint import pformat

import hikari
from hikari import ComponentInteraction, Embed, ResponseType, VoiceStateUpdateEvent, ButtonStyle
from hikari.impl import MessageActionRowBuilder
import lightbulb
from lightbulb import SlashContext, commands, context
from lightbulb.commands import OptionModifier as OM
from lightbulb.context import Context
import lavalink_rs
from youtubesearchpython.__future__ import VideosSearch  # async variant
from fuzzywuzzy import fuzz
from pytimeparse.timeparse import timeparse
from humanize import naturaldelta
from expiring_dict import ExpiringDict
from tabulate import tabulate
from emoji import replace_emoji

from core import Inu, get_context, InuContext, getLogger, BotResponseError
from utils import (
    Paginator,
    Colors, 
    Human, 
    MusicHistoryHandler, 
    TagManager,
    TagType, 
    crumble
)
from utils.paginators.music_history import MusicHistoryPaginator
from .tags import get_tag, _tag_add

from .music_utils import (
    PlayerManager, 
    MusicHelper, 
    MusicDialogs
)
from .music_utils.constants import *
from .music_utils.queue import setup as setup_queue
from .music_utils.player import setup as setup_player
from .music_utils.helpers import setup as setup_helpers

log = getLogger(__name__)



first_join = False
bot: Inu


class EventHandler:
    """Events from the Lavalink server"""
    def __init__(self):
        pass
    async def track_start(self, lavalink: lavalink_rs.Lavalink, event: lavalink_rs.TrackStart) -> None:
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

    async def track_finish(self, lavalink: lavalink_rs.Lavalink, event: lavalink_rs.TrackFinish) -> None:
        node = await lavalink.get_guild_node(event.guild_id)
        if node is None or len(node.queue) == 0:
            player = await PlayerManager.get_player(event.guild_id)
            await player._leave()

    async def track_exception(self, lavalink: lavalink_rs.Lavalink, event: lavalink_rs.TrackException) -> None:
        log.warning(f"Track exception event happened: {event.exception_message}")
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



music = lightbulb.Plugin(name="Music", include_datastore=True)
lavalink: lavalink_rs.Lavalink = None
music_dialog: MusicDialogs = None
music_helper: MusicHelper = None
music_messages: Dict[int, Union[hikari.Message, None]] = {}  # guild_id: hikari.Message
last_context: Dict[int, InuContext] = {}

@music.listener(hikari.ShardReadyEvent)
async def on_ready(event: hikari.ShardReadyEvent):
    global music_dialog, music_helper
    if music.d is None:
        raise RuntimeError("Plugin has no datastore")
    music.d.log = logging.getLogger(__name__)
    music_dialog = MusicDialogs(music.bot)
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
            player = await PlayerManager.get_player(event.state.guild_id)
            is_alone = player.check_if_bot_is_alone()
            if is_alone:
                log.debug(f"Bot is alone in {event.state.guild_id}")
                await player.on_bot_lonely()
            else:
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
                    try:
                        music_message = player.queue.message
                    except TypeError:
                        music_message = None
                    if music_message:
                        try:
                            log.info("disabling music message buttons")
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
                #PlayerManager.remove_player(player.guild_id)
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
        await player._leave()
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
    log.debug(f"Sleep for {sleep_time} seconds before connecting to Lavalink", prefix="init") 
    await asyncio.sleep(sleep_time)
    for x in range(10):
        try:
            builder = (
                # TOKEN can be an empty string if you don't want to use lavasnek's discord gateway.
                lavalink_rs.LavalinkBuilder(music.bot.get_me().id, music.bot.conf.bot.DISCORD_TOKEN) #, 
                # This is the default value, so this is redundant, but it's here to show how to set a custom one.
                .set_host(music.bot.conf.lavalink.IP)
                .set_password(music.bot.conf.lavalink.PASSWORD)
            )
            builder.set_start_gateway(False)
            lava_client = await builder.build(EventHandler())
            music_dialog.lavalink = lava_client
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
    setup_player(lavalink_=lavalink, message_id_to_queue_cache_=message_id_to_queue_cache)
    log.info("lavalink is connected", prefix="init")


# inner dict keys: title, url
message_id_to_queue_cache: Dict[hikari.Snowflake, List[Dict[str, str]]] = ExpiringDict(ttl=60*60*4)
@music.listener(hikari.InteractionCreateEvent)
async def on_queue_to_tag_click(event: hikari.InteractionCreateEvent):
    if not isinstance(event.interaction, hikari.ComponentInteraction):
        return
    ctx = get_context(event)
    if not event.interaction.custom_id.startswith("queue_to_tag_"):
        return
    if not event.interaction.message.id in message_id_to_queue_cache:
        return await ctx.respond("Sorry, I have thrown it away. I only kept it for a certain time")
    queue = message_id_to_queue_cache[event.interaction.message.id]
    text = "\n".join([f"- [{track['title']}]({track['url']})" for x, track in enumerate(queue)])
    ctx = get_context(
            event, 
            options={"name": None, "value": text}
    )
    try:
        _ = await _tag_add(ctx, TagType.MEDIA)
    except BotResponseError as e:
        await ctx.respond(**e.context_kwargs)



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
    player._clean_queue = True
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
@lightbulb.option(
    "query", 
    "the title of the track", 
    required=False,
    modifier=OM.CONSUME_REST, 
    autocomplete=True, 
    default=None
)
@lightbulb.command("play", "play a song", aliases=["pl"])
@lightbulb.implements(commands.SlashCommand)
async def play_normal(ctx: context.Context) -> None:
    player = await PlayerManager.get_player(ctx.guild_id, ctx.event)

    query = ctx.options.query
    # modal if no query was not given
    if not ctx.options.query or ctx.options.query == "None":
        try:
            query, _, event = await bot.shortcuts.ask_with_modal(
                "Music", 
                "What do you want to play?", 
                placeholder_s="URL or title or multiple titles over multiple lines", 
                interaction=ctx.event.interaction
            )
            ctx = get_context(event)
        except asyncio.TimeoutError:
            return
        player.ctx = ctx
        await player.ctx.respond("🔍 Searching...")
    await player._play(query)



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
@lightbulb.add_cooldown(20, 1, lightbulb.UserBucket)
@lightbulb.add_checks(lightbulb.guild_only)
@lightbulb.command("upcoming-songs", "The full music queue")
@lightbulb.implements(commands.PrefixCommand, commands.SlashCommand)
async def upcoming_songs(_ctx: Context) -> None:
    player = await PlayerManager.get_player(_ctx.guild_id, _ctx.event)
    # defer, that it doesn't timeout while loading queue
    await player.ctx.defer()
    if player._node is None or len(player.node.queue) == 0:
        return await player.ctx.respond("Nothing's playing", ephemeral=True)
    
    def default_embed():
        embed = Embed(title="Upcoming songs")
        embed.description = ""
        return embed
    
    embeds: List[Embed] = []
    embed = default_embed()
    length = len(str(len(player.node.queue)))
    numbers = ['0️⃣','1️⃣','2️⃣','3️⃣','4️⃣','5️⃣','6️⃣','7️⃣','8️⃣','9️⃣','🔟']

    for i, track in enumerate(player.node.queue):
        track = track.track
        if (i % 20 == 0 or len(embed.description) + len(track.info.title) + len(track.info.uri) + 10 > 4096) and i != 0:
            embeds.append(embed)
            embed = default_embed()
        # number with leading zeros
        str_i = f"{''.join('0' for _ in range(length-len(str(i))))}{i}"
        emoji_i = f"{''.join([numbers[int(x)] for x in str_i])}"
        embed.description += f"{emoji_i} [{track.info.title[:100]}]({track.info.uri})\n"

    if embed.description:
        embeds.append(embed)

    pag = Paginator(embeds)
    await pag.start(player.ctx)
        


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
@lightbulb.option("position", "e.g. 1:30, 3min, -30sec", type=str)
@lightbulb.command("seek", "skip within the current track to a specific position")
@lightbulb.implements(commands.PrefixCommand, commands.SlashCommand)
async def seek(ctx: Context):
    """clears the music queue"""
    if not ctx.guild_id or not ctx.member:
        return
    player = await PlayerManager.get_player(ctx.guild_id, ctx.event)
    if len(player.queue) == 0:
        return await player.ctx.respond("There is no song playing", ephemeral=True)
    await player.ctx.defer()
    try:
        secs = await player.seek(ctx.options.position)
        if secs is None:
            raise Exception
        await player.queue.send(force_resend=True)
    except Exception:
        raise BotResponseError(
            f"I had problems parsing your given time: {ctx.options.position}", 
            ephemeral=True
        )
    

@music.command
@lightbulb.add_checks(lightbulb.guild_only)
@lightbulb.command("join", "joins the channel")
@lightbulb.implements(commands.PrefixCommand, commands.SlashCommand)
async def clear(ctx: Context):
    """clears the music queue"""
    if not ctx.guild_id or not ctx.member:
        return
    player = await PlayerManager.get_player(ctx.guild_id, ctx.event)
    await player.ctx.defer()
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
    query = option.value or ""
    records = [
        {"title": record["title"], "prefix": HISTORY_PREFIX} 
        for record in await MusicHistoryHandler.cached_get(interaction.guild_id)
    ]
    if not query:
        records = records[:23]
    else:
        if len(str(query)) > 1:
            tag_records = await TagManager.cached_find_similar(query, interaction.guild_id, tag_type=TagType.MEDIA)
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
    return [r[:100] for r in converted_records[:23]]



def load(inu: Inu) -> None:
    global bot
    bot = inu
    inu.add_plugin(music)
    setup_player(
        inu=bot, 
        lavalink_=lavalink, 
        message_id_to_queue_cache_=message_id_to_queue_cache
    )
    setup_queue(
        inu=inu,
    )
    setup_helpers(
        bot_=inu
    )


def unload(inu: Inu) -> None:
    inu.remove_plugin(music)