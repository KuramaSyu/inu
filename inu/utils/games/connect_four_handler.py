
from asyncio import create_subprocess_shell
from typing import Union, Optional, List, Dict, Union, Tuple
import traceback
import logging
import random
import numpy as np
from copy import deepcopy
from enum import Enum
from collections import OrderedDict
import json

import hikari
from hikari import Member
from hikari.impl import MessageActionRowBuilder
import lightbulb
from lightbulb.context import Context

from utils.paginators.base import PaginatorReadyEvent, listener, Paginator
from utils import Colors, Grid
from core import get_context, InuContext

log = logging.getLogger(__name__)
log.setLevel(logging.WARNING)



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
        id: int,
        token: str,
        user: hikari.Member
    ):
        self.name = name
        self.id = id
        self.token = token
        self.user = user



class Slot:
    """Represents one solt of the board"""
    def __init__(self, row: int, column: int, marker: Optional[str] = None):
        self.row = row
        self.column = column
        self.marker = marker   



class GameStatus(Enum):
    """Represents the game status"""
    OVER = 0
    RUNNING = 1
    SURRENDERED = 2
    DRAW = 3   

class Board:
    """A class which represents a connect 4 board"""
    def __init__(self, game: "BaseConnect4", marker: str, rows: int = 8, columns: int = 8):
        """
        Args:
        -----
        marker : str
            the emoji which should be used in __str__ to highlight the game over coordinates
        """
        self.game = game
        self.board: List[List[Slot]] = [[Slot(r, c) for c in range(columns)] for r in range(rows)]
        # game is over when these are set
        # int, int = row, column
        self.game_over_slots: List[Slot] | None = None
        self.marker = marker
        self.bg_color = "⬛"
        self.rows = rows
        self.columns = columns
        

    def drop_token(self, column: int, player: Player):
        """
        Drops a token into the board.
        
        Args:
        -----
        column : int 
            the column of the board where you want to drop the token
        player : ~.Player 
            The player who "owns" the "dropped token". 
        """
        col = Grid.get_cols(self.board)[column]
        first_free_slot = 0
        for i, cell in enumerate(col):
            if i == 0 and not cell.marker is None:
                raise ColumnError(f"Column {column+1} has no free slots anymore")
            if cell.marker is None:
                first_free_slot = i
            else:
                break
        self.board[first_free_slot][column].marker = player.token


    def check_for_game_draw(self):
        """checks if game is a draw

        Note:
        -----
        If game is draw, `self.game.status` will be set to `GameStatus.DRAW`        
        """
        valid_marker_count = 0
        for row in self.board:
            for slot in row:
                if slot.marker:
                    valid_marker_count += 1
        if valid_marker_count == int(self.rows * self.columns):
            self.game.status = GameStatus.DRAW

        
    def check_for_game_over(self):
        """
        Checks if the game is over.
        If the game is over, `self.game_over_slots` will be changed to the coordinates and wont be `None` anymore
        And `self.game.status` will be set to `GameStatus.OVER`
        """
        def check(lines: List[List[Slot]]) -> List[Slot]:
            # I know that this could be shorter
            # but I also want, that when a game is won with more than 4 slots,
            # the system will also display more the 4 slots
            longest: List[Slot] = []
            slots: List[Slot] = []

            def set_if_longest():
                nonlocal longest
                nonlocal slots
                if len(slots) > len(longest):
                    longest = slots

            for line in lines:
                slots = []
                for slot in line:
                    if slot.marker is None:
                        # empty slot
                        set_if_longest()
                        slots = []
                    elif slots == []:
                        # first slot
                        slots.append(slot)
                    elif slots[-1].marker != slot.marker:
                        # other slot then before
                        set_if_longest()
                        slots = [slot]
                    else:
                        # same slot as before
                        slots.append(slot) 
                set_if_longest()

            if len(longest) >= 4:
                return longest
            return []

        # test rows, cols and diagonals and backward diagonals
        # for a +4 row
        for slots in [
            self.board,
            Grid.get_cols(self.board), 
            Grid.get_backward_diagonals(self.board), 
            Grid.get_forward_diagonals(self.board)
        ]:
            row_of_4 = check(slots)
            if row_of_4:
                self.game_over_slots = row_of_4
                self.game.status = GameStatus.OVER
                break
            

    def __str__(self) -> str:
        lines = []
        part = ""
        board = deepcopy(self.board)
        if self.game_over_slots:
            for slot in self.game_over_slots:
                board[slot.row][slot.column].marker = self.marker
            
        for line in board:
            for slot in line:
                if slot.marker:
                    part += slot.marker
                else:
                    part += self.bg_color
            lines.append(part)
            part = ""       
        return "\n".join(lines)


    def marked_slots_board(self) -> str:
        return str(self)
                    
                
                
class BaseConnect4:
    def __init__(
        self,
        player1: Player,
        player2: Player,
        extra_marker: str,
        rows: int,
        columns: int,
    ):
        self.player1: Player = player1
        self.player2: Player = player2
        self.player_turn: Player
        self.game_winner: Optional[Player] = None
        self.game_over = True
        self.status = GameStatus.RUNNING
        self.board = Board(
            game=self,
            marker=extra_marker,
            rows=rows,
            columns=columns,
        )
        self.start()
        self.turn: int = 1


    @property
    def surrendered(self) -> bool:
        """wether or not a player has surrendered"""
        return self.status == GameStatus.RUNNING

        
    def start(self):
        """
        sets `self.game_over` to False
        and chooses a player randomly
        """
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
            - self.board.game_over_slots: the coordinates of the tokes, when the game is over. Otherwise `None`
        
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
        # checks
        if not player is None and player != self.player_turn:
            raise WrongPlayerError(f"Not {player.name}'s turn")
        if self.game_over:
            raise GameOverError("Game is already over!")
        if not player:
            player = self.player_turn

        # executing game
        self.board.drop_token(column, player)
        self.board.check_for_game_over()
        self.board.check_for_game_draw()
        if self.status != GameStatus.RUNNING:
            self.game_over = True
            if self.status == GameStatus.OVER:
                self.game_winner = self.player_turn
        self.cycle_players()
        self.turn += 1
   

    def cycle_players(self):
        if self.player_turn == self.player1:
            self.player_turn = self.player2
        else:
            self.player_turn = self.player1
            

    def surrender(self, player: Player):
        """
        end game if player has surrendered a game

        Args:
        -----
        player : ~.Player
            the player who surrendered
        """
        self.game_over = True
        self.status = GameStatus.SURRENDERED
        self.game_winner = self.player1 if player == self.player2 else self.player2
        
        

class Connect4Handler(Paginator):
    """
    A handler which connects Connect4 with hikari/discord
    """
    def __init__(
        self,
        player1: hikari.Member,
        player2: hikari.Member,
        rows: int,
        columns: int,
    ):
        self.player1 = player1
        self.player2 = player2
        super().__init__(
            page_s=["starting up..."],
            timeout=10*60,
            disable_pagination=True,
            disable_component=True,
            disable_components=False,
            disable_paginator_when_one_site=False,
            listen_to_events=[hikari.InteractionCreateEvent],
        )
        # generate player marks
        marks = ['🔵','🟣','🔴','🟠','🟢','🟡','🟤'] #,'⚪'
        self.mark1 = random.choice(marks)
        marks.remove(self.mark1)
        self.mark2 = random.choice(marks)
        marks.remove(self.mark2)
        if self.mark1 in '🟢🟡' and self.mark2 in '🟢🟡':
            self.mark2 = random.choice(marks)
            marks.remove(self.mark2)
        extra_marker = random.choice(marks)
        self._ctx: None | InuContext = None

        self.orienation_letter = [f':regional_indicator_{l}:' for l in 'abcdefghijklmnop']
        self.orientation_number = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣"]  #*️⃣ #*️⃣

        # generate game
        g_player1 = HikariPlayer(player1.display_name, 1, self.mark1, player1)
        g_player2 = HikariPlayer(player2.display_name, 2, self.mark2, player2)
        self.game = BaseConnect4(
            g_player1, 
            g_player2, 
            extra_marker,
            rows=rows,
            columns=columns,
        )
        
        # these Errors will be displayed to the players
        # these should contain why a player can't make a specific move etc.
        self.game_infos: List[Exception] = []
        
        # a legend for the board
        self.game_explanation = (
            f"{self.game.player1.token} {self.game.player1.name}\n\n"
            f"{self.game.player2.token} {self.game.player2.name}\n\n"
            f"{self.game.board.marker} System"
        )


    async def start(self, ctx: InuContext):
        """sets the game embed into `self._pages`"""
        self._pages = [self.build_embed()]
        self.set_context(ctx)
        await super().start(ctx)
    
    async def stop(self):
        """
        end of game - called from base class
        -> create embed with
        stateless restart button
        """
        self._stop.set()
        self._stopped = True

        # make stateless restart button
        custom_id = json.dumps(
            {
                "type": f"c4-{self.game.board.rows}x{self.game.board.columns}",  # type
                "p1": self.game.player1.user.id,  # player 2
                "p2": self.game.player2.user.id,  # player 1
                "gid": self.game.board.game.player1.user.guild_id  # guild_id
            },
            separators=(',', ':'),
            indent=None,
        )
        restart_btn = MessageActionRowBuilder().add_button(hikari.ButtonStyle.SECONDARY, custom_id).set_emoji("🔁").add_to_container()

        await self.ctx.respond(components=[restart_btn], update=True, embed=self.build_embed())


    def build_default_components(self, position=None) -> List[MessageActionRowBuilder]:
        """needed for `super().start` to make the right components instantly"""
        return self.message_components
    

    @property
    def message_components(self) -> List[hikari.impl.MessageActionRowBuilder]:
        """
        Number buttons and surrender button for connect 4
        """
        rows = []
        emoji_rows: List[OrderedDict] = []
        row_index = 5  # to add ordered dict at start of iteration

        # add OrderedDict to emoji_row lists - max 4 dicts per list
        for index, emoji in enumerate(self.orientation_number):
            if index > self.game.board.rows:
                break
            if row_index >= 4:
                emoji_rows.append(OrderedDict())
                row_index = 0
            emoji_rows[-1][emoji] = f"num_{index+1}"
            row_index += 1
        while len(emoji_rows) < 2:
            emoji_rows.append(OrderedDict())
        emoji_rows[-1]["🏳"] = "surrender"
        for d in emoji_rows:
            row = MessageActionRowBuilder()
            for emoji, custom_id in d.items():
                row = (
                    row
                    .add_button(hikari.ButtonStyle.SECONDARY, f"connect4_{custom_id}")
                    .set_emoji(emoji).add_to_container()
                )
            rows.append(row)
        return rows

        
    async def update_embed(self):
        """sends a message with an embed representing this game"""
        log.debug("update message")
        await self.ctx.respond(embed=self.build_embed(), components=self.message_components, update=True)
    

    def build_embed(self):
        """represents the current game as an embed"""
        embed = hikari.Embed()
        embed.title = f"{'- '*4} Connect 4 {'- '*4}"
        embed.add_field(f"turn {self.game.turn}", self.board_to_str(), inline=True)
        embed.add_field("explanation", f"\n\n{self.game_explanation}", inline=True)
        if self.game.game_over:
            # game is over -> check why it is over
            if self.game.status == GameStatus.OVER:
                embed.set_footer(f"{self.game.game_winner.name} has won the game", icon=self.game.game_winner.user.avatar_url)  # type: ignore
            elif self.game.status == GameStatus.SURRENDERED:
                p = self.game.player2 if self.game.game_winner == self.game.player1 else self.game.player1
                embed.set_footer(f"{p.name} has surrendered the game", icon=p.user.avatar_url)  # type: ignore  
            elif self.game.status == GameStatus.DRAW:
                embed.set_footer("Game Draw")    
        else:
            embed.set_footer(f"{self.game.player_turn.name}'s turn", icon=self.game.player_turn.user.avatar_url)
        if self.game_infos:
            embed.add_field('Be aware:', "\n\n".join(str(info) for info in self.game_infos))
        return embed
    

    def board_to_str(self) -> str:
        """Adds column and row indicators to the board string"""
        string = ""
        b = str(self.game.board)
        lines = b.split("\n")
        for i, line in enumerate(lines):
            string += f"{self.orienation_letter[self.game.board.rows - i - 1]}{line}\n"
        string += f"*️⃣{''.join(self.orientation_number[:self.game.board.columns])}"
        return string


    @listener(hikari.InteractionCreateEvent)
    async def on_interaction_add(self, event: hikari.InteractionCreateEvent):
        """triggered, when player presses a button"""
        # predicate
        if not self.interaction_pred(event):
            return
        message = self._message
        log.debug(f"executing on interaction with pag id: {self.count} | msg id: {message.id}")

        # this is a valid interaction for this game, so set context
        self.set_context(event=event)

        # extract the element from the custom_id e.g. num_{num} | surrender
        custom_id = event.interaction.custom_id.replace("connect4_", "", 1)
        if self.game.player1.name == self.game.player2.name:
            # possibility to play against yourself
            player = self.game.player_turn
        else:
            player = self.game.player1 if self.game.player1.user.id == event.interaction.user.id else self.game.player2
        
        if custom_id in [f"num_{x}" for x in range(1,9)]:
            num = int(custom_id[-1]) -1
            log.debug(f"custom_id num `{num}` found")
            await self.do_turn(num, player) #type: ignore  # this sends the message
        elif custom_id == "surrender":
            self.game.surrender(player)
            self._stop.set()  # base class will call stop() and create with it the final message

            
    async def do_turn(self, column: int, user: HikariPlayer):
        """handles the game logic and stops the game
        
        Args:
        ----
        column : int
            the column (0 is first) where <user> placed his token
        user : HikariPlayer
            the user who has placed a token in <column>

        Note:
        -----
        Game logic errors will be added to `self.game_infos`
        to show it to the player. These will be cleared one round later
        """
        self.game_infos.clear()
        try:
            self.game.do_turn(column, user)
        except WrongPlayerError as e:
            self.game_infos.append(e)
        except ColumnNotInFieldError as e:
            self.game_infos.append(e)
        except ColumnError as e:
            self.game_infos.append(e)
        except IndexError as e:
            self.game_infos.append(e)
        except GameOverError as e:
            self.game_infos.append(e)
        
        if self.game.game_over:
            log.debug("call stop from do turn")
            self._stop.set()  # stop() will be called from the base class in pagination loop
        else:
            log.debug("call from do turn")
            await self.update_embed()


    def interaction_pred(self, event: hikari.InteractionCreateEvent):
        """
        predicate for `hikari.ComponentInteraction` 
        when user is one of the 2 players 
        and the interaction message is this message 
        and custom_id starts with `connect4`
        """
        if (
            not isinstance(event.interaction, hikari.ComponentInteraction)
            or not event.interaction.custom_id.startswith("connect4")
            or not (event.interaction.user.id in [self.game.player1.user.id, self.game.player2.user.id])
            or not event.interaction.message.id == self._message.id
        ):
            return False
        return True
        
            
        
    
    
    


        
        
        
        

