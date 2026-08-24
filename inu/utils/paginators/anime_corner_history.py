import asyncio
import re
import traceback
from collections import Counter
from copy import deepcopy
from datetime import datetime, timedelta
from io import BytesIO
from typing import *

import hikari
import matplotlib
import matplotlib.pyplot as plt
import mplcyberpunk
import pandas as pd
import seaborn as sn
from hikari import ComponentInteraction, Embed
from humanize import naturaldelta
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from pandas.plotting import register_matplotlib_converters
from tabulate import tabulate

from inu.core import InuContext, getLogger
from inu.utils import Colors
from inu.utils.db import AnimeCornerHistoryManager, get_season

from .base import Paginator

log = getLogger(__name__)
register_matplotlib_converters()


# Maximum width the anime overview table is allowed to span. The bot embeds
# get truncated aggressively beyond ~80 chars in Discord's mobile clients,
# so we cap the rendered table there by pre-truncating the longest field
# (the anime name).
TABLE_MAX_WIDTH = 52

# After accounting for the fixed columns (header text + cell padding + the
# borders and " │ " separators the rounded_outline tablefmt always emits),
# the anime-name cell is allowed 53 characters. This was measured empirically
# against tabulate settings that render exactly 80 characters wide.
ANIME_NAME_MAX_LEN = 42

# Seasons in chronological order (winter comes first because it's the
# Dec(prev)/Jan/Feb quarter that opens the year).
SEASON_ORDER = ("winter", "spring", "summer", "fall")


def _season_first_monday(year: int, season: str) -> datetime:
    """Return the first Monday that falls inside ``season`` of ``year``.

    Seasons are the standard Anime Corner ranges:
        winter = Dec (prev year) / Jan / Feb
        spring = Mar / Apr / May
        summer = Jun / Jul / Aug
        fall   = Sep / Oct / Nov

    Returns a ``datetime`` at midnight of the first Monday in that range.
    """
    # Anchor months: the calendar month that always belongs to the season
    # regardless of hemisphere or split-year weirdness.
    anchor_month = {"winter": 1, "spring": 3, "summer": 6, "fall": 9}[season]
    # Scan up to 14 days from the 1st of the anchor month until we hit a
    # Monday. 14 covers the longest possible gap (1st can be any weekday).
    from datetime import date as _date
    first = _date(year, anchor_month, 1)
    for offset in range(14):
        candidate = first + timedelta(days=offset)
        if candidate.weekday() == 0:  # Monday
            return datetime.combine(candidate, datetime.min.time())
    # Should be unreachable.
    return datetime.combine(first, datetime.min.time())


def _next_season_first_monday(year: int, season: str) -> datetime:
    """Return the first Monday of the season that immediately follows
    ``(year, season)``.

    Used to derive the inclusive upper bound when the user requests a
    specific season: ``since`` is the first Monday of the requested season
    and ``until`` is the first Monday of the next one.
    """
    idx = SEASON_ORDER.index(season)
    if idx == len(SEASON_ORDER) - 1:
        # fall → winter, year bumps by 1
        return _season_first_monday(year + 1, "winter")
    return _season_first_monday(year, SEASON_ORDER[idx + 1])


def parse_season_arg(value: str) -> Tuple[datetime, datetime, Optional[str], Optional[int]]:
    """Resolve the slash-command ``season`` option to a date range.

    Args:
        value: one of:
            - ``"current"`` → the season that contains "now"
            - ``"<season> <year>"`` e.g. ``"spring 2026"`` → that season

    Returns:
        ``(since, until, season, year)`` where ``since``/``until`` bracket
        the season (both at midnight) and ``season``/``year`` identify the
        selected season (or ``None`` when ``value == "current"``).

    Raises:
        ValueError when ``value`` does not match either shape.
    """
    normalized = (value or "").strip().lower()
    if not normalized or normalized == "current":
        now = datetime.now()
        season = get_season(now)
        # Match the convention used by list_available_seasons(): December
        # belongs to the *following* year's winter season.
        year = now.year + 1 if now.month == 12 else now.year
        since = _season_first_monday(year, season)
        return since, now, season, year

    parts = normalized.split()
    if len(parts) != 2:
        raise ValueError(
            f"Invalid season {value!r}. Expected 'current' or '<season> <year>' "
            f"(e.g. 'spring 2026')."
        )
    season_str, year_str = parts
    if season_str not in SEASON_ORDER:
        raise ValueError(
            f"Unknown season {season_str!r}. Expected one of: "
            f"{', '.join(SEASON_ORDER)}."
        )
    try:
        year = int(year_str)
    except ValueError as exc:
        raise ValueError(
            f"Invalid year {year_str!r}. Expected an integer."
        ) from exc
    since = _season_first_monday(year, season_str)
    until = _next_season_first_monday(year, season_str)
    return since, until, season_str, year


def _truncate_anime_name(name: str, max_len: int = ANIME_NAME_MAX_LEN) -> str:
    """Truncate ``name`` so it fits inside the overview table cell.

    Adds an ellipsis to make the cut obvious. We prefer to truncate the
    *name* (rather than wrap) because wrapped names make the embed taller
    and push the rest of the page below the Discord embed limits.
    """
    if len(name) <= max_len:
        return name
    return name[: max_len - 1] + "…"


def _table_total_width(table_text: str) -> int:
    """Returns the width of the widest line in the rendered table.

    Used by :meth:`AnimeCornerHistoryPaginator._build_summary_embed` to
    double-check the truncation actually kept the table within the
    80-char budget.
    """
    if not table_text:
        return 0
    return max(len(line) for line in table_text.splitlines())


class AnimeCornerHistoryPaginator(Paginator):
    """A paginator which visualises the historical `Anime of the Week` rankings
    from Anime Corner.

    The first page is an embed with information about the time range and the
    number of weeks/animes covered. Pages 2..N each show an embed for the
    ranked anime paired with a matplotlib line graph of its rank history
    (lower rank = better; rank 1 is drawn from the top y-down).
    """

    GRID_MAX_LINES = 12  # cap on how many anime get their own chart

    def __init__(
        self,
        since: "datetime",
        until: "datetime",
        ctx: "InuContext",
        **kwargs,
    ):
        self.since = since
        self.until = until
        self.df: "pd.DataFrame" = None  # populated in start()
        self._animes: List[Dict[str, Any]] = []
        self._graphs: Dict[int, BytesIO] = {}

        super().__init__(
            page_s=[Embed(title="Anime of the Week History", description="Loading...")],
            timeout=60 * 5,
            disable_paginator_when_one_site=True,
            disable_search_btn=True,
            **kwargs,
        )
        self.ctx = ctx

    # ------------------------------------------------------------------ start

    async def start(self, ctx: "InuContext" = None) -> hikari.Message:
        ctx = ctx or self.ctx
        self.ctx = ctx

        # Load the requested history data.
        self.df = await AnimeCornerHistoryManager.fetch_for_chart(self.since)
        if not self.df.empty and self.until is not None:
            # Exclude the first day of the next season.
            self.df = self.df[self.df["date"] < self.until]

        # Build the sns plot from whatever data we have inside the requested
        # range. If the range is empty (or only partially covered), the chart
        # is rendered from the available subset without falling back to the
        # entire history table.
        # Pick a single "dominant" season to label the overview with and use
        # as the origin for the X-axis week numbers. If the data spans more
        # than one season, the dominant one is used and the X-axis still
        # numbers weeks relative to its first week.
        self._season_info = self._resolve_season_info(self.df)

        self._pages = [self._build_summary_embed()]

        if not self.df.empty:
            # Ignore rows without IDs when grouping anime by ID.
            appearance_counts = (
                self.df.dropna(subset=["mal_id"])
                .groupby("mal_id")["name"]
                .agg(lambda s: s.value_counts().idxmax())
            )
            # Count appearances using only rows with IDs.
            counts = (
                self.df.dropna(subset=["mal_id"])
                .groupby("mal_id").size()
                .sort_values(ascending=False)
            )
            # Select the IDs with the most appearances.
            top_ids = list(counts.head(self.GRID_MAX_LINES).index)
            for mal_id in top_ids:
                self._animes.append({
                    "mal_id": int(mal_id),
                    "name": appearance_counts[mal_id],
                })
            # Select rows without IDs for the name-based fallback.
            for name in (
                self.df[self.df["mal_id"].isna()]["name"]
                .value_counts()
                .head(self.GRID_MAX_LINES - len(self._animes)).index
            ):
                if name in (a["name"] for a in self._animes):
                    continue
                self._animes.append({"mal_id": None, "name": name})

        for anime in self._animes:
            self._pages.append(self._build_anime_embed(anime))

        # first page gets an overview chart
        self._graphs[0] = await asyncio.to_thread(self._build_overview_graph)

        # Seed the download fields so the overview chart ships with page 1.
        if self._graphs.get(0) is not None:
            self._download = self._graphs[0].getvalue()
            self._download_name = self._attachment_name()

        # generate per-anime graphs up front in the background
        for index, anime in enumerate(self._animes, start=1):
            asyncio.create_task(self._render_graph_for(index, anime))

        return await super().start(ctx)

    # ----------------------------------------------------------------- helpers

    def _resolve_season_info(self, df: "pd.DataFrame") -> Dict[str, Any]:
        """Pick the dominant season from ``df`` and compute the dates that
        bracket it.

        Returns a dict with:
            ``season``       - "winter" / "spring" / "summer" / "fall"
            ``year``         - the dominant season's calendar year
            ``season_start`` - the first Monday of that season (date)
            ``title``        - human readable title for the embed
        Returns sensible fallbacks when ``df`` is empty.
        """
        empty: Dict[str, Any] = {
            "season": None,
            "year": None,
            "season_start": None,
            "title": None,
        }
        if df is None or df.empty:
            return empty

        seasons = [get_season(d) for d in df["date"]]
        dominant_season, _ = Counter(seasons).most_common(1)[0]
        # The dominant year is the year of the latest row tagged with that
        # season (so a split-year season like "winter" picks the year of its
        # January tail rather than its December head).
        years_for_season = [
            d.year for d, s in zip(df["date"], seasons) if s == dominant_season
        ]
        dominant_year = max(years_for_season)
        season_start = _season_first_monday(dominant_year, dominant_season)

        # Single-season data renders as "Anime of Fall 2026"; multi-season
        # data falls back to a date range so the title still makes sense.
        unique_seasons = set(zip(seasons, [d.year for d in df["date"]]))
        if len(unique_seasons) == 1:
            title = f"Anime of {dominant_season.title()} {dominant_year}"
        else:
            earliest = df["date"].min().to_pydatetime()
            latest = df["date"].max().to_pydatetime()
            title = (
                f"Anime of {earliest:%b %Y} → {latest:%b %Y}"
            )
        return {
            "season": dominant_season,
            "year": dominant_year,
            "season_start": season_start,
            "title": title,
        }

    def _build_summary_embed(self) -> Embed:
        season_info = self._season_info or {}
        title = season_info.get("title") or "Anime of the Week History"
        embed = Embed(
            title=title,
            description=(
                f"Anime Corner Top 10 Anime of the Week history "
                f"between **{self.since:%Y-%m-%d}** and **{self.until:%Y-%m-%d}**"
            ),
        )
        embed.color = Colors.random_blue()
        if self.df.empty:
            embed.description += (
                "\n\n_No data yet: the AnimeCorner task hasn't written any"
                " ranking rows yet. New entries will show up here automatically"
                " the next time it runs._"
            )
            embed.set_footer(text=f"page 1/1")
            return embed

        weeks = int(self.df["date"].nunique())
        animes_tracked = int(self.df["name"].nunique())

        # ---- top animes (with average rank, name truncated to fit table) ----
        # Copy the data before changing it.
        ranked = self.df.copy()
        # Use the name when a database row has no MyAnimeList ID.
        ranked["_key"] = ranked["mal_id"].fillna(ranked["name"])
        # Remove rows without a usable key or rank.
        ranked = ranked.dropna(subset=["_key", "rank"])
        if not ranked.empty:
            avg_rank_by_key = (
                ranked.groupby("_key")["rank"].mean().sort_values().head(10)
            )
            top_names = ranked.drop_duplicates("_key").set_index("_key")["name"]
            rows_for_table = [
                (
                    _truncate_anime_name(str(top_names.get(key, f"[{key}]"))),
                    f"{avg:.1f}",
                )
                for key, avg in avg_rank_by_key.items()
            ]
            table = tabulate(
                rows_for_table,
                headers=["Anime", "Avg"],
                tablefmt="rounded_outline",
                # Cap to properly display it on discord
                maxcolwidths=[ANIME_NAME_MAX_LEN, 4],
            )
            if _table_total_width(table) > TABLE_MAX_WIDTH:
                log.warning(
                    f"Anime of the Week overview table is "
                    f"{_table_total_width(table)} chars wide (target "
                    f"<= {TABLE_MAX_WIDTH}); truncation may need tweaking."
                )
            embed.add_field(
                "Most weeks in Top 10",
                f"```{table[:1024]}```",
                inline=False,
            )

        # ---- date / week metadata ----
        earliest_date = self.df["date"].min().to_pydatetime()
        latest_date = self.df["date"].max().to_pydatetime()
        season_start = season_info.get("season_start")
        if season_start is not None:
            # week_index mirrors the X-axis numbering on the overview chart.
            week_index = max(
                1,
                (pd.Timestamp(latest_date) - pd.Timestamp(season_start)).days // 7 + 1,
            )
            current_week_value = (
                f"{latest_date:%Y-%m-%d}  (W{week_index})"
            )
        else:
            current_week_value = latest_date.strftime("%Y-%m-%d")

        embed.add_field("First week", earliest_date.strftime("%Y-%m-%d"), inline=True)
        embed.add_field("Current week", current_week_value, inline=True)
        embed.add_field("Weeks tracked", str(weeks), inline=True)
        embed.add_field("Animes tracked", str(animes_tracked), inline=True)

        # always surface the available data range in the footer so it never
        # looks empty to the user
        earliest = self.df["date"].min()
        latest = self.df["date"].max()
        embed.set_footer(text=(
            f"page 1/{len(self._pages)} · "
            f"data: {earliest:%Y-%m-%d} → {latest:%Y-%m-%d}"
        ))
        return embed

    def _build_anime_embed(self, anime: Dict[str, Any]) -> Embed:
        page_index = self._animes.index(anime) + 1
        name = anime["name"]
        mal_id = anime["mal_id"]
        embed = Embed(title=f"#{name}")
        if mal_id:
            embed.url = f"https://myanimelist.net/anime/{mal_id}"
        embed.color = Colors.random_blue()
        embed.description = (
            f"Historical `Anime of the Week` rank over the last "
            f"{naturaldelta(self.until - self.since)}."
        )
        if mal_id is None:
            embed.description += (
                "\n_No MyAnimeList id could be resolved – the chart is built from the raw name._"
            )
        embed.set_footer(text=f"page {page_index + 1}/{len(self._pages)}")
        return embed

    # ---------------------------------------------------- graph generation ---

    async def _render_graph_for(self, page_index: int, anime: Dict[str, Any]):
        buffer = await asyncio.to_thread(self._build_anime_graph, anime)
        if buffer is not None:
            self._graphs[page_index] = buffer

    def _history_view(self) -> "HistoryView":
        """Returns a configured :class:`HistoryView` for the current data."""
        return HistoryView(
            df=self.df,
            season_info=self._season_info or {},
            top_n=self.GRID_MAX_LINES,
            overview_rank_cap=20,
        )

    def _build_anime_graph(self, anime: Dict[str, Any]) -> Optional[BytesIO]:
        return self._history_view().build_anime_graph(anime)

    def _build_overview_graph(self) -> Optional[BytesIO]:
        result = self._history_view().build_overview_graph()
        return result[0] if result is not None else None

    # --------------------------------------------------------------- attachment

    async def send(self, content, interaction: Optional[ComponentInteraction] = None, **kwargs):
        """Attaches the current page's graph (if available) and lets `Paginator`
        continue with the regular send."""
        if self._pages:
            buffer = self._graphs.get(self._position)
            if buffer is not None and not kwargs.get("attachment"):
                kwargs["attachment"] = hikari.Bytes(buffer.getvalue(), self._attachment_name())
        return await super().send(content, interaction=interaction, **kwargs)

    @property
    def download(self) -> Optional[bytes]:
        # Preserve raw bytes so the overview image is included in the first response.
        value = self._download
        if isinstance(value, (bytes, bytearray)):
            return bytes(value)
        if callable(value):
            return value(self)
        if isinstance(value, str):
            return value
        if value is True:
            return self._pages_to_str()
        return None

    def _attachment_name(self) -> str:
        if self._position == 0:
            return "anime-of-the-week-overview.png"
        if self._position - 1 < len(self._animes):
            anime = self._animes[self._position - 1]
            safe = re.sub(r"[^a-zA-Z0-9_-]", "_", anime["name"])[:40] or "anime"
            return f"rank-history-{safe}.png"
        return "anime-of-the-week.png"


class HistoryView:
    """Reusable chart builder for the Anime-of-the-Week history.

    Mirrors :class:`inu.ext.commands.statistics.GameViews`: every chart is a
    small method that returns the PNG buffer (and, for the overview, the
    summarised dataset) and delegates the styling to a handful of
    sub-components.
    """

    # Keep an isolated copy of plt.rcParams so we don't mutate the global
    # style when we tweak context settings, like the GameViews implementation.
    _RC_PARAMS = deepcopy(plt.rcParams)

    def __init__(
        self,
        df: "pd.DataFrame",
        season_info: Dict[str, Any],
        top_n: int = 12,
        overview_rank_cap: int = 20,
    ) -> None:
        self.df = df
        self.season_info = season_info or {}
        self.top_n = top_n
        self.overview_rank_cap = overview_rank_cap

    # ----------------------------------------------------------- sub-components

    def _switch_backend(self) -> None:
        """Restore matplotlib's agg backend + the captured rcParams snapshot."""
        matplotlib.use("agg")
        plt.rcParams.update(self._RC_PARAMS)

    def _apply_style(self, line_width: float = 2.0, font_scale: float = 1.2) -> None:
        """Apply the cyberpunk/bright seaborn style used across the bot."""
        self._switch_backend()
        plt.style.use("cyberpunk")
        sn.set_palette("bright")
        sn.set_context(
            "notebook",
            font_scale=font_scale,
            rc={"lines.linewidth": line_width},
        )

    def _label_week_axis(self, df: "pd.DataFrame") -> Tuple[Any, str]:
        """Returns the X column and X-axis label for the given dataframe.

        When a season start is known the column is a synthetic 1-based
        "week in <season> <year>" index so labels stay compact (``W1, W2,
        ...``); otherwise we fall back to the raw date column.
        """
        season_start = self.season_info.get("season_start")
        if season_start is not None and "date" in df.columns:
            # Copy the data before adding the week index.
            df = df.copy()
            dates = pd.to_datetime(df["date"])
            start = pd.Timestamp(season_start)
            # Compare calendar days, not time zones, to avoid DST shifts.
            if dates.dt.tz is not None and start.tzinfo is None:
                start = start.tz_localize(dates.dt.tz)
            elif dates.dt.tz is None and start.tzinfo is not None:
                dates = dates.dt.tz_localize(start.tzinfo)
            if dates.dt.tz is not None:
                start = start.tz_convert(dates.dt.tz)
            dates = dates.dt.tz_localize(None)
            start = start.tz_localize(None)
            # Add whole-number week indexes relative to the season start.
            df["week_index"] = (
                (dates.dt.normalize() - start.normalize()).dt.days // 7 + 1
            ).astype(int)
            season = self.season_info.get("season")
            year = self.season_info.get("year")
            label = f"Week in {season.title()} {year}" if season else "Season week"
            return df["week_index"], label
        return pd.to_datetime(df["date"]), "Week"

    @staticmethod
    def _y_for_rank(rank: Any, y_top: int) -> Any:
        """Map a rank value to the y-data that puts rank 1 at the top.

        Rank ``1`` is the best anime and is plotted at the largest ``y``
        value (``y_top``), rank ``y_top`` is the worst and is plotted at
        ``y=1``. The transformation is linear so lines stay straight.
        """
        return y_top + 1 - rank

    def _invert_rank_axis(self, ax: "Axes", max_rank: int, cap: Optional[int] = None) -> None:
        """Rank 1 on top, tick every rank down to ``min(max_rank, cap)`` (or
        ``max_rank`` when ``cap`` is ``None``).

        Charts must plot ``_y_for_rank(rank, y_top)`` so rank 1 sits at the
        top. Tick labels are mapped back to the original rank numbers so
        users see ``1`` at the top and ``y_top`` at the bottom.
        """
        y_top = max(max_rank, 1)
        if cap is not None:
            y_top = min(y_top, cap)
        ax.set_yticks(range(1, y_top + 1))
        ax.set_yticklabels([str(r) for r in range(y_top, 0, -1)])
        ax.set_ylim(0.5, y_top + 0.5)

    def _annotate_points(
        self,
        ax: "Axes",
        x: Any,
        y: Any,
        prefix: str = "#",
        label_values: Optional[Any] = None,
    ) -> None:
        """Annotate every point on the line with its rank.

        ``y`` carries the coordinates to anchor the annotation on; pass
        ``label_values`` separately when the labels need to differ from
        the plotted y (e.g. when ``y`` has been negated to put rank 1 at
        the top of the axis).
        """
        if label_values is None:
            label_values = y
        for xi, yi, li in zip(x, y, label_values):
            ax.annotate(
                f"{prefix}{int(li)}",
                (xi, yi),
                textcoords="offset points",
                xytext=(0, 8),
                ha="center",
                color="white",
                fontsize=9,
            )

    def _add_glow(self, ax: "Axes") -> None:
        try:
            mplcyberpunk.add_glow_effects(ax=ax)
        except Exception:
            log.debug("mplcyberpunk glow effects unavailable")

    def _save(self, fig: "Figure") -> BytesIO:
        buffer = BytesIO()
        fig.tight_layout()
        fig.savefig(buffer, dpi=110)
        plt.close(fig)
        buffer.seek(0)
        return buffer

    # --------------------------------------------------------------- charts

    def build_overview_graph(self) -> Optional[Tuple[BytesIO, "pd.DataFrame"]]:
        """One chart, every top anime's rank history as a separate line.

        Uses :func:`seaborn.lineplot` with ``hue="name"`` so the colour
        palette is centralised the same way :class:`GameViews` does it.
        """
        # Copy the source data before preparing the overview chart.
        df = self.df.copy() if self.df is not None else None
        if df is None or df.empty:
            return None
        required = {"mal_id", "name", "rank", "date"}
        if not required.issubset(df.columns):
            return None
        # Use a name as the key when a row has no MyAnimeList ID.
        df["_anime_key"] = df["mal_id"].fillna(df["name"])
        # Remove rows without a usable key or rank.
        df = df.dropna(subset=["_anime_key", "rank"])
        if df.empty:
            return None

        # Prefer the best rank, then the number of appearances.
        candidates = (
            df.groupby("_anime_key")["rank"]
            .agg(["min", "size"])
            .query("min <= 10")
            .sort_values(by=["min", "size"], ascending=[True, False])
        )
        top_keys = candidates.head(self.top_n).index
        # Keep only the anime selected for the overview.
        df = df[df["_anime_key"].isin(top_keys)].copy()
        if df.empty:
            return None
        name_lookup = (
            df.groupby("_anime_key")["name"]
            .agg(lambda s: s.value_counts().idxmax())
        )
        # Use the most common spelling for each anime.
        df["name"] = df["_anime_key"].map(name_lookup).astype(str)
        LEGEND_NAME_MAX_LEN = 40
        # Keep legend labels readable.
        df["name"] = df["name"].map(
            lambda n: (n[: LEGEND_NAME_MAX_LEN - 1] + "…")
            if len(n) > LEGEND_NAME_MAX_LEN else n
        )
        # Sort points chronologically for the line chart.
        df.sort_values(by="date", inplace=True)

        # Keep the anime ordered by rank on its final recorded week.
        last_week = (
            df.drop_duplicates("_anime_key", keep="last")
            .sort_values("rank", kind="stable")
        )
        # Match the legend order to the final week.
        top_keys = last_week["_anime_key"].tolist()
        hue_order = last_week["name"].tolist()

        x_values, x_label = self._label_week_axis(df)

        self._apply_style(line_width=2.0, font_scale=1.2)
        fig, ax = plt.subplots(figsize=(21, 7))
        sn.despine(offset=10)

        # Compute the y-axis cap BEFORE transforming rank so the helper
        # has a clean reference frame to invert around.
        max_rank = int(df["rank"].max())
        cap = self.overview_rank_cap
        y_top = min(max(max_rank, 1), cap)

        palette = sn.color_palette("husl", n_colors=len(top_keys))
        # Keep confidence bands disabled and use dots for each point.
        # Map rank to y so rank 1 ends up at the top of the axis.
        # Store the transformed rank for plotting.
        df["_plot_rank"] = self._y_for_rank(df["rank"], y_top)
        sn.lineplot(
            x=x_values,
            y="_plot_rank",
            hue="name",
            hue_order=hue_order,
            data=df,
            ax=ax,
            marker="o",
            sort=True,
            palette=palette,
            errorbar=None,
            legend="brief",
        )

        self._invert_rank_axis(ax, max_rank, cap=cap)
        ax.set_xlabel(x_label)
        ax.set_ylabel("Rank (1 = best)")
        ax.set_title(
            self.season_info.get("title")
            or "Anime of the Week – rank history (top animes)"
        )
        ax.grid(True, alpha=0.25)
        ax.legend(
            loc="upper left",
            bbox_to_anchor=(1.01, 1.0),
            fontsize=14,
        )
        self._add_glow(ax)
        return self._save(fig), df

    def build_anime_graph(
        self,
        anime: Dict[str, Any],
    ) -> Optional[BytesIO]:
        """Single-anime rank history. Same colour as the overview for visual
        consistency, single ``seaborn.lineplot`` call.
        """
        df = self.df
        if df is None or df.empty:
            return None
        if anime.get("mal_id") is not None:
            # Filter by ID when an ID is available.
            df = df[df["mal_id"] == anime["mal_id"]].copy()
        else:
            # Filter by raw name when no ID is available.
            df = df[df["name"] == anime["name"]].copy()
        if df.empty or df["rank"].isna().all():
            return None
        # Sort the selected anime points chronologically.
        df.sort_values(by="date", inplace=True)

        x_values, x_label = self._label_week_axis(df)

        # No cap for per-anime charts — show every rank the anime actually
        # reached so brief drops below the top 10 are visible.
        max_rank = int(df["rank"].max())
        y_top = max(max_rank, 1)

        self._apply_style(line_width=2.5, font_scale=1.2)
        fig, ax = plt.subplots(figsize=(15, 7))
        sn.despine(offset=10)

        # Map rank to y so rank 1 ends up at the top of the axis.
        plot_y = self._y_for_rank(df["rank"], y_top)
        # Add the transformed rank without mutating the source data.
        df_for_plot = df.assign(_plot_rank=plot_y)
        sn.lineplot(
            x=x_values,
            y="_plot_rank",
            data=df_for_plot,
            ax=ax,
            marker="o",
            sort=True,
            errorbar=None,
            legend=False,
        )
        # Annotate against the *transformed* y so labels land on the points,
        # but show the original (positive) rank in the label.
        self._annotate_points(ax, x_values, plot_y, label_values=df["rank"])

        self._invert_rank_axis(ax, max_rank)
        ax.set_xlabel(x_label)
        ax.set_ylabel("Rank (1 = best)")
        ax.set_title(str(anime["name"]))
        ax.grid(True, alpha=0.25)
        self._add_glow(ax)
        return self._save(fig)
