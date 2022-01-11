from typing import *

import hikari
from hikari import Snowflakeish
import lightbulb
from lightbulb.context import Context

from core import Inu
from .onu import *

class HikariOnu(OnuHandler):
    def __init__(
        self,
        players: Dict[Snowflakeish: Union[hikari.User, hikari.Member]]
    ):
        legacy_players = {str(snowfl): user.username for snowfl, user in players.items()}
        super().__init__(legacy_players)

    def on_event(self, event: Event):
        print(event)
        print(event.hand)

    def on_turn_success(self, event: TurnSuccessEvent):
        pass

    def on_game_end(self, event: GameEndEvent):
        pass

    def on_turn_error(self, event: TurnErrorEvent):
        print(event.info)
    
    def on_cards_received(self, event: CardsReceivedEvent):
        pass

    async def loop(self):
        hand = self.current_hand
        while not self.onu.game_over:
            for i, card in enumerate(self.current_hand.cards):
                print(i, "---", card)
            print(f"top card: {self.onu.cast_off.top}")
            card_index = input(f"Which card do you wanna play @{self.current_hand.name}:\n")
            event = self.do_turn(hand, hand.cards[int(card_index)])
            await self.a_on_event(event)

    async def start(self, bot: Inu, ctx: Context):
        self.bot = bot
        self.ctx = ctx

    async def a_on_event(self, event: Event):
        if isinstance(event, TurnSuccessEvent):
            await self.a_on_turn_success(event)
        elif isinstance(event, GameEndEvent):
            await self.a_on_game_end(event)
        elif isinstance(event, TurnErrorEvent):
            await self.a_on_turn_error(event)
        elif isinstance(event, CardsReceivedEvent):
            await self.a_on_cards_received(event)

    async def a_on_turn_success(self, event: TurnSuccessEvent):
        pass

    async def a_on_game_end(self, event: GameEndEvent):
        pass

    async def a_on_turn_error(self, event: TurnErrorEvent):
        print(event.info)
    
    async def a_on_cards_received(self, event: CardsReceivedEvent):
        pass

    def create_player_hand_embed(self, hand: Hand):
        embed = hikari.Embed(titile="Your hand")
        for i, row in enumerate(hand.build_card_row()):
            embed.add_field(name="{i}. row", value=row)
        embed.add_field(f"top card: {str(self.onu.cast_off.top)}", "\n".join(self.onu.cast_off.top.design.value), inline=True)
        embed.add_field("upcoming players", "--> ".join(hand.name for hand in self.onu.hands))


            
                
            

players = {
    "1": "Olaf",
    "2": "Annie"
}
onu = test(players)
onu.loop()
