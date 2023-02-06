from weakref import WeakValueDictionary
from abc import abstractmethod
from typing import *

from core import getLogger
from . import InuContext

log = getLogger(__name__)

InuContextT = TypeVar("InuContextT", bound="InuContext")

class UniqueContextInstance:
    _instances: WeakValueDictionary[int, InuContext] = WeakValueDictionary()

    @classmethod
    def get(cls, self: InuContextT) -> InuContextT:
        if (instance := cls._instances.get(self.id)) is not None:
            log.debug(f"return existing instance with type {type(self)} and ID {self.id}")
            return instance  # type: ignore
        if self.id:
            log.debug(f"create instance with type {type(self)} ID {self.id}")
            cls._instances[self.id] = self
        return self



class ContextEqualTrait:
    @property
    def id(self) -> int:
        raise NotImplementedError("This method needs to be subclassed")
    def __eq__(self, other: object):
        if not isinstance(other, InuContext):
            raise TypeError(f"Can't compare {type(self)} from `InuContext` with {type(other)}")
        if not type(self) == type(other):
            return False
        if other.id is None:
            return False
        return other.id == self.id


class InuContextBase(ContextEqualTrait):
    ...