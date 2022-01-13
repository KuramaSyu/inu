from os import close
from typing import *
import asyncio

import hikari
from hikari import Snowflakeish, Embed
from hikari.events.message_events import MessageCreateEvent
from hikari.impl import ActionRowBuilder
from hikari.events.interaction_events import InteractionCreateEvent
from hikari.interactions.base_interactions import ResponseType
from hikari.interactions.component_interactions import ComponentInteraction
from hikari.messages import ButtonStyle
import lightbulb
from lightbulb.context import Context

from utils import Colors
from core import Inu, getLogger
from .onu import *
from .onu import CardColors
from .onu import CardFunctions
from .onu import SideEvent
from .onu import WrongTurnEvent

log = getLogger(__name__)

class HikariOnu(OnuHandler):
    def __init__(
        self,
        players: Dict[Snowflakeish, Union[hikari.User, hikari.Member]],
    ):
        self.log = getLogger(__name__, self.__class__.__name__)
        self.players = players
        legacy_players = {str(snowfl): user.username for snowfl, user in players.items()}
        super().__init__(legacy_players, cards_per_hand=10)
        self.timeout = 14.5*60
        self.messages: Dict[Snowflakeish, Snowflakeish] = {}
        self.channels: Dict[Snowflakeish, Snowflakeish] = {}
        self.colors = {
            "red": CardColors.RED, 
            "yellow": CardColors.YELLOW,
            "green": CardColors.GREEN, 
            "blue": CardColors.BLUE
        }
        self.bot = None
        self.ctx = None

    def get_user(self, hand: Hand) -> Union[hikari.User, hikari.Member]:
        return self.players[int(hand.id)]

    async def send(
        self, 
        hand: Hand, 
        embed: Embed = None, 
        *, 
        add_hand_components: bool = True, 
        info: str = None,
    ):
        channel_id = self.channels[int(hand.id)]
        message_id = self.messages[int(hand.id)]
        # log.debug(f"send to channel: {channel_id}, message update: {message_id}")
        if embed is None:
            args = [hand, info] if info else [hand]
            embed = self.create_player_hand_embed(*args)
        component = []
        if add_hand_components:
            component = self.create_player_hand_component(hand)
        await asyncio.create_task(
            self.bot.rest.edit_message(channel_id, message_id, embed=embed, components=component)
        )

    def on_event(self, event: Event):
        # log.debug(event)
        pass

    def on_turn_success(self, event: TurnSuccessEvent):
        pass

    def on_game_end(self, event: GameEndEvent):
        pass

    def on_turn_error(self, event: TurnErrorEvent):
        pass

    def on_cards_received(self, event: CardsReceivedEvent):
        pass

    def on_wrong_turn(self, event: CardsReceivedEvent):
        pass

    def on_side_event(self, event: SideEvent):
        pass

    async def loop(self):
        while not self.onu.game_over:
            card_index, user_id = await self._wait_for_interaction()
            hand = [h for h in self.onu.hands if int(h.id) == int(user_id)][0]
            if card_index is None:
                # self.# log.debug("card index is None")
                break
            elif card_index in self.colors.keys():
                # change selected color
                # here the name card_index is maybe a bit weird
                event = self.do_turn(hand, select_color=self.colors[card_index])
            elif card_index == 0:
                # draw a card
                event = self.do_turn(hand, draw_cards=True)
            else:
                # cast a card
                event = self.do_turn(hand, hand.cards[int(card_index)-1])
            await self.a_on_event(event)

    async def _wait_for_interaction(self) -> Tuple[Optional[Union[int, str]], Optional[Snowflakeish]]:
        coros = [
            self.bot.wait_for(
                MessageCreateEvent,
                timeout=self.timeout,
                predicate=lambda e:(
                    str(e.author_id) in [str(player.id) for player in self.players.values()]
                )
            ),
            self.bot.wait_for(
                InteractionCreateEvent,
                timeout=self.timeout,
                predicate=lambda e:(
                    isinstance(e.interaction, ComponentInteraction)
                    and e.interaction.custom_id in ["onu_card_menu", "red", "yellow", "green", "blue"]
                    and str(e.interaction.user.id) in [str(player.id) for player in self.players.values()]
                )
            )
        ]
        try:
            done, pending = await asyncio.wait(
                [asyncio.create_task(coro) for coro in coros],
                return_when=asyncio.FIRST_COMPLETED,
                timeout=self.timeout
            )
            for task in pending:
                task.cancel()
            event = done.pop().result()
            if isinstance(event, MessageCreateEvent):
                return int(event.message.content), event.author_id
            await event.interaction.create_initial_response(ResponseType.DEFERRED_MESSAGE_UPDATE)
            if event.interaction.custom_id in ["red", "yellow", "green", "blue"]:
                return event.interaction.custom_id, event.interaction.user.id
            return int(event.interaction.values[0]), event.interaction.user.id # the card number the player has choosen
        except asyncio.TimeoutError:
            await self.a_on_timeout()
            return None, None
        except ValueError:
            return await self._wait_for_interaction()

    async def start(self, bot: Inu, ctx: Context):
        self.bot = bot
        self.ctx = ctx
        tasks = []
        for user in self.players.values():
            tasks.append(asyncio.create_task(user.fetch_dm_channel(), name=str(user.id)))
        done, _ = await asyncio.wait(
            [asyncio.create_task(user.fetch_dm_channel(), name=str(user.id)) for user in self.players.values()],
            return_when=asyncio.ALL_COMPLETED,
            timeout=self.timeout
        )
        for task in done:
            # # log.debug(task.get_name())
            self.channels[int(task.get_name())] = int(task.result().id)

        async def initial_message(self: OnuHandler, hand):
            channel_id = self.channels[int(hand.id)]
            message = await self.bot.rest.create_message(channel_id, self.create_player_hand_embed(hand), components=self.create_player_hand_component(hand))
            self.messages[int(hand.id)] = message.id

        _, _ = await asyncio.wait(
            [asyncio.create_task(initial_message(self, hand)) for hand in self.onu.hands],
            return_when=asyncio.ALL_COMPLETED,
            timeout=self.timeout
        )
        await self.loop()

    async def a_on_event(self, event: Event):
        if isinstance(event, TurnSuccessEvent):
            await self.a_on_turn_success(event)
        elif isinstance(event, GameEndEvent):
            await self.a_on_game_end(event)
        elif isinstance(event, TurnErrorEvent):
            await self.a_on_turn_error(event)
        elif isinstance(event, CardsReceivedEvent):
            await self.a_on_cards_received(event)
        elif isinstance(event, SideEvent):
            await self.a_on_side_event(event)
        elif isinstance(event, WrongTurnEvent):
            await self.a_on_wrong_turn(event)

    async def a_on_wrong_turn(self, event: SideEvent):
        await self.send(event.hand, info=event.info)

    async def a_on_side_event(self, event: SideEvent):
        await self.send(event.hand, info=event.info)

    async def a_on_timeout(self):
        embed = Embed(title="Game timed out | DRAW", color=Colors.from_name("slategrey"))
        for player in self.players.values():
            asyncio.create_task(player.send(embed=embed))

    async def a_on_turn_success(self, event: TurnSuccessEvent):
        for hand in self.onu.hands:
            await self.send(hand)

    async def a_on_game_end(self, event: GameEndEvent):
        embed = hikari.Embed(
            title="Game Over", 
            description=f"{event.winner.name} won the game", 
            color=Colors.from_name("darkred")
        )
        for hand in self.onu.hands:
            if hand.id == event.hand.id:
                continue
            asyncio.create_task(self.send(hand, embed, add_hand_components=False))
        asyncio.create_task(
            self.send(
                event.winner, 
                Embed(title="You have won the game!", color=Colors.from_name("royalblue")), 
                add_hand_components=False
            )
        )
        asyncio.create_task(
            self.send(
                self.ctx.respond(
                    embed=Embed(
                        title="{event.winner} has won the game!", 
                        color=Colors.from_name("royalblue"),
                        description=f"start another game with `/onu @player1 ...` or `inu.onu @player1 ...`"
                    ), 
                )
            )
        )
    async def a_on_turn_error(self, event: TurnErrorEvent):
        asyncio.create_task(
            self.send(
                hand=event.hand,
                embed=self.create_player_hand_embed(event.hand, event.info)
            )
        )
    
    async def a_on_cards_received(self, event: CardsReceivedEvent):
        # update all hands, since next player also should be changed
        for hand in self.onu.hands:
            await self.send(hand)

    def create_player_hand_embed(self, hand: Hand, info: str = None):
        embed = hikari.Embed(
            title="Your hand", 
            color=Colors.from_name(
                self.color_translation(self.onu.cast_off.top.color)
            )
        )
        for i, row in enumerate(hand.build_card_row()):
            embed.add_field(name=f"{i}. row", value=f"{row}\n\n")
        embed.add_field(f"top card: {str(self.onu.cast_off.top)}", "\n".join(self.onu.cast_off.top._design), inline=True)
        embed.add_field("upcoming players", "\n--> ".join(hand.name for hand in self.onu.hands), inline=True)
        embed.add_field("selected color for colorchanger", value=hand.color.name if hand.color else "/")
        if info:
            embed.add_field("Info", info)
        return embed

    def create_player_hand_component(self, hand: Hand) -> List[ActionRowBuilder]:
        components: List[ActionRowBuilder] = []
        menu = (
            ActionRowBuilder()
            .add_select_menu("onu_card_menu")
            .add_option(f"Draw cards ({self.onu.cast_off.draw_calue})", "0").add_to_menu()
        )
        for i, card in enumerate(hand.cards):
            if i >= 24:
                # limit of menu len reached
                break  
            menu.add_option(f"{i+1}: {str(card)}", str(int(i+1))).add_to_menu()
        menu = menu.add_to_container()
        for i, card in enumerate(hand.cards):

            if CardFunctions.CHANGE_COLOR in card.functions:
                btns = (
                    ActionRowBuilder()
                    .add_button(ButtonStyle.SECONDARY, "green").set_emoji("🟢").add_to_container()
                    .add_button(ButtonStyle.SECONDARY, "red").set_emoji("🔴").add_to_container()
                    .add_button(ButtonStyle.SECONDARY, "blue").set_emoji("🔵").add_to_container()
                    .add_button(ButtonStyle.SECONDARY, "yellow").set_emoji("🟡").add_to_container()
                )
                components.append(btns)
                break
        components.append(menu)
        return components

    def color_translation(self, color: CardColors) -> str:
        t = {
            "COLORFULL": "darkslateblue",
            "BLUE": "cornflowerblue",
        }
        c = t.get(color.name)
        if c is None:
            # log.debug(f"not found in dict: {color.name}")
            return color.name.lower()
        return c