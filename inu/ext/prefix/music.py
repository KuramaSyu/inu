import os
import typing
from typing import (
    Optional,
    Union,
    List,
    Dict,
    Any,
)
import asyncio
import logging
import asyncio

import hikari
from hikari import ComponentInteraction, Embed, ShardReadyEvent
from hikari.impl import ActionRowBuilder
import lightbulb
from lightbulb import Context, command, check
import lavasnek_rs

from core import Inu

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)


# If True connect to voice with the hikari gateway instead of lavasnek_rs's
HIKARI_VOICE = True


class EventHandler:
    """Events from the Lavalink server"""

    async def track_start(self, _: lavasnek_rs.Lavalink, event: lavasnek_rs.TrackStart) -> None:
        log.info("Track started on guild: %s", event.guild_id)

    async def track_finish(self, _: lavasnek_rs.Lavalink, event: lavasnek_rs.TrackFinish) -> None:
        log.info("Track finished on guild: %s", event.guild_id)

    async def track_exception(self, lavalink: lavasnek_rs.Lavalink, event: lavasnek_rs.TrackException) -> None:
        log.warning("Track exception event happened on guild: %d", event.guild_id)

        # If a track was unable to be played, skip it
        skip = await lavalink.skip(event.guild_id)
        node = await lavalink.get_guild_node(event.guild_id)

        if skip and not node is None:
            if not node.queue and not node.now_playing:
                await lavalink.stop(event.guild_id)

class Interactive:
    """A class with methods which do some music stuff interactive"""
    def __init__(self, bot: Inu):
        self.bot = bot
        self.lavalink = self.bot.data.lavalink


    async def ask_for_song(self, ctx: lightbulb.Context, query: str, displayed_song_count: int = 3) -> Optional[lavasnek_rs.Track]:
        """
        Creates an interactive menu for choosing a song

        Args
        ----
            - ctx: (Context) the context invoked with
            - query: (str) the query to search; either an url or just a string
            - displayed_song_count: (int, default=3) the amount of songs which will be showen in the interactive message
            
        returns
        -------
            - (lavasnek_rs.Track | None) the chosen title (is None if timeout or other errors)
        """
        # Search the query, auto_search will get the track from a url if possible, otherwise,
        # it will search the query on youtube.
        if not ctx.guild_id:
            return
        query_print = ""
        query_information = await self.lavalink.auto_search_tracks(query)
        menu = (
            ActionRowBuilder()
            .add_select_menu("query_menu")
        )
        # building selection menu
        for x in range(displayed_song_count):
            try:
                track = query_information.tracks[x]
            except IndexError:
                break
            query_print = f"{x+1} | [{track.info.title}]({track.info.uri})\n"
            if len(query_print) > 100:
                query_print = query_print[:100]
            menu.add_option(query_print, "x").add_to_menu()

        menu.add_to_container()
        menu_msg = await ctx.respond(f"Choose the song which should be added", component=menu)

        try:
            event = await self.bot.wait_for(
                hikari.InteractionCreateEvent,
                30,
                lambda e: (
                    isinstance(e.interaction, ComponentInteraction) 
                    and e.interaction.user.id == ctx.author.id
                    and e.interaction.message.id == menu_msg.id
                )
            )
            if not isinstance(event.interaction, ComponentInteraction):
                return  # to avoid problems with typecheckers
            track_num = int(event.interaction.values[0])
        except asyncio.TimeoutError as e:
            raise e
        
        return query_information.tracks[track_num]
        # await self.lavalink.play(ctx.guild_id, query_information.tracks[track_num]).requester(ctx.author.id).queue()
        # music_embed = hikari.Embed()
        # music_embed.title = "Track added to the queue"
        # music_embed.description = f"[{query_information.tracks[track_num].info.title}]({query_information.tracks[track_num].info.uri})"
        # music_embed.color = 

        # if not query_information.tracks:  # tracks is empty
        #     await ctx.respond("Could not find any video of the search query.")
        #     return

        # try:
        #     # `.requester()` To set who requested the track, so you can show it on now-playing or queue.
        #     # `.queue()` To add the track to the queue rather than starting to play the track now.
        #     await self.bot.data.lavalink.play(ctx.guild_id, query_information.tracks[0]).requester(
        #         ctx.author.id
        #     ).queue()
        # except lavasnek_rs.NoSessionPresent:
        #     await ctx.respond(f"Use `{self.bot.conf.DEFAULT_PREFIX}join` first")
        #     return

        # await ctx.respond(f"Added to queue: {query_information.tracks[0].info.title}")



class Music(lightbulb.Plugin):
    def __init__(self, bot: Inu) -> None:
        super().__init__()
        self.bot = bot
        self.log = logging.getLogger(__name__)
        self.log.setLevel(logging.DEBUG)

    @lightbulb.listener(hikari.ShardReadyEvent)
    async def on_ready(self, event: ShardReadyEvent):
        self.lavalink = self.bot.data.lavalink

    # @lightbulb.check(lightbulb.guild_only) #type: ignore
    async def _join(self, ctx: lightbulb.Context) -> Optional[hikari.Snowflake]:
        if not (guild := ctx.get_guild()) or not ctx.guild_id:
            return
        states = self.bot.cache.get_voice_states_view_for_guild(guild)
        voice_state = [state async for state in states.iterator().filter(lambda i: i.user_id == ctx.author.id)]

        if not voice_state:
            await ctx.respond("Connect to a voice channel first")
            return None

        channel_id = voice_state[0].channel_id

        if HIKARI_VOICE:
            await self.bot.update_voice_state(ctx.guild_id, channel_id, self_deaf=True)
            connection_info = await self.bot.data.lavalink.wait_for_full_connection_info_insert(ctx.guild_id)
        else:
            try:
                connection_info = await self.bot.data.lavalink.join(ctx.guild_id, channel_id)
            except TimeoutError:
                await ctx.respond(
                    "I was unable to connect to the voice channel, maybe missing permissions? or some internal issue."
                )
                return None

        await self.bot.data.lavalink.create_session(connection_info)

        return channel_id

    @lightbulb.listener(hikari.ShardReadyEvent)
    async def start_lavalink(self, _: hikari.ShardReadyEvent) -> None:
        """Event that triggers when the hikari gateway is ready."""
        builder = (
            # TOKEN can be an empty string if you don't want to use lavasnek's discord gateway.
            lavasnek_rs.LavalinkBuilder(self.bot.me.id, self.bot.conf.DISCORD_TOKEN) #, 
            # This is the default value, so this is redundant, but it's here to show how to set a custom one.
            .set_host("127.0.0.1").set_password("youshallnotpass")
        )

        if HIKARI_VOICE:
            builder.set_start_gateway(False)

        lava_client = await builder.build(EventHandler())

        self.bot.data.lavalink = lava_client
        logging.debug("lavalink loaded")

    @lightbulb.check(lightbulb.guild_only)
    @lightbulb.command()
    async def join(self, ctx: lightbulb.Context) -> None:
        """Joins the voice channel you are in."""
        channel_id = await self._join(ctx)

        if channel_id:
            await ctx.respond(f"Joined <#{channel_id}>")

    @lightbulb.check(lightbulb.guild_only)
    @lightbulb.command()
    async def leave(self, ctx: lightbulb.Context) -> None:
        """Leaves the voice channel the bot is in, clearing the queue."""

        await self.bot.data.lavalink.destroy(ctx.guild_id)

        if HIKARI_VOICE:
            await self.bot.update_voice_state(ctx.guild_id, None)
            await self.bot.data.lavalink.wait_for_connection_info_remove(ctx.guild_id)
        else:
            await self.bot.data.lavalink.leave(ctx.guild_id)

        # Destroy nor leave remove the node nor the queue loop, you should do this manually.
        await self.bot.data.lavalink.remove_guild_node(ctx.guild_id)
        await self.bot.data.lavalink.remove_guild_from_loops(ctx.guild_id)

        await ctx.respond("Left voice channel")

    @lightbulb.check(lightbulb.guild_only)
    @lightbulb.command()
    async def play(self, ctx: lightbulb.Context, *, query: str) -> None:
        """Searches the query on youtube, or adds the URL to the queue."""

        con = await self.bot.data.lavalink.get_guild_gateway_connection_info(ctx.guild_id)
        # Join the user's voice channel if the bot is not in one.
        if not con:
            await self._join(ctx)

        # Search the query, auto_search will get the track from a url if possible, otherwise,
        # it will search the query on youtube.
        query_information = await self.bot.data.lavalink.auto_search_tracks(query)

        if not query_information.tracks:  # tracks is empty
            await ctx.respond("Could not find any video of the search query.")
            return

        try:
            # `.requester()` To set who requested the track, so you can show it on now-playing or queue.
            # `.queue()` To add the track to the queue rather than starting to play the track now.
            await self.bot.data.lavalink.play(ctx.guild_id, query_information.tracks[0]).requester(
                ctx.author.id
            ).queue()
        except lavasnek_rs.NoSessionPresent:
            await ctx.respond(f"Use `{self.bot.conf.DEFAULT_PREFIX}join` first")
            return

        await ctx.respond(f"Added to queue: {query_information.tracks[0].info.title}")

    @lightbulb.check(lightbulb.guild_only)
    @lightbulb.command()
    async def stop(self, ctx: lightbulb.Context) -> None:
        """Stops the current song (skip to continue)."""

        await self.bot.data.lavalink.stop(ctx.guild_id)
        await ctx.respond("Stopped playing")

    @lightbulb.check(lightbulb.guild_only)
    @lightbulb.command()
    async def skip(self, ctx: lightbulb.Context) -> None:
        """Skips the current song."""

        skip = await self.bot.data.lavalink.skip(ctx.guild_id)
        node = await self.bot.data.lavalink.get_guild_node(ctx.guild_id)

        if not skip:
            await ctx.respond("Nothing to skip")
        else:
            # If the queue is empty, the next track won't start playing (because there isn't any),
            # so we stop the player.
            if not node.queue and not node.now_playing:
                await self.bot.data.lavalink.stop(ctx.guild_id)

            await ctx.respond(f"Skipped: {skip.track.info.title}")

    @lightbulb.check(lightbulb.guild_only)
    @lightbulb.command()
    async def pause(self, ctx: lightbulb.Context) -> None:
        """Pauses the current song."""

        await self.bot.data.lavalink.pause(ctx.guild_id)
        await ctx.respond("Paused player")

    @lightbulb.check(lightbulb.guild_only)
    @lightbulb.command()
    async def resume(self, ctx: lightbulb.Context) -> None:
        """Resumes playing the current song."""

        await self.bot.data.lavalink.resume(ctx.guild_id)
        await ctx.respond("Resumed player")

    @lightbulb.check(lightbulb.guild_only)
    @lightbulb.command(aliases=["np"])
    async def now_playing(self, ctx: lightbulb.Context) -> None:
        """Gets the song that's currently playing."""

        node = await self.bot.data.lavalink.get_guild_node(ctx.guild_id)

        if not node or not node.now_playing:
            await ctx.respond("Nothing is playing at the moment.")
            return

        # for queue, iterate over `node.queue`, where index 0 is now_playing.
        await ctx.respond(f"Now Playing: {node.now_playing.track.info.title}")

    @lightbulb.check(lightbulb.guild_only)
    @lightbulb.check(lightbulb.owner_only)  # Optional
    @lightbulb.command()
    async def data(self, ctx: lightbulb.Context, *args: Any) -> None:
        """Load or read data from the node.
        If just `data` is ran, it will show the current data, but if `data <key> <value>` is ran, it
        will insert that data to the node and display it."""

        node = await self.bot.data.lavalink.get_guild_node(ctx.guild_id)

        if not args:
            await ctx.respond(await node.get_data())
        else:
            if len(args) == 1:
                await node.set_data({args[0]: args[0]})
            else:
                await node.set_data({args[0]: args[1]})
            await ctx.respond(await node.get_data())

    if HIKARI_VOICE:

        @lightbulb.listener(hikari.VoiceStateUpdateEvent)
        async def voice_state_update(self, event: hikari.VoiceStateUpdateEvent) -> None:
            await self.bot.data.lavalink.raw_handle_event_voice_state_update(
                event.state.guild_id,
                event.state.user_id,
                event.state.session_id,
                event.state.channel_id,
            )

        @lightbulb.listener(hikari.VoiceServerUpdateEvent)
        async def voice_server_update(self, event: hikari.VoiceServerUpdateEvent) -> None:
            await self.bot.data.lavalink.raw_handle_event_voice_server_update(
                event.guild_id, event.endpoint, event.token
            )


def load(bot: Inu) -> None:
    bot.add_plugin(Music(bot))


def unload(bot: lightbulb.Bot) -> None:
    bot.remove_plugin("Music")

