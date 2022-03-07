from . import *
from ..vote import PollVote



class ScaleVoteInstance(Paginator):
    def __init__(
        self, 
        options: Dict[str, str],
        active_until: int,
        anonymous: bool = True,
        poll_title: str = "Poll",
        poll_description: str = "",
    ) -> None:
        self.title = title
        self.description = description
        super().__init__()

class PollVoteInstance(Paginator):
    def __init__(self):
        self._vote = PollVote(options, active_until, anonymous, poll_title, poll_description)
        super().__init__([self._vote.embed])