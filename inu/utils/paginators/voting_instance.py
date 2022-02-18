from . import *


class ScaleVoteInstance(Paginator):
    def __init__(
        self,
        title: str,
        description: str = "",
    ) -> None:
        self.title = title
        self.description = description
        super().__init__()