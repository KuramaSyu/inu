import asyncio
from typing import *
from datetime import datetime, timedelta
import abc
import functools

import hikari
from hikari import ComponentInteraction, ResponseType
from ._logging import getLogger

import lightbulb
from lightbulb.context.base import Context, ResponseProxy

log = getLogger(__name__)


REST_SENDING_MARGIN = 0.5 #seconds



class _InteractionContext(Context, abc.ABC):
    __slots__ = ("_event", "_interaction")

    def __init__(
        self, app: lightbulb.app.BotApp, event: hikari.InteractionCreateEvent
    ) -> None:
        super().__init__(app)
        self._event = event
        assert isinstance(event. interaction, hikari.ComponentInteraction)
        self._interaction: hikari.ComponentInteraction = event.interaction
        self._default_ephemeral: bool = False

    @property
    def app(self) -> lightbulb.app.BotApp:
        return self._app
    @property
    def event(self) -> hikari.InteractionCreateEvent:
        return self._event

    @property
    def interaction(self) -> hikari.ComponentInteraction:  #type: ignore
        return self._interaction

    @property
    def channel_id(self) -> hikari.Snowflakeish:
        return self._interaction.channel_id

    @property
    def guild_id(self) -> Optional[hikari.Snowflakeish]:
        return self._interaction.guild_id

    @property
    def attachments(self) -> Sequence[hikari.Attachment]:
        return []

    @property
    def member(self) -> Optional[hikari.Member]:
        return self._interaction.member

    @property
    def author(self) -> hikari.User:
        return self._interaction.user

    def get_channel(self) -> Optional[Union[hikari.GuildChannel, hikari.Snowflake]]:
        if self.guild_id is not None:
            return self.app.cache.get_guild_channel(self.channel_id)
        return self.app.cache.get_dm_channel_id(self.user)

    async def respond(
        self, *args: Any, delete_after: Union[int, float, None] = None, update: bool = False, **kwargs: Any
    ) -> ResponseProxy:
        """
        Create a response for this context. The first time this method is called, the initial
        interaction response will be created by calling
        :obj:`~hikari.interactions.command_interactions.CommandInteraction.create_initial_response` with the response
        type set to :obj:`~hikari.interactions.base_interactions.ResponseType.MESSAGE_CREATE` if not otherwise
        specified.

        Subsequent calls will instead create followup responses to the interaction by calling
        :obj:`~hikari.interactions.command_interactions.CommandInteraction.execute`.

        Args:
            *args (Any): Positional arguments passed to ``CommandInteraction.create_initial_response`` or
                ``CommandInteraction.execute``.
            delete_after (Union[:obj:`int`, :obj:`float`, ``None``]): The number of seconds to wait before deleting this response.
            **kwargs: Keyword arguments passed to ``CommandInteraction.create_initial_response`` or
                ``CommandInteraction.execute``.

        Returns:
            :obj:`~ResponseProxy`: Proxy wrapping the response of the ``respond`` call.

        .. versionadded:: 2.2.0
            ``delete_after`` kwarg.
        """

        async def _cleanup(timeout: Union[int, float], proxy_: ResponseProxy) -> None:
            await asyncio.sleep(timeout)

            try:
                await proxy_.delete()
            except hikari.NotFoundError:
                pass

        includes_ephemeral: Callable[[Union[hikari.MessageFlag, int],], bool] = (
            lambda flags: (hikari.MessageFlag.EPHEMERAL & flags) == hikari.MessageFlag.EPHEMERAL
        )

        kwargs.pop("reply", None)
        kwargs.pop("mentions_reply", None)
        kwargs.pop("nonce", None)

        if self._default_ephemeral:
            kwargs.setdefault("flags", hikari.MessageFlag.EPHEMERAL)

        if self._responded:
            kwargs.pop("response_type", None)
            if args and isinstance(args[0], hikari.ResponseType):
                args = args[1:]

            async def _ephemeral_followup_editor(
                _: ResponseProxy,
                *args_: Any,
                _wh_id: hikari.Snowflake,
                _tkn: str,
                _m_id: hikari.Snowflake,
                **kwargs_: Any,
            ) -> hikari.Message:
                return await self.app.rest.edit_webhook_message(_wh_id, _tkn, _m_id, *args_, **kwargs_)
            if update:
                proxy = self._responses[-1]
                await proxy.edit(*args, **kwargs)
            else:
                message = await self._interaction.execute(*args, **kwargs)
                proxy = ResponseProxy(
                    message,
                    editor=functools.partial(
                        _ephemeral_followup_editor,
                        _wh_id=self._interaction.webhook_id,
                        _tkn=self._interaction.token,
                        _m_id=message.id,
                    ),
                    deleteable=not includes_ephemeral(kwargs.get("flags", hikari.MessageFlag.NONE)),
                )
                self._responses.append(proxy)
                self._deferred = False

            if delete_after is not None:
                self.app.create_task(_cleanup(delete_after, proxy))

            return self._responses[-1]

        if args:
            if not isinstance(args[0], hikari.ResponseType):
                kwargs["content"] = args[0]
                kwargs.setdefault("response_type", hikari.ResponseType.MESSAGE_CREATE)
            else:
                kwargs["response_type"] = args[0]
                if len(args) > 1:
                    kwargs.setdefault("content", args[1])
        else:
            kwargs.setdefault("response_type", hikari.ResponseType.MESSAGE_CREATE)

        await self._interaction.create_initial_response(**kwargs)

        # Initial responses are special and need their own edit method defined
        # so that they work as expected for when the responses are ephemeral
        async def _editor(
            rp: ResponseProxy, *args_: Any, inter: hikari.CommandInteraction, **kwargs_: Any
        ) -> hikari.Message:
            await inter.edit_initial_response(*args_, **kwargs_)
            return await rp.message()

        proxy = ResponseProxy(
            fetcher=self._interaction.fetch_initial_response,
            editor=functools.partial(_editor, inter=self._interaction)
            if includes_ephemeral(kwargs.get("flags", hikari.MessageFlag.NONE))
            else None,
        )
        self._responses.append(proxy)
        self._responded = True

        if kwargs["response_type"] in (
            hikari.ResponseType.DEFERRED_MESSAGE_CREATE,
            hikari.ResponseType.DEFERRED_MESSAGE_UPDATE,
        ):
            self._deferred = True

        if delete_after is not None:
            self.app.create_task(_cleanup(delete_after, proxy))

        return self._responses[-1]


class InteractionContext(_InteractionContext):
    """
    A wrapper for `hikari.ComponentInteraction`
    """
    def __init__(
        self, 
        event: hikari.InteractionCreateEvent,
        app: lightbulb.app.BotApp,
        ephemeral: bool = False,
        defer: bool = False,
        auto_defer: bool = False,
    ):
        super().__init__(event=event, app=app)
        self._interaction = event.interaction
        self._responded = False
        self.message: hikari.Message | None = None
        self._default_ephemeral = ephemeral
        self._deferred: bool = defer
        self._parent_message: hikari.Message | None = None
        self._auto_defer: bool = auto_defer
        if defer:
            asyncio.create_task(self._ack_interaction())
        if auto_defer:
            asyncio.create_task(self._deferr_on_timelimit())


    async def _maybe_defer(self) -> None:
        if self._auto_defer:
            await self.respond(hikari.ResponseType.DEFERRED_MESSAGE_CREATE)

    async def _deferr_on_timelimit(self):
        respond_at = self.i.created_at + timedelta(seconds=(3 - REST_SENDING_MARGIN))  
        respond_at = respond_areplace(tzinfo=None)
        await asyncio.sleep(
            (respond_at - datetime.utcnow()).total_seconds()
        )
        if not self._responded:
            await self._ack_interaction()

    async def fetch_parent_message(self):
        self.i.delete
        if not self._parent_message:
            self._parent_message = await self.i.fetch_parent_message()

    async def _ack_interaction(self):
        if self._upadate:
            await self.i.create_initial_response(ResponseType.DEFERRED_MESSAGE_UPDATE)
        else:
            await self.i.create_initial_response(ResponseType.DEFERRED_MESSAGE_CREATE)
        self._deferred = True

    @property
    def i(self) -> hikari.ComponentInteraction:
        return self._interaction

    @property
    def author(self) -> hikari.User:
        return self.interaction.user

    async def delete_initial_response(self, after: int | None = None):
        if after:
            await asyncio.sleep(after)
        return await self.i.delete_initial_response()

    async def delete_webhook_message(self, message: int | hikari.Message, after: int | None = None):
        if after:
            await asyncio.sleep(after)
        return await self.i.delete_message(message)
    
    async def execute(self, delete_after: int | None = None, **kwargs) -> hikari.Message:
        if not self._responded:
            # make inital response instead
            await self.respond(**kwargs)
            if delete_after:
                # start delete timeer
                asyncio.create_task(self.delete_initial_response(after=delete_after))
            # if ensure_return:
            #     # ensure, that a message and not None is returned
            return await self.i.fetch_initial_response()
        else:
            # initial response was made -> actually execute the webhook
            msg = await self.i.execute(**kwargs)
            if delete_after:
                # start delete timer
                asyncio.create_task(self.delete_webhook_message(msg, after=delete_after))
            return msg

    @property
    def custom_id(self) -> str:
        return self.interaction.custom_id

    @property
    def values(self) -> Sequence[str]:
        return self.interaction.values

    @property
    def created_at(self) -> datetime:
        return self.interaction.created_at

    @property
    def is_valid(self) -> bool:
        return datetime.now() < (self.created_at + timedelta(minutes=15))

    @property
    def command(self) -> None:
        return None
    
    @property
    def prefix(self) -> None:  # type: ignore
        return None

    @property
    def invoked_with(self) -> None:  #type: ignore
        return None

    async def initial_response_create(self, **kwargs):
        if not self._deferred:
            await self.i.create_initial_response(
                response_type=ResponseType.MESSAGE_CREATE, 
                **self._extra_respond_kwargs, 
                **kwargs
            )
        else:
            await self.i.edit_initial_response(
                **self._extra_respond_kwargs, 
                **kwargs
            )
        self._responded = True
        asyncio.create_task(self._cache_initial_response())
    
    async def _cache_initial_response(self) -> None:
        self.message = await self.i.fetch_initial_response()

    async def fetch_response(self):
        """message from initial response or the last execute"""
        if not self.message:
            await self._cache_initial_response()
        return self.message

    async def initial_response_update(self, **kwargs):
        if not self._deferred:
            await self.i.create_initial_response(
                response_type=ResponseType.MESSAGE_UPDATE, 
                **self._extra_respond_kwargs, 
                **kwargs
            )
        else:
            await self.i.edit_initial_response(
                **self._extra_respond_kwargs, 
                **kwargs
            )
        self._responded = True
        asyncio.create_task(self._cache_initial_response())

            


InteractionContext.execute.__doc__ = hikari.ComponentInteraction.execute.__doc__

    