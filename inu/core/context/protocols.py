from typing import *

from lightbulb.context import Context


T = TypeVar("T")


class InuContextProtocol(Protocol[T]):
    def from_context(cls: Context, ctx: Context) -> T:
        ...