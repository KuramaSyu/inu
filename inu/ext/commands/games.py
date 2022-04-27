from pprint import pformat
import traceback
from typing import *
from typing import Union
import asyncio
from datetime import datetime, timedelta

import hikari
import lightbulb
import lightbulb.context as context
from lightbulb import commands
from lightbulb.commands import OptionModifier as OM

from utils.games.connect_four_handler import Connect4Handler
from utils.games import HikariOnu
from utils.db import CurrentGamesManager
from utils import AkinatorSI, Paginator
from core import getLogger, Inu

log = getLogger(__name__)

Context = Union[context.SlashContext, context.PrefixContext]
plugin = lightbulb.Plugin("Game Commands", "Extends the commands with commands all about games")
onu_sessions = set()

async def start_4_in_a_row(ctx: Context, rows: int, columns: int):
    if not ctx._options.get("player2"):
        ctx._options["player2"] = ctx.member
    
    h = Connect4Handler(ctx.options.player1, ctx.options.player2, rows=rows, columns=columns)
    msg = await h.start(ctx)
    log.debug(msg)
    await msg.add_reaction("🔁")
    try:
        await plugin.bot.wait_for(
            hikari.ReactionAddEvent,
            timeout=15*60,
            predicate=lambda e: (
                    e.message_id == msg.id
                    and e.user_id in [ctx.options.player1.id, ctx.options.player2.id]
                    and e.emoji_name == "🔁"
            )
        )
        await start_4_in_a_row(ctx, rows=rows, columns=columns)
    except asyncio.TimeoutError:
        pass
    await msg.remove_all_reactions()


@plugin.command
@lightbulb.add_checks(lightbulb.guild_only)
@lightbulb.add_cooldown(30, 2, lightbulb.UserBucket)
@lightbulb.option("player2", "The second player - DEFAULT: you", type=hikari.Member, default=None)
@lightbulb.option("player1", "A player\nNOTE: ping like @user", type=hikari.Member)
@lightbulb.command("connect4", "starts a Connect 4 game", aliases=["con4", "connect-4", "4-in-a-row", "4inarow"])
@lightbulb.implements(commands.PrefixCommandGroup, commands.SlashCommandGroup)
async def connect4(ctx: Context):
    await start_4_in_a_row(ctx, rows=6, columns=7)

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
@lightbulb.command("square", "starts a Connect 4 game", aliases=["8x8"])
@lightbulb.implements(commands.PrefixSubCommand, commands.SlashSubCommand)
async def connect4_8by8(ctx: Context):
    await start_4_in_a_row(ctx, rows=8, columns=8)
    
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
    if not ctx.author.id not in players.keys():
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


@plugin.command
@lightbulb.add_cooldown(60, 1, lightbulb.UserBucket)
@lightbulb.command("current-games", "Shows, which games are played in which guild", auto_defer=True)
@lightbulb.implements(commands.SlashCommand, commands.PrefixCommand)
async def current_games(ctx: Context):
    def dict_to_sorted_dict_by_value(d: Dict[Any, Any]) -> Dict[Any, Any]:
        return {k: v for k, v in sorted(d.items(), key=lambda x: x[1], reverse=True)}

    bot: Inu = plugin.bot
    embeds: List[hikari.Embed] = []

    for _, guild in bot.cache.get_guilds_view().items():
        games = await CurrentGamesManager.fetch_games(
            guild.id, 
            datetime.now() - timedelta(days=30)
        )
        games.sort(key=lambda g: g['amount'], reverse=True)

        log.debug(pformat(games))
        
        embeds.append(
            hikari.Embed(
                title=f"{guild.name}",
                description="\n".join(
                    f"{game['game']}: {str(timedelta(minutes=int(game['amount']*10)))}" for game in games
                )
            )
            .set_footer("Records form last 30 days")
            .add_field("Total played games", str(len(games)), inline=True)
            .add_field("Total played time", str(timedelta(minutes=sum(int(game['amount']) for game in games)*10)) , inline=True)
        )
    pag = Paginator(page_s=embeds)
    await pag.start(ctx)


def load(bot: lightbulb.BotApp):
    bot.add_plugin(plugin)