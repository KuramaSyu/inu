from abc import abstractmethod, ABC

from hikari import Snowflakeish
from core import InuContext
from lavalink_rs.model.search import SearchEngines
from lavalink_rs.model.track import Track, TrackData, PlaylistData, TrackLoadType, PlaylistInfo
from lavalink_rs.model.player import Player

from core import BotResponseError
from utils import Human, MusicHistoryHandler
from .constants import HISTORY_PREFIX, MEDIA_TAG_PREFIX, MARKDOWN_URL_REGEX, URL_REGEX

from ..tags import get_tag


class QueryStrategy(ABC):
    @abstractmethod
    async def process_query(self, ctx: InuContext, query: str, guild_id: Snowflakeish) -> str:
        ...
        
    @abstractmethod
    def matches_query(self, query: str) -> bool:
        """Determines if this strategy should be used for the given query."""
        ...


   
class SearchQueryStrategy(QueryStrategy):
    async def process_query(self, ctx: InuContext, query: str, guild_id: Snowflakeish) -> str:
        return SearchEngines.soundcloud(query)
    
    def matches_query(self, query: str) -> bool:
        # Default strategy for plain text searches
        return True


  
class UrlQueryStrategy(QueryStrategy):
    async def process_query(self, ctx: InuContext, query: str, guild_id: Snowflakeish) -> str:
        return query
    
    def matches_query(self, query: str) -> bool:
        return query.startswith(('http://', 'https://', 'www.'))



class MarkdownUrlQueryStrategy(QueryStrategy):
    async def process_query(self, ctx: InuContext, query: str, guild_id: Snowflakeish) -> str:
        """Get url from markdown url; can raise Botresponseerror"""
        if (match:=MARKDOWN_URL_REGEX.match(query)):
            return match.group(2)
        else:
            raise BotResponseError("Invalid markdown url")
    
    def matches_query(self, query: str) -> bool:
        return bool(MARKDOWN_URL_REGEX.match(query))


  
class TagQueryStrategy(QueryStrategy):
    async def process_query(self, ctx: InuContext, query: str, guild_id: Snowflakeish) -> str:
        """Get url from tag; can raise Botresponseerror"""
        query = query.replace(MEDIA_TAG_PREFIX, "")
        tag = await get_tag(ctx, query)
        if not tag:
            raise BotResponseError(f"Couldn't find the tag `{query}`")
        return tag["tag_value"][0]
    
    def matches_query(self, query: str) -> bool:
        return query.startswith(MEDIA_TAG_PREFIX)



class HistoryQueryStrategy(QueryStrategy):
    async def process_query(self, ctx: InuContext, query: str, guild_id: Snowflakeish) -> str:
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