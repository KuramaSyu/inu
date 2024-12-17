from hikari import Event

from core import Inu

class PaginatorReadyEvent(Event):
    def __init__(self, bot: Inu):
        self.bot = bot

    @property
    def app(self):
        return self.bot



class PaginatorTimeoutEvent(Event):
    def __init__(self, bot: Inu):
        self.bot = bot

    @property
    def app(self):
        return self.bot