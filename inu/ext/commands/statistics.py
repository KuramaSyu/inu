import asyncio
import logging
import typing
from datetime import datetime, timedelta
from typing import *
from numpy import full, isin
import random
from io import BytesIO


import aiohttp
import hikari
import lightbulb
import lightbulb.utils as lightbulb_utils
from pytz import timezone
from dataenforce import Dataset
from pytimeparse.timeparse import timeparse

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
#from matplotlib.dates import DateFormatter
from typing_extensions import Self
import pandas as pd
import seaborn as sn
import mplcyberpunk
from pandas.plotting import register_matplotlib_converters
from matplotlib.dates import DateFormatter, ConciseDateFormatter
import matplotlib.ticker as plticker 
import humanize

from utils import (
    Colors, 
    Human, 
    Paginator, 
    Reddit, 
    Urban, 
    crumble,
    CurrentGamesManager,
    TimezoneManager,
    SettingsManager,
    get_date_format_by_timedelta
)
from core import (
    BotResponseError, 
    Inu, 
    Table, 
    getLogger
)

log = getLogger(__name__)
register_matplotlib_converters()
plugin = lightbulb.Plugin("Statistics", "Shows statistics about the server")
bot: Inu

# mapping from guild to list with top games in it
top_games_cache = {}

async def maybe_raise_activity_tracking_disabled(guild_id: int):
    """Raises BotResponseError when guilds activity is not tracked"""
    if not await SettingsManager.fetch_activity_tracking(guild_id):
        raise BotResponseError(
            (
                "Activity tracking is disabled.\nTo enable it, execute this command:\n"
                "`/settings activity-tracking enable:True`\nOR use\n"
                "`/settings menu`, go to Activity tracking and disable it"
            ),
            ephemeral=True
        )

@plugin.command
@lightbulb.add_checks(lightbulb.checks.guild_only)
@lightbulb.add_cooldown(10, 1, lightbulb.UserBucket)
@lightbulb.option(
    "time", 
    "The time you want to get stats for - e.g. 30 days, 3 hours",
    default="9 days"
)
@lightbulb.command("week-activity", "Shows the activity of all week days", auto_defer=True)
@lightbulb.implements(commands.SlashCommand, commands.PrefixCommand)
async def week_activity(ctx: Context):
    await maybe_raise_activity_tracking_disabled(ctx.guild_id)
    seconds = timeparse(ctx.options.time)
    if not seconds:
        return await ctx.respond(
            f"Well - I've no idea what you mean with `{ctx.options.time}`"
            f"\n\nYou can try something like `5 days 1 hour` or `2 weeks 3 days` or `7000000 seconds`"
        )
    buffer, _ = await build_week_activity_chart(
        ctx.guild_id, 
        timedelta(seconds=seconds)
    )
    await ctx.respond(
        f"{ctx.get_guild().name}'s daily activity",  # type: ignore
        attachment=buffer,
    )



@plugin.command
@lightbulb.add_checks(lightbulb.checks.guild_only)
@lightbulb.add_cooldown(10, 1, lightbulb.UserBucket)
@lightbulb.option(
    "apps", 
    "Which apps? Seperate with commas (e.g. League of Legends, Overwatch)",
    default=None,
    autocomplete=True,
)
@lightbulb.option(
    "clean-colors",
    "Use distinguishable colors (clear color difference)",
    default=False,
    type=bool,
)
@lightbulb.option(
    "show-all",
    "[Yes | No] wether you see everyting (not only games). Default is No",
    default=False,
    type=bool,
)
@lightbulb.option(
    "time", 
    "The time you want to get stats for - e.g. 30 days, 3 hours",
    default="9 days"
)
@lightbulb.command("current-games", "Shows, which games are played in which guild", auto_defer=True)
@lightbulb.implements(commands.SlashCommand)
async def current_games(ctx: Context):
    
    await maybe_raise_activity_tracking_disabled(ctx.guild_id)
    seconds = timeparse(ctx.options.time)
    if not seconds:
        raise BotResponseError(
            (
                f"Well - I've no idea what you mean with `{ctx.options.time}`"
                f"\n\nYou can try something like `5 days 1 hour` or `2 weeks 3 days` or `7000000 seconds`"
                f"\nShort forms of time are also supported: `d`, `h`, `m`, `s`"
                f"\nIf you want to see the activity of the last 10 days, just use `10 days` or `10d`"
            ),
            ephemeral=True,
        )
    # constants
    timedelta_ = timedelta(seconds=seconds)
    show_only_games = not ctx.options["show-all"]
    remove_apps: List[str] = []
    apps = [app.strip() for app in ctx.options.apps.split(",")] if ctx.options.apps else None
    coding_apps = ["Visual Studio Code", "Visual Studio", "Sublime Text", "Atom", "VSCode", "Webflow"]
    music_apps = ["Spotify", "Google Play Music", "Apple Music", "iTunes", "YouTube Music"]
    double_games = ["Rainbow Six Siege", "PUBG: BATTLEGROUNDS"]  # these will be removed from games too
    remove_apps.extend(double_games)
    if show_only_games:
        remove_apps.extend([*coding_apps, *music_apps])
    max_ranking_num: int = 20

    async def build_embeds() -> List[Embed]:
        bot: Inu = plugin.bot
        embeds: List[hikari.Embed] = []
        # build embed for current guild
        guild: hikari.Guild = ctx.get_guild()  # type: ignore
        activity_records = await CurrentGamesManager.fetch_games(
            guild.id, 
            datetime.now() - timedelta_
        )
        activity_records.sort(key=lambda g: g['amount'], reverse=True)
        
        # set cache
        global top_games_cache
        top_games_cache[guild.id] = [g["game"] for g in activity_records[:24]]

        # get smallest first_occurrence
        first_occurrence = datetime.now()
        for record in activity_records:
            if record['first_occurrence'] < first_occurrence:
                first_occurrence = record['first_occurrence']

        embed = (
            hikari.Embed(
                title=f"{guild.name}",
            )
            .set_footer((

                f"all records I've taken since {first_occurrence.strftime('%d. %B')} "
                f"({Human.plural_('day', (datetime.now() - first_occurrence).days, True, 'days')})")
            )
        )

        field_value = ""
        embeds.append(embed)

        # enuerate all games
        # filter apps if these where specified
        if apps:
            game_records = [g for g in activity_records if g['game'] in apps]
        else:
            game_records = [g for g in activity_records if g['game'] not in remove_apps]
        for i, game in enumerate(game_records):
            if i > 150:
                break
            if i < max_ranking_num:
                field_value += f"{i+1}. {game['game']:<40}{str(timedelta(minutes=int(game['amount']*10)))}\n"
            else:
                field_value += f"{game['game']:<40}{str(timedelta(minutes=int(game['amount']*10)))}\n"
            if i % 10 == 9 and i:
                embeds[-1].description = (
                    f"{f'Top {i+1} games' if i <= max_ranking_num else 'Less played games'}"
                    f"```{field_value[:2000]}```"
                )
                embeds.append(hikari.Embed())
                field_value = ""
        
        # add last remaining games
        if field_value:
            embeds[-1].description = (
                f"Less played games"
                f"```{field_value[:2000]}```"
            )
        else:
            embeds.pop()
        
        # add total played games/time
        embeds[0] = (
            embeds[0]
            .add_field("Total played games", str(len(game_records)), inline=False)
            .add_field("Total gaming time", str(timedelta(minutes=sum(int(game['amount']) for game in game_records)*10)) , inline=True)
        )

        # add total coding time
        coding_time = sum([g["amount"]*10 for g in activity_records if g['game'] in coding_apps])
        if coding_time:
             embeds[0].add_field(
                "Total coding time", 
                str(timedelta(minutes=int(coding_time))), 
                inline=True
            )

        # add total music time
        music_time = sum([g["amount"]*10 for g in activity_records if g['game'] in music_apps])
        if music_time:
            embeds[0].add_field(
                "Total music time", 
                str(timedelta(minutes=int(music_time))), 
                inline=True
            )

        return embeds
    # prepare apps to fetch
    custom_time: datetime = datetime.now() - timedelta_
    # build embeds
    # if apps where specified, only specified will be showen
    embeds = await build_embeds()

    # apps are needed, so top games will be fetched
    if not apps:
        apps = [
            list(d.keys())[0]
            for d in
            await CurrentGamesManager.fetch_top_games(
                guild_id=ctx.guild_id, 
                since=custom_time,
                limit=6,
                remove_activities=remove_apps
            )
        ]
        # nothing was played during given time
        if not apps:
            raise BotResponseError(
                f"There were no games played in the last {humanize.naturaldelta(timedelta_)}."
            )
    # build picture
    try:
        picture_buffer, _ = await build_activity_graph(
            ctx.guild_id, 
            since=timedelta_,
            activities=apps,
            distinguishable_colors=ctx.options["clean-colors"]
        )
    except Exception as e:
        if not ctx.options.apps:
            raise e
        raise BotResponseError(
            "Something went wrong. Are you sure, that your game exists?",
            ephemeral=True,
        )
    # send image and afterwards the 
    #await ctx.respond(attachment=picture_buffer)
    pag = Paginator(
        page_s=embeds,
        first_message_kwargs={"attachment": picture_buffer}
    )
    await pag.start(ctx)




@current_games.autocomplete("apps")
async def tag_name_auto_complete(
    option: hikari.AutocompleteInteractionOption, 
    interaction: hikari.AutocompleteInteraction
) -> List[str]:
    if not isinstance(interaction.guild_id, int):
        return []
    games = top_games_cache.get(interaction.guild_id, [])
    if not games:
        dicts = await CurrentGamesManager.fetch_top_games(
            interaction.guild_id, 
            datetime.now() - timedelta(days=3), 
            limit=24
        )
        games = [list(d.keys())[0] for d in dicts]
        top_games_cache[interaction.guild_id] = games
    return games



async def build_activity_graph(
    guild_id: int,
    since: timedelta,
    activities: List[str],
    distinguishable_colors: bool = False,
) -> Tuple[BytesIO, Dataset]:

    picture_buffer = BytesIO()

    df = await CurrentGamesManager.fetch_activities(
        guild_id=guild_id, 
        since=datetime.now() - since,
        activity_filter=activities,
    )
    old_row_amount = len(df.index)
    # drop NaN values (r_timestamp bc of rounding issues)
    df.dropna(axis=0, how='any', subset=None, inplace=True)
    df.set_index(keys="r_timestamp", inplace=True)
    if old_row_amount != (new_row_amount := len(df.index)):
        log.waring(f"missing rows ({old_row_amount - new_row_amount}) in guild {guild_id}")
    
    since: datetime = df.index.min()
    until: datetime = df.index.max()
    df_timedelta: timedelta = until - since
   
    if df_timedelta >= timedelta(days=20):
        resample_delta = df_timedelta / 15
    elif df_timedelta >= timedelta(days=4.5):
        resample_delta = timedelta(days=1)
    else:
        resample_delta = df_timedelta / 20 
        if resample_delta.total_seconds() < 60*10:
            resample_delta = timedelta(minutes=10)

    # resampeling dataframe
    # group by game 
    # and resample hours to `resample_delta` and sum them up
    activity_series = df.groupby("game")["hours"].resample(resample_delta).sum()
    df_summarized = activity_series.to_frame().reset_index()

    # set before and after game to 0
    games = set(df_summarized["game"])
    last_date = max(df_summarized["r_timestamp"])

    def game_add_zero_r(game_name: str):
        nonlocal df_summarized
        game_df: pd.DataFrame = df_summarized[df_summarized["game"] == game_name]
        added_zero = True
        prev_date: datetime = game_df.iloc[0]["r_timestamp"]
        to_add: Dict[str, Any] = {
            "game": [],
            "hours": [],
            "r_timestamp": [],
        }
        def add_row(dt: Optional[datetime] = None):
            to_add["game"].append(game_name)
            to_add["hours"].append(0)
            to_add["r_timestamp"].append(dt or prev_date + resample_delta,)

        for _, row in game_df.iterrows():
            date = row["r_timestamp"]
            if date - prev_date > resample_delta and not added_zero:
                # missing row of a specific time
                # add this row with hours=0
                add_row()
                added_zero = True
            else:
                added_zero = False
            prev_date = date
        if last_date - prev_date >= resample_delta:
            add_row()
        else:
            pass
        df_summarized = pd.concat([df_summarized, pd.DataFrame(to_add)])

    min_date = min(df_summarized["r_timestamp"])
    def game_add_zero_l(game_name: str):
        nonlocal df_summarized
        game_df: pd.DataFrame = df_summarized[df_summarized["game"] == game_name]
        added_zero = True
        prev_date: datetime = game_df.iloc[-1]["r_timestamp"]
        to_add: Dict[str, Any] = {
            "game": [],
            "hours": [],
            "r_timestamp": [],
        }
        def add_row(dt: Optional[datetime] = None):
            to_add["game"].append(game_name)
            to_add["hours"].append(0)
            to_add["r_timestamp"].append(dt or prev_date - resample_delta,)

        for _, row in reversed([*game_df.iterrows()]):
            date = row["r_timestamp"]
            if prev_date - date > resample_delta and not added_zero:
                # missing row of a specific time
                # add this row with hours=0
                add_row()
                added_zero = True
            else:
                added_zero = False
            prev_date = date
        if prev_date - min_date >= resample_delta:
            # log.debug(f"add first entry for {game_name}")
            add_row()
        else:
            pass
            # log.debug(f"{game_name} {last_date} - {prev_date} < {resample_delta}")
        df_summarized = pd.concat([df_summarized, pd.DataFrame(to_add)])

    for game in games:
        game_add_zero_r(game)
        game_add_zero_l(game)

    df_summarized.reset_index(inplace=True)

    color_paletes = ["magma_r", "rocket_r", "mako_r"]
    clean_color_paletes = ["Set3", "Set2"]
    color = random.choice(clean_color_paletes) if distinguishable_colors else random.choice(color_paletes)
    plt.style.use("cyberpunk")
    sn.set_palette("bright")
    sn.set_context("notebook", font_scale=1.4, rc={"lines.linewidth": 1.5})

    
    #Create chart
    fig, ax1 = plt.subplots(figsize=(21,9))
    fig.set_tight_layout(True)
    sn.despine(offset=20)
    ax: matplotlib.axes.Axes = sn.lineplot(
        x='r_timestamp', 
        y='hours', 
        data=df_summarized,
        hue="game", 
        legend="full", 
        markers=False,
        palette=color,
        ax=ax1,
    )

    # style chart
    mplcyberpunk.add_glow_effects(ax=ax)
    #ax.set_xticklabels([f"{d[:2]}.{d[3:5]}" for d in ax.get_xlabel()], rotation=45, horizontalalignment='right')
    ax.set_ylabel("Hours")
    ax.set_xlabel("")

    date_format = get_date_format_by_timedelta(df_timedelta)

    tz = await TimezoneManager.fetch_timezone(guild_or_author_id=guild_id)
    date_form = DateFormatter(date_format, tz=tz)

    # set Locator
    ax.xaxis.set_major_formatter(date_form)
    X_LABLE_AMOUNT: int = 12  # about
    base = round(df_timedelta.days / X_LABLE_AMOUNT, 0)  # base have to be .0, otherwise not matching with plot peaks
    if base > 0:
        loc = plticker.MultipleLocator(base=base)  # this locator puts ticks at regular intervals (when float is .0)
        ax.xaxis.set_major_locator(loc)
    # ax.figure.autofmt_xdate(rotation=45)
    
    # save chart
    figure = fig.get_figure()    
    figure.savefig(picture_buffer, dpi=100)
    picture_buffer.seek(0)
    return picture_buffer, df_summarized


async def build_week_activity_chart(guild_id: int, since: timedelta) -> Tuple[BytesIO, Dataset]:
    df: pd.DataFrame = await CurrentGamesManager.fetch_total_activity_per_day(
        guild_id,
        datetime.now() - since
    )

    #rolling_mean_days = 3
    mean_hours = df["hours"].median()
    
    # mean hours total
    df['mean'] = mean_hours

    # mean hours per <rolling_mean_days>
    df_dt_range = df['datetime'].max() - df['datetime'].min()
    cols = ['mean', 'hours']
    if since >= timedelta(days=40):
        rolling_mean = int(df_dt_range.days / 12)
        df['dynamic mean'] = df['hours'].rolling(window=rolling_mean, center=True).mean()
        df['dynamic mean'].interpolate(inplace=True)
        df['dynamic mean'].fillna(value=mean_hours, inplace=True)
        cols.append('dynamic mean')
        # df["dynamic mean"] = df["hours"].resample(df_dt_range / 8)

    # fill in NaN values with total mean


    # melt dataframe, that seaplot can plot all lines together
    df = df.melt(id_vars =['datetime'], value_vars =cols, var_name ='line kind')

    # sort by datetime column
    df.sort_values(by='datetime', inplace=True)

    # style preparations
    color_paletes = ["magma", "rocket", "mako"]
    plt.style.use("cyberpunk")
    sn.set_palette("bright")
    sn.set_context("notebook", font_scale=1.4, rc={"lines.linewidth": 1.5})

    #Create graph
    fig, ax1 = plt.subplots(figsize=(21,9))
    fig.set_tight_layout(True)
    sn.despine(offset=20)
    picture_buffer = BytesIO()

    ax = sn.lineplot(
        x = "datetime", 
        y = 'value', 
        data = df,
        palette = random.choice(color_paletes),  
        ax=ax1,
        hue="line kind",
        legend="brief",
    )

    X_LABLE_AMOUNT: int = 20  # about
    base = round(df_dt_range.days / X_LABLE_AMOUNT, 0)  # base have to be .0, otherwise not matching with plot peaks
    base = 1 if base < 1 else base
    loc = plticker.MultipleLocator(base=base)  # this locator puts ticks at regular intervals (when float is .0)
    ax.xaxis.set_major_locator(loc)
    ax.figure.autofmt_xdate(rotation=45)

    mplcyberpunk.add_glow_effects(ax=ax)
    ax.set_ylabel("Hours")
    ax.set_xlabel("")
    date_format = get_date_format_by_timedelta(df_dt_range)
    date_form = DateFormatter(date_format)
    ax.xaxis.set_major_formatter(date_form)
    
    # save graph
    figure = fig.get_figure()    
    figure.savefig(picture_buffer, dpi=100)
    picture_buffer.seek(0)
    return picture_buffer, df



def load(inu: lightbulb.BotApp):
    global bot
    bot = inu
    inu.add_plugin(plugin)

