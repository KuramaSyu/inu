from typing import Union, Optional, List, Dict, Union, Tuple
import traceback
import logging
import random
import numpy as np

import hikari
from hikari import Member
from hikari.impl import ActionRowBuilder
import lightbulb
from lightbulb.context import Context

from utils.paginators.common import PaginatorReadyEvent, listener, Paginator
from utils import Colors, Grid

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

class WrongPlayerError(Exception):
    pass
        
class ColumnNotInFieldError(Exception):
    pass

class ColumnError(Exception):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)
        
class GameOverError(Exception):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)
    

class PlayerData:
    def __init__(self):
        pass

class Player:
    
    __slots__: List[str] = ["name", "id", "token"]
    def __init__(
        self,
        name: str,
        id: str,
        token: str,
    ):
        self.name = name
        self.id = id
        self.token = token
        
class HikariPlayer(Player):
    __slots__: List[str] = ["name", "id", "token", "user"]
    def __init__(
        self,
        name: str,
        id: str,
        token: str,
        user: hikari.Member
    ):
        self.name = name
        self.id = id
        self.token = token
        self.user = user

class Board:
    """A class which represents a connect 4 board"""
    def __init__(self, marker: str):
        """
        Args:
        -----
            - marker: (str) the emoji which should be used in __str__ to highlight the game over coordinates
        """
        self.board: List[List[Union[None, Player]]] = [ [None, None, None, None, None, None, None, None],  ##⬛
                                                        [None, None, None, None, None, None, None, None],
                                                        [None, None, None, None, None, None, None, None],
                                                        [None, None, None, None, None, None, None, None],
                                                        [None, None, None, None, None, None, None, None],
                                                        [None, None, None, None, None, None, None, None],
                                                        [None, None, None, None, None, None, None, None],
                                                        [None, None, None, None, None, None, None, None]
                                                      ]
        # game is over when these are set
        # int, int = row, column
        self.game_over_coordinates: List[Tuple[int, int]] | None = None
        self.marker = marker
        self.bg_color = "⬛"
        
    def drop_token(self, column: int, player: Player):
        """
        Drops a token into the board.
        
        Args:
        -----
            - column: (int) th column of the board where you want to drop the token
            - player: (~.Player) The player who "owns" the "dropped token". 
        """
        col = Grid.get_cols(self.board)[column]
        first_free_slot = 0
        for i, cell in enumerate(col):
            if i == 0 and not cell is None:
                raise ColumnError(f"Column: {column} has no free slots anymore")
            if cell is None:
                first_free_slot = i
            else:
                break
        self.board[first_free_slot][column] = player
        
    def check_for_game_over(self):
        """
        Checks if the game is over.
        If the game is over, `self.game_over_coordinates` will be changed to the coordinates and wont be `None` anymore
        """
        lines = [*self.board, *Grid.get_cols(self.board), *Grid.get_forward_diagonals(self.board)]
        def check(lines: List) -> Tuple[int, int]:
            for i_l, line in enumerate(lines):
                count = 0
                for i_s, slot in enumerate(line):
                    if count >= 4:
                        return i_l, i_s-1  #(in the last iteration it got 4, hence -1)
            return -1, -1
        line, slot = check(*self.board)
        if not -1 in [line, slot]:
            self.game_over_coordinates = [(line, slot), (line, slot-1), (line, slot-2), (line, slot-3)]
            return
        line, slot = check([*Grid.get_cols(self.board)])
        if not -1 in [line, slot]:
            self.game_over_coordinates = [(line, slot), (line-1, slot), (line-2, slot), (line-3, slot)]
            return
        line, slot = check([*Grid.get_forward_diagonals(self.board)])
        if not -1 in [line, slot]:
            self.game_over_coordinates = [(line, slot), (line-1, slot-1), (line-2, slot-2), (line-3, slot-3)]
            
    def __str__(self) -> str:
        lines = []
        part = ""
        string = ""
        for line in self.board:
            for player in line:
                if player:
                    part += player.token
                else:
                    part += self.bg_color
            lines.append(part)

        if not self.game_over_coordinates:        
            return "\n".join(lines)

        for c in self.game_over_coordinates:
            lines[c[0]][c[1]] = self.marker
        return "\n".join(lines)
                    
                
                

            
        
class BaseConnect4:
    def __init__(
        self,
        player1: Player,
        player2: Player,
        extra_marker: str,
    ):
        self.player1: Player = player1
        self.player2: Player = player2
        self.player_turn: Player
        self.game_winner: Optional[Player] = None
        self.game_over = True
        self.board = Board(extra_marker)
        
    def start(self):
        self.game_over = False
        self.player_turn = random.choice([self.player1, self.player2])
        
    def do_turn(self, column: int,  player: Optional[Player] = None):
        """
        Make a turn for a player.
        
        Overwrites:
        -----------
            - self.game_over: wehter or not the game is over
            - self.game_winner: the winner of the game, if the game is over
            - self.player_turn: players will be twisted
            - self.board.game_over_coordinates: the coordinates of the tokes, when the game is over. Otherwise `None`
        
        Args:
        -----
            - column: (int) the column where to player put in his token. Start with 0
            - player: (~.Player) the player whos turn is. Just an addidional test. If not given, then the test is skipped
            
        Raises:
        -------
            - ~.WrongPlayerError: Not the players turn
            - ~.ColumnNotInFieldError: The chosen Column doesn't exist
            - ~.ColumnError: The given column is filled up
            - ~.IndexError: th board contains no <column>th column
            - ~.GameOverError: game is already over. No further moves accepted
        """
        if not player is None and player != self.player_turn:
            raise WrongPlayerError(f"Not {player.name}'s turn")
        if self.game_over:
            raise GameOverError("Game is already over!")
        if not player:
            player = self.player_turn
        self.board.drop_token(column, player)
        self.board.check_for_game_over()
        if self.board.game_over_coordinates:
            self.game_over = True
        self.game_winner = self.player_turn
        
        

        

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
        # generate player marks
        marks = ['🔵','🟣','🔴','🟠','🟢','🟡','🟤'] #,'⚪'
        self.mark1 = random.choice(marks)
        marks.remove(self.mark1)
        self.mark2 = random.choice(marks)
        marks.remove(self.mark2)
        if self.mark1 in '🟢🟡' and self.mark2 in '🟢🟡':
            marks.remove(self.mark2)
            self.mark2 = random.choice(marks)
        extra_marker = random.choice(marks)

        self.orienation_letter = [f':regional_indicator_{l}:' for l in 'abcdefgh']
        self.orientation_number = "1️⃣2️⃣3️⃣4️⃣5️⃣6️⃣7️⃣8️⃣"  #*️⃣ #*️⃣

        # generate game
        g_player1 = HikariPlayer(player1.display_name, player1.id, self.mark1, player1)
        g_player2 = HikariPlayer(player2.display_name, player2.id, self.mark2, player2)
        self.game = BaseConnect4(g_player1, g_player2, extra_marker)
        
        self.game_infos = []

    def out_put(self):
        pass
    
    @listener(PaginatorReadyEvent)
    async def build_up_game(self, _: PaginatorReadyEvent):
        pass
    
    def update_embed(self):
        embed = hikari.Embed()
        embed.title = f"{'- '*4} Connect 4 {'- '*4}"
        embed.description = self.board_to_str()
        if self.game_infos:
            embed.add_field('Be aware:', "\n\n".join(info for info in self.game_infos))
        embed.set_footer(f"{self.game.player_turn.name}'s turn", icon=self.game.player_turn.d.user.avatar_url)
    
    def board_to_str(self) -> str:
        string = ""
        b = str(self.game.board)
        
        lines = b.split("\n")
        for i, line in enumerate(lines):
            string += f"{self.orientation_number[i]}{line}\n"
        string += f"*️⃣{''.join}"
        return string
            
        
    
    
    


        
        
        
        

