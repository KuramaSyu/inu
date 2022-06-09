from enum import Enum
from abc import ABC, abstractmethod
from typing import *
import random
from datetime import datetime, timedelta
import asyncio


import hikari
import lightbulb

from utils.db import PollManager
from core import Table





class DisplayType(Enum):
    """A Enum to define with how many information the embed will be created in the poll classes"""
    USERS_LIST = 1
    USERS_AMOUNT = 2
    USER_TO_AMOUNT_LIST = 3


class AbstractPoll(ABC):
    # Dict[option, List[Dict[user_id, vote_amount]]]
    _result: Dict[str, List[Dict[int, int]]] = {}

    def __init__(
        self,
        options: List[str],
    ):
        self._result: Dict[str, Dict[int, int]] = {o: [] for o in options}
        self._start: datetime = datetime.now()
        self._end: datetime = self._start + timedelta(hours=3)
        self._anomymous: bool = True
        self._hide_until_end: bool = False
        self._display_type: DisplayType = DisplayType.USERS_AMOUNT

    # @abstractmethod
    # def start(self):
    #     ...

    def with_privacy(self, annonymous: bool, hide_until_end: bool) -> "AbstractPoll":
        """to set privacy options"""
        self._anomymous = annonymous
        self._hide_until_end = hide_until_end
        return self

    def with_timeframe(self, from_: datetime, to: datetime) -> "AbstractPoll":
        """shedule when the poll should start and end"""
        self._start = from_
        self._end = to
        return self

    def with_duration(self, duration: timedelta) -> "AbstractPoll":
        """set a duration how long the poll should take"""
        self._start = datetime.now()
        self._end = self._start + duration
        return self

    def set_display_type(self, user_list: bool, user_amount: bool, user_to_amount_list: bool) -> "AbstractPoll":
        """set, how many data should be showen to the user"""
        if user_list:
            self._display_type = DisplayType.USERS_LIST
        elif user_amount:
            self._display_type = DisplayType.USERS_AMOUNT
        elif user_to_amount_list:
            self._display_type = DisplayType.USER_TO_AMOUNT_LIST
        return self

    def set_button_labal(self, option: str, labal: str) -> "AbstractPoll":
        ...

    

    @property
    @abstractmethod
    def embed(self) -> hikari.Embed:
        """will build the embed"""
        ...

    # @property
    # @abstractmethod
    # def user_ids(self):
    #     ...

    # @property
    # @abstractmethod
    # def votes(self):
    #     ...

    # @property
    # @abstractmethod
    # def options(self):
    #     ...

    # @property
    # @abstractmethod
    # def result(self) -> Dict[str, Dict[int, int]]:
    #     ...
    
    @abstractmethod
    def add_vote(
        self,
        user_id: int,
        amount: int,
        option: str,
    ):
        """
        Args:
        ----
        user_id: `int` 
            the number, to identify the name (name will be mapped to number)
        amount: `int`
            the amount of votes. typically 1 or -1
        option : `str`
            the option where to enter under
        """
        ...

    # @classmethod
    # def from_record(cls, record: Dict[str, Any]):
    #     ...

    # @classmethod
    # async def to_record(cls, record: Dict[str, Any]):
    #     ...

class Poll(AbstractPoll):
    """A class for making polls
    
    Members:
    -------
    self._poll : Dict[str, Set[int]]
        Mapping from option identifier to a Set with every user id voted for that point
    self._options : Dict[str, str]
        Mapping from name (...letter_x) to description what the user has entered
    """
    _options: Dict[str, str]
    _guild_id: int
    _message_id: int
    _channel_id: int
    _creator_id: int

    def __init__(
        self, 
        options: List[str],
        active_until: timedelta,
        anonymous: bool = True,
        title: str = "",
        description: str = "",
    ):
        """
        Args:
        -----
        options : `Dict[str, str]`
            mapping from option name (e.g. A,B,C,1,2,3) to option desciption.
        anonoymous : `bool`
            wether or not the names of voted persons should be displayed
        poll_title : `str`
            the title of the poll
        poll_description : `str`
            the description of the poll.
            Per default empty
        
        """
        letter_emojis = [f':regional_indicator_{l}:' for l in 'abcdefghijklmnop']
        self._poll: Dict[str, List[int]] = {letter_emojis[k]: [] for k in range(len(options))}
        self._options = {letter_emojis[i]: v for i, v in enumerate(options)}
        self._title = title
        self._description = description
        self._anonymous = anonymous
        self._active_until: datetime = active_until + datetime.now()
        self._id = None
        self._type = "poll"
        self._option_ids: List[int] = []
        # f"{int(time.time)}{ctx.author.id}{ctx.guild_id}"
    @property
    def anonymous(self) -> bool:
        return self._anonymous

    @property
    def channel_id(self) -> int:
        return self._channel_id

    @property
    def message_id(self) -> int:
        return self._message_id

    @property
    def guild_id(self) -> int:
        return self._guild_id

    @property
    def needs_to_sync(self) -> bool:
        return not (self._id is None)

    @property
    def id(self) -> int:
        if self._id:
            return self._id
        raise ValueError("Poll is to short and was not added to the database")

    @property
    def kind(self):
        if self._type is None:
            raise ValueError("Poll type not set")

    @kind.setter
    def kind(self, value: Literal["poll", "vote"]):
        """can be poll or vote"""
        self._type = value

    def __str__(self):
        text = f"{self._title}\n{self._description}\n{self._options}"
        for k in self._options.keys():
            text += f"\n{k:<10} : {self._amount_to_str(k)}"
        return text

    @property
    def embed(self):
        """
        converts `self` to `hikari.Embed`
        """
        embed = hikari.Embed(title=self._title)
        if self._description:
            embed.description = self._description
        embed.description += "\n"
        for o, d in self._options.items():
            if d:
                embed.description += f"**{o}** = {d}\n"   
        if self.anonymous:
            vote_result = ""
            for o, o_votes in self._poll.items():
                vote_result += f"**{o}** \n{self._amount_to_str(o)}\n\n"
            embed.add_field("Results", value)
        else:
            for o, o_votes in self._poll.items():
                value = ">>>".join(m.display_name for m in o_votes) if len(o_votes) > 0 else r"¯\_(ツ)_/¯"
                embed.add_field(
                    f"**{o}** | {self._amount_to_str(o)}",
                    value,
                )
        embed.set_footer(f"Vote ends <t:{self._active_until}:R>")
        return embed

    @property
    def total_votes(self):
        count = 0
        for v in self._poll.values():
            count += len(v)
        return count

    def _amount_to_str(self, option_key: str, str_len: int = 40) -> str:
        """
        returns a string with len <str_len> which displays the poll percentage with terminal symbols
        """
        # █ ░
        try:
            option_perc = float(len(self._poll[option_key]) / self.total_votes)
        except ZeroDivisionError:
            option_perc = 0
        option_filled_blocks = int(round(option_perc * str_len, 0))
        print(option_perc)
        return f"{option_filled_blocks * '█'}{int(str_len - option_filled_blocks) * '░'}"
    
    def add_vote(
        self,
        user_id: int,
        amount: int,
        option: str,
    ) -> Optional[Tuple[int, str]]:
        """
        Args:
        ----
        user_id: `int` 
            the number, to identify the name (name will be mapped to number)
        amount: `int`
            the amount of votes. typically 1 or -1
        option : `str`
            the option where to enter under

        Returns:
        -------
        `Optional[Tuple[int, str]]` :
            the old removed vote, if anys
            Mapping from user_id to option_id
        """
        return_value = None
        for o, members in self._poll.items():
            if user_id in members:
                self._poll[o].remove(user_id)
                return_value = (user_id, o)
        self._poll[option].append(user_id)
        return return_value

    async def finish(self, in_seconds: int):
        """ edits the last message to discord with the finished poll
        """
        await asyncio.sleep(in_seconds)
        await self.bot.rest.create_message(channel=self._channel_id, embed=self.embed)
        if self._id:
            await self._delete_from_db()

    async def _delete_from_db(self):
        await PollManager.remove_poll(self.id)

    @classmethod
    async def from_record(cls, poll_record: Dict[str, Any]) -> "Poll":
        
        self = cls(
            options=[],
            active_until=poll_record["active_until"],
        )

        option_table = Table("poll_options")
        vote_table = Table("poll_votes")
        options = []
        option_ids = []
        polls: Dict[str, List[int]] = {}
        poll_id = poll_record['poll_id']
        option_sql = f"""
        SELECT * FROM poll_options 
        WHERE poll_id = {poll_id}
        """

        # fetch options
        for option_record in await option_table.fetch(
            f"""
            SELECT * FROM poll_options 
            WHERE poll_id = {poll_id}
            """
        ):
            options.append(option_record['description'])
            option_ids.append(option_record['option_id'])
        
        # fetch votes
        for vote_record in await vote_table.fetch(
            f"""
            SELECT * FROM poll_votes 
            WHERE poll_id = {poll_id}
            """
        ):
            # insert votes into polls - mapping from option_id to a list of user_ids
            if vote_record['option_id'] in polls.keys():
                polls[vote_record['option_id']].append(vote_record['user_id'])
            else:
                polls[vote_record['option_id']] = [vote_record['user_id']]

        # create class
        self = cls(
            options=options,
            active_until=poll_record["active_until"],
            anonymous=poll_record["anonymous"],
            title=poll_record["title"],
            description=poll_record["description"],
        )
        self._poll = polls
        return self

    async def _register_in_manager(self):
        """syncs poll and all options into the database"""
        self._id = await PollManager.add_poll(self)
        if self._id:
            for name, description in self._options.items():
                self._option_ids.append(
                    await PollManager.add_option(self._id, name, description)
                )

    async def add_vote_and_update(
        self,
        user_id: int,
        amount: int,
        option: str,
    ):
        """Adds a vote, syncs it to db and updates the poll message"""
        old_vote = self.add_vote(user_id, amount, option)
        if old_vote and self.needs_to_sync:
            await self._sync_vote_to_db(user_id=user_id, option_id=old_vote[1], remove=True)
        await self.update_poll()
        if self.needs_to_sync:
            await self._sync_vote_to_db(user_id=user_id, option_id=option)
        

    async def update_poll(self):
        await self.bot.rest.edit_message(
            channel=self._channel_id,
            message_id=self._message_id,
            embed=self.embed,
        )
    
    async def _sync_vote_to_db(self, user_id: int, option_id: str, remove: bool = False):
        """syncs all new votes of this poll into the db"""
        if remove:
            await PollManager.remove_vote(self.id, user_id, option_id)
        else:
            await PollManager.add_vote(self.id, user_id, option_id)


    async def start(self, ctx: lightbulb.Context):
        letter_emojis = [l for l in 
            [
                "🇦", "🇧", "🇨", "🇩", "🇪", "🇫", "🇬", 
                "🇭", "", "🇯", "🇰", "🇱", "🇲", "🇳", 
                "🇴", "🇵", "🇶", "🇷", "🇸", "🇹", "🇺", 
                "🇻", "🇼", "🇽", "🇾", "🇿"
            ]
        ]
        self._message = await (await ctx.respond(embed=self.embed)).message()
        for i in range(len(self._options)):
            await self._message.add_reaction(letter_emojis[i])
        self._channel_id = ctx.channel_id
        self._guild_id = ctx.guild_id  # type: ignore
        self._creator_id = ctx.author.id
        self.bot = ctx.bot
        await self._register_in_manager()

      


# class ScaleVote():

#     __slots__ = [
#         'title', 'description', 'votes', 'author', 'message_id', 'len_scale',
#         'channel_id', 'guild_id', 'person_vote'
#     ]

#     def __init__(
#         self,
#         title: str,
#         description: str = None, 
#         len_scale: int = 24,
#         storage: Optional[dict] = None,
#     ):

#         self.title = title
#         self.description = description
#         self.len_scale = len_scale
#         self.storage: Dict[str, Any] = storage or {}
#         self.person_vote = {}
#         self.options = {
#             '0': int(0),
#             '1': int(0),
#             '2': int(0),
#             '3': int(0),
#             '4': int(0),
#             '5': int(0),
#         }
#         super().__init__()

#     @property
#     def average(self) -> float:
#         total_value = int(self.options['1'])*1 + int(self.options['2'])*2 + int(self.options['3'])*3 + \
#             int(self.options['4'])*4 + int(self.options['5'])*5 + int(self.options['0'])*0
#         total_votes = self.total_votes()
#         if total_votes == 0:
#             return 0
#         return round(float(total_value / total_votes / 5), 2) 

#     @property
#     def total_votes(self) -> int:
#         total_votes = int(self.options['1']) + int(self.options['2']) + int(self.options['3']) + \
#             int(self.options['4']) + int(self.options['5']) + int(self.options['0'])
#         return total_votes

#     @property
#     def total_options(self) -> int:
#         return len(self.options.keys()) - 1 #because 0 is a key

#     def scale(self) -> str:
#         average = self.average
#         len_scale = self.len_scale
#         black = self.len_scale - round(self.len_scale*average)
#         yellow = round(len_scale / float(len_scale / self.len_scale * 100) * 33)
#         len_scale -= yellow
#         green = round(len_scale / float(len_scale / self.len_scale * 100) * 33)
#         len_scale -= green
#         red = len_scale
#         #🟥​🟧​🟨​🟩​🟦​🟪​⬛️​⬜️​🟫​ 
#         scale =  f'{red*"🟥"}{yellow*"🟨"}{green*"🟩"}'#{brown*"🟫"}{orange*"🟧"}
#         scale = f'{scale[0:int((int(len(scale))- black))]}{black*"⬛"}'
#         return f'{scale}'

#     def add_vote(self, option: str, name: str, add: int = 1):
#         if name in self.person_vote.keys():
#             voted_num = self.person_vote[name]
#             self.options[str(voted_num)] -= 1
#         self.person_vote[name] = option
#         self.options[option] += add
#         return
        
#     def __str__(self):
#         scale = self.scale()
#         len_ = self.len_scale
#         multiplier = round(len_*1.75)
#         half_scale_indicator = f'|{multiplier*"-"}|{multiplier*"-"}|'
#         return f'{half_scale_indicator}\n|{scale}|\n|{scale}|\n{half_scale_indicator}'

#     @property
#     def embed(self):
#         embed = hikari.Embed()
#         embed.title = self.title
#         if self.description:
#             embed.description = self.description
#         embed.add_field(
#             name=f'{round(float(self.average * 5), 3)}/{5} ||'\
#             f'{int(round(float(self.average * 5 *20),0))}% ',
#             value = f'{str(self)}\n\nVotes: {self.total_votes}'
#         )
            
#         if self.author:
#             embed.set_footer(text=self.author)
#         return embed


  
        

# if __name__ == "__main__":
#     poll = Poll(
#         options={"A": "yes", "B": "no", "C": "maybe"},
#         active_until=datetime.now() + timedelta(days=1),
#         title="Do you smoke?",
#     )
#     poll.add_vote(2, 1, "A")
#     poll.add_vote(3, 1, "A")
#     poll.add_vote(5, 1, "A")
#     poll.add_vote(7, 1, "B")
#     poll.add_vote(6, 1, "B")
#     poll.add_vote(4, 1, "C")
#     poll.add_vote(5, 1, "B")
#     print(poll)







    