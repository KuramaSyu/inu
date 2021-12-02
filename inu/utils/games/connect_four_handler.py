from typing import Union, Optional, List, Dict
import traceback
import logging
import random
import numpy as np

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

class WrongPlayerError(Exception):
    pass
        
class ColumnNotInFieldError(Exception):
    pass
    

class PlayerData:
    pass

class Player:
    
    __slots__: List[str] = ["name", "id", "token", "d"]
    def __init__(
        self,
        name: str,
        id: str,
        token: str,
    ):
        self.name = name
        self.id = id
        self.token = token
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
        
    def drop_token(self, token: str):
        

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
        self.player1: Player = player1
        self.player2: Player = player2
        self.player_turn: Player
        self.winning_conditions = []
        self.game_over = True
        self.board = Board()
        
    def start(self):
        self.game_over = False
        self.player_turn = random.choice([self.player1, self.player2])
        
    def do_turn(self, column: int,  player: Optional[Player] = None):
        """
        Make a turn for a player
        
        Args:
        -----
            - column: (int) the column where to player put in his token. Start with 0
            - player: (~.Player) the player whos turn is. Just an addidional test. If not given, then the test is skipped
            
        Raises:
        -------
            - ~.WrongPlayerError: Not the players turn
            - ~.ColumnNotInFieldError: The chosen Column doesn't exist
        """
        if not player is None and player != self.player_turn:
            raise WrongPlayerError(f"Not {player.name}'s turn")
        self.board.drop_token(column, player.token)
        
        
        
        

