import traceback
from typing import *
import asyncio
import json

import hikari
from hikari.impl import MessageActionRowBuilder
import lightbulb
import lightbulb.context as context
from lightbulb import commands
from lightbulb.commands import OptionModifier as OM

from utils.games.connect_four_handler import Connect4Handler, Connect4FallingRowsHandler, get_handler_from_letter, MemoryConnect4Handler
from utils.games import HikariOnu
from utils import AkinatorSI
from core import getLogger, Inu, get_context


log = getLogger(__name__)
Context = Union[context.SlashContext, context.PrefixContext]
plugin = lightbulb.Plugin("Game Commands", "Extends the commands with commands all about games")
onu_sessions = set()
bot: Inu


@plugin.listener(hikari.InteractionCreateEvent)
async def on_connect4_restart(event: hikari.InteractionCreateEvent):
    game_modifier = ""
    if not isinstance(event.interaction, hikari.ComponentInteraction):
        return
    try:
        custom_id_json = json.loads(event.interaction.custom_id)
        custom_id: str = custom_id_json["type"]
        assert custom_id.startswith("c4") # c4{game_letter}-{rows}x{columns}
        game_modifier = custom_id[2]
        rxc: List[str] = custom_id[4:].split("x")
        rows = int(rxc[0])
        columns = int(rxc[1])
        guild_id = custom_id_json["gid"]

        p1 = await bot.mrest.fetch_member(guild_id, custom_id_json["p1"])
        p2 = await bot.mrest.fetch_member(guild_id, custom_id_json["p2"])
    except:
        return
    handler_class = get_handler_from_letter(game_modifier)
    handler = handler_class(p1, p2, rows=rows, columns=columns)
    ctx = get_context(event)
    await ctx.respond(
        components=[
            MessageActionRowBuilder()
            .add_button(hikari.ButtonStyle.PRIMARY, "connect4-activated-restart")
            .set_emoji("🔁").add_to_container()
        ],
        update=True
    )
    await handler.start(ctx)

    
async def start_4_in_a_row(ctx: Context, rows: int, columns: int, handler: Type[Connect4Handler] | None = None):
    if not ctx._options.get("player2"):
        ctx._options["player2"] = ctx.member

    handler = handler or Connect4Handler
    
    h = handler(ctx.options.player1, ctx.options.player2, rows=rows, columns=columns)
    msg = await h.start(ctx)



@plugin.command
@lightbulb.add_checks(lightbulb.guild_only)
@lightbulb.add_cooldown(30, 2, lightbulb.UserBucket)
@lightbulb.option("player2", "The second player - DEFAULT: you", type=hikari.Member, default=None)
@lightbulb.option("player1", "A player\nNOTE: ping like @user", type=hikari.Member)
@lightbulb.command("connect-4", "starts a Connect 4 game")
@lightbulb.implements(commands.PrefixCommandGroup, commands.SlashCommandGroup)
async def connect4(ctx: Context):
    ...



@connect4.child
@lightbulb.add_checks(lightbulb.guild_only)
@lightbulb.add_cooldown(30, 2, lightbulb.UserBucket)
@lightbulb.option("player2", "The second player - DEFAULT: you", type=hikari.Member, default=None)
@lightbulb.option("player1", "A player\nNOTE: ping like @user", type=hikari.Member)
@lightbulb.command("classic", "starts a Connect 4 game", aliases=["6x7"])
@lightbulb.implements(commands.PrefixSubCommand, commands.SlashSubCommand)
async def connect4_classic(ctx: Context):
    await start_4_in_a_row(ctx, rows=6, columns=7)



@connect4.child
@lightbulb.add_checks(lightbulb.guild_only)
@lightbulb.add_cooldown(30, 2, lightbulb.UserBucket)
@lightbulb.option("player2", "The second player - DEFAULT: you", type=hikari.Member, default=None)
@lightbulb.option("player1", "A player\nNOTE: ping like @user", type=hikari.Member)
@lightbulb.command("square", "starts a Connect 4 game")
@lightbulb.implements(commands.PrefixSubCommand, commands.SlashSubCommand)
async def connect4_8by8(ctx: Context):
    await start_4_in_a_row(ctx, rows=8, columns=8)



@connect4.child
@lightbulb.add_checks(lightbulb.guild_only)
@lightbulb.add_cooldown(30, 2, lightbulb.UserBucket)
@lightbulb.option("player2", "The second player - DEFAULT: you", type=hikari.Member, default=None)
@lightbulb.option("player1", "A player\nNOTE: ping like @user", type=hikari.Member)
@lightbulb.command("falling-rows", "A game of Connect 4 which drops rows Tetris like")
@lightbulb.implements(commands.PrefixSubCommand, commands.SlashSubCommand)
async def connect4_falling_rows(ctx: Context):
    await start_4_in_a_row(ctx, rows=6, columns=7, handler=Connect4FallingRowsHandler)



@connect4.child
@lightbulb.add_checks(lightbulb.guild_only)
@lightbulb.add_cooldown(30, 2, lightbulb.UserBucket)
@lightbulb.option("player2", "The second player - DEFAULT: you", type=hikari.Member, default=None)
@lightbulb.option("player1", "A player\nNOTE: ping like @user", type=hikari.Member)
@lightbulb.command("memory", "A game of Connect 4 where you can't distinguish the tokens")
@lightbulb.implements(commands.PrefixSubCommand, commands.SlashSubCommand)
async def connect4_falling_rows(ctx: Context):
    await start_4_in_a_row(ctx, rows=6, columns=7, handler=MemoryConnect4Handler)



@plugin.command
@lightbulb.add_checks(lightbulb.guild_only)
@lightbulb.add_cooldown(120, 2, lightbulb.UserBucket)
@lightbulb.option("player8", "The 8th @player", type=hikari.Member, default=None)
@lightbulb.option("player7", "The 7th @player", type=hikari.Member, default=None)
@lightbulb.option("player6", "The 6th @player", type=hikari.Member, default=None)
@lightbulb.option("player5", "The 5th @player", type=hikari.Member, default=None)
@lightbulb.option("player4", "The 4th @player", type=hikari.Member, default=None)
@lightbulb.option("player3", "The third @player", type=hikari.Member, default=None)
@lightbulb.option("player2", "The second @player", type=hikari.Member)
@lightbulb.option("player1", "The first @player", type=hikari.Member)
@lightbulb.command("onu", "starts a onu game")
@lightbulb.implements(commands.PrefixCommand, commands.SlashCommand)
async def onu(ctx: Context):
    players: Dict[int, hikari.Member] = {p.id: p for p in ctx._options.values() if not p is None}
    if not ctx.author.id in players.keys():
        return await ctx.respond("You can't start a game without you")
    for p_id, p in players.items():
        if p_id in onu_sessions:
            return await ctx.respond(
                f"There is currently a game running with {p.mention}, hence you can't start a game"
            )
        else:
            onu_sessions.add(p_id)
    onu = HikariOnu(players)
    try:
        await onu.start(ctx.bot, ctx)
    except Exception:
        log.error(traceback.format_exc())
    finally:
        for p_id in players.keys():
            onu_sessions.remove(p_id)



@plugin.command
@lightbulb.add_cooldown(60, 1, lightbulb.UserBucket)
@lightbulb.command("akinator", "I guess a character for you", aliases=["aki"], auto_defer=True)
@lightbulb.implements(commands.SlashCommand, commands.PrefixCommand)
async def akinator(ctx: Context):
    aki = AkinatorSI("en")
    await aki.start(ctx)



def load(inu: lightbulb.BotApp):
    global bot
    bot = inu
    inu.add_plugin(plugin)