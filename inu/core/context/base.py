from weakref import WeakValueDictionary
from abc import abstractmethod
from typing import *
from datetime import timedelta

from cachetools import cached, TTLCache
from hikari import Embed
from hikari.impl import MessageActionRowBuilder
from core import getLogger

from ..bot import Inu
from .protocols import InuContext
from .response_state import BaseResponseState, InitialResponseState

log = getLogger(__name__)

InuContextT = TypeVar("InuContextT", bound="InuContext")


class Response:
    @abstractmethod
    async def respond(
        self,
        embeds: List[Embed] | None = None,
        content: str | None = None,
        delete_after: timedelta | None = None,
        ephemeral: bool = False,
        components: List[MessageActionRowBuilder] | None = None,
    ):
        ...
        
    
    
class UniqueContextInstance:
    _instances: WeakValueDictionary[int, InuContext] = WeakValueDictionary()

    @classmethod
    def get(cls, self: InuContextT) -> InuContextT:
        if not self.is_hashable:
            return self
        return cls._get(self)

    @classmethod
    @cached(cache=TTLCache(maxsize=1024, ttl=500))
    def _get(cls, self: InuContextT) -> InuContextT:
        return self



class ContextEqualTrait:
    @property
    def id(self) -> int:
        raise NotImplementedError("This method needs to be subclassed")
    def __eq__(self, other: object):
        if not isinstance(other, InuContext):
            return False
        if not type(self) == type(other):
            return False
        if other.id is None:
            return False
        return other.id == self.id


class InuContextBase(ContextEqualTrait):
    """
    Base class for InuContext defining all necessary properties and methods
    """
    _responses: List[Response] = []
    _options: Dict[str, Any] = {}
    _update: bool
    _defered: bool
    _responded: bool
    _response_state: BaseResponseState
    _bot: Inu
    
    def __init__(self) -> None:
        self._update = False
        self._defered = False
        self._responded = False
        self._responses: List[Response] = []
        self._response_state: BaseResponseState = InitialResponseState(self.interaction, self, [])  # type: ignore
        self._bot: Inu = Inu()
    
    def set_response_state(self, new_state: BaseResponseState):
        """Changes the response state to a new state"""
        log.debug(f"Setting response state to {type(new_state).__name__}")
        self._response_state = new_state
    
    def is_responded(self) -> bool:
        """Whether the context has been responded. Checks is the response state is not InitialResponseState"""
        return not isinstance(self.response_state, InitialResponseState)

    @property
    def response_state(self) -> BaseResponseState:
        return self._response_state

    @property
    def defered(self):
        """
        whether or not the interaction has been defered
        """
        return self._defered

    @defered.setter
    def defered(self, value):
        self._defered = value

    @property
    def responded(self):
        """
        whether or not the interaction has been responded/acknowledged
        """
        return self._responded

    @responded.setter
    def responded(self, value):
        self._responded = value
        
    def __hash__(self) -> int:
        return self.id
    
    def set_update(self, value: bool):
        """Whether to update the message or not when responding as default"""
        self._update = value

    @property
    def last_response(self) -> Optional[Response]:
        return self._responses[-1] if self._responses else None

    @property
    def is_hashable(self) -> bool:
        return self.id is not None

    @property
    def options(self) -> Dict[str, Any]:
        return {}
    

