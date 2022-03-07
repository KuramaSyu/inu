from enum import Enum
from abc import ABC, abstractmethod
from typing import *
import random


import hikari


class Vote(ABC):
    storage: dict
    options: Dict[str, Any]

    @property
    @abstractmethod
    def embed(self):
        ...
    
    @abstractmethod
    def add_vote(
        self,
        number: int,
        name: str,
        add: int,
    ):
        """
        Args:
        ----
        number: `int` 
            the number, to identify the name (name will be mapped to number)
        name : `str` 
            the name, which will be mapped to the given number
        add : (`int`) 
            the amount of votes to add to this number. Typically -1 or 1 
        """
        ...

    


class ScaleVote(Vote):
    __slots__ = [
        'title', 'description', 'votes', 'author', 'message_id', 'len_scale',
        'channel_id', 'guild_id', 'person_vote'
    ]

    def __init__(
        self,
        title: str,
        description: str = None, 
        len_scale: int = 24,
        storage: Optional[dict] = None,
    ):

        self.title = title
        self.description = description
        self.len_scale = len_scale
        self.storage: Dict[str, Any] = storage or {}
        self.person_vote = {}
        self.options = {
            '0': int(0),
            '1': int(0),
            '2': int(0),
            '3': int(0),
            '4': int(0),
            '5': int(0),
        }
        super().__init__()

    @property
    def average(self) -> float:
        total_value = int(self.options['1'])*1 + int(self.options['2'])*2 + int(self.options['3'])*3 + \
            int(self.options['4'])*4 + int(self.options['5'])*5 + int(self.options['0'])*0
        total_votes = self.total_votes()
        if total_votes == 0:
            return 0
        return round(float(total_value / total_votes / 5), 2) 

    @property
    def total_votes(self) -> int:
        total_votes = int(self.options['1']) + int(self.options['2']) + int(self.options['3']) + \
            int(self.options['4']) + int(self.options['5']) + int(self.options['0'])
        return total_votes

    @property
    def total_options(self) -> int:
        return len(self.options.keys()) - 1 #because 0 is a key

    def scale(self) -> str:
        average = self.average
        len_scale = self.len_scale
        black = self.len_scale - round(self.len_scale*average)
        yellow = round(len_scale / float(len_scale / self.len_scale * 100) * 33)
        len_scale -= yellow
        green = round(len_scale / float(len_scale / self.len_scale * 100) * 33)
        len_scale -= green
        red = len_scale
        #🟥​🟧​🟨​🟩​🟦​🟪​⬛️​⬜️​🟫​ 
        scale =  f'{red*"🟥"}{yellow*"🟨"}{green*"🟩"}'#{brown*"🟫"}{orange*"🟧"}
        scale = f'{scale[0:int((int(len(scale))- black))]}{black*"⬛"}'
        return f'{scale}'

    def add_vote(self, option: str, name: str, add: int = 1):
        if name in self.person_vote.keys():
            voted_num = self.person_vote[name]
            self.options[str(voted_num)] -= 1
        self.person_vote[name] = option
        self.options[option] += add
        return
        
    def __str__(self):
        scale = self.scale()
        len_ = self.len_scale
        multiplier = round(len_*1.75)
        half_scale_indicator = f'|{multiplier*"-"}|{multiplier*"-"}|'
        return f'{half_scale_indicator}\n|{scale}|\n|{scale}|\n{half_scale_indicator}'

    @property
    def embed(self):
        embed = hikari.Embed()
        embed.title = self.title
        if self.description:
            embed.description = self.description
        embed.add_field(
            name=f'{round(float(self.average * 5), 3)}/{5} ||'\
            f'{int(round(float(self.average * 5 *20),0))}% ',
            value = f'{str(self)}\n\nVotes: {self.total_votes}'
        )
            
        if self.author:
            embed.set_footer(text=self.author)
        return embed


class PollVote:
    storage: dict
    options: Dict[str, Any]

    def __init__(
        self, 
        options: Dict[str, str],
        active_until: int,
        custom_id: str,
        anonymous: bool = True,
        poll_title: str = "Poll",
        poll_description: str = "",
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
        self._poll: Dict[str, List[int]] = {k: [] for k in options.keys()}
        self._options = options
        self._title = poll_title
        self._description = poll.desciption
        self._anomymous = anonymous
        self._active_until = active_until
        self._custom_id = custom_id
        # f"{int(time.time)}{ctx.author.id}{ctx.guild_id}"

    @property
    def embed(self):
        """
        converts `self` to `hikari.Embed`
        """
        embed = hikari.Embed(title=self._title)
        if self._description:
            embed.description = self._description
        description += "\n"
        for o, d in self._options.keys():
            description += f"**{o}** = {d}\n"   
        if self.anonymous:
            vote_result = ""
            for o, o_votes in self._poll.items():
                vote_result += f"**{o}** | {self._amount_to_str(o)}"
            embed.add_field("Results", value)
        else:
            for o, o_votes in self._poll_items():
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
        for v in self._options.values():
            count += len(v)
        return count

    def _amount_to_str(option_key: str, str_len: int = 20) -> str:
        """
        returns a string with len <str_len> which displays the poll percentage with terminal symbols
        """
        # █ ░
        option_perc = round(float(len(self._poll[option_key]) / self.total_votes), 0)
        return f"{option_perc * '█'}{int(str_len - len(option_perc)) * '░'}"
    
    def add_vote(
        self,
        option: str,
        member: hikari.Member,
        remove_old_poll: bool = True,
    ):
        """
        Args:
        ----
        number: `int` 
            the number, to identify the name (name will be mapped to number)
        member : `hikari.Member` 
            the person who voted
        remove_old_poll : `bool`
            wether or not to remove the old poll of that member
            Default=True

        Raises:
        -------
        ValueError:
            when option is invalid
        """
        if remove_old_poll:
            previous_option = None
            for o, members in self._poll:
                if member in members:
                    previous_option = o
            if o:
                self._poll[o].remove(member)
        self._poll[option].append(member)
        
        


class VoteKinds(Enum):
    SCALE = ScaleVote 







    