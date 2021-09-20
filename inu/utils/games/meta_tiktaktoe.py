import discord
import numpy as np
import random
import asyncio
from dataclasses import dataclass
from discord.ext.commands import Context
import traceback

NON_SPACE = "᲼"  # (1x)
ENTER = "\n"


class CellTakenError(Exception):
    """
    Raised when a player tries to alter a cell of MetaTikTakToe
    which is already taken
    """
    def __init__(self, *args: object) -> None:
        super().__init__(*args)


@dataclass
class Player():
    """
    Represents a MetaTikTakToe Player
    """
    def __init__(self, name, marker, identifier, extra: dict = {}):
        self.name = name
        self.marker = marker
        self.id = identifier
        self.extra = extra

    def __repr__(self) -> str:
        return self.marker


class Board():
    def __init__(self, player1: Player, player2: Player):
        self.global_board = np.zeros(shape=(9, 9), dtype=int)
        possible_bgs = [
            ['🟥', '🟦'], ['🟥', '🟧'], ['🟦', '🟪'],
        ]
        possible_bgs.extend([[str(color), '⬛'] for color in "🟥🟧🟩🟦🟪"])
        self.bg = random.choice(possible_bgs)
        self.player1 = player1
        self.player2 = player2

    def update_local_boards(self) -> dict:
        '''
        returns a dict with all 9 local fields of the tiktaktoe field
        {field_num: [list of field values]}
        '''
        local_boards = {num: [] for num in range(9)}
        for index, row in enumerate(self.global_board):
            field = int((index) / 3)*3
            for i, cell in enumerate(row):
                if i % 3 == 0 and i != 0:
                    field += 1
                local_boards[field].append(cell)  
        return local_boards

    def get_local_boards(self):
        return self.update_local_boards()

    def set_to(self, row: int, column: int, value: int):
        '''
        Inserts the value into the global board
        '''
        if not self.global_board[row][column]:
            self.global_board[row][column] = value
            return True
        return False

    def __str__(self):
        board = ''
        for r_i, row in enumerate(self.global_board):
            for c_i, cell in enumerate(row):
                if cell == 0:
                    cell = self.bg[0] if self.get_field(r_i, c_i) % 2 == 0 else self.bg[1]
                board += str(cell)
            board += "\n"
        return board

    def local_boards_to_str(self) -> dict[int, list[str]]:
        boards = {}
        # will raise an error, when the ID "1" and "2" is changed
        # to smth different - but also don't want to init the ID's in board
        local_boards = self.update_local_boards()
        for num in range(9):
            add = ''
            list_local_board = []
            local_board = local_boards[num]
            for i, cell in enumerate(local_board):
                if i in [3,6]:
                    list_local_board.append(add)
                    list_local_board.append(f"{9*str('=')}")
                    add = ''
                if i in [1,2,4,5,7,8]:
                    add += "║"
                if cell == 0:
                    add += self.bg[0] if num % 2 == 0 else self.bg[1]
                else:
                    add += self._convert_id_to_marker(cell)
            list_local_board.append(add)
            boards.update({num: list_local_board})
        return boards

    def get_value(self, row: int, column: int) -> int:
        return self.global_board[row][column]

    def get_field(self, row, column):
        """
        returns the field, where the global cordinates show to
        """
        field =  (int(row / 3) * 3) + int(column / 3)
        return field

    def get_cell(self, row, column):
        """
        returns the cell of the local field, where the global cordinates show to
        """
        return (int(row % 3) * 3) + (column % 3)

    def _convert_id_to_marker(self, id_):
        if id_ == self.player1.id:
            return self.player1.marker
        return self.player2.marker


class BaseMetaTikTakToe():
    """
    Represents a MetaTikTakToe game with it's basic methods.
    This class needs to be implementet in a specific class which
    creates a GUI of this class.
    """
    def __init__(
        self,
        player1,
        player2,
        player1_extra: dict = {},
        player2_extra: dict = {},
    ):
        self.player1 = Player(
            name=player1,
            marker='⭕',
            identifier=1,
            extra=player1_extra,
        )
        self.player2 = Player(
            name=player2,
            marker='❌',
            identifier=2,
            extra=player2_extra,
        )
        self.board = Board(
            player1=self.player1,
            player2=self.player2,
        )
        self.player_now = random.choice(
            [self.player1, self.player2]
        )
        self.draw_id = 3
        self.win_conditions = [
            [0, 1, 2], [3, 4, 5], [6, 7, 8],  # horizontal
            [0, 3, 6], [1, 4, 7], [2, 5, 8],  # vertical
            [0, 4, 8], [2, 4, 6],             # diagonal
        ]
        self.gameover = False
        self.draw = False
        self.global_field_standings = [0 for _ in range(9)]

    def __str__(self):
        return self.board.__str__()

    def _change_player(self):
        if self.player_now is self.player1:
            self.player_now = self.player2
        else:
            self.player_now = self.player1

    def convert_to_letter(self, number):
        letters = {
            1: '\N{regional indicator symbol letter a}',
            2: '\N{regional indicator symbol letter b}',
            3: '\N{regional indicator symbol letter c}',
            4: '\N{regional indicator symbol letter d}',
            5: '\N{regional indicator symbol letter e}',
            6: '\N{regional indicator symbol letter f}',
            7: '\N{regional indicator symbol letter g}',
            8: '\N{regional indicator symbol letter h}',
            9: '\N{regional indicator symbol letter i}',
        }
        return letters.get(number, None)

    def _check_for_win(self, board: list):
        """
        Checks if given board is wether finished or not
        """
        for win_cond in self.win_conditions:
            marker = board[win_cond[0]]
            if marker == 0:
                continue
            if (
                board[win_cond[0]] == marker
                and board[win_cond[1]] == marker
                and board[win_cond[2]] == marker
            ):
                return True
        return False

    def _check_for_draw(self, board: list, stupid_test=True):
        if stupid_test:
            return not 0 in board
        else:
            return not 0 in board and not self._check_for_win(board)

    def check_for_gobal_win(self, changed_field: int = None) -> bool:
        """
        # Returns wether the MetaTikTakToe game is over or not.
        If a local field was won, than all cells of the
        local field will be changed to the winners marker
        """
        if self.gameover:
            return True
        # have to test for None -> field could be 0 -> falsy
        if changed_field == None:
            return self.gameover

        # only re-calculate and/or alter if any field has changed
        # and isn't already won
        if changed_field != None and self.global_field_standings[changed_field] == 0:
            change = self._check_for_win(
                board=(board := self.board.get_local_boards()[changed_field]),
            )
            if change:
                self.global_field_standings[changed_field] = self.player_now.id
                self.gameover = self._check_for_win(
                    board=(global_board := self.global_field_standings)
                )
            else:
                if (draw := self._check_for_draw(board=board)):
                    self.global_field_standings[changed_field] = self.draw_id
            if change or draw:
                self.gameover = self._check_for_draw(board=global_board)
                if self.gameover:
                    self.draw = True
                if self.gameover:
                    return True
            return False
        return False

    def turn(self, row, column):
        """
        Changes the board according to the changes the player made.
        This should be the method called after a player took a turn.
        It will updates:
        self.board, the self.gameover,
        self.player_now, self.global_field_standings
        or raises an Error (e.g. when the player tries to alter a cell,
        when this cell is already taken)
        """
        success = self.board.set_to(
            row=row,
            column=column,
            value=self.player_now.id,
        )
        if success:
            self._change_player()
        else:
            error = f"cell of row {row} and column {column}"\
                    f" ( Field {self.get_field(row, column)}"\
                    f" cell {self.get_cell(row, column)} )"\
                    f" is already taken"
            
            raise CellTakenError(error)
        self.gameover = self.check_for_gobal_win(
            self.get_field(row, column)
        )
        if self.gameover:
            self._change_player()

    def get_field(self, row, column):
        """
        returns the field, where the global cordinates show to
        """
        return self.board.get_field(row, column)

    def get_cell(self, row, column):
        """
        returns the cell of the local field, where the global cordinates show to
        """
        return self.board.get_cell(row, column)


class DiscordMetaTikTakToe(BaseMetaTikTakToe):
    def __init__(
        self,
        player1: discord.Member,
        player2: discord.Member,
        timeout: int = None,
        ):

        super().__init__(
            player1=player1.nick or player1.name,
            player2=player2.nick or player2.name,
            player1_extra={
                "icon_url": player1.avatar_url,
                "id": int(player1.id)
                },
            player2_extra={
                "icon_url": player2.avatar_url,
                "id": int(player2.id)
            }
        )

        self.client = None
        self.loop = None
        self.ctx = None

        self.game_message = None
        self.row_panel_msg = None
        self.column_panel_msg = None

        self.__tasks = []
        self.timeout = timeout or 5*60
        self.numbers = [
            "1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣",
        ]
        self.convert_numbers = {
            value: [num+1, "int"] for num, value in enumerate(self.numbers)
        }
        self.letters = [
            '\N{regional indicator symbol letter a}',
            '\N{regional indicator symbol letter b}',
            '\N{regional indicator symbol letter c}',
            '\N{regional indicator symbol letter d}',
            '\N{regional indicator symbol letter e}',
            '\N{regional indicator symbol letter f}',
            '\N{regional indicator symbol letter g}',
            '\N{regional indicator symbol letter h}',
            '\N{regional indicator symbol letter i}',
        ]
        self.convert_letters = {
            value: [num+1, "str"] for num, value in enumerate(self.letters)
        }
        self.convert_extra = {
            "🏳": [0, "surrender"]
        }
        self.convert_reacts = {}
        self.convert_reacts.update(self.convert_numbers)
        self.convert_reacts.update(self.convert_letters)
        self.convert_reacts.update(self.convert_extra)

    async def start(self, ctx: Context):
        """
        Start MetaTikTakToe discord game.

        Parameters
        -----------
        ctx: :class:`Context`
            The invocation context to use.
        """
        self.ctx = ctx
        self.client = ctx.bot
        self.loop = ctx.bot.loop

        self.game_message = await ctx.send(
            embed=self._create_board_embed()
        )
        await self.game_message.add_reaction(str("🏳"))

        self.row_panel_msg = await ctx.send("row panel")
        for emoji in self.convert_letters.keys():
            await self.row_panel_msg.add_reaction(emoji)

        self.column_panel_msg = await ctx.send("column panel")
        for emoji in self.convert_numbers.keys():
            await self.column_panel_msg.add_reaction(emoji)
        self.__tasks.append(self.loop.create_task(self.main()))

    def check(self, payload):
        if (
            payload.user_id != self.client.user.id
            and payload.user_id == self.player_now.extra["id"]
            and payload.channel_id == self.game_message.channel.id
        ):
            return True
        return False
        #return str(payload.emoji) in self.reactions

    async def main(self):
        letter = None
        number = None
        
        while not self.gameover:
            try:
                if number and letter:
                    letter = None
                    number = None
                    # creating tasks
                tasks = [
                    asyncio.ensure_future(
                        self.client.wait_for("raw_reaction_add", check=self.check)
                    ),
                    asyncio.ensure_future(
                        self.client.wait_for("raw_reaction_remove", check=self.check)
                    ),
                ]
                # do tasks until first completed
                # if not timeout the payload (reaciton) will went into done
                done, pending = await asyncio.wait(
                    tasks,
                    timeout=self.timeout,
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for task in pending:
                    task.cancel()
                if len(done) == 0:
                    # Clear reactions once the timeout has elapsed
                    return await self.stop(
                        stop_reason=f"DRAW - {self.player_now.name}'s turn \ntook "
                                    f"longer than {(self.timeout / 60):.2f} minutes"
                    )
                
                # get reaction
                payload = done.pop().result()
                
                message = await self.ctx.fetch_message(payload.message_id)
                await message.remove_reaction(
                    str(payload.emoji),
                    self.ctx.guild.get_member(payload.user_id),
                )

                # if reaction matches, than put it into number or letter
                reaction_list = self.convert_reacts.get(str(payload.emoji), None)
                reaction = reaction_list[0]
                type_ = reaction_list[1]
                print(type_)
                if reaction and type_ == "int":
                    number = reaction
                elif reaction and type_ == "str":
                    letter = reaction
                elif type_ == "surrender":
                    return await self.stop(
                        reason=f"{self.player_now.name} has surrendered"
                    )

                if number and letter:
                    await self._make_turn(number-1, letter-1)
            except Exception:
                traceback.print_exc()

    async def _make_turn(self, number, letter):
        column = number
        row = letter

        try:
            self.turn(
                row=row,
                column=column,
            )
        except CellTakenError as e:
            fail = discord.Embed()
            fail.title = str(e)
            fail.color = discord.Color.red()
            await self.ctx.send(embed=fail, delete_after=20)
            return
        except Exception:
            traceback.print_exc()

        await self.game_message.edit(
            embed=self._create_board_embed(self.gameover)
        )
        return

    def _create_board_embed(
        self,
        gameover: bool = False,
        stop_reason: str = None,
    ) -> discord.Embed:
        # weird stuff - don't try to understand
        if stop_reason:
            gameover = False
        numbers: list = self.numbers.copy()
        numbers[0] = "⬛1️⃣"
        letters: list = self.letters.copy()

        game_embed = discord.Embed()
        game_embed.color = discord.Color.dark_blue()
        text = self.player_now.name + "'s turn"
        if self.draw:
            text = "DRAW"
        elif stop_reason:
            text = stop_reason
        elif gameover:
            text = self.player_now.name + " has won the game"
        game_embed.set_footer(
            text=text,
            icon_url=self.player_now.extra["icon_url"]
        )

        game_embed.title = "Meta TikTakToe"
        boards: dict = self.board.local_boards_to_str()
        for num in range(9):
            board: list = boards[num]
            str_board = ''
            name = 13*NON_SPACE
            if num in [0, 3, 6]:
                name = 15*NON_SPACE
            for i, line in enumerate(board):
                if num in [0, 1, 2] and i == 0:
                    nums = numbers[num*3: num*3+3]
                    str_board += f"{nums[0]}║{nums[1]}║{nums[2]}"
                if num in [0, 3, 6] and i in [0, 2, 4]:
                    str_board += f"\n{letters.pop(0)}{line}"
                elif num in [0, 3, 6] and i in [1, 3]:
                    str_board += f"\n=={line}"
                else:
                    str_board += f"\n{line}"
            game_embed.add_field(
                name=name,
                value=str_board,
                inline=True,
            )
        return game_embed

    async def stop(self, reason: str = None):
        self.gameover = True
        await self.game_message.edit(
            embed=self._create_board_embed(
                gameover=True,
                stop_reason=reason,
            ),
        )
