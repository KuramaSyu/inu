import os
import traceback
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
import datetime
from pprint import pformat
import random

import hikari
from hikari import ComponentInteraction, Embed, ResponseType, ShardReadyEvent, VoiceState, VoiceStateUpdateEvent
from hikari.impl import ActionRowBuilder
import lightbulb
from lightbulb import Context, command, check
import lavasnek_rs

from core import Inu

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)


# If True connect to voice with the hikari gateway instead of lavasnek_rs's
HIKARI_VOICE = False


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
        self.queue_msg: Optional[hikari.Message] = None


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
            query_print = f"{x+1} | {track.info.title}"
            if len(query_print) > 100:
                query_print = query_print[:100]
            menu.add_option(query_print, str(x)).add_to_menu()

        menu = menu.add_to_container()
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
            return None
        log.debug(f"track num: {track_num}")
        await event.interaction.create_initial_response(
            ResponseType.DEFERRED_MESSAGE_UPDATE
        )
        log.debug(pformat([track.info.title for track in query_information.tracks]))
        log.debug(query_information.tracks[track_num].info.title)
        return query_information.tracks[track_num]


class MusicHelper:
    def __init__(self):
        pass


class MusicLog:
    def __init__(self, guild_id: int):
        self.guild_id = guild_id
        self.music_log = []

    def add_to_log():
        pass

    def format_time_now(self):
        """
        Returns:
        --------
            - (str) `hour`:`minute`:`second` - `month_day_num`. `month`
        """
        time = datetime.datetime.now()
        return f'{time.hour}:{time.minute}:{time.second} - {time.day}. {time.month}'
        



class Music(lightbulb.Plugin):
    def __init__(self, bot: Inu) -> None:
        super().__init__()
        self.bot = bot
        self.log = logging.getLogger(__name__)
        self.log.setLevel(logging.DEBUG)
        self.interactive = Interactive(self.bot)
        self.music_message: Dict[int, hikari.Message] = {}  # guild_id: hikari.Message

    @lightbulb.listener(hikari.VoiceStateUpdateEvent)
    async def on_voice_state_update(self, event: VoiceStateUpdateEvent):
        # check if the user is the bot
        if not event.state.user_id == self.bot.get_me().id: # type: ignore
            return

        # bot connected (No channel -> channel)
        if event.old_state is None and event.state.channel_id:
            pass
        elif event.state.channel_id is None and not event.old_state is None:
            await self._leave(event.guild_id)

    @lightbulb.listener(hikari.ReactionAddEvent)
    async def on_reaction_add(self, event: hikari.ReactionAddEvent):
        if event.message_id not in self.music_message.keys():
            return
        try:
            message = self.bot.cache.get_message(event.message_id)

            guild_id = message.guild_id  # type: ignore
            if not isinstance(message, hikari.Message) or guild_id is None:
                return
        except AttributeError:
            return
        emoji = event.emoji_name
        if emoji == '🔀':

            node = self.lavalink.get_guild_node(guild_id)
            random.shuffle(player.queue)
            await self.queue(ctx=user, fetch_ctx=True)
            await message.remove_reaction(emoji, user=event.user_id)
            await self.append_music_log(guild_id = str(guild_id), info = f'🔀 Music was shuffled by {user.name}')
        elif emoji == '▶':
            await self.append_music_log(guild_id = str(guild_id), info = f'▶ Music was resumed by {user.name}')
            await message.remove_reaction(emoji, user=event.user_id)
            await message.remove_reaction(emoji, user=self.bot.me)
            await asyncio.sleep(0.1)
            await message.add_reaction(str('⏸'))
            await self._resume(reaction.message.guild)
        elif emoji == '1️⃣':
            await self._skip(guild_id, amount = 1)
            await message.remove_reaction(emoji, user=event.user_id)
            await self.append_music_log(guild_id = str(guild_id), info = f'1️⃣ Music was skipped by {user.name} (once)')
        elif emoji == '2️⃣':
            await self._skip(guild_id, amount = 2)
            await message.remove_reaction(emoji, user=event.user_id)
            await self.append_music_log(
                guild_id = str(guild_id), 
                info = f'2️⃣ Music was skipped by {self.bot.cache.get_member(guild_id, event.user_id).display_name} (twice)'
            )
        elif emoji == '3️⃣':
            await self._skip(guild_id, amount = 3)
            await reaction.message.remove_reaction(emoji,user)
            await self.append_music_log(guild_id = str(guild_id), info = f'3️⃣ Music was skipped by {user.name} (3 times)')
        elif emoji == '4️⃣':
            await self._skip(guild_id, amount = 4)
            await reaction.message.remove_reaction(emoji,user)
            await self.append_music_log(guild_id = str(guild_id), info = f'4️⃣ Music was skipped by {user.name} (4 times)')
        elif emoji == '⏸':
            await self.append_music_log(guild_id = str(guild_id), info = f'⏸ Music was paused by {user.name}')
            await reaction.message.remove_reaction(emoji,user)
            await reaction.message.remove_reaction(emoji,self.client.user)
            await asyncio.sleep(0.1)
            await reaction.message.add_reaction(str('▶'))
            await self._pause(reaction.message)
        elif emoji == '🗑':
            await reaction.message.remove_reaction(emoji,user)
            await information_message(reaction.message.channel, info=f'🗑 Queue was cleared by {user.name}', del_after=int(4*60), user=user, small = True)
            await self.append_music_log(guild_id = str(guild_id), info = f'🗑 Queue was cleared by {user.name}')
            await self._clear(reaction.message)
            await self.queue(ctx = user, fetch_ctx=True)
        elif emoji == '🛑':
            await information_message(reaction.message.channel, info=f'🛑 Music was stopped by {user.name}', del_after=int(5*60), user=user, small = True)
            await self.append_music_log(guild_id = str(guild_id), info = f'🛑 Music was stopped by {user.name}')
            await self._leave(user.guild)

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
            .set_host("127.0.0.1").set_password(self.bot.conf.LAVALINK_PASSWORD)
        )

        if HIKARI_VOICE:
            builder.set_start_gateway(False)

        lava_client = await builder.build(EventHandler())
        self.bot.data.lavalink = lava_client
        self.lavalink = self.interactive.lavalink = self.bot.data.lavalink
        log.debug(type(self.interactive.lavalink))
        logging.info("lavalink is connected")

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
        if not ctx.guild_id:
            return  # just for pylance
        await self._leave(ctx.guild_id)
        await ctx.respond("Left voice channel")

    async def _leave(self, guild_id: int):
        await self.bot.data.lavalink.destroy(guild_id)

        if HIKARI_VOICE:
            await self.bot.update_voice_state(guild_id, None)
            await self.bot.data.lavalink.wait_for_connection_info_remove(guild_id)
        else:
            await self.bot.data.lavalink.leave(guild_id)

        # Destroy nor leave remove the node nor the queue loop, you should do this manually.
        await self.bot.data.lavalink.remove_guild_node(guild_id)
        await self.bot.data.lavalink.remove_guild_from_loops(guild_id)
        
    @lightbulb.check(lightbulb.guild_only)
    @lightbulb.command()
    async def play(self, ctx: lightbulb.Context, *, query: str) -> None:
        """Searches the query on youtube, or adds the URL to the queue."""
        if not ctx.guild_id or not ctx.member:
            return  # just for pylance
        con = await self.bot.data.lavalink.get_guild_gateway_connection_info(ctx.guild_id)
        # Join the user's voice channel if the bot is not in one.
        if not con:
            await self._join(ctx)

        # check for youtube playlist
        if 'youtube' in query and 'playlist?list=' in query:
            await self.load_yt_playlist(ctx, query)
        else:
            track = await self.search_track(ctx, query)
            if track is None:
                await ctx.respond("I can't find anything with your query")
                return
            await self.load_track(ctx, track)


        # play the track
        


        self.log.debug("start queue()")
        await self.queue(ctx)
        self.log.debug("ended queue()")

    async def load_track(self, ctx: Context, track: lavasnek_rs.Track):
        guild_id = ctx.guild_id
        author_id = ctx.author.id
        if not guild_id:
            raise Exception("guild_id is missing in `lightbulb.Context`")
        try:
            # `.queue()` To add the track to the queue rather than starting to play the track now.
            await self.bot.data.lavalink.play(guild_id, track).requester(
                author_id
            ).queue()
        except lavasnek_rs.NoSessionPresent:
            await ctx.respond(f"Use `{self.bot.conf.DEFAULT_PREFIX}join` first")
            return

        embed = Embed(
            title=f'Title added',
            description=f'[{track.info.title}]({track.info.uri})'
        ).set_thumbnail(ctx.member.avatar_url)  # type: ignore
        await ctx.respond(embed=embed)

    async def load_yt_playlist(self, ctx: Context, query) -> lavasnek_rs.Tracks:
        """
        loads a youtube playlist

        Returns
        -------
            - (lavasnek_rs.Track) the first track of the playlist
        """
        tracks = await self.lavalink.get_tracks(query)
        log.debug(len(tracks.tracks))
        for track in tracks.tracks:
            await self.bot.data.lavalink.play(ctx.guild_id, track).requester(
                ctx.author.id
            ).queue()
        if tracks.playlist_info:
            embed = Embed(
                title=f'Playlist added',
                description=f'[{tracks.playlist_info.name}]({query})'
            ).set_thumbnail(ctx.member.avatar_url)
            await ctx.respond(embed=embed)
        return tracks

    async def search_track(self, ctx: Context, query: str) -> Optional[lavasnek_rs.Track]:
        """
        searches the query and returns the Track or None
        """
        query_information = await self.bot.data.lavalink.auto_search_tracks(query)
        track = None
        if not query_information.tracks:  # tracks is empty
            await ctx.respond("Could not find any video of the search query.")
            return None

        if len(query_information.tracks) > 1:
            try:
                track = await self.interactive.ask_for_song(ctx, query)
                if track is None:
                    self.log.warning("track is None - error")
            except Exception:
                self.log.error(traceback.print_exc())
                await ctx.respond("Error")

        else:
            track = query_information.tracks[0]

        if track is None:
            return None
        return track

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
        if not (node := await self.bot.data.lavalink.get_guild_node(ctx.guild_id)):
            return

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

    async def queue(self, ctx: Context):
        '''
        refreshes the queue of the player
        '''
        if not ctx.guild_id:
            return
        channel = ctx.get_channel()
        node = await self.bot.data.lavalink.get_guild_node(ctx.guild_id)
        if not node:
            self.log.warning("node is None, in queue command")
            return
        numbers = ['1️⃣','2️⃣','3️⃣','4️⃣','5️⃣','6️⃣','7️⃣','8️⃣','9️⃣','🔟']
        upcoming_songs = ''
        for track in node.queue:
            self.log.debug(track.track.info.title)
        for x in range (1,5,1):
            try:
                num = numbers[int(x) - 1]
                upcoming_songs = (
                    f'{upcoming_songs}\n' 
                    f'{num} {str(datetime.timedelta(milliseconds=int(int(node.queue[x - 1].track.info.length))))} '
                    f'- {node.queue[x - 1].track.info.title}'
                )
            except:
                break
        queue = None
        if upcoming_songs == '':
            upcoming_songs = '/'
        elif int(len(node.queue)) > 4:
            queue_len = int(len(node.queue))-4
            if queue_len > 1:
                queue = f'waiting in Queue: ---{queue_len}--- songs'
            else:
                try:
                    queue = f'waiting in Queue: ---{queue_len}--- song'
                except:
                    queue = f'waiting in Queue: ---N0TH1NG---'
        if queue is None:
            queue = f'Queue: ---N0TH1NG---'
        try:
            track = node.now_playing.track
        except Exception:
            return self.log.warning("can't get current playing song")

        if not node.now_playing.requester:
            self.log.warning("no requester of current track - returning")
        #get thumbnail of the video

        self.log.debug(track.info.uri)
        requester = ctx.get_guild().get_member(int(node.now_playing.requester))
        current_duration = str(datetime.timedelta(milliseconds=int(int(track.info.length))))
        music_embed = hikari.Embed(
            colour=hikari.Color.from_rgb(71, 89, 211)
        )
        music_embed.add_field(name = "Playing Song:", value=f'[{track.info.title}]({track.info.uri})', inline=True)#{"🔂 " if player.repeat else ""}
        music_embed.add_field(name = "Author:", value=f'{track.info.author}', inline=True)
        music_embed.add_field(name="Added from:", value=f'{requester.display_name}' , inline=True)
        music_embed.add_field(name = "Duration:", value=f'{current_duration}', inline=False)
        
        
        
        # music_embed.set_thumbnail(url=f'{video_thumbnail}')
        music_embed.add_field(name = "——————————Queue—————————————————", value=f'```ml\n{upcoming_songs}\n```', inline=False)
        music_embed.set_footer(text = f'{queue or "/"}')
        try:
            self.music_message[ctx.guild_id]
        except:
            self.music_message[ctx.guild_id] = None

        #edit existing message
        resume = True
        if self.music_message[ctx.guild_id] != None:
            try:
                timeout = 4
                async for m in self.bot.rest.fetch_messages(ctx.channel_id):
                    if m.id == self.music_message[ctx.guild_id].id:
                        await self.music_message[ctx.guild_id].edit(embed=music_embed)
                        resume = False
                    timeout -= 1
                    if timeout == 0:
                        break
            except Exception as e:
                traceback.print_exc()
        try:
            if resume:
                #last message not among the last 3. Del and re send
                if self.music_message[ctx.guild_id] != None:
                    await self.music_message[ctx.guild_id].delete()
                    self.music_message[ctx.guild_id] = None#edit(embed=music_embed)
                    self.music_message[ctx.guild_id] = await ctx.respond(embed=music_embed)
                    message = self.music_message[ctx.guild_id]
                    await self.add_music_reactions(message)
                else: #self.music_message[str(ctx.guild)] == None:
                    self.music_message[ctx.guild_id] = await ctx.respond(embed=music_embed)
                    message = self.music_message[ctx.guild_id]
                    await self.add_music_reactions(message)
        except Exception as e:
            traceback.print_exc()
            try:
                self.music_message[ctx.guild_id] = await ctx.respond(embed=music_embed)
                message = self.music_message[ctx.guild_id]
                await self.add_music_reactions(message)
            except Exception as e:
                traceback.print_exc()
        return

    async def add_music_reactions(self, message: hikari.Message):
        await message.add_reaction(str('1️⃣'))
        await message.add_reaction(str('2️⃣'))
        await message.add_reaction(str('3️⃣'))
        await message.add_reaction(str('4️⃣'))
        await message.add_reaction(str('🔀'))
        await message.add_reaction(str('🗑'))
        await message.add_reaction(str('🛑'))
        await message.add_reaction(str('⏸'))


def load(bot: Inu) -> None:
    bot.add_plugin(Music(bot))


def unload(bot: lightbulb.Bot) -> None:
    bot.remove_plugin("Music")

