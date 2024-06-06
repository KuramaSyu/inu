"""Context based on REST responses"""
from typing import * 

import asyncio
import hikari
from hikari import Snowflake, SnowflakeishOr
from hikari.impl import MessageActionRowBuilder
import lightbulb
from lightbulb.context import Context, ResponseProxy, OptionsProxy
from lightbulb.context.prefix import PrefixContext

from . import InuContextProtocol, InuContext, InuContextBase, UniqueContextInstance, InteractionContext



class RESTContext(Context, InuContextProtocol, InuContext, InuContextBase):
    """
    Class for Context, which is not based on Interactions.

    Args:
        app (:obj:`~.app.BotApp`): The ``BotApp`` instance that the context is linked to.
    """

    __slots__ = ("_app", "_responses", "_responded", "_deferred", "_invoked", "_event", "_options")
    def __init__(self, app: hikari.GatewayBot, event: hikari.MessageCreateEvent | hikari.MessageUpdateEvent):
        self._event = event
        self._options: Dict[str, Any] = {}
        super().__init__(app) # type: ignore
        self = UniqueContextInstance.get(self)
        self._options: Dict[str, Any] = {}

    @property
    def raw_options(self) -> Dict[str, Any]:
        return self._options
    
    @property
    def last_response(self) -> ResponseProxy:
        return self._responses[-1]

    @property
    def options(self) -> OptionsProxy:
        """:obj:`~OptionsProxy` wrapping the options that the user invoked the command with."""
        return OptionsProxy(self.raw_options)

    @property
    def id(self):
        """
        Bare RESTContext can be created at anytime. But the cache holds one instance 
        determined by the message id for a specific time. So MessageUpdateEvents will
        return the exact same instance as MessageCreateEvents.
        """
        return self.original_message.id

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
    def guild_id(self) -> Optional[Snowflake]:
        return self.event.message.guild_id
    
    @property
    def guild(self) -> Optional[hikari.Guild]:
        if not self.guild_id:
            return None
        return self.bot.cache.get_guild(self.guild_id)

    @property
    def invoked_with(self) -> str:
        return ""

    @property
    def prefix(self) -> str:
        return ""

    @property
    def command(self) -> None:
        return None
    
    @property
    def message_id(self) -> hikari.Snowflake:
        return self.event.message_id

    @property
    def original_message(self) -> hikari.Message:
        return self._event.message
    

    async def message(self) -> hikari.Message:
        return self._event.message

    def get_channel(self) -> Optional[Union[hikari.GuildChannel, hikari.Snowflake]]:
        if self.guild_id is not None:
            return self.app.cache.get_guild_channel(self.channel_id)
        return self.app.cache.get_dm_channel_id(self.author.id)

    async def respond(
        self, 
        *args: Any, 
        delete_after: Union[int, float, None] = None, 
        update: bool | SnowflakeishOr[hikari.Message] = False,
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
        update_message: SnowflakeishOr[hikari.PartialMessage] | None = update if isinstance(update, (hikari.Snowflake, hikari.PartialMessage)) else None
        self._deferred = False
        msg = None

        kwargs.pop("flags", None)
        kwargs.pop("response_type", None)

        if args and isinstance(args[0], hikari.ResponseType):
            args = args[1:]
        if update and (self._responses or update_message):
            if update_message:
                kwargs.setdefault("channel", self.channel_id)
                msg = await self.app.rest.edit_message(*args, message=update_message, **kwargs)
            else:
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

    async def _maybe_defer(self) -> None:
        """Not needed when using REST"""
        ...

    async def defer(self, background: bool = True):
        """
        Acknowledges interactions.

        Note:
        -----
        Not needed with REST based Context 
        """
        ...
    
    async def auto_defer(self) -> None:
        """
        automatically defers interactions

        Note:
        -----
        Not needed with RSET based Context
        """
        ...

    def set(self, **kwargs):
        """custom things to set"""
        if options := kwargs.get("options"):
            self._options = options

    async def respond_with_modal(self, *args, **kwargs) -> None:
        raise NotImplementedError(f"`respond_with_modal` does not work with {self.__class__.__name__}")
        #return await super().respond_with_modal(title, custom_id, component, components)

    @classmethod
    def from_event(cls, event: hikari.Event):
        if not isinstance(event, (hikari.MessageCreateEvent, hikari.MessageUpdateEvent)):
            raise TypeError(f"Can't create `{cls.__name__}` with `{type(event)}`")
        return cls(app=event.app, event=event)
    

    async def delete_initial_response(self) -> None:
        await self.original_message.delete()


    async def delete_webhook_message(self, message: int | hikari.Message, after: int | None = None):
        """
        delete a webhook message

        Args:
        ----
        message : int
            the message to delete. Needs to be created by this interaction
        after : int
            wait <after> seconds, until deleting
        """
        if after is not None:
            await asyncio.sleep(after)
        await self.app.rest.delete_message(self.channel_id, message)

    async def ask(
            self, 
            title: str, 
            button_labels: List[str] = ["Yes", "No"], 
            ephemeral: bool = True, 
            timeout: int = 120,
            delete_after_timeout: bool = True,
            allowed_users: List[hikari.SnowflakeishOr[hikari.User]] | None = None
    ) -> Tuple[str, "InteractionContext"]:
        """
        ask a question with buttons

        Args:
        -----
        title : str
            the title of the message
        button_labels : List[str]
            the labels of the buttons
        ephemeral : bool
            whether or not the message should be ephemeral
        timeout : int
            the timeout in seconds
        allowed_users : List[hikari.User]
            the users allowed to interact with the buttons
        
        Returns:
        --------
        Tuple[str, "InteractionContext"]
            the selected label and the new context
        """
        prefix = "ask_"
        components: List[MessageActionRowBuilder] = []
        for i, label in enumerate(button_labels):
            if i % 5 == 0:
                components.append(MessageActionRowBuilder())
            components[0].add_interactive_button(
                hikari.ButtonStyle.SECONDARY,
                f"{prefix}{label}",
                label=label
            )
        proxy = await self.respond(title, components=components, ephemeral=ephemeral)
        selected_label, event, interaction = await self.app.wait_for_interaction(
            custom_ids=[f"{prefix}{l}" for l in button_labels],
            user_ids=allowed_users or self.author.id,
            message_id=(await proxy.message()).id,
            timeout=timeout
        )
        new_ctx = InteractionContext.from_event(event)
        return selected_label.replace(prefix, "", 1), new_ctx

    async def ask_with_modal(
            self, 
            **kwargs
    ) -> Tuple[str | List[str], "InteractionContext"] | Tuple[None, None]:
        raise NotImplementedError(f"`ask_with_modal` does not work with {self.__class__.__name__}")
    
    @property
    def author_id(self) -> hikari.Snowflake:
        return self.author.id