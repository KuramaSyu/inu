from typing import Union, Optional, List, Dict
import traceback
import logging


import hikari
from hikari import Member
from hikari.impl import ActionRowBuilder
import lightbulb
from lightbulb import Context

from .common import PaginatorReadyEvent
from .common import Paginator
from .common import listener
from utils import Color

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)


class Connect4Handler(Paginator):
    def __init__(
        self,
        player1: hikari.Member,
        player2: hikari.Member,
    ):
        self.player1 = player1
        self.player2 = player2
        super().__init__(
            page_s=["starting up..."],
            timeout=10*60,
            disable_pagination=True,
            disable_paginator_when_one_site=False,
            listen_to_events=[hikari.ReactionAddEvent]
        )

    def build_message(self):
        pass