import asyncio
import logging
import typing
from datetime import datetime, timedelta
from typing import *
from numpy import full, isin
import random

import aiohttp
import hikari
import lightbulb
import lightbulb.utils as lightbulb_utils
from io import BytesIO

from fuzzywuzzy import fuzz
from hikari import (
    ActionRowComponent, 
    Embed, 
    MessageCreateEvent, 
    embeds, 
    ResponseType, 
    TextInputStyle
)
from hikari.events import InteractionCreateEvent
from hikari.impl.special_endpoints import ActionRowBuilder, LinkButtonBuilder
from hikari.messages import ButtonStyle
from jikanpy import AioJikan
from lightbulb import OptionModifier as OM
from lightbulb import commands, context
from lightbulb.context import Context
import matplotlib
import matplotlib.pyplot as plt
from typing_extensions import Self
import pandas as pd
import seaborn as sn


from utils import (
    Colors, 
    Human, 
    Paginator, 
    Reddit, 
    Urban, 
    crumble,
    CurrentGamesManager,
)
from core import (
    BotResponseError, 
    Inu, 
    Table, 
    getLogger
)

log = getLogger(__name__)

plugin = lightbulb.Plugin("Statistics", "Shows statistics about the server")
bot: Inu


@plugin.command
@lightbulb.add_checks(lightbulb.checks.guild_only)
@lightbulb.add_cooldown(1, 1, lightbulb.UserBucket)
@lightbulb.option("app", "The application you want stats for")
@lightbulb.command("app", "Shows, which games are played in which guild", auto_defer=True)
@lightbulb.implements(commands.SlashCommand, commands.PrefixCommand)
async def application(ctx: Context):
    data = await CurrentGamesManager.fetch_activity_from_application(
        ctx.guild_id, 
        ctx.options.app, 
        datetime.now() - timedelta(days=30),
    )
    now = datetime.now()
    fake_data = []
    for i in range(1, 10): #
        fake_data.append(
            [now + timedelta(days=i), random.randint(0, 100), i-1] #
        )
    plt.style.use("dark_background")
    picture_in_bytes = BytesIO()
    df = pd.DataFrame(
        fake_data,
        columns=["date", "amount", "count"]
    )


    log.debug(f"\n{df}")
    # #Create combo chart
    fig, ax1 = plt.subplots()#figsize=(10,6)
    color = 'tab:green'
    # #bar plot creation
    # ax1.set_title('Avg Playtime in Minutes', fontsize=16)
    # ax1.set_xlabel('date', fontsize=16)
    # ax1.set_ylabel('minutes', fontsize=16)
    ax1 = sn.barplot(x='date', y='amount', data = df, palette='summer')
    ax1.set_xticklabels([f"{d.day}.{d.month}" for d in df["date"]], rotation=45, horizontalalignment='right')
    # # ax1.tick_params(axis='y')
    # #specify we want to share the same x-axis
    ax2 = ax1.twinx()
    # color = 'tab:red'
    # #line plot creation
    # #ax2.set_ylabel('Avg playtime', fontsize=16)
    ax2 = sn.lineplot(x='count', y='amount', data = df, color=color, sort=True)
    # ax2.tick_params(axis='y', color=color)


    # svm = sn.heatmap(df_cm, annot=True,cmap='coolwarm', linecolor='white', linewidths=1)
    figure = fig.get_figure()    
    #matplotlib.pyplot.show() 
    figure.savefig(picture_in_bytes, dpi=100)
    picture_in_bytes.seek(0)
    await ctx.respond(
        "data",
        attachment=picture_in_bytes
    )


@plugin.command
@lightbulb.add_checks(lightbulb.checks.guild_only)
@lightbulb.add_cooldown(60, 1, lightbulb.UserBucket)
@lightbulb.command("current-games", "Shows, which games are played in which guild", auto_defer=True)
@lightbulb.implements(commands.SlashCommand, commands.PrefixCommand)
async def current_games(ctx: Context):
    # constants

    coding_apps = ["Visual Studio Code", "Visual Studio", "Sublime Text", "Atom", "VSCode"]
    music_apps = ["Spotify", "Google Play Music", "Apple Music", "iTunes", "YouTube Music"]
    double_games = ["Rainbow Six Siege", "PUBG: BATTLEGROUNDS"]  # these will be removed from games too
    max_ranking_num: int = 20

    bot: Inu = plugin.bot
    embeds: List[hikari.Embed] = []

    # build embed for current guild
    guild: hikari.Guild = ctx.get_guild()  # type: ignore
    activity_records = await CurrentGamesManager.fetch_games(
        guild.id, 
        datetime.now() - timedelta(days=30)
    )
    activity_records.sort(key=lambda g: g['amount'], reverse=True)

    # get smallest first_occurrence
    first_occurrence = datetime.now()
    for record in activity_records:
        if record['first_occurrence'] < first_occurrence:
            first_occurrence = record['first_occurrence']

    embed = (
        hikari.Embed(
            title=f"{guild.name}",
        )
        .set_footer(f"all records I've taken since {first_occurrence.strftime('%d. %B')}")
    )

    field_value = ""

    # enuerate all games
    game_records = [g for g in activity_records if g['game'] not in [*coding_apps, *music_apps, *double_games]]
    for i, game in enumerate(game_records):
        if i > 150:
            break
        if i < max_ranking_num:
            field_value += f"{i+1}. {game['game']:<40}{str(timedelta(minutes=int(game['amount']*10)))}\n"
        else:
            field_value += f"{game['game']:<40}{str(timedelta(minutes=int(game['amount']*10)))}\n"
        if i % 10 == 9 and i:
            embed.add_field(
                f"{f'Top {i+1} games' if i <= max_ranking_num else 'Less played games'}", 
                f"```{field_value[:1010]}```", 
                inline=False
            )
            field_value = ""
    
    # add last remaining games
    if field_value:
        embed.add_field(
            f"Less played games", 
            f"```{field_value[:1010]}```", 
            inline=False
        )
    
    # add total played games/time
    embed = (
        embed
        .add_field("Total played games", str(len(game_records)), inline=False)
        .add_field("Total gaming time", str(timedelta(minutes=sum(int(game['amount']) for game in game_records)*10)) , inline=True)
    )

    # add total coding time
    coding_time = sum([g["amount"]*10 for g in activity_records if g['game'] in coding_apps])
    if coding_time:
        embed = embed.add_field(
            "Total coding time", 
            str(timedelta(minutes=int(coding_time))), 
            inline=True
        )

    # add total music time
    music_time = sum([g["amount"]*10 for g in activity_records if g['game'] in music_apps])
    if music_time:
        embed = embed.add_field(
            "Total music time", 
            str(timedelta(minutes=int(music_time))), 
            inline=True
        )

    embeds.append(embed)

    pag = Paginator(page_s=embeds)
    await pag.start(ctx)




def load(inu: lightbulb.BotApp):
    global bot
    bot = inu
    inu.add_plugin(plugin)

