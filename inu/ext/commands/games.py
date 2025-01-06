from os import name
from re import T
import traceback
from typing import *
import aiohttp

from hikari import Member, Snowflake, User
from hikari.impl import MessageActionRowBuilder
import lightbulb
from lightbulb import Context, Loader, SlashCommand, invoke, Group
from lightbulb.prefab import sliding_window


from utils.games.connect_four_handler import (
    Connect4Handler, 
    Connect4FallingRowsHandler,
    Player, 
    get_handler_from_letter, 
    MemoryConnect4Handler,
    RandomTerrainConnect4Handler,
)
from utils.games import HikariOnu
from utils import AkinatorSI, Human
from core import getLogger, Inu, get_context, InuContext

log = getLogger(__name__)
loader = lightbulb.Loader()
bot: Inu = Inu.instance
onu_sessions = set()

def cast_to_members(p1: User, p2: Optional[User], guild: Snowflake | None) -> Tuple[Member, Optional[Member]]:
    """casts `Tuple[User, Optional[User]]` to `Tuple[Member, Optional[Member]]`"""
    assert guild is not None
    player1 = bot.cache.get_member(guild, p1)
    assert player1 is not None
    player2 = bot.cache.get_member(guild, p2) if p2 else None
    return (player1, player2)


# Shared functions
async def start_connect_4(
    ctx: InuContext, 
    rows: int, 
    columns: int, 
    players: Tuple[Member, Optional[Member]],
    handler: Type[Connect4Handler] | None = None, 
    **kwargs
):
    if not players[1]:
        member = ctx.member
        assert member is not None
        players = (players[0], member)
    handler = handler or Connect4Handler
    h = handler(players[0], players[1], rows=rows, columns=columns, **kwargs)  # type: ignore
    await h.start(ctx)


con4 = Group(name="Connect4", description="Various Connect 4 games", dm_enabled=False)
# Connect 4 base command group

@con4.register
class ClassicConnect4(
    SlashCommand,
    name = "classic",
    description = "Starts a classic 6x7 Connect 4 game"
):
    player1 = lightbulb.user("player1", "The first player")
    player2 = lightbulb.user("player2", "The second player", default=None)

    @invoke
    async def callback(self, _: Context, ctx: InuContext):
        players = cast_to_members(self.player1, self.player2, ctx.guild_id)
        await start_connect_4(ctx, rows=6, columns=7, players=players)


@con4.register
class SquareConnect4(
    SlashCommand,
    name="square",
    description="Starts an 8x8 Connect 4 game"
):
    player1 = lightbulb.user("player1", "The first player")
    player2 = lightbulb.user("player2", "The second player", default=None)

    @invoke
    async def callback(self, _: lightbulb.Context, ctx: InuContext):
        players = cast_to_members(self.player1, self.player2, ctx.guild_id)
        await start_connect_4(ctx, rows=8, columns=8, players=players)

@con4.register
class FallingRowsConnect4(
    SlashCommand,
    name="falling-rows",
    description="A game of Connect 4 with Tetris-like falling rows"
):
    player1 = lightbulb.user("player1", "The first player")
    player2 = lightbulb.user("player2", "The second player", default=None)

    @invoke
    async def callback(self, _: lightbulb.Context, ctx: InuContext):
        players = cast_to_members(self.player1, self.player2, ctx.guild_id)
        await start_connect_4(ctx, rows=6, columns=7, handler=Connect4FallingRowsHandler, players=players)

@con4.register
class MemoryConnect4(
    SlashCommand,
    name="memory",
    description="A Connect 4 game with hidden tokens"
):

    player1 = lightbulb.user("player1", "The first player")
    player2 = lightbulb.user("player2", "The second player", default=None)
    unmemory_count = lightbulb.integer("unmemory-count", "Rounds before tokens are visible again", default=5)

    @invoke
    async def callback(self, _: lightbulb.Context, ctx: InuContext):
        players = cast_to_members(self.player1, self.player2, ctx.guild_id)
        await start_connect_4(ctx, rows=6, columns=7, handler=MemoryConnect4Handler, unmemory=self.unmemory_count, players=players)

@con4.register
class RandomTerrainConnect4(
    SlashCommand,
    name="random-terrain",
    description="A Connect 4 game with a random start terrain"
):
    player1 = lightbulb.user("player1", "The first player")
    player2 = lightbulb.user("player2", "The second player", default=None)

    @invoke
    async def callback(self, _: lightbulb.Context, ctx: InuContext):
        players = cast_to_members(self.player1, self.player2, ctx.guild_id)
        await start_connect_4(ctx, rows=6, columns=7, handler=RandomTerrainConnect4Handler, players=players)


loader.command(con4)



# @loader.command
# class OnuGame(
#     SlashCommand,
#     name="onu",
#     description="Starts an ONU game",
#     dm_enabled=False,
#     default_member_permissions=None
# ):
#     player1 = lightbulb.user("player1", "The first player")
#     player2 = lightbulb.user("player2", "The second player")
#     player3 = lightbulb.user("player3", "The third player", default=None)
#     player4 = lightbulb.user("player4", "The fourth player", default=None)
#     player5 = lightbulb.user("player5", "The fifth player", default=None)
#     player6 = lightbulb.user("player6", "The sixth player", default=None)
#     player7 = lightbulb.user("player7", "The seventh player", default=None)
#     player8 = lightbulb.user("player8", "The eighth player", default=None)

#     @invoke
#     async def callback(self, _: lightbulb.Context, ctx: InuContext):
#         players: List[Member] = [ctx.bot.cache.get_member(ctx.guild, v) for k, v in self.__dict__.items() if "player" in k]  # type:ignore
#         player_map = {p.id: p for p in players if p is not None}
#         if ctx.author.id not in players:
#             await ctx.respond("You can't start a game without yourself")
#             return

#         for p_id, p in player_map.items():
#             if p_id in onu_sessions:
#                 await ctx.respond(f"There is a running game with {p.mention}. Cannot start a new game.")
#                 return

#         for p_id in players:
#             onu_sessions.add(p_id)

#         await ctx.respond(f"Starting Onu game with {Human.list_([p.display_name for p in player_map.values()], with_a_or_an=False)}")
#         onu = HikariOnu(player_map)  # type:ignore

#         try:
#             await onu.start(ctx.bot, ctx)
#         except Exception:
#             log.error(traceback.format_exc())
#         finally:
#             for p_id in players:
#                 onu_sessions.remove(p_id)


# @loader.command
# class AkinatorGame(
#     SlashCommand,
#     name="akinator",
#     description="Guess a character with Akinator",
#     dm_enabled=False,
# ):
#     @invoke
#     async def callback(self, ctx: lightbulb.Context):
#         aki = AkinatorSI("en")
#         await aki.start(ctx)


REVERSI_BASE_URL = "http://inuthebot.duckdns.org:8888"
CREATE_SESSION_ENDPOINT = f"{REVERSI_BASE_URL}/create_session"

# @loader.command
# class ReversiGame(lightbulb.SlashCommand):
#     name = "reversi"
#     description = "Creates a session for Reversi"
#     dm_enabled = False
#     default_member_permissions = None

#     @invoke
#     async def callback(self, ctx: lightbulb.Context):
#         async with aiohttp.ClientSession() as session:
#             async with session.get(CREATE_SESSION_ENDPOINT, ssl=False) as resp:
#                 if resp.status != 200:
#                     await ctx.respond("Something went wrong", ephemeral=True)
#                     return

#                 data = await resp.json()
#                 await ctx.respond(
#                     component=(
#                         MessageActionRowBuilder()
#                         .add_link_button(
#                             data['data']["link"],
#                             label=f"Reversi Lobby Code: {data['data']['code']}"
#                         )
#                     )
#                 )
