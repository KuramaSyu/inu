
from typing import *
import asyncio
import logging
from datetime import datetime, timedelta, time, date
import traceback

import lightbulb
import hikari
import apscheduler
from apscheduler.triggers.interval import IntervalTrigger
from humanize import naturaldelta
from inu.core import Table, getLogger, Inu, stopwatch
from inu.utils import (
    Reddit,
    AnimeCornerAPI,
    AnimeCornerPaginator2,
    AnimeCornerView,
    build_anime_corner_url,
)
from inu.utils.db import AnimeCornerHistoryManager, get_season
from inu.utils.db.anime_corner_history import MAX_FAILURE_COUNT



log = getLogger(__name__)
METHOD_SYNC_TIME: int = 60*60*6
SYNCING = False
TARGET_TIME = time(18,00)
TRIGGER_NAME = "Anime Corner Trigger"
bot: Inu = Inu.instance
METHOD_SYNC_TIME = bot.conf.commands.anime_corner_sync_time * 60 * 60  # type: ignore
BACKFILL_LOOKBACK = timedelta(weeks=52)  # 1 year worth of weekly rankings
BACKFILL_TRIGGER_NAME = "Anime Corner Backfill Trigger"



plugin = lightbulb.Loader()

@plugin.listener(hikari.StartedEvent)
async def load_tasks(event: hikari.StartedEvent):
    global SYNCING
    if SYNCING:
        return
    SYNCING = True
    await asyncio.sleep(3)
    # 1. Make sure the latest ranking is fetched and stored (normal sync flow).
    await method()
    # 2. Backfill any missing weeks from the last `BACKFILL_LOOKBACK`.
    await _backfill_missing_weeks()
    logging.getLogger('apscheduler.executors.default').setLevel(logging.WARNING)
    await init_method()
    await defer_trigger_to_time()


async def defer_trigger_to_time(target_time: time | None = TARGET_TIME):
    target_datetime = None
    if target_time is not None:
        current_time = datetime.now().time()
        target_datetime = datetime.combine(date.today(), target_time)

        if target_datetime.time() < current_time:
            target_datetime += timedelta(days=1)

        wait_time = (target_datetime - datetime.now()).total_seconds()
        log.info(f"Waiting for {naturaldelta(timedelta(seconds=wait_time))} to shedule the {TRIGGER_NAME}", prefix="task")
    trigger = IntervalTrigger(seconds=METHOD_SYNC_TIME, start_date=target_datetime)
    bot.scheduler.add_job(method, trigger)


async def init_method():
    pass

@stopwatch(
    note=f"[CACHE] Task: Fetching Anime Corner Ranking (Reddit + Anime Corner)",
    cache_threshold=timedelta(microseconds=1)
)
async def method():
    url = None
    try:
        submission = await Reddit.get_anime_of_the_week_post()
        # build pag + API
        pag = AnimeCornerPaginator2()
        pag.submission = submission
        pag.title = submission.title
        url = pag.anime_corner_url
        api = AnimeCornerAPI()

        await api.fetch_ranking(url)  # fetches the ranking from Anime Corner
        await pag.fetch_matches()  # fetches every single anime match

        # persist the Anime Corner rankings for the history graph
        await _store_history(pag)
    except Exception as e:
        log.error(
            f"[CACHE] Error while fetching Anime Corner ranking with URL `{url}`\n",
            f"{traceback.format_exc() or traceback.format_exception_only(type(e), e)}",
            prefix="task"
        )


async def _store_history(pag: AnimeCornerPaginator2) -> None:
    """Saves the fetched Anime Corner ranking into the history table. duplicates are prevented
    """
    ranking_date: datetime = pag.submission.created_utc or datetime.now()
    # AniList-style: only keep the date, drop the time
    ranking_date = datetime(ranking_date.year, ranking_date.month, ranking_date.day)
    if await AnimeCornerHistoryManager.has_entry_for(ranking_date):
        log.debug(f"Anime Corner history already has entries for {ranking_date.date()}", prefix="task")
        return
    if not pag.anime_matches:
        log.warning("`AnimeCornerPaginator2` has no `anime_matches` – skipping history write", prefix="task")
        return
    for match in pag.anime_matches:
        try:
            await AnimeCornerHistoryManager.add(
                name=match["name"],
                score=float(match["score"]),
                rank=int(match["rank"]),
                date=ranking_date,
            )
        except Exception:
            log.warning(
                f"Failed to persist AnimeCorner ranking for {match.get('name')!r}",
                f"\n{traceback.format_exc()}",
                prefix="task",
            )




@stopwatch(
    note=f"[CACHE] Task: Backfilling missing Anime Corner weekly rankings",
    cache_threshold=timedelta(microseconds=1),
)
async def _backfill_missing_weeks() -> None:
    """Find every week start within the last ``BACKFILL_LOOKBACK`` that has no
    history row, fetch its Anime Corner ranking, and persist it.

    The function groups missing weeks by ``(season, year)`` (because Anime
    Corner uses a per-season ``week-N`` counter) and asks the API for the
    highest ``N`` that actually contains data to avoid probing URLs that don't
    exist.
    """
    try:
        # One-time data migration: a previous version wrote the season as
        # "autumn"; the Anime Corner URL contract (and the SQL CHECK
        # constraint) want "fall". This UPDATE is idempotent — re-runs are a
        # no-op once the value is correct.
        try:
            table = Table("anime_of_the_week_history")
            migrated = await table.fetch(
                "UPDATE anime_of_the_week_history "
                "SET season = 'fall' "
                "WHERE season = 'autumn' "
                "RETURNING id"
            )
            if migrated:
                log.info(
                    f"Migrated {len(migrated)} historical row(s) from "
                    f"season='autumn' to 'fall'.",
                    prefix="task",
                )
        except Exception:
            log.debug("Autumn->fall migration skipped:\n" + traceback.format_exc())

        now = datetime.now()
        since = now - BACKFILL_LOOKBACK
        missing_weeks = await AnimeCornerHistoryManager.missing_weeks(
            since=since, until=now
        )
        if not missing_weeks:
            log.info(
                "Anime Corner backfill: no missing weeks in the last "
                f"{BACKFILL_LOOKBACK.days} days.",
                prefix="task",
            )
            return
        log.info(
            f"Anime Corner backfill: {len(missing_weeks)} missing week(s) to fetch "
            f"between {since:%Y-%m-%d} and {now:%Y-%m-%d}.",
            prefix="task",
        )

        # Map each missing week-start to its (season, year).
        grouped: Dict[Tuple[str, int], List[datetime]] = {}
        for week_start in missing_weeks:
            # week_start may be a pandas Timestamp or a datetime; coerce.
            if hasattr(week_start, "to_pydatetime"):
                week_start = week_start.to_pydatetime()
            season = get_season(week_start)
            year = week_start.year
            # December rolls over into the next year's winter; shift if so.
            if week_start.month == 12:
                year = week_start.year + 1
            grouped.setdefault((season, year), []).append(week_start)

        api = AnimeCornerAPI()
        total_inserted = 0
        total_errors = 0
        total_skipped_absent = 0
        total_skipped_beyond_season = 0
        # Sort to get deterministic, chronological logs.
        for (season, year), weeks in sorted(grouped.items()):
            weeks_sorted = sorted(weeks)
            log.info(
                f"Scrapping {len(weeks_sorted)} missing week(s) for "
                f"`{season}-{year}`.",
                prefix="task",
            )
            # Optimization: only probe URLs we haven't covered yet.
            # `max_known_week_index` is the highest week_index we ever
            # inserted into `anime_of_the_week_known_weeks` for this
            # `(season, year)` regardless of state, so a season that's
            # been running for weeks costs only a handful of probes
            # instead of all 14.
            start_week = await AnimeCornerHistoryManager.max_known_week_index(
                season=season, year=year,
            )
            max_week = await api.find_latest_week_with_ranking(
                season, year, start_week=start_week,
            )
            if max_week is None:
                log.warning(
                    f"No weekly rankings were ever published for "
                    f"`{season}-{year}` (website returned empty for every probed week).",
                    prefix="task",
                )
                total_errors += len(weeks_sorted)
                continue
            # Weeks already confirmed absent (URL came back empty once and we
            # persisted it) so we shouldn't re-probe them on every run.
            absent_indices = set(
                await AnimeCornerHistoryManager.known_absent_week_indices(
                    season=season, year=year,
                )
            )
            for week_start in weeks_sorted:
                # Map week_start to a 1-based season-week index. We compute it
                # by linear probing in chronological order: for any missing
                # week-start date, walk through the season's known weeks in
                # `find_latest_week_with_ranking` order — but those are
                # calendar dates we don't know server-side. So we instead use
                # the delta between consecutive missing weeks (or the season
                # start) to assign a stable index.
                week_index = _season_week_index(season, year, week_start)
                if week_index is None:
                    # week_start is before the season's base date. The PK
                    # of `anime_of_the_week_known_weeks` is on
                    # `week_index`, so we can't persist a meaningful
                    # absent marker for this row. Just skip — the
                    # ``BACKFILL_LOOKBACK`` upper bound keeps this rare.
                    log.debug(
                        f"Skipping week {week_start:%Y-%m-%d}: before the "
                        f"start of {season}-{year}.",
                        prefix="task",
                    )
                    continue
                if week_index > max_week:
                    # The season ended at week <max_week>; week_index is
                    # past the end and we already know the URL is empty
                    # (`find_latest_week_with_ranking` returned the first
                    # empty one as the break condition). Persist the
                    # marker so we don't re-list this week as missing on
                    # every subsequent run.
                    log.debug(
                        f"Skipping week {week_start:%Y-%m-%d}: beyond known "
                        f"weeks for {season}-{year} (latest is week "
                        f"{max_week}).",
                        prefix="task",
                    )
                    try:
                        await AnimeCornerHistoryManager.mark_week_absent(
                            season=season, year=year, week_index=week_index,
                        )
                        absent_indices.add(week_index)
                    except Exception:
                        log.warning(
                            "Failed to persist absent marker for "
                            f"{season}-{year} w{week_index:02d}:\n"
                            + traceback.format_exc(),
                            prefix="task",
                        )
                    total_skipped_beyond_season += 1
                    continue
                if week_index in absent_indices:
                    log.debug(
                        f"Skipping week {week_start:%Y-%m-%d} "
                        f"({season}-{year} w{week_index:02d}): already "
                        "marked as absent in a previous backfill.",
                        prefix="task",
                    )
                    total_skipped_absent += 1
                    continue
                url = build_anime_corner_url(season, year, week_index)
                log.debug(
                    f"Fetching Anime Corner ranking for {season}-{year} "
                    f"week {week_index:02d} ({week_start:%Y-%m-%d}) from {url}.",
                    prefix="task",
                )
                ranking: List[Dict[str, Any]] = []
                fetch_failed = False
                try:
                    ranking = await api.fetch_ranking(url)
                except Exception:
                    log.warning(
                        f"Failed to fetch `{url}`:\n{traceback.format_exc()}",
                        prefix="task",
                    )
                    fetch_failed = True
                if fetch_failed or not ranking:
                    # The URL returned zero rows (or crashed). Don't mark
                    # it absent immediately — Anime Corner occasionally
                    # returns empty rows for a known good URL during
                    # scraping hiccups, and a season that genuinely ends
                    # at week N would otherwise keep us re-fetching the
                    # same week N+1 on every run. Increment
                    # ``failure_count`` instead; once it crosses
                    # ``MAX_FAILURE_COUNT`` the row is flipped to
                    # ``absent`` (handled inside mark_week_pending).
                    try:
                        new_count = await AnimeCornerHistoryManager.mark_week_pending(
                            season=season, year=year, week_index=week_index,
                        )
                    except Exception:
                        log.warning(
                            "Failed to persist pending/failure marker for "
                            f"{season}-{year} w{week_index:02d}:\n"
                            + traceback.format_exc(),
                            prefix="task",
                        )
                        new_count = 0
                    if new_count >= MAX_FAILURE_COUNT:
                        log.info(
                            f"`{url}` returned no ranking rows "
                            f"{new_count}× in a row – locking "
                            f"{season}-{year} w{week_index:02d} as absent.",
                            prefix="task",
                        )
                        absent_indices.add(week_index)
                    else:
                        log.info(
                            f"`{url}` returned no ranking rows "
                            f"(attempt {new_count}/{MAX_FAILURE_COUNT}) "
                            f"– will retry {season}-{year} w{week_index:02d} "
                            "on the next backfill run.",
                            prefix="task",
                        )
                    total_errors += 1
                    continue
                inserted = await _persist_week_ranking(
                    ranking=ranking,
                    date=datetime(week_start.year, week_start.month, week_start.day),
                    season=season,
                )
                if inserted > 0:
                    log.info(
                        f"Fetched {season}-{year} w{week_index:02d} "
                        f"({week_start:%Y-%m-%d}) – stored {inserted} ranking "
                        f"row(s) from `{url}`.",
                        prefix="task",
                    )
                    total_inserted += inserted
                    try:
                        await AnimeCornerHistoryManager.mark_week_present(
                            season=season, year=year, week_index=week_index,
                        )
                    except Exception:
                        log.warning(
                            "Failed to persist present marker for "
                            f"{season}-{year} w{week_index:02d}:\n"
                            + traceback.format_exc(),
                            prefix="task",
                        )
                else:
                    log.debug(
                        f"Week {week_start:%Y-%m-%d} already populated "
                        f"(likely written by another worker).",
                        prefix="task",
                    )
        log.info(
            "Anime Corner backfill summary: "
            f"{total_inserted} row(s) inserted, "
            f"{total_errors} fetch failure(s), "
            f"{total_skipped_absent} week(s) already known absent, "
            f"{total_skipped_beyond_season} week(s) past the season end.",
            prefix="task",
        )
    except Exception:
        log.error(
            "Anime Corner backfill crashed:\n" + traceback.format_exc(),
            prefix="task",
        )


async def _persist_week_ranking(
    ranking: List[Dict[str, Any]],
    date: datetime,
    season: str,
) -> int:
    """Persist a ranking list against a week start date. Returns the number of
    rows actually inserted (existing rows are skipped).
    """
    if await AnimeCornerHistoryManager.has_entry_for(date):
        return 0
    inserted = 0
    for match in ranking:
        try:
            await AnimeCornerHistoryManager.add(
                name=match["name"],
                score=float(match["score"]),
                rank=int(match["rank"]),
                date=date,
                season=season,
            )
            inserted += 1
        except Exception:
            log.warning(
                f"Failed to persist AnimeCorner ranking for {match.get('name')!r}",
                f"\n{traceback.format_exc()}",
                prefix="task",
            )
    return inserted


_SEASON_START_MONTHS = {
    "winter": 12,  # December -> January == winter
    "spring": 3,
    "summer": 6,
    "fall": 9,
}
_SEASON_MONTHS_PER_YEAR = 3


def _season_week_index(season: str, year: int, week_start: datetime) -> Optional[int]:
    """Estimate which week index within ``season`` ``year`` the given
    ``week_start`` date belongs to.

    Anime Corner typically publishes one ranking per ISO week, so we can
    approximate the index by taking the number of weeks since the season
    began (rounded down).
    """
    season = season.lower()
    if season not in _SEASON_START_MONTHS:
        return None
    month = week_start.month
    if season == "winter":
        # winter spans Dec (prev year) → Jan/Feb (this year)
        if month == 12:
            base = datetime(week_start.year, 12, 1)
            candidate_year = week_start.year + 1
        else:
            base = datetime(year - 1, 12, 1)
            candidate_year = year
    else:
        base = datetime(year, _SEASON_START_MONTHS[season], 1)
        candidate_year = year
    # Normalise to Monday so ISO weeks line up.
    days_since_start = (week_start - base).days
    if days_since_start < 0:
        return None
    return max(1, days_since_start // 7 + 1)

    
