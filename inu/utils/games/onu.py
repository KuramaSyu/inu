import math
from pydoc import describe
import random
import re
from typing import (
    Dict,
    List,
    Optional
    
)
import enum
from collections import deque


from .onu_cards import (
    card_0,
    card_1,
    card_2,
    card_3,
    card_4,
    card_5,
    card_6,
    card_7,
    card_8,
    card_9,
    card_color_changer,
    card_draw_cards_2,
    card_draw_cards_4,
    card_reverse,
    card_stop
)

class CardColors(enum.Enum):
    RED = "red"
    GREEN = "green"
    BLUE = "blue"
    YELLOW = "yellow"
    COLORFULL = "colorfull"


class CardFunctions(enum.Enum):
    DRAW_CARDS_2 = 2
    DRAW_CARDS_4 = 4
    NORMAL = 11
    STOP = 12
    REVERSE = 13
    CHANGE_COLOR = 14
    
class CardDesign(enum.Enum):
    CARD_0 = card_0
    CARD_1 = card_1
    CARD_2 = card_2
    CARD_3 = card_3
    CARD_4 = card_4
    CARD_5 = card_5
    CARD_6 = card_6
    CARD_7 = card_7
    CARD_8 = card_8
    CARD_9 = card_9
    COLOR_CHANGER = card_color_changer
    DRAW_CARDS_2 = card_draw_cards_2
    DRAW_CARDS_4 = card_draw_cards_4
    REVERSE = card_reverse
    STOP = card_stop
    
    
class Card:
    def __init__(
        self, 
        function: CardFunctions,
        color: CardColors,
        card_design: CardDesign = None,
        value: int = None,
        is_active: bool = False,
    ):
        if card_design is None and value is None:
            raise RuntimeError(
                "Can't build a card without value or card_design. Minimun one of them has to be given"
                )
        self.design = card_design
        self.function = function
        self.color = color
        if card_design is None:
            self.design = self.get_design_from_value(value)
        else:
            self.design = card_design
        if value is None:
            self.value = self.get_value_from_design(self.design)
        else:
            self.value = value
        self.is_active = is_active
        self.draw_value = self.get_draw_value(self.design)
        
    
    @staticmethod
    def get_value_from_design(design: CardDesign) -> Optional[int]:
        regex = "CARD_[0-9]"
        if re.match(regex, design.name):
            return int(design.name[-1])
        else:
            return None
        
    @staticmethod
    def get_design_from_value(value) -> CardDesign:
        regex = "CARD_[0-9]"
        if not 0 <= value <= 9:
            raise RuntimeError(f"Can't build card with value: {value}")
        for design in CardDesign:
            if re.match(regex, design.name):
                return design
        raise RuntimeError(f"Card design with matches to value {value} not found")
       
    @staticmethod 
    def get_draw_value(design: CardDesign) -> Optional[int]:
        regex = "DRAW_CARDS_[0-9]"
        if re.match(regex, design.name):
            return int(design.name[-1])
        else:
            return None

        

class Hand:
    pass

class NewCardStack:
    def __init__(self):
        self.stack: List[Card] = []
        self.extend_stack()

    def pop(self, index: int = 0) -> Card:
        "returns a card from the stack"
        if len(self.stack) < 1:
            self.extend_stack()
        return self.stack.pop(index)

    def extend_stack(self):
        numbers = [0,1,2,3,4,5,6,7,8,9]
        colors = [CardColors.RED, CardColors.BLUE, CardColors.GREEN, CardColors.YELLOW]

        for color in colors:
            for _ in range(0,4):
                self.stack.extend(
                    [
                        Card(
                            card_design=CardDesign.DRAW_CARDS_2,
                            function=CardFunctions.DRAW_CARDS_2,
                            color=color,
                            is_active=True,
                        ),

                        Card(
                            card_design=CardDesign.REVERSE,
                            function=CardFunctions.REVERSE,
                            color=color,
                            is_active=True,
                        ),
                        Card(
                            card_design=CardDesign.STOP,
                            function=CardFunctions.STOP,
                            color=color,
                            is_active=True,
                        ),
                    ]
                )

            for number in numbers:
                if number == 0:
                    count = 2
                        
                else:
                    count = 4
                for _ in range(0, count):
                    self.stack.append(
                        Card(
                            color=color,
                            function=CardFunctions.NORMAL,
                            value=number,
                        )
                    )
                        
        for _ in range(0,4):
            self.stack.extend(
                [
                    Card(
                        function=CardFunctions.DRAW_CARDS_4,
                        color=CardColors.COLORFULL,
                    ),
                    Card(
                        function=CardFunctions.CHANGE_COLOR,
                        color=CardColors.COLORFULL,
                    )
                ]
            ) 
        for _ in range(0,3):
            random.shuffle(self.stack)

class CastOffStack:
    def __init__(self):
        self.stack: deque[Card] = deque()

    @property
    def top(self):
        self.stack[-1]
        
    def append(self, item: Card):
        self.stack.append(item)

class Onu:
    def __init__(
        self,
        player_names: List[str],
        cards_per_hand: int,
    ):
        self.hands: List[Hand] = []
        self.stack: NewCardStack = NewCardStack()
        self.cast_off: CastOffStack = CastOffStack()
        self.cast_off.append(self.stack.pop())
        
    
    def build_hands(self):
        pass
    
