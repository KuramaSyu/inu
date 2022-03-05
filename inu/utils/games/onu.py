from abc import abstractmethod, ABC
import math
from pydoc import describe
import random
import re
from typing import (
    Dict,
    List,
    Optional,
    Union,
    Final
    
)
import enum
from collections import deque

from core import getLogger
from utils import Emoji


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

__all__: Final[List[str]] = [
    "Card",
    "Hand",
    "Onu",
    "Event",
    "TurnErrorEvent",
    "TurnSuccessEvent",
    "CardsReceivedEvent",
    "GameEndEvent",
    "OnuHandler",
]


log = getLogger(__name__)

class CardColors(enum.Enum):
    RED = "🟥"
    GREEN = "🟩"
    BLUE = "🟦"
    YELLOW = "🟨"
    COLORFULL = "colorfull"

class CardAlgorithms:
    @staticmethod
    def draw_cards(onu: "Onu", hand: "Hand", card: Optional["Card"]):
        if card is None:
            raise RuntimeError("Can't draw cards when card (for draw_value) is not given")
    
    @staticmethod
    def normal(onu: "Onu", hand: "Hand", card: Optional["Card"]):
        pass

    @staticmethod
    def stop(onu: "Onu", hand: "Hand", card: Optional["Card"]):
        pass

    @staticmethod
    def reverse(onu: "Onu", hand: "Hand", card: Optional["Card"]):
        pass
    
    @staticmethod
    def change_color(onu: "Onu", hand: "Hand", card: Optional["Card"]):
        pass

class CardFunctions(enum.Enum):
    DRAW_CARDS = 1
    NORMAL = 11
    STOP = 12
    REVERSE = 13
    CHANGE_COLOR = 14
    
class CardDesigns(enum.Enum):
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
        function: Union[CardFunctions, List[CardFunctions]],
        color: CardColors,
        card_design: CardDesigns = None,
        value: int = None,
        is_active: bool = False,
        draw_value: int = 0,
    ):
        if card_design is None and value is None:
            raise RuntimeError(
                "Can't build a card without value or card_design. Minimun one of them has to be given"
            )
        self.design = card_design
        
        if isinstance(function, List):
            self.functions = function
        else:
            self.functions = [function]
        self.color = color
        self.possible_color = color  # color attr will be changed to selected one
        if card_design is None:
            self.design = self.get_design_from_value(value)
        else:
            self.design = card_design
        self._design = self._chage_card_color()
        if value is None:
            self.value = self.get_value_from_design(self.design)
        else:
            self.value = value
        self.draw_value = self.get_draw_value(self.design)
        self.is_active = is_active or bool(self.draw_value)
        self._original_is_active = self.is_active
        self.log = getLogger(__name__, self.__class__.__name__)
        
        
    
    @staticmethod
    def get_value_from_design(design: CardDesigns) -> int:
        regex = "CARD_[0-9]"
        if re.match(regex, design.name):
            return int(design.name[-1])
        else:
            return None
        
    @staticmethod
    def get_design_from_value(value) -> CardDesigns:
        card_name = f"CARD_{value}"
        if not 0 <= value <= 9:
            raise RuntimeError(f"Can't build card with value: {value}")
        for design in CardDesigns:
            if re.match(card_name, design.name):
                return design
        raise RuntimeError(f"Card design with matches to value {value} not found")
       
    @staticmethod 
    def get_draw_value(design: CardDesigns) -> int:
        regex = "DRAW_CARDS_[0-9]"
        if re.match(regex, design.name):
            return int(design.name[-1])
        else:
            return 0

    def disable(self):
        """disables the is_active attr, which represents, wether or not the draw_value has been drawen"""
        self.is_active = False
        self.draw_value = 0

    def can_cast_onto(self, other: "Card") -> bool:
        """
        Checks if <other> can be casted onto this card

        Returns:
        --------
            - (bool) wether or not <other> can be casted onto this card
        
        """
        log = self.log
        other.maybe_make_active(self)
        # log.debug(f"{str(self)} ..... {str(other)}")
        if other.color == CardColors.COLORFULL:
            # log.debug("other color is colorfull")
            return False
        # if (not other.possible_color == CardColors.COLORFULL) and (self.possible_color == CardColors.COLORFULL):
        #     # log.debug("this card is colorfull")
        #     return False
        if self.is_active and not other.is_active:
            # log.debug("other card is not active")
            return False
        if CardFunctions.NORMAL in self.functions and CardFunctions.NORMAL in other.functions:
            if not (self.color == other.color or self.value == other.value):
                # log.debug("normal color and value not matching")
                return False
        else:
            if not (
                (self.functions == other.functions or self.draw_value and other.draw_value) 
                or 
                (self.color == other.color or other.possible_color == CardColors.COLORFULL)
            ):
                # log.debug("function or color is not same")
                return False
        return True

    def __str__(self):
        prefix = ""
        for f in self.functions:
            prefix += (
                {
                    CardFunctions.CHANGE_COLOR: "color chagner",
                    CardFunctions.REVERSE: "reverse",
                    CardFunctions.STOP: "stop",
                }.get(f, "")
            )
        number = ""
        if not self.value is None:
            number += str(self.value)
        if self.draw_value > 0:
            number += f"+{self.draw_value}"
        color = self.color.name.lower()
        l = []
        for x in (prefix, number, color):
            if x:
                l.append(x)
        return " | ".join(l)

    def _chage_card_color(self):
        if CardFunctions.CHANGE_COLOR in self.functions:
            return self.design.value
        return [row.replace("🟦", self.color.value) for row in self.design.value]

    def set_color(self, color: CardColors):
        self.color = color

    def do_action(self, onu: "Onu", self_hand: "Hand") -> None:
        """
        If the card has impact on players, then it will be done here
        """
        if CardFunctions.REVERSE in self.functions:
            onu.hands = [*reversed(onu.hands)]

        if CardFunctions.STOP in self.functions:
            onu.cycle_hands()
        if CardColors.COLORFULL == self.color:
            self.color = self_hand.color

    def maybe_make_active(self, other: "Card"):
        """edits `self.is_active` depending on the top card of cast_off stack"""
        self.is_active = self._original_is_active
        if self.is_active:
            return
        if CardFunctions.REVERSE in self.functions and other.is_active:
            self.is_active = True
    
    def set_default_active(self):
        self.is_active = self._original_is_active



        



        

class Hand:
    def __init__(
        self,
        name: str,
        id: str,
    ):
        self.name = name
        self.id = id
        self.cards: List[Card] = []
        self.color = CardColors.COLORFULL

    def __len__(self):
        return len(self.cards)

    def build_card_row(self, cards_per_row: int = 5, numbering: bool = True) -> List[str]:
        """
        Returns:
        --------
            - List[str] A list with strings which represent one row of cards respectively
        """
        rows = []
        row_str = ""
        to_process = []
        for card_i, card in enumerate(self.cards):
            row_str = ""
            to_process.append(card)
            if len(to_process) == cards_per_row or card_i+1 == len(self.cards):
                # draw fist row of <cards_per_row> cards to hand_str
                for i in range(len(card.design.value)):
                    # draw line for line until row is complete
                    if numbering and i == 0:
                        numbs = [Emoji.as_number(f"{n+2:02d}") for n in range(card_i-len(to_process), card_i)]
                        for j, item in enumerate(numbs):
                            if j % 5 == 0 or j == 0:
                                row_str += f"{item}"
                            elif j % 2 == 0:
                                row_str += f"⬛⬛{item}"
                            else:
                                row_str += f"⬛⬛⬛{item}"
                        row_str += "\n"
                        # disable for and enable this below if it's not for discord
                        #row_str += f" {'⬛⬛⬛'.join(numbs)}\n"
                    row_str += f'{"⬛⬛".join([card._design[i] for card in to_process])}\n'
                rows.append(row_str)
                to_process = []
        return rows

    def __str__(self) -> str:
        return "\n--------------\n".join(self.build_card_row())

    def set_color(self, color: CardColors):
        self.color = color

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            raise TypeError(f"type `{type(other)}` isn't comparable with `{self.__class__}`")
        return self.id == other.id

    def __ne__(self, other):
        return not self.__eq__(other)

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
                            card_design=CardDesigns.DRAW_CARDS_2,
                            function=CardFunctions.DRAW_CARDS,
                            color=color,
                            draw_value=2,
                            is_active=True,
                        ),

                        Card(
                            card_design=CardDesigns.REVERSE,
                            function=CardFunctions.REVERSE,
                            color=color,
                        ),
                        Card(
                            card_design=CardDesigns.STOP,
                            function=CardFunctions.STOP,
                            color=color,
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
                        function=[CardFunctions.DRAW_CARDS, CardFunctions.CHANGE_COLOR],
                        color=CardColors.COLORFULL,
                        draw_value=4,
                        is_active=True,
                        card_design=CardDesigns.DRAW_CARDS_4
                    ),
                    Card(
                        function=CardFunctions.CHANGE_COLOR,
                        color=CardColors.COLORFULL,
                        card_design=CardDesigns.COLOR_CHANGER,
                    )
                ]
            ) 
        for _ in range(0,3):
            random.shuffle(self.stack)
    

class CastOffStack:
    def __init__(self):
        self.stack: deque[Card] = deque()
        self._draw_value = 0

    @property
    def draw_calue(self) -> int:
        if self._draw_value == 0:
            return 1
        else:
            return self._draw_value

    @property
    def top(self) -> Card:
        return self.stack[-1]
        
    def append(self, card: Card):
        try:
            if CardFunctions.REVERSE in card.functions and self.top.is_active:
                card.is_active = True
        except:
            card.is_active = False
        self.stack.append(card)
        self._draw_value += card.draw_value
        
    def reset_draw_value(self):
        self._draw_value = 0
        self.top.disable()


class Event:
    def __init__(
        self,
        hand: Hand,
        info: str,
    ):
        self.hand = hand
        self.info = info


class SideEvent(Event):
    def __init__(
        self,
        hand: Hand,
        info: str,
    ):
        super().__init__(hand, info)


class CardsReceivedEvent(Event):
    def __init__(
        self,
        hand: Hand,
        info: str,
        cards: List[Card],
    ):
        super().__init__(hand, info)
        self.cards = cards


class TurnErrorEvent(Event):
    def __init__(
        self,
        hand: Hand,
        info: str,
        top_card: Card,
        given_card: Card,

    ):
        super().__init__(hand, info)
        self.top_card = top_card
        self.given_card = given_card


class TurnSuccessEvent(Event):
    def __init__(
        self,
        hand: Hand,
        info: str,
        top_card: Card,

    ):
        super().__init__(hand, info)
        self.top_card = top_card


class GameEndEvent(Event):
    def __init__(
        self,
        hand: Hand,
        info: str,
        winner: Hand,
    ):
        super().__init__(hand, info)
        self.winner = winner


class WrongTurnEvent(Event):
    def __init__(
        self,
        hand: Hand,
        info: str,
    ):
        super().__init__(hand, info)


class Onu:
    def __init__(
        self,
        players: Dict[str, str],
        cards_per_hand: int,
    ):
        """
        Constructor of Onu

        Args:
        -----
            - player_names (Dict[int, str]) A mapping from str (id of player) to str (name of player)
            - cards_per_hand (int) how many cards should one hand have
        """
        self.stack: NewCardStack = NewCardStack()

        self.cast_off: CastOffStack = CastOffStack()
        first_card = self.stack.pop()
        if CardFunctions.CHANGE_COLOR in first_card.functions:
            first_card.set_color(
                random.choice([CardColors.BLUE, CardColors.GREEN, CardColors.YELLOW, CardColors.RED])
            )
        self.cast_off.append(first_card)

        self.hands: List[Hand] = [Hand(name, str(id)) for id, name in players.items()]
        random.shuffle(self.hands)
        for hand in self.hands:
            for _ in range(0, cards_per_hand):
                hand.cards.append(self.stack.pop())

    def turn(
        self,
        hand: Union[Hand, str],
        card: Card,
        draw: bool = False,
        select_color: CardColors = None
    ) -> Event:
        """
        Main function to control the game
        
        Args:
        ----
            - hand: (`~.Hand`) The player who made an aktion
            - card: (`~.Card`) The card the player has casted
            - draw: (bool) wether or not the player wants to draw cards
        """
        if isinstance(hand, str):
            # convert id to hand
            hand = [h for h in self.hands if h.id == hand][0]
        if select_color:
            # change selected hand color
            hand.set_color(select_color)
            return SideEvent(hand, f"Changed selected color to `{hand.color}`")
        if hand != self.current_hand:
            # wrong player
            return WrongTurnEvent(hand, "It's not your turn!")
        if draw is True and not card is None:
            # wether playing a card nor casting one
            raise RuntimeError(f"Can't make a turn, where a card is played AND the player draw cards")
        args = {
            "hand": hand,
            "info": f"You can't cast a {str(card)} onto a {str(self.cast_off.top)}",
            "top_card": self.cast_off.top,   
        }
        if draw:
            # draw card
            for _ in range(0, self.cast_off.draw_calue):
                hand.cards.append(self.stack.pop())
            self.cast_off.reset_draw_value()
            args["info"] = f"Successfully drawn {self.cast_off.draw_calue} cards"
            self.cycle_hands()
            return TurnSuccessEvent(**args)

        if not self.cast_off.top.can_cast_onto(card):
            # can't cast onto top card
            
            if card.color == CardColors.COLORFULL:
                if hand.color != CardColors.COLORFULL:
                    # change card color to selected color
                    card.color = hand.color
                    # log.debug(f"changed card color to {hand.color}")
                    return self.turn(hand, card, draw)
                else:
                    # card and hand are colorfull
                    args["info"] = "given <card> color is `~.CardColors.COLORFULL` which is not castable"
                    return TurnErrorEvent(**args, given_card=card)
            else:
                # typical onu error (cards don't match)
                return TurnErrorEvent(**args, given_card=card)
        card.do_action(self, hand)
        hand.cards.remove(card)
        self.cast_off.append(card)
        args["info"] = "Successfully casted card"
        if self.game_over:
            del args["top_card"]
            return GameEndEvent(**args, winner=self.winner)
        else:
            self.cycle_hands()
            return TurnSuccessEvent(**args)
    
    @property
    def game_over(self) -> bool:
        for hand in self.hands:
            if len(hand.cards) == 0:
                return True
        return False
    
    @property
    def winner(self) -> Optional[Hand]:
        for hand in self.hands:
            if len(hand.cards) == 0:
                # log.debug(f"winner is {hand.name}")
                return hand
        return None

        
        
    @property
    def current_hand(self):
        return self.hands[0]
    
    def cycle_hands(self):
        """cycles hands in direction left"""
        self.hands.append(self.hands.pop(0))
        

class OnuHandler:
    def __init__(
        self,
        players: Dict[str, str],
        cards_per_hand: int = 10,
    ):
        self.onu = Onu(players, cards_per_hand=cards_per_hand)

    @property
    def current_hand(self) -> Hand:
        return self.onu.current_hand

    def on_event(self, event: Event):
        pass

    def on_turn_success(self, event: TurnSuccessEvent):
        pass

    def on_game_end(self, event: GameEndEvent):
        pass

    def on_turn_error(self, event: TurnErrorEvent):
        pass
    
    def on_cards_received(self, event: CardsReceivedEvent):
        pass

    def on_side_event(self, event: SideEvent):
        pass
    
    def do_turn(
        self,
        hand: Optional[Hand] = None,
        card: Optional[Card] = None,
        draw_cards: bool = False,
        select_color: CardColors = None,
    ):
        event = self.onu.turn(hand, card, draw_cards, select_color)
        self.on_event(event)
        if isinstance(event, TurnSuccessEvent):
            self.on_turn_success(event)
        elif isinstance(event, GameEndEvent):
            self.on_game_end(event)
        elif isinstance(event, TurnErrorEvent):
            self.on_turn_error(event)
        elif isinstance(event, CardsReceivedEvent):
            self.on_cards_received(event)
        elif isinstance(event, SideEvent):
            self.on_side_event(event)
        elif isinstance(event, WrongTurnEvent):
            self.on_wrong_turn(event)
        return event

# bare example
if __name__ == "__main__":
    # log.debug("TEST")
    class TerminalOnu(OnuHandler):
        def on_event(self, event: Event):
            print(event)

        def on_turn_success(self, event: TurnSuccessEvent):
            pass

        def on_game_end(self, event: GameEndEvent):
            pass

        def on_turn_error(self, event: TurnErrorEvent):
            print(event.info)
        
        def on_cards_received(self, event: CardsReceivedEvent):
            pass

        def on_side_event(self, event: SideEvent):
            pass

        def loop(self):
            while not self.onu.game_over:
                hand = self.current_hand
                print(self.create_player_hand_embed(hand))
                print(f"0 --- draw cards ({self.onu.cast_off.draw_calue})")
                for i, card in enumerate(self.current_hand.cards):
                    print(i+1, "---", card)
                print(f"top card: {self.onu.cast_off.top}")
                card_index = input(f"Which card do you wanna play @{self.current_hand.name}:\n")
                if card_index == "0":
                    self.do_turn(hand, draw_cards=True)
                else:
                    self.do_turn(hand, hand.cards[int(card_index)-1])

        def create_player_hand_embed(self, hand: Hand):
            print(hand.name)
            display = f"\n\n{hand.name}'s hand:\n"
            display += str(hand)
            display += f"top card: {str(self.onu.cast_off.top)} --- {self.onu.cast_off.top.is_active}\n"
            display += "\n".join(self.onu.cast_off.top._design)
            display += "\nupcoming players\n"
            display += "\n--> ".join(hand.name for hand in self.onu.hands)
            return display
    players = {
        "1": "Olaf",
        "2": "Annie"
    }
    onu = TerminalOnu(players)
    onu.loop()


