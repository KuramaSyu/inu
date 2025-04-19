from copy import deepcopy
from datetime import datetime, timedelta
from typing import *
import random
from io import BytesIO
import traceback
import asyncio
import hikari
import lightbulb

import aiohttp
import hikari
import lightbulb
from dataenforce import Dataset
from pytimeparse.timeparse import timeparse
import re

from hikari import (
    Embed,
    Snowflake, 
)
from hikari import (
    Embed,
    ResponseType, 
    TextInputStyle,
    Permissions
)
from hikari.impl import MessageActionRowBuilder
from lightbulb import Context, Loader, Group, SubGroup, SlashCommand, invoke
from lightbulb.prefab import sliding_window
from hikari.impl import MessageActionRowBuilder
from lightbulb import Context, Loader, Group, SubGroup, SlashCommand, invoke
from lightbulb.prefab import sliding_window
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import PathPatch
from matplotlib.path import Path
from matplotlib.axes import Axes
import colorcet as cc
import pandas as pd
import seaborn as sn
import mplcyberpunk
from pandas.plotting import register_matplotlib_converters
from matplotlib.dates import DateFormatter
import matplotlib.ticker as plticker 
import humanize
from tabulate import tabulate
from numpy import datetime64, timedelta64, uint8

from utils import (
    Human, 
    Paginator, 
    CurrentGamesManager,
    TimezoneManager,
    SettingsManager,
    get_date_format_by_timedelta,
    ts_round,
    Games,
    YES, NO, YES_NO
)
from core import (
    BotResponseError, 
    Inu, 
    Table, 
    getLogger,
    get_context,
    InuContext
)


log = getLogger(__name__)

loader = lightbulb.Loader()
bot: Inu
register_matplotlib_converters()


# mapping from guild to list with top games in it
top_games_cache = {}
RC_PARAMS = deepcopy(plt.rcParams)
def switch_backend():
    """
    Method for switching backend between statistics and latex
    """
    matplotlib.use("agg")
    plt.rcParams.update(RC_PARAMS)


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


async def game_autocomplete(ctx: lightbulb.AutocompleteContext) -> None:
    interaction = ctx.interaction
    guild_id = interaction.guild_id
    assert guild_id is not None
    games = top_games_cache.get(interaction.guild_id, [])
    if not games:
        dicts = await CurrentGamesManager.fetch_top_games(
            guild_id,
            datetime.now() - timedelta(days=3), 
            limit=24
        )
        games = [list(d.keys())[0] for d in dicts]
        top_games_cache[interaction.guild_id] = games
    await ctx.respond(games)


@loader.command
class CurrendGames(
    SlashCommand,
    name="current-games",
    description="Shows, which games are played in your guild",
    dm_enabled=False,
    default_member_permissions=None,
    hooks=[sliding_window(60, 5, "user")]
):
    time = lightbulb.string(
        "time", 
        "The time you want to get stats for - e.g. 30 days, 3 hours", 
        default="14 days"
    )  # Option 1
    show_all = lightbulb.string(
        "show-all", 
        "Shows all apps, not only games (e.g. music, programming)", 
        choices=YES_NO,
        default=NO
    )  # Option 2
    clean_colors = lightbulb.string(
        "clean-colors", 
        "Use distinguishable colors (clear color difference)", 
        choices=YES_NO,
        default=NO
    )  # Option 3
    apps = lightbulb.string(
        "apps",
        "Which apps? Seperate with commas (e.g. League of Legends, Overwatch)",
        default=None,
        autocomplete=game_autocomplete,
    ) # Option 4
    app_amount = lightbulb.integer(
        "app-amount",
        "The amount of apps you want to see",
        default=6,
        min_value=1,
        max_value=24,
    ) # Option 5


    @invoke
    async def callback(self, _ctx: lightbulb.Context, ctx: InuContext):
        if ctx.guild_id is None:
            raise BotResponseError("This command can only be used in a guild", True)
        
        try:
            await ctx.defer()
        except Exception:
            log.error(traceback.format_exc())
        await maybe_raise_activity_tracking_disabled(ctx.guild_id)
        seconds = timeparse(self.time)
        if not seconds:
            raise BotResponseError(
                (
                f"Well - I've no idea what you mean with `{self.time}`"
                f"\n\nYou can try something like `5 days 1 hour` or `2 weeks 3 days` or `7000000 seconds`"
                f"\nShort forms of time are also supported: `d`, `h`, `m`, `s`"
                f"\nIf you want to see the activity of the last 10 days, just use `10 days` or `10d`"
                ),
                ephemeral=True,
            )
        # constants
        app_amount = self.app_amount
        timedelta_ = timedelta(seconds=seconds)
        show_only_games = self.show_all == NO
        remove_apps: List[str] = []
        apps = [app.strip() for app in self.apps.split(",")] if self.apps else None
        coding_apps = Games.PROGRAMMING
        music_apps = Games.MUSIC
        double_games = Games.DUPLEX_GAMES  # these will be removed from games too
        remove_apps.extend(double_games)
        if show_only_games:
            remove_apps.extend([*coding_apps, *music_apps])
        max_ranking_num: int = 20

        async def build_embeds() -> List[Embed]:
            embeds: List[hikari.Embed] = []
            # build embed for current guild
            guild: hikari.Guild = ctx.get_guild()  # type: ignore
            activity_records = await CurrentGamesManager.fetch_games(
                guild.id, 
                datetime.now() - timedelta_
            )
            if activity_records is None:
                raise BotResponseError(
                    f"No games were played in the last {humanize.naturaldelta(timedelta_)}",
                    ephemeral=True
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
            timedelta_days = (datetime.now() - first_occurrence).days+1
            embed = (
                hikari.Embed(
                    title=f"{guild.name}",
                )

            )
            if timedelta_days > 5:
                embed.set_footer((
                    f"all records I've taken since {first_occurrence.strftime('%d. %B')} "
                    f"({Human.plural_('day', timedelta_days, True, 'days')})"
                ))

            field_value = []
            embeds.append(embed)

            # enuerate all games
            # filter apps if these where specified
            if apps:
                game_records = [g for g in activity_records if g['game'] in apps]
            else:
                game_records = [g for g in activity_records if g['game'] not in remove_apps]

            maxcolwidths = [33, 16]
            tabulate_kwargs = {
                "headers": ["App", "Time"],
                "tablefmt": "rounded_outline",
                "maxcolwidths": maxcolwidths,
                "maxheadercolwidths": maxcolwidths,
            }
            for i, game in enumerate(game_records):
                if i > 150:
                    break
                delta = timedelta(minutes=float(game['amount']*10))
                field_value.append(
                    [
                        f"{i+1:02d}. {Human.short_text(game['game'], maxcolwidths[0]-4, '..', False)}", 
                        re.sub(r"[ ]?day[s]?", "d", str(delta))
                    ]
                )

                if i % 10 == 9 and i:
                    title = f"{f'Top {i+1} games' if i <= max_ranking_num else 'Less played games'}"
                    table = tabulate(field_value, **tabulate_kwargs)
                    embeds[-1].description = (
                        
                        f"{title}\n```{table[:2040]}```"
                    )
                    embeds.append(hikari.Embed())
                    field_value = []
            
            # add last remaining games
            if field_value:
                title = f"Less played games"
                table = tabulate(field_value, **tabulate_kwargs)
                embeds[-1].description = (
                    f"{title}\n```{table[:2040]}```"
                )
            else:
                embeds.pop()
            
            if len(embeds) == 0:
                raise BotResponseError("No games where played durring the given period of time", ephemeral=True)
            
            # calculate times for music, coding and gaming
            music_time = timedelta(minutes=int(
                sum([g["amount"]*10 for g in activity_records if g['game'] in music_apps])
            ))
            coding_time = timedelta(minutes=int(
                sum([g["amount"]*10 for g in activity_records if g['game'] in coding_apps])
            ))
            # for gaming, use prefiltered `game_records`
            gaming_time = timedelta(minutes=int(
                sum(int(game['amount']) for game in game_records)*10
            ))
            
            # add total played games/time
            embeds[0] = (
                embeds[0]
                .add_field("Total played games", str(len(game_records)), inline=False)
                .add_field("Total gaming time", str(gaming_time) , inline=True)
            )

            # add total coding time
            if coding_time:
                embeds[0].add_field(
                    "Total coding time", 
                    str(coding_time),
                    inline=True
                )

            # add total music time
            if music_time:
                embeds[0].add_field(
                    "Total music time", 
                    str(music_time), 
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
                    limit=app_amount,
                    remove_activities=remove_apps
                )
            ]
            # nothing was played during given time
            if not apps:
                raise BotResponseError(
                    f"No games were played in the last {humanize.naturaldelta(timedelta_)}."
                )
        # build picture
        try:
            picture_buffer, _ = await GameViews().build_activity_graph(
                ctx.guild_id, 
                since=timedelta_,
                activities=apps,
                distinguishable_colors=self.clean_colors == "Yes",
            )
        except Exception as e:
            if not self.app_amount:
                raise e
            raise BotResponseError(
                "Something went wrong. Are you sure, that your game exists?",
                ephemeral=True,
            )
        pag = Paginator(
            page_s=embeds,
            first_message_kwargs={"attachment": picture_buffer}
        )
        await pag.start(ctx)



@loader.command
class WeekActivity(
    SlashCommand,
    name="week-activity",
    description="Shows the activity of all week days",
    dm_enabled=False,
    default_member_permissions=None,
    hooks=[sliding_window(5, 1, "user")]
):
    time = lightbulb.string(
        "time",
        "The time you want to get stats for - e.g. 30 days, 3 hours",
        default="9 days"
    )  # Option 1
    show_all = lightbulb.string(
        "show-all",
        "Shows all apps, not only games (e.g. music, programming)",
        choices=YES_NO,
        default=NO
    )  # Option 2

    @invoke
    async def callback(self, _: lightbulb.Context, ctx: InuContext):
        await ctx.defer()
        guild_id = ctx.guild_id
        assert guild_id is not None
        await maybe_raise_activity_tracking_disabled(guild_id)
        seconds = timeparse(self.time)
        if not seconds:
            return await ctx.respond(
                f"Well - I've no idea what you mean with `{self.time}`"
                f"\n\nYou can try something like `5 days 1 hour` or `2 weeks 3 days` or `7000000 seconds`"
            )
        show_all = self.show_all == "Yes"
        buffer, __ = await GameViews().build_week_activity_chart(
            guild_id, 
            timedelta(seconds=seconds),
            remove=[*Games.MUSIC, *Games.PROGRAMMING, *Games.DUPLEX_GAMES] if not show_all else []
        )
        await ctx.respond(
            f"{ctx.get_guild().name}'s daily activity",  # type: ignore
            attachment=buffer,
        )



class GameViews:
    """
    A class for rendering game activity graphs
    """
    def highlight_weekends(self, ax: Axes, df_summarized: pd.DataFrame, y_position: float, height: float) -> None:
        """
        Highlights the weekends in the graph as bar above the x-axis
        """
        min_date: pd.Series = df_summarized['r_timestamp'].min()
        max_date: pd.Series = df_summarized['r_timestamp'].max()
        dates: pd.DatetimeIndex = pd.date_range(start=min_date, end=max_date, freq='D')
        
        for date in dates:
            if date.weekday() >= 5:  # 5 and 6 represent Saturday and Sunday
                start: float = ax.get_xaxis().convert_units(date - pd.Timedelta(days=1))
                end: float = ax.get_xaxis().convert_units(date)
                width: float = end - start
                
                y_min, y_max = [0.95, 1]
                height: float = y_max - y_min
                #y_position = ax.get_ylim()[0] - ax.get_ylim()[0]*0.05
                
                path: Path = self.rounded_rectangle(start, y_position, width, height, radius=0)
                patch: PathPatch = PathPatch(path, facecolor='lightgray', alpha=0.2, edgecolor='none')
                ax.add_patch(patch)
        
        ax.autoscale()

    def highlight_weekend_labels(self, ax: Axes) -> None:
        """
        highlights the x-axis labels of the weekends
        """
        for label in ax.get_xticklabels():
            date: datetime = mdates.num2date(label.get_position()[0])
            if date.weekday() >= 5:  # 5 and 6 represent Saturday and Sunday
                label.set_color('mediumslateblue')


    async def build_activity_graph(
        self,
        guild_id: int,
        since: timedelta,
        activities: List[str],
        distinguishable_colors: bool = False,
    ) -> Tuple[BytesIO, Dataset]:
        """
        Builds an activity graph for `/current-games` based on the provided parameters.

        Parameters:
        - guild_id (int): The ID of the guild.
        - since (timedelta): The time period to consider for the graph.
        - activities (List[str]): The list of activities to include in the graph.
        - distinguishable_colors (bool): Whether to use distinguishable colors for the graph.

        Returns:
        - Tuple[BytesIO, Dataset]: A tuple containing the graph image as a BytesIO object and the summarized dataset.

        """

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
            log.warning(f"missing rows ({old_row_amount - new_row_amount}) in guild {guild_id}")

        X_LABLE_AMOUNT: int = 15  # about
        base = None
        df_start: datetime = df.index.min()
        until: datetime = df.index.max()
        df_timedelta: timedelta = until - df_start

        if df_timedelta >= timedelta(days=20):
            resample_delta = df_timedelta / 20
        elif df_timedelta >= timedelta(days=4.5):
            resample_delta = timedelta(days=1)
        else:
            resample_delta = df_timedelta / 13
        
            if resample_delta.total_seconds() < 60*10:
                resample_delta = timedelta(minutes=10)

        def normalize_delta(delta: timedelta, resample_rate: timedelta):
            """normalize the timedelta, to make the chart better readable"""
            references = [
                {timedelta(hours=6): timedelta(seconds=300)},
                {timedelta(hours=12): timedelta(hours=0.25)},
                {timedelta(days=1): timedelta(hours=0.5)},
                {timedelta(days=3): timedelta(hours=1)},
                {timedelta(days=5): timedelta(hours=3)},
                {timedelta(days=10): timedelta(hours=6)},
                {timedelta(days=20): timedelta(hours=12)}
            ]
            nearest = [list(references[0].keys())[0], list(references[0].values())[0]]
            difference = abs(delta.total_seconds() - nearest[0].total_seconds())
            for entry in references:
                for key, value in entry.items():
                    if (diff := abs(delta.total_seconds() - key.total_seconds())) < difference:
                        difference = diff
                        nearest = [key, value]
            return ts_round(resample_rate, nearest[1])
        
        resample_delta = normalize_delta(df_timedelta, resample_delta)

        # resampeling dataframe
        # group by game 
        # and resample hours to `resample_delta` and sum them up
        activity_series: pd.Series = df.groupby("game")["hours"].resample(resample_delta).sum()
        df_summarized: pd.DataFrame = activity_series.to_frame().reset_index()
        # normalize timestamps to avoid uneven tick rates
        df_summarized["r_timestamp"] = df_summarized["r_timestamp"].dt.round(resample_delta)

        # set before and after game to 0
        games = set(df_summarized["game"])
        last_date = max(df_summarized["r_timestamp"])

        def game_add_zero_r(game_name: str):
            """Adds entries to the dataframe, so that chart is 0 instead of missing"""
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
            """Adds entries to the dataframe, so that chart is 0 instead of missing"""
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
                add_row()
            else:
                pass
            df_summarized = pd.concat([df_summarized, pd.DataFrame(to_add)])

        for game in games:
            # make line graphs start at 0 and end at 0
            game_add_zero_r(game)
            game_add_zero_l(game)

        df_summarized.reset_index(inplace=True)

        # color and style preparations
        color_paletes = ["magma_r", "rocket_r", "mako_r"]
        clean_color_paletes = [sn.color_palette(cc.glasbey, n_colors=len(activities))]#["Set3", "Set2"]
        color = random.choice(clean_color_paletes) if distinguishable_colors else random.choice(color_paletes)
        
        switch_backend()
        plt.style.use("cyberpunk")
        sn.set_palette("bright")
        sn.set_context("notebook", font_scale=1.4, rc={"lines.linewidth": 1.5})

        
        #Create chart
        fig, ax1 = plt.subplots(figsize=(21,9))
        ax1.set_xticks(df_summarized['r_timestamp'])
        fig.set_tight_layout(True)
        sn.despine(offset=20)
        ax: matplotlib.axes.Axes = sn.lineplot(
            x='r_timestamp', 
            y='hours', 
            data=df_summarized,
            hue="game", 
            hue_order=activities,
            legend="auto", 
            markers=False,
            palette=color,
            ax=ax1,
        )

        # style chart
        mplcyberpunk.add_glow_effects(ax=ax)

        # set date formatter with guild tz
        date_format = get_date_format_by_timedelta(df_timedelta)
        tz = await TimezoneManager.fetch_timezone(guild_or_author_id=guild_id)
        date_form = DateFormatter(date_format, tz=tz)
        ax.xaxis.set_major_formatter(date_form)

        ax.set_ylabel("Hours")
        ax.set_xlabel(f"Date (rounded to {humanize.naturaldelta(resample_delta)})",)

        # Highlight weekend areas and labels
        y_min, y_max = ax.get_ylim()
        highlight_height = (y_max - y_min) * 0.05  # 5% of the plot height
        highlight_position = y_min + (y_max - y_min) * 1  # 100% above the bottom of the plot
        self.highlight_weekends(ax, df_summarized, highlight_position, highlight_height)
        if resample_delta < timedelta(days=23):
            self.highlight_weekend_labels(ax)
        
        # save chart
        figure = fig.get_figure()    
        figure.savefig(picture_buffer, dpi=100)
        picture_buffer.seek(0)
        return picture_buffer, df_summarized


    async def build_week_activity_chart(
            self,
            guild_id: int, 
            since: timedelta,
            remove: List[str],
        ) -> Tuple[BytesIO, Dataset]:
        """
        Builds a week activity chart for `/week-activity` based on the given parameters.

        Args:
            guild_id (int): The ID of the guild.
            since (timedelta): The time period to consider for the chart.
            remove (List[str]): A list of activities to ignore.

        Returns:
            Tuple[BytesIO, Dataset]: A tuple containing the chart image as BytesIO and the dataset used for the chart.
        """
        log.debug(f"remove: {remove}")
        df: pd.DataFrame = await CurrentGamesManager.fetch_total_activity_per_day(
            guild_id,
            datetime.now() - since,
            ignore_activities=remove,
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

        switch_backend()
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



    def rounded_rectangle(self, x: float, y: float, width: float, height: float, radius: float) -> Path:
        """Generates a rounded rectangle path"""
        path_data: List[Tuple[uint8, Tuple[float, float]]] = [
            (Path.MOVETO, (x + radius, y)),
            (Path.LINETO, (x + width - radius, y)),
            (Path.CURVE4, (x + width, y)),
            (Path.CURVE4, (x + width, y + radius)),
            (Path.LINETO, (x + width, y + height - radius)),
            (Path.CURVE4, (x + width, y + height)),
            (Path.CURVE4, (x + width - radius, y + height)),
            (Path.LINETO, (x + radius, y + height)),
            (Path.CURVE4, (x, y + height)),
            (Path.CURVE4, (x, y + height - radius)),
            (Path.LINETO, (x, y + radius)),
            (Path.CURVE4, (x, y)),
            (Path.CURVE4, (x + radius, y)),
            (Path.CLOSEPOLY, (x + radius, y))
        ]
        
        codes, verts = zip(*path_data)
        return Path(verts, codes)



