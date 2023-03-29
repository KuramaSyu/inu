from weakref import WeakValueDictionary
from abc import abstractmethod
from typing import *

from cachetools import cached, TTLCache
from core import getLogger
from . import InuContext
from lightbulb import ResponseProxy

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
    @cached(cache=TTLCache(maxsize=1024, ttl=60))
    def _get(cls, self: InuContextT) -> InuContextT:
        # if (instance := cls._instances.get(self.id)) is not None:
        #     print(f"return existing instance with type {type(self)} and ID {self.id}")
        #     return instance  # type: ignore
        # #if self.id:
        # print(f"create instance with type {type(self)} ID {self.id}")
        # cls._instances[self.id] = self
        # print(f"return instance with type {type(self)} ID {self.id}")
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
    def __hash__(self) -> int:
        return self.id
    
    @property
    def last_response(self) -> Optional[ResponseProxy]:
        return self._responses[-1] if self._responses else None

    @property
    def is_hashable(self) -> bool:
        return self.id is not None