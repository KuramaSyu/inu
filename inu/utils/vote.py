from enum import Enum
from abc import ABC, abstractmethod
from typing import *



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
            - number (`int`) the number, to identify the name (name will be mapped to number)
            - name (`str`) the name, which will be mapped to the given number
            - add (`int`) the amount of votes to add to this number. Typically -1 or 1 
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

    def average(self) -> float:
        total_value = int(self.options['1'])*1 + int(self.options['2'])*2 + int(self.options['3'])*3 + \
            int(self.options['4'])*4 + int(self.options['5'])*5 + int(self.options['0'])*0
        total_votes = self.total_votes()
        if total_votes == 0:
            return 0
        return round(float(total_value / total_votes / 5), 2) 

    def total_votes(self) -> int:
        total_votes = int(self.options['1']) + int(self.options['2']) + int(self.options['3']) + \
            int(self.options['4']) + int(self.options['5']) + int(self.options['0'])
        return total_votes

    def total_grades(self) -> int:
        return len(self.options.keys()) - 1 #because 0 is a key

    def scale(self) -> str:
        average = self.average()
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
            name=f'{round(float(self.average() * 5), 3)}/{5} ||'\
            f'{int(round(float(self.average() * 5 *20),0))}% ',
            value = f'{str(self)}\n\nVotes: {self.total_votes()}'
        )
            
        if self.author:
            embed.set_footer(text=self.author)
        return embed


class PollVote(Vote):
    storage: dict
    options: Dict[str, Any]

    def __init__(self, options: Dict[str, Any]):
        self.options = options

    @property
    def embed(self):
        ...
    
    def add_vote(
        self,
        number: int,
        name: str,
        add: int,
    ):
        """
        Args:
        ----
            - number (`int`) the number, to identify the name (name will be mapped to number)
            - name (`str`) the name, which will be mapped to the given number
            - add (`int`) the amount of votes to add to this number. Typically -1 or 1 
        """
        ...


class VoteKinds(Enum):
    SCALE = ScaleVote 







    