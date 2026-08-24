from datetime import datetime
from typing import *
import traceback

from fuzzywuzzy import fuzz

from inu.core import Table, getLogger
# Import directly from the sibling module to avoid the circular import through
# `inu.utils` (which is mid-loading when `inu.utils.db` is initialised).
from inu.utils.db.anime import MyAnimeList

log = getLogger(__name__)

# How many times a known-failing URL is retried across consecutive
# backfill runs before it is locked as ``absent`` in
# `anime_of_the_week_known_weeks`. Kept here (instead of in the task
# module) because the threshold appears directly in the SQL of
# :meth:`AnimeCornerHistoryManager.mark_week_pending`.
MAX_FAILURE_COUNT: int = 3


def get_season(dt: datetime) -> str:
    """Returns the season string for the given datetime.

    Note:
        Anime Corner calls the September–November quarter ``fall`` (not
        ``autumn``). This function always returns the Anime Corner spelling
        so callers can pass the result straight into
        :func:`inu.utils.rest.build_anime_corner_url` and the matching CHECK
        constraint on ``anime_of_the_week_history``.
    """
    month = dt.month
    if month in (12, 1, 2):
        return "winter"
    if month in (3, 4, 5):
        return "spring"
    if month in (6, 7, 8):
        return "summer"
    return "fall"


class AnimeCornerHistoryManager:
    """Manager for persisting and querying historical `Anime of the Week` rankings
    from Anime Corner."""

    table_name = "anime_of_the_week_history"
    FUZZY_DB_THRESHOLD = 70  # percent

    @classmethod
    async def add(
        cls,
        name: str,
        score: float,
        rank: int,
        date: datetime,
        mal_id: Optional[int] = None,
        season: Optional[str] = None,
    ) -> Optional[List[Mapping[str, Any]]]:
        """Insert a single `Anime of the Week` ranking record.

        Args:
            name: the anime name as written on Anime Corner
            score: the Anime Corner poll score (percent)
            rank: the rank of the anime for that week (1-10)
            date: the date of the ranking poll
            mal_id: optional MyAnimeList id; found by fuzzy search if not given
            season: optional season; defaults to the season that <date> is in

        Note:
            If an entry for the same `(rank, date)` already exists it will be
            updated instead of duplicated.
        """
        season = season or get_season(date)
        if mal_id is None:
            mal_id = await cls._fuzzy_lookup_mal_id(name)
        # insert placeholder if mal entry not present, so that FK-constraint by mal id does not fail
        if mal_id is not None:
            try:
                await MyAnimeList.ensure_placeholder(mal_id, name)
            except Exception:
                log.warning(
                    "Failed to ensure myanimelist placeholder for "
                    f"mal_id={mal_id} ({name!r}); will still attempt the "
                    "history insert:\n" + traceback.format_exc()
                )
        table = Table(cls.table_name)
        return await table.upsert(
            which_columns=["name", "score", "rank", "season", "date", "mal_id"],
            values=[name, score, rank, season, date, mal_id],
            where={"rank": rank, "date": date},
            compound_of=2,
        )

    @classmethod
    async def add_many(
        cls,
        entries: List[Dict[str, Any]],
        default_date: Optional[datetime] = None,
    ) -> None:
        """Insert many ranking rows in one go.

        Args:
            entries: list of dicts with keys: `name`, `score`, `rank` and
                optional `mal_id`/`season`. <`date`> defaults to `default_date`.
            default_date: timestamp used as the date for every entry if missing
        """
        default_date = default_date or datetime.now()
        for entry in entries:
            date = entry.get("date") or default_date
            season = entry.get("season") or get_season(date)
            mal_id = entry.get("mal_id")
            if mal_id is None:
                mal_id = await cls._fuzzy_lookup_mal_id(entry["name"])
            await cls.add(
                name=entry["name"],
                score=entry["score"],
                rank=entry["rank"],
                date=date,
                mal_id=mal_id,
                season=season,
            )

    @classmethod
    async def _fuzzy_lookup_mal_id(cls, name: str) -> Optional[int]:
        """Finds a MyAnimeList id for `name` using a 3 step search:

        1. Exact match against the local `myanimelist` cache (title, title_english,
           title_japanese, title_synonyms).
        2. pg_trgm similarity against the local cache.
        3. MyAnimeList REST search (which is also local-cached via
           `MyAnimeList.search_anime`).

        Returns:
            The best matching mal_id or `None` if nothing matches above the
            fuzzy threshold.
        """
        if not name:
            return None
        # 1) exact (case insensitive) match against cached anime
        cached = await cls._exact_lookup_db(name)
        if cached is not None:
            return cached
        # 2) pg_trgm similarity
        cached = await cls._fuzzy_lookup_db(name)
        if cached is not None:
            return cached
        # 3) fallback to REST search
        try:
            search_result = await MyAnimeList.search_anime(query=name)
        except Exception:
            log.warning(traceback.format_exc())
            return None
        data = search_result.get("data") if isinstance(search_result, dict) else None
        if not data:
            return None
        best = cls._fuzzy_sort(data, name)
        if not best:
            return None
        first = best[0]
        node = first.get("node", {})
        return int(node.get("id")) if node else None

    @classmethod
    async def _exact_lookup_db(cls, name: str) -> Optional[int]:
        """Returns the mal_id for an anime with an exact title match in the
        local cache. The check covers title, title_english, title_japanese
        and every synonym."""
        table = Table("myanimelist")
        sql = (
            "SELECT mal_id, title, title_english, title_japanese, title_synonyms "
            "FROM myanimelist "
            "WHERE LOWER(title) = $1 OR LOWER(title_english) = $1 "
            "OR LOWER(title_japanese) = $1 OR EXISTS ("
            "  SELECT 1 FROM unnest(title_synonyms) AS syn WHERE LOWER(syn) = $1"
            ")"
        )
        records = await table.fetch(sql, name.lower())
        return int(records[0]["mal_id"]) if records else None

    @classmethod
    async def _fuzzy_lookup_db(cls, name: str) -> Optional[int]:
        """Returns the mal_id for the best pg_trgm match of `name` in the local
        cache, provided the trigram similarity is high enough."""
        table = Table("myanimelist")
        sql = (
            "SELECT mal_id, title, title_english, title_japanese, title_synonyms, "
            "GREATEST("
            "  similarity(title, $1), "
            "  similarity(COALESCE(title_english, ''), $1), "
            "  similarity(COALESCE(title_japanese, ''), $1)"
            ") AS sim "
            "FROM myanimelist "
            "ORDER BY sim DESC "
            "LIMIT 25"
        )
        try:
            records = await table.fetch(sql, name)
        except Exception:
            log.warning(traceback.format_exc())
            return None
        if not records:
            return None
        best_ratio = 0
        best_id = None
        for record in records:
            titles = [record["title"], record["title_english"], record["title_japanese"]]
            for syn in record["title_synonyms"] or []:
                titles.append(syn)
            for title in titles:
                if not title:
                    continue
                ratio = fuzz.ratio(title.lower(), name.lower())
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_id = int(record["mal_id"])
        if best_ratio >= cls.FUZZY_DB_THRESHOLD:
            return best_id
        return None

    @staticmethod
    def _fuzzy_sort(results: List[Dict[str, Any]], compare_name: str) -> List[Dict[str, Any]]:
        """Reorders `results` so that close fuzzy matches of `compare_name`
        come first (mirrors `AnimeCornerView._fuzzy_sort_results`)."""
        close_matches = []
        for anime in results.copy():
            titles = [anime["node"]["title"]]
            alt = anime["node"].get("alternative_titles")
            if isinstance(alt, dict):
                for value in alt.values():
                    if isinstance(value, list):
                        titles.extend(value)
                    else:
                        titles.append(value)
            max_ratio = max(
                (fuzz.ratio(title.lower(), compare_name.lower()) for title in titles),
                default=0,
            )
            anime["fuzz_ratio"] = max_ratio
            if max_ratio >= 80:
                results.remove(anime)
                close_matches.append(anime)
        close_matches.sort(key=lambda a: a["fuzz_ratio"], reverse=True)
        return [*close_matches, *results]

    @classmethod
    async def fetch_history(
        cls,
        since: datetime,
        season: Optional[str] = None,
        mal_id: Optional[int] = None,
    ) -> List[Mapping[str, Any]]:
        """Returns ranking rows newer than `since`.

        Args:
            since: lower bound for the date column (exclusive)
            season: optionally filter for a single season
            mal_id: optionally filter for a single anime
        """
        table = Table(cls.table_name)
        filters = ["date >= $1"]
        values: List[Any] = [since]
        if season is not None:
            filters.append(f"season = ${len(values)+1}")
            values.append(season)
        if mal_id is not None:
            filters.append(f"mal_id = ${len(values)+1}")
            values.append(mal_id)
        where = " AND ".join(filters)
        sql = (
            f"SELECT name, score, rank, season, date, mal_id "
            f"FROM {cls.table_name} "
            f"WHERE {where} "
            f"ORDER BY date ASC, rank ASC"
        )
        return await table.fetch(sql, *values)

    @classmethod
    async def fetch_for_chart(
        cls,
        since: datetime,
    ) -> "pd.DataFrame":
        """Returns a `pd.DataFrame` with the columns `date`, `rank`, `name`,
        `mal_id`, `score`, `season`. Sorted by `date` ascending."""
        import pandas as pd
        records = await cls.fetch_history(since=since)
        if not records:
            return pd.DataFrame(columns=["date", "rank", "name", "mal_id", "score", "season"])
        df = pd.DataFrame([dict(r) for r in records])
        df["date"] = pd.to_datetime(df["date"])
        return df.sort_values(by=["date", "rank"]).reset_index(drop=True)

    @classmethod
    async def fetch_all_for_chart(cls) -> "pd.DataFrame":
        """Returns every row in `anime_of_the_week_history` as a `DataFrame`,
        sorted by `date` ascending. Useful as a fallback when the user-requested
        time range has no entries yet.
        """
        import pandas as pd
        table = Table(cls.table_name)
        sql = (
            f"SELECT name, score, rank, season, date, mal_id "
            f"FROM {cls.table_name} "
            f"ORDER BY date ASC, rank ASC"
        )
        records = await table.fetch(sql)
        if not records:
            return pd.DataFrame(columns=["date", "rank", "name", "mal_id", "score", "season"])
        df = pd.DataFrame([dict(r) for r in records])
        df["date"] = pd.to_datetime(df["date"])
        return df.sort_values(by=["date", "rank"]).reset_index(drop=True)

    @classmethod
    async def list_available_seasons(cls) -> List[Tuple[str, int]]:
        """Returns the distinct ``(season, year)`` pairs the history table
        actually has data for, ordered from most recent to oldest.

        The "year" follows Anime Corner's convention: ``winter`` belongs to
        the calendar year of its January/February tail (so a row dated
        January 2025 is reported as ``("winter", 2025)`` even though the
        December 2024 weeks are part of the same season).

        Used to populate the slash-command option list. Discord caps a
        single option at 25 choices, so callers should slice the result
        down to ``24`` and reserve one slot for the synthetic ``current``
        choice.
        """
        table = Table(cls.table_name)
        sql = (
            "SELECT season, year FROM ("
            "  SELECT season, "
            "    CASE WHEN season = 'winter' AND EXTRACT(MONTH FROM date) = 12 "
            "         THEN EXTRACT(YEAR FROM date)::INT + 1 "
            "         ELSE EXTRACT(YEAR FROM date)::INT "
            "    END AS year "
            "  FROM anime_of_the_week_history"
            ") AS s "
            "GROUP BY season, year "
            "ORDER BY year DESC, "
            "  CASE season "
            "    WHEN 'winter' THEN 0 "
            "    WHEN 'spring' THEN 1 "
            "    WHEN 'summer' THEN 2 "
            "    WHEN 'fall'   THEN 3 "
            "  END DESC"
        )
        records = await table.fetch(sql)
        return [(str(r["season"]), int(r["year"])) for r in records]

    @classmethod
    async def data_range(cls) -> Optional[Tuple[datetime, datetime]]:
        """Returns the inclusive `(earliest_date, latest_date)` of stored rows,
        or `None` when the table is empty.
        """
        table = Table(cls.table_name)
        sql = f"SELECT MIN(date) AS earliest, MAX(date) AS latest FROM {cls.table_name}"
        record = await table.fetch(sql)
        if not record or record[0]["earliest"] is None:
            return None
        earliest: datetime = record[0]["earliest"]
        latest: datetime = record[0]["latest"]
        return earliest, latest

    @classmethod
    async def has_entry_for(cls, date: datetime) -> bool:
        """Whether at least one row exists for the given date."""
        table = Table(cls.table_name)
        sql = (
            f"SELECT 1 FROM {cls.table_name} "
            f"WHERE date_trunc('day', date) = date_trunc('day', $1::TIMESTAMP) "
            f"LIMIT 1"
        )
        records = await table.fetch(sql, date)
        return bool(records)

    @classmethod
    async def missing_weeks(
        cls,
        since: datetime,
        until: Optional[datetime] = None,
    ) -> List[datetime]:
        """Returns every week start (Monday, midnight) inside the
        `[since, until]` range for which **no** row exists in the history table.

        Weeks that have already been probed and confirmed empty by
        :meth:`mark_week_absent` are excluded so the backfill task stops
        re-trying them forever. The exclusion is applied per ``(season,
        year)``: each generated Monday is classified into its own season
        (using Anime Corner's convention that December belongs to the
        *next* year's winter) and matched against the corresponding
        ``anime_of_the_week_known_weeks`` row.
        """
        table = Table(cls.table_name)
        until = until or datetime.now()
        # Each generated Monday is classified into its own (season, year)
        # and a per-season base date is computed (December for winter,
        # March/June/September for the rest). The week_index used to match
        # the known-weeks table mirrors :func:`_season_week_index` in
        # ``inu/ext/tasks/anime_corner.py``.
        sql = (
            "WITH weeks AS ("
            "  SELECT generate_series("
            "    date_trunc('week', $1::TIMESTAMP),"
            "    date_trunc('week', $2::TIMESTAMP),"
            "    interval '7 days'"
            "  ) AS week_start"
            "),"
            "classified AS ("
            "  SELECT"
            "    w.week_start,"
            "    CASE"
            "      WHEN EXTRACT(MONTH FROM w.week_start) IN (12, 1, 2) THEN 'winter'"
            "      WHEN EXTRACT(MONTH FROM w.week_start) IN (3, 4, 5)  THEN 'spring'"
            "      WHEN EXTRACT(MONTH FROM w.week_start) IN (6, 7, 8)  THEN 'summer'"
            "      ELSE 'fall'"
            "    END AS season,"
            "    CASE"
            "      WHEN EXTRACT(MONTH FROM w.week_start) = 12"
            "        THEN EXTRACT(YEAR FROM w.week_start)::INT + 1"
            "      ELSE EXTRACT(YEAR FROM w.week_start)::INT"
            "    END AS year"
            "  FROM weeks w"
            "),"
            "indexed AS ("
            "  SELECT"
            "    c.week_start,"
            "    c.season,"
            "    c.year,"
            "    GREATEST(1,"
            "      (EXTRACT(DAY FROM (c.week_start::TIMESTAMP - CASE"
            "        WHEN c.season = 'winter' THEN make_timestamp(c.year - 1, 12, 1, 0, 0, 0)"
            "        WHEN c.season = 'spring' THEN make_timestamp(c.year,     3, 1, 0, 0, 0)"
            "        WHEN c.season = 'summer' THEN make_timestamp(c.year,     6, 1, 0, 0, 0)"
            "        ELSE                          make_timestamp(c.year,     9, 1, 0, 0, 0)"
            "      END)))::INT / 7 + 1"
            "    ) AS week_index"
            "  FROM classified c"
            ")"
            "SELECT i.week_start::TIMESTAMP AS week_start "
            "FROM indexed i "
            "LEFT JOIN anime_of_the_week_history h "
            "  ON date_trunc('day', h.date) = i.week_start::TIMESTAMP "
            "LEFT JOIN anime_of_the_week_known_weeks k "
            "  ON k.season = i.season "
            "    AND k.year = i.year "
            "    AND k.state = 'absent' "
            "    AND k.week_index = i.week_index "
            "WHERE h.date IS NULL AND k.season IS NULL "
            "ORDER BY i.week_start"
        )
        records = await table.fetch(sql, since, until)
        return [r["week_start"] for r in records]

    @classmethod
    async def mark_week_present(
        cls,
        season: str,
        year: int,
        week_index: int,
    ) -> None:
        """Records that ``(season, year, week_index)`` successfully produced
        ranking rows. Idempotent — re-marking bumps ``last_seen`` and
        resets ``failure_count`` (a previously-pending URL that recovers
        shouldn't carry over its old failure tally).
        """
        table = Table("anime_of_the_week_known_weeks")
        sql = (
            "INSERT INTO anime_of_the_week_known_weeks "
            "  (season, year, week_index, state, failure_count) "
            "VALUES ($1, $2, $3, 'present', 0) "
            "ON CONFLICT (season, year, week_index) DO UPDATE "
            "  SET state = 'present', failure_count = 0, last_seen = NOW()"
        )
        await table.fetch(sql, season, year, week_index)

    @classmethod
    async def mark_week_absent(
        cls,
        season: str,
        year: int,
        week_index: int,
    ) -> None:
        """Records that ``(season, year, week_index)`` was probed but came
        back empty so future backfill runs skip it.
        """
        table = Table("anime_of_the_week_known_weeks")
        sql = (
            "INSERT INTO anime_of_the_week_known_weeks "
            "  (season, year, week_index, state, failure_count) "
            "VALUES ($1, $2, $3, 'absent', 0) "
            "ON CONFLICT (season, year, week_index) DO UPDATE "
            "  SET state = 'absent', failure_count = 0, last_seen = NOW()"
        )
        await table.fetch(sql, season, year, week_index)

    @classmethod
    async def mark_week_pending(
        cls,
        season: str,
        year: int,
        week_index: int,
    ) -> int:
        """Records that ``(season, year, week_index)`` failed to fetch but
        has not yet crossed the :data:`MAX_FAILURE_COUNT` threshold.
        Increments ``failure_count``; if the new count meets or exceeds
        the threshold the row is transitioned to ``absent`` instead.
        Returns the new ``failure_count``.
        """
        table = Table("anime_of_the_week_known_weeks")
        # Upsert into pending, increment failure_count atomically; if we
        # cross the threshold in the same statement, flip to absent so the
        # next backfill run skips the URL entirely.
        sql = (
            "INSERT INTO anime_of_the_week_known_weeks "
            "  (season, year, week_index, state, failure_count) "
            "VALUES ($1, $2, $3, 'pending', 1) "
            "ON CONFLICT (season, year, week_index) DO UPDATE "
            "  SET state = CASE "
            "    WHEN anime_of_the_week_known_weeks.failure_count + 1 >= $4 "
            "      THEN 'absent' "
            "    ELSE 'pending' "
            "    END, "
            "    failure_count = anime_of_the_week_known_weeks.failure_count + 1, "
            "    last_seen = NOW() "
            "  RETURNING failure_count, state"
        )
        records = await table.fetch(
            sql, season, year, week_index, MAX_FAILURE_COUNT,
        )
        if not records:
            return 0
        return int(records[0]["failure_count"])

    @classmethod
    async def get_failure_count(
        cls,
        season: str,
        year: int,
        week_index: int,
    ) -> int:
        """Returns the recorded ``failure_count`` for ``(season, year,
        week_index)`` or 0 if the row does not exist."""
        table = Table("anime_of_the_week_known_weeks")
        sql = (
            "SELECT failure_count FROM anime_of_the_week_known_weeks "
            "WHERE season = $1 AND year = $2 AND week_index = $3"
        )
        records = await table.fetch(sql, season, year, week_index)
        return int(records[0]["failure_count"]) if records else 0

    @classmethod
    async def max_known_week_index(
        cls,
        season: str,
        year: int,
    ) -> int:
        """Returns the largest ``week_index`` we have ever probed for
        ``(season, year)`` regardless of state. Used by the backfill task
        to skip weeks it has already covered when re-running
        ``find_latest_week_with_ranking``."""
        table = Table("anime_of_the_week_known_weeks")
        sql = (
            "SELECT MAX(week_index) AS max_idx "
            "FROM anime_of_the_week_known_weeks "
            "WHERE season = $1 AND year = $2"
        )
        records = await table.fetch(sql, season, year)
        if not records or records[0]["max_idx"] is None:
            return 0
        return int(records[0]["max_idx"])

    @classmethod
    async def known_absent_week_indices(
        cls,
        season: str,
        year: int,
    ) -> List[int]:
        """Returns all week indices for ``(season, year)`` that were
        confirmed empty by :meth:`mark_week_absent`."""
        table = Table("anime_of_the_week_known_weeks")
        sql = (
            "SELECT week_index FROM anime_of_the_week_known_weeks "
            "WHERE season = $1 AND year = $2 AND state = 'absent' "
            "ORDER BY week_index"
        )
        records = await table.fetch(sql, season, year)
        return [int(r["week_index"]) for r in records]
