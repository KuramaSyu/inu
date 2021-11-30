from typing import Union, Optional, List, Dict
import traceback
import logging


import hikari
from hikari import Member
from hikari.impl import ActionRowBuilder
import lightbulb
from lightbulb.context import Context

from utils.paginators.common import PaginatorReadyEvent
from utils import Paginator
from utils.paginators.common import listener
from utils import Colors

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

class PlayerData:
    pass

class Player:
    
    __slots__: List[str] = ["name", "id", "marker", "d"]
    def __init__(
        self,
        name: str,
        id: str,
        marker: str,
    ):
        self.name = name
        self.id = id
        self.marker = marker
        self.d = PlayerData

class Board:
    """A class which represents a connect 4 board"""
    def __init__(self):
        self.board =[   '⬛','⬛','⬛','⬛','⬛','⬛','⬛','⬛',
                        '⬛','⬛','⬛','⬛','⬛','⬛','⬛','⬛',
                        '⬛','⬛','⬛','⬛','⬛','⬛','⬛','⬛',
                        '⬛','⬛','⬛','⬛','⬛','⬛','⬛','⬛',
                        '⬛','⬛','⬛','⬛','⬛','⬛','⬛','⬛',
                        '⬛','⬛','⬛','⬛','⬛','⬛','⬛','⬛',
                        '⬛','⬛','⬛','⬛','⬛','⬛','⬛','⬛',
                        '⬛','⬛','⬛','⬛','⬛','⬛','⬛','⬛' ]


class Connect4Handler(Paginator):
    def __init__(
        self,
        player1: Player,
        player2: Player,
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

        self.last_ctx = None

        self.winning_conditions = []
        self.gameOver = True
        self.player1 = int()
        self.player2 = int()
        self.turn = 'initialisierung...'
        self.board_message = ''
        self.mark = ''
        self.turn_count = int(0)
        self.error_message = ''
        self.board_message_id = int()
        self.game_board = ''
        self.board_title = '— — — — Connect 4 — — — —'
        self.board_description = 'Spiel läuft'
        self.value1_title = f'Zug {self.turn_count}'
        self.board_footer = f'{self.turn}'
        self.value2_title = 'Log'
        self.value2 = '———————\n'
        self.mark1 = ''
        self.mark2 = ''
        self.should_logic_run = None
        self.old_player1 = None
        self.old_player2 = None
        self.old_board_message_id = None
        self.inu = None

    def out_put(self):
        pass
    

class BaseConnect4:
    def __init__(
        self,
        player1: Player,
        player2: Player,
    ):
        self.player1 = player1
        self.player2 = player2
        self.winning_conditions = []
        self.gameOver = True
        self.board = Board()
        
        
        

