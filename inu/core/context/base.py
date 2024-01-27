from weakref import WeakValueDictionary
from abc import abstractmethod
from typing import *

from cachetools import cached, TTLCache
from core import getLogger
from . import InuContext
from lightbulb import ResponseProxy, OptionsProxy

log = getLogger(__name__)

InuContextT = TypeVar("InuContextT", bound="InuContext")

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
    _responses: List[ResponseProxy] = []
    _options: Dict[str, Any] = {}
    _update: bool
    def __hash__(self) -> int:
        return self.id
    
    def set_update(self, value: bool):
        """Whether to update the message or not when responding as default"""
        self._update = value

    @property
    def last_response(self) -> Optional[ResponseProxy]:
        return self._responses[-1] if self._responses else None

    @property
    def is_hashable(self) -> bool:
        return self.id is not None
    
    @property
    def raw_options(self) -> Dict[str, Any]:
        return self._options

    @property
    def options(self) -> OptionsProxy:
        """:obj:`~OptionsProxy` wrapping the options that the user invoked the command with."""
        return OptionsProxy(self.raw_options)