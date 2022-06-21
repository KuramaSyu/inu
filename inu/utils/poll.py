from enum import Enum
from abc import ABC, abstractmethod
from typing import *
import random
from datetime import datetime, timedelta
import asyncio
import time as tm
from io import BytesIO
import numpy as np

import hikari
import lightbulb
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import mplcyberpunk

from utils.db import PollManager
from utils import Colors
from core import Table, Inu, getLogger, ConfigProxy, ConfigType

log = getLogger(__name__)
conf = ConfigProxy(ConfigType.YAML)
POLL_SYNC_TIME = conf.commands.poll_sync_time




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
class PollTypes(Enum):
    STANDARD_POLL = 1
    SCALE_POLL = 2
    BOOL_POLL = 3


class Poll():
    """
    Represents the current state of the poll
    
    Members:
    -------
    self._poll : Dict[str, Set[int]]
        Mapping from option identifier to a Set with every user id voted for that point
    self._options : Dict[int, str]
        Mapping from option to description what the user has entered
    """
    _type: PollTypes = PollTypes.STANDARD_POLL
    _options: Dict[str, str]
    _guild_id: int
    _message_id: int
    _channel_id: int
    _creator_id: int
    # list with poll ids
    _finalizing: Set[int] = set()

    def __init__(
        self, 
        record: Dict[str, Any],
        bot: Inu,
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
        self.letter_emojis = [
            "🇦", "🇧", "🇨", "🇩", "🇪", "🇫", "🇬", 
            "🇭", "🇮", "🇯", "🇰", "🇱", "🇲", "🇳", 
            "🇴", "🇵", "🇶", "🇷", "🇸", "🇹", "🇺", 
            "🇻", "🇼", "🇽", "🇾", "🇿"
        ]
        self._reaction_letter: Dict[str, str] = {r: l for r, l in zip(self.letter_emojis, "ABCDEFGHIJKLMNOPQRSTUVWXYZ")}
        self.bot = bot
        # mapping from option id to a list with user ids
        # Dict[option_id, List[user_id]]
        self._poll: Dict[int, List[int]] = {}
        # mapping from option id to the option title
        self._options: Dict[int, str] = {}
        self._id_reaction: Dict[int, str] = {}

        self._title = record["title"]
        self._description = record["description"]
        self._anonymous = record["anonymous"]
        self._expires = record["expires"]
        self._starts = record["starts"]
        self._type = record["poll_type"]

        self._id = record["poll_id"]
        self._guild_id = record["guild_id"]
        self._message_id = record["message_id"]
        self._channel_id = record["channel_id"]
        self._creator_id = record["creator_id"]


        # f"{int(time.time)}{ctx.author.id}{ctx.guild_id}"

    @property
    def expires(self) -> datetime:
        """when the poll will expire"""
        if not self._expires:
            raise ValueError("Poll has no expire datetime")
        return self._expires

    @property
    def title(self) -> str:
        if not self._title:
            if not self._description:
                raise ValueError("Neither title nor description was set")
            return "Poll"
        return self._title

    @property
    def description(self) -> str:
        if not self._description:
            if not self._title:
                raise ValueError("Neither title nor description was set")
            return ""
        return self._description

    @property
    def poll_type(self) -> int:
        if self._type is None:
            raise AttributeError("Poll type is not set")
        return self._type.value

    @property
    def starts(self) -> datetime:
        """when does the poll starts"""
        return self._starts or datetime.now()

    @property
    def anonymous(self) -> bool:
        return self._anonymous

    @property
    def channel_id(self) -> int:
        if not self._channel_id:
            raise AttributeError("Channel id is not set")
        return self._channel_id

    @property
    def message_id(self) -> int:
        if not self._message_id:
            raise AttributeError("Message id is not set")
        return self._message_id

    @property
    def guild_id(self) -> int:
        if not self._guild_id:
            raise AttributeError("Guild id is not set")
        return self._guild_id

    @property
    def creator_id(self) -> int:
        if not self._creator_id:
            raise AttributeError("Creator id is not set")
        return self._creator_id

    @property
    def needs_to_sync(self) -> bool:
        return not (self._id is None)

    @property
    def id(self) -> int:
        if self._id:
            return self._id
        raise ValueError("Poll is to short and was not added to the database")

    def __str__(self):
        text = f"{self._title}\n{self._description}\n{self._options}"
        for k in self._options.keys():
            text += f"\n{k:<10} : {self._amount_to_str(k)}"
        return text

    @property
    def embed(self) -> hikari.Embed:
        """
        converts `self` to `hikari.Embed`
        """
        embed = hikari.Embed(title=self._title)
        embed.color = Colors.random_blue()
        embed.description = ""
        if self._description:
            embed.description = f"**Details**: {self._description}\n\n"
        embed.description += f"**Ends**: <t:{int(self.expires.timestamp())}:R>\ne.g. <t:{int(self.expires.timestamp())}:F>"
        
        if self.anonymous:
            vote_result = ""
            for option_id, o_votes in self._poll.items():
                vote_result += f"**{self._reaction_by_id(option_id)}** _{self._options[option_id]}_\n{self._amount_to_str(option_id)}\n\n"
            embed.add_field("Results", vote_result)
        else:
            for option_id, o_votes in self._poll.items():
                value = "\n".join(
                    self.bot.cache.get_member(self.guild_id, m).display_name 
                    for m in o_votes
                ) if len(o_votes) > 0 else "/" #r"¯\_(ツ)_/¯"
                embed.add_field(
                    f"**{self._reaction_by_id(option_id)}** | {self._amount_to_str(option_id)}",
                    f"_{self._options[option_id]}_\n>>> {value}",
                )
        return embed

    @property
    def final_embed(self):
        embed = self.embed
        embed.description = ""
        if self.description:
            embed.description = f"**Description**: {self.description}\n\n"
        embed.description += f"**Ended at**: <t:{int(self.expires.timestamp())}:F>\n\n"
        embed.description += f"**Total votes**: {self.total_votes}\n"
        embed.set_footer(
            text=f"Poll created by {self.bot.cache.get_member(self.guild_id, self.creator_id).display_name}",
            icon=self.bot.cache.get_member(self.guild_id, self.creator_id).avatar_url,
        )
        embed.set_image(self._make_pie_chart())
        return embed

    @property
    def total_votes(self):
        count = 0
        for v in self._poll.values():
            count += len(v)
        return count

    def __repr__(self) -> str:
        return (
            f"<Poll(id={self.id}, title={self.title}, "
            f"options={self._options}, poll={self._poll}, "
        )

    def _amount_to_str(self, option_key: int, str_len: int = 44) -> str:
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

    def _reaction_by_id(self, id: int) -> str:
        """
        returns the emoji for the given id
        """
        return self._id_reaction[id]

    def _letter_by_id(self, id: int) -> str:
        """
        returns the letter for the given id
        """
        return self._reaction_letter.get(self._reaction_by_id(id), "None")

    async def fetch(self) -> None:

        option_table = Table("poll_options")
        vote_table = Table("poll_votes")

        # fetch options
        for option_record in await PollManager.fetch_options(self.id):
            self._options[option_record["option_id"]] = option_record["description"]
            self._id_reaction[option_record["option_id"]] = option_record["reaction"]

        for k in self._options.keys():
            self._poll[k] = []

        # fetch votes
        for vote_record in await PollManager.fetch_votes(self.id):
            # insert votes into polls - mapping from option_id to a list of user_ids
            if vote_record['option_id'] in self._poll.keys():
                self._poll[vote_record['option_id']].append(vote_record['user_id'])
            else:
                self._poll[vote_record['option_id']] = [vote_record['user_id']]

    async def dispatch_embed(
        self, 
        bot: Inu, 
        edit: bool = True, 
        add_reactions: bool = False,
        embed: Optional[hikari.Embed] = None,
        **kwargs,
    ) -> hikari.Message:

        if edit:
            message = await bot.rest.edit_message(
                channel=self._channel_id,
                message=self._message_id,
                embed=embed or self.embed,
                **kwargs,
            )
        else:
            message = await bot.rest.create_message(
                channel=self._channel_id,
                embed=embed or self.embed,
                **kwargs,
            )
            
        if not add_reactions:
            return message

        letter_emojis = [
                "🇦", "🇧", "🇨", "🇩", "🇪", "🇫", "🇬", 
                "🇭", "🇮", "🇯", "🇰", "🇱", "🇲", "🇳", 
                "🇴", "🇵", "🇶", "🇷", "🇸", "🇹", "🇺", 
                "🇻", "🇼", "🇽", "🇾", "🇿"
            ]

        for i in range(len(self._options)):
            await message.add_reaction(letter_emojis[i])
        return message

    async def finalize(self) -> None:
        """
        Sends result and deletes db entry

        Note:
        ----
        Automatically calls self.fetch()
        """
        if self.id in self.__class__._finalizing:
            return
        self.__class__._finalizing.add(self.id)
        await asyncio.sleep(self.expires.timestamp() - tm.time())
        await self.fetch()
        await self.dispatch_embed(
            self.bot, 
            edit=False, 
            content="Results", 
            embed=self.final_embed
        )
        await PollManager.remove_poll(self.id, self.message_id)
        self.__class__._finalizing.remove(self.id)

    def _make_pie_chart(self) -> BytesIO:
        #Using matplotlib
        plt.style.use("cyberpunk")
        sns.set_palette("Set2")
        sns.set_context("notebook", font_scale=4.5, rc={"lines.linewidth": 4.5})
        chart, ax = plt.subplots(figsize=[7,7])
        all_labels = [v for v in self._options.values()]
        all_data = [len(self._poll[k]) for k in self._poll.keys()]
        labels = []
        data = []
        reaction_letters = []
        for labal, value in zip(all_labels, self._poll.items()):
            if len(value[1]) > 0:
                labels.append(labal)
                data.append(len(value[1]))
                reaction_letters.append(self._letter_by_id(value[0]))
        #chart.set_tight_layout(True)
        wedges, texts = ax.pie(
            x=data, 
            # autopct="%.1f%%", 
            autopct=None,
            explode=[0.05]*len(labels), 
            wedgeprops=dict(width=0.4),
            labels=reaction_letters, 
            # pctdistance=0.5,
            labeldistance=0.7,
            startangle=-40
        )
        #form matplotlib - create annotations
        # bbox_props = dict(boxstyle="square")#, fc="white", ec="white", lw=3,pad=0.3
        # kw = dict(arrowprops=dict(arrowstyle="-", color='white', linewidth=3,),
        #         bbox=bbox_props, zorder=0, va="center")

        # for i, p in enumerate(wedges):
        #     ang = (p.theta2 - p.theta1)/2. + p.theta1
        #     y = np.sin(np.deg2rad(ang))
        #     x = np.cos(np.deg2rad(ang))
        #     horizontalalignment = {-1: "right", 1: "left"}[int(np.sign(x))]
        #     connectionstyle = "angle,angleA=0,angleB={}".format(ang)
        #     kw["arrowprops"].update({"connectionstyle": connectionstyle})
        #     ax.annotate(labels[i], xy=(x, y), xytext=(1.35*np.sign(x), 1.4*y),
        #                 horizontalalignment=horizontalalignment, **kw)
        # plt.legend()
        # mplcyberpunk.add_glow_effects(ax=ax)
        buffer = BytesIO()
        # plt.title(f"{self.title}", fontsize=14);
        chart.savefig(buffer, dpi=40, transparent=True)
        buffer.seek(0)
        return buffer



      


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







    