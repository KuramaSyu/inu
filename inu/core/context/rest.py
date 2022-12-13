"""Context based on REST responses"""
from typing import * 

import asyncio
import hikari
import lightbulb
from lightbulb.context import Context, ResponseProxy
from lightbulb.context.prefix import PrefixContext

from . import InuContextProtocol



class RESTContext(Context):
    """
    Class for Context, which is not based on Interactions.

    Args:
        app (:obj:`~.app.BotApp`): The ``BotApp`` instance that the context is linked to.
    """

    __slots__ = ("_app", "_responses", "_responded", "_deferred", "_invoked", "_event", "_options")
    def __init__(self, app: lightbulb.BotApp, event: hikari.MessageCreateEvent):
        self._event = event
        self._options = {}
        super().__init__(app)

    @property
    def event(self) -> hikari.MessageCreateEvent:
        return self._event

    @property
    def channel_id(self) -> hikari.Snowflakeish:
        return self.event.message.channel_id

    @property
    def guild_id(self) -> Optional[hikari.Snowflakeish]:
        return self.event.message.guild_id

    @property
    def attachments(self) -> Sequence[hikari.Attachment]:
        return self.event.message.attachments

    @property
    def member(self) -> Optional[hikari.Member]:
        return self.event.message.member

    @property
    def author(self) -> hikari.User:
        return self.event.message.author

    @property
    def invoked_with(self) -> str:
        return ""

    @property
    def prefix(self) -> str:
        return ""

    @property
    def command(self) -> None:
        return None

    def get_channel(self) -> Optional[Union[hikari.GuildChannel, hikari.Snowflake]]:
        if self.guild_id is not None:
            return self.app.cache.get_guild_channel(self.channel_id)
        return self.app.cache.get_dm_channel_id(self.author.id)

    async def respond(
        self, 
        *args: Any, 
        delete_after: Union[int, float, None] = None, 
        update: bool = False,
        **kwargs: Any
    ) -> ResponseProxy:
        """
        Create a response for this context. This method directly calls :obj:`~hikari.messages.Message.respond`. You
        should note that it is not possible to send ephemeral messages as responses to prefix commands. All message flags
        will be removed before the call to :obj:`~hikari.messages.Message.respond`.

        Args:
            *args : Any 
                Positional arguments passed to :obj:`~hikari.messages.Message.respond`.
            delete_after : int | float | None
                The number of seconds to wait before deleting this response.

            **kwargs : Any 
                Keyword arguments passed to :obj:`~hikari.messages.Message.respond`.

        Returns:
            :obj:`~hikari.messages.Message`: The created message object.

        .. versionadded:: 2.2.0
            ``delete_after`` kwarg.
        """
        self._deferred = False

        kwargs.pop("flags", None)
        kwargs.pop("response_type", None)

        if args and isinstance(args[0], hikari.ResponseType):
            args = args[1:]
        if update and self._responses:
            msg = await self._responses[0].edit(*args, **kwargs)
        else:
            msg = await self._event.message.respond(*args, **kwargs)
        if delete_after is not None:

            async def _cleanup(timeout: Union[int, float]) -> None:
                await asyncio.sleep(timeout)

                try:
                    await msg.delete()
                except hikari.NotFoundError:
                    pass

            self.app.create_task(_cleanup(delete_after))

        self._responses.append(ResponseProxy(msg))
        self._responded = True
        return self._responses[-1]