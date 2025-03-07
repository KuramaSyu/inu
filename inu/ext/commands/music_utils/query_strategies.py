from abc import abstractmethod, ABC
from math import log
from typing import *

from hikari import Snowflakeish
from matplotlib.pylab import f
from core import InuContext
from lavalink_rs.model.search import SearchEngines  # type: ignore
from lavalink_rs.model.track import Track, TrackData, PlaylistData, TrackLoadType, PlaylistInfo  # type: ignore
from lavalink_rs.model.player import Player  # type: ignore

from core import BotResponseError, getLogger
from utils import Human, MusicHistoryHandler, Tag
from .constants import HISTORY_PREFIX, MEDIA_TAG_PREFIX, MARKDOWN_URL_REGEX, URL_REGEX

from ..tags import get_tag


__all__: Final[List[str]] = [
    "QueryStrategyABC", "SearchQueryStrategy", "UrlQueryStrategy", 
    "MarkdownUrlQueryStrategy", "TagQueryStrategy", "HistoryQueryStrategy", 
    "QUERY_STRATEGIES"
]

log = getLogger(__name__)

def get_preferred_search(ctx: InuContext, guild_id: Snowflakeish) -> Callable[[str], str]:
    DEFAULT = "soundcloud"
    search = ctx.bot.data.preffered_music_search.get(guild_id, DEFAULT)
    match search:
        case "soundcloud":
            return SearchEngines.soundcloud
        case "youtube":
            return SearchEngines.youtube
        case _:
            return SearchEngines.soundcloud


class QueryStrategyABC(ABC):
    @abstractmethod
    async def process_query(self, ctx: InuContext, query: str, guild_id: Snowflakeish, search_engine: Optional[str] = None) -> str:
        ...
        
    @abstractmethod
    def matches_query(self, query: str) -> bool:
        """Determines if this strategy should be used for the given query."""
        ...


   
class SearchQueryStrategy(QueryStrategyABC):
    async def process_query(self, ctx: InuContext, query: str, guild_id: Snowflakeish, search_engine: Optional[str] = None) -> str:
        match search_engine:
            case None:
                return get_preferred_search(ctx, guild_id)(query)
            case "youtube":
                return SearchEngines.youtube(query)
            case "soundcloud":
                return SearchEngines.soundcloud(query)
            case _:
                return get_preferred_search(ctx, guild_id)(query)
    
    def matches_query(self, query: str) -> bool:
        # Default strategy for plain text searches
        return True


  
class UrlQueryStrategy(QueryStrategyABC):
    async def process_query(self, ctx: InuContext, query: str, guild_id: Snowflakeish, search_engine: Optional[str] = None) -> str:
        if (match := URL_REGEX.match(query)):
            return match.group(0)
        else:
            raise BotResponseError("Invalid url")
    
    def matches_query(self, query: str) -> bool:
        return query.startswith(('http://', 'https://', 'www.')) or bool(URL_REGEX.match(query))



class MarkdownUrlQueryStrategy(QueryStrategyABC):
    async def process_query(self, ctx: InuContext, query: str, guild_id: Snowflakeish, search_engine: Optional[str] = None) -> str:
        """Get url from markdown url; can raise Botresponseerror"""
        if (match:=MARKDOWN_URL_REGEX.match(query)):
            return match.group(1)
        else:
            raise BotResponseError("Invalid markdown url")
    
    def matches_query(self, query: str) -> bool:
        return bool(MARKDOWN_URL_REGEX.match(query))


  
class TagQueryStrategy(QueryStrategyABC):
    async def process_query(self, ctx: InuContext, query: str, guild_id: Snowflakeish, search_engine: Optional[str] = None) -> str:
        """Get url from tag; can raise Botresponseerror"""
        query = query.replace(MEDIA_TAG_PREFIX, "")
        tag = await get_tag(ctx, query)
        if not tag:
            raise BotResponseError(f"Couldn't find the tag `{query}`")
        tag = await Tag.from_record(tag)
        if not tag:
            raise BotResponseError(f"Couldn't find the tag `{query}`")
        return tag.value[0]  # type: ignore
    
    def matches_query(self, query: str) -> bool:
        return query.startswith(MEDIA_TAG_PREFIX)



class HistoryQueryStrategy(QueryStrategyABC):
    async def process_query(self, ctx: InuContext, query: str, guild_id: Snowflakeish, search_engine: Optional[str] = None) -> str:
        """
        get url from history
        only edits the query
        can raise BotResponseError
        """
        query = query.replace(HISTORY_PREFIX, "")
        history = await MusicHistoryHandler.cached_get(guild_id)
        if (alt_query:=[t["url"] for t in history if query in t["title"]]):
            return alt_query[0]
        else:
            raise BotResponseError(f"Couldn't find the title `{query}` in the history")
    
    def matches_query(self, query: str) -> bool:
        return query.startswith(HISTORY_PREFIX)


# from most unique to least unique
QUERY_STRATEGIES: List[QueryStrategyABC] = [
    TagQueryStrategy(),
    HistoryQueryStrategy(),
    MarkdownUrlQueryStrategy(),
    UrlQueryStrategy(),
    SearchQueryStrategy(),
]