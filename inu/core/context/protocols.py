from typing import *
from abc import ABC, abstractmethod

import hikari
from lightbulb.context import Context


T = TypeVar("T")


class InuContext(ABC):
    @abstractmethod
    def from_context(cls: Context, ctx: Context) -> T:
        ...

    @abstractmethod
    def from_event(cls: Context, event: hikari.Event) -> T:
        ...
    
    @property
    @abstractmethod
    def original_message(self) -> hikari.Message:
        ...



class InuContextProtocol(Protocol[T]):
    def from_context(cls: Context, ctx: Context) -> T:
        ...
    
    def from_event(cls: Context, event: hikari.Event) -> T:
        ...

    @property
    def original_message(self) -> hikari.Message:
        ...
