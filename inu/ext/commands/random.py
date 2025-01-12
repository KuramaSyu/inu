import asyncio
import random
from fractions import Fraction
import os
import traceback
import typing
from typing import *
import logging
from copy import deepcopy

import hikari
from hikari.impl import MessageActionRowBuilder
import lightbulb
from lightbulb.context import Context
from PIL import Image, ImageEnhance
from io import BytesIO
from expiring_dict import ExpiringDict

from .tags import tag_name_auto_complete, _tag_add
from core import getLogger, Inu, get_context, BotResponseError, InuContext
from utils import (
    crumble, 
    BoredAPI, 
    Tag, 
    TimeButton, 
    PacmanButton,
    ListParser, 
    TagType,
    ResendButton
)

log = getLogger(__name__)

loader = lightbulb.Loader()
bot = Inu.instance
RESEND_ID = "rnd-list"

random_group = lightbulb.Group(name="random", description="Dices, Lists, Numbers and more")

@random_group.register
class NumberCommand(
    lightbulb.SlashCommand,
    name="number",
    description="Gives a number between start and stop",
    dm_enabled=False,
    default_member_permissions=None,
):
    stop_number = lightbulb.integer("stop-number", "This number is included")
    start_number = lightbulb.integer("start-number", "This number is included", default=1)

    @lightbulb.invoke
    async def callback(self, _: lightbulb.Context, ctx: InuContext):
        try:
            number = random.randint(self.start_number, self.stop_number)
        except ValueError:
            await ctx.respond("No. You can't do that. Stop it. Get some help.")
            return
        emoji_numbers = [ "0️⃣", "1️⃣", "2️⃣", "3️⃣", "4️⃣",
                          "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣"]
        emoji_number = "".join([emoji_numbers[int(i)] for i in str(number)])
        await ctx.respond(f"{emoji_number}")

user_list_cache: ExpiringDict[int, List[str]] = ExpiringDict(ttl=60*60)  # type: ignore

@random_group.register
class ListCommand(
    lightbulb.SlashCommand,
    name="list",
    description="shuffles a given list",
    dm_enabled=False,
    default_member_permissions=None,
):
    tag_with_list = lightbulb.string("tag-with-list", "a tag which contains the list", autocomplete=tag_name_auto_complete, default=None)
    list = lightbulb.string('list', 'seperate with comma -- eg: apple, kiwi, tree, stone', default=None)

    @lightbulb.invoke
    async def callback(self, _: lightbulb.Context, ctx: InuContext):
        await self._callback(ctx, self.list, self.tag_with_list)
    @staticmethod
    async def _callback(ctx: InuContext, list: Optional[str], tag_with_list: Optional[str], pacman_index: int = 0, color: str = "S"):
        colors = {
            "R": hikari.ButtonStyle.DANGER,
            "G": hikari.ButtonStyle.SUCCESS,
            "B": hikari.ButtonStyle.PRIMARY,
            "S": hikari.ButtonStyle.SECONDARY,
        }
        def shift_color(color: str, shift: int = 1) -> str:
            colors = ["R", "G", "B", "S"]
            colors.remove(color)
            return random.choice(colors)
        
        SPLIT = ","
        kwargs = {}
        
        # no options given
        if not list and not tag_with_list:
            try:
                facts, new_ctx = await ctx.ask_with_modal(
                    "Enter a list", 
                    "List:", 
                    placeholder_s="Kiwi, tree, stone, strawberries, teamspeak",
                )
            except Exception:
                return
            if not facts:
                return
            assert new_ctx is not None
            ctx = new_ctx
            list_text: str = facts
        # tag given
        elif tag_with_list:
            tag = await Tag.fetch_tag_from_link(f"tag://{tag_with_list}.local", ctx.guild_id)
            list_text = ("".join(tag.value))
            length = 16
            pacman_index += 3
            if pacman_index >= length:
                pacman_index = pacman_index % length
                color = shift_color(color, 1)

            custom_id_base = f"{tag_with_list};;{pacman_index};;{color}"
            kwargs["components"] = [
                MessageActionRowBuilder()
                .add_interactive_button(
                    colors.get(color), 
                    f"shuffle-{custom_id_base}", 
                    emoji="🎲"
                )
            ]
            kwargs["components"] = PacmanButton.add(
                kwargs["components"], 
                index=pacman_index, 
                length=length, 
                short=True, 
                color=colors.get(color),
            )
            kwargs["components"] = ResendButton.add(
                kwargs["components"], 
                f"shuffle-resend-{custom_id_base}", 
                color=colors.get(color)
            )
        # list given
        else:
            list_text = list
            
        # clean list
        fact_list = ListParser().parse(list_text)
        
        # add component to save list
        if not tag_with_list:
            rand_int = random.randint(0, 10**8)
            user_list_cache[rand_int] = deepcopy(fact_list)
            kwargs["components"] = ([
                MessageActionRowBuilder()
                .add_interactive_button(
                    hikari.ButtonStyle.SECONDARY, 
                    f"add-rnd-list-{rand_int}",
                    emoji="➕",
                    label="Add list as tag"
                )
            ])   
        # shuffle list
        random.shuffle(fact_list)
        random.shuffle(fact_list)
        rand_int: int | None = None
        
        longest_fact = max([len(fact) for fact in fact_list])
        fact_list = [f"{fact:^{longest_fact}}" for fact in fact_list]

        #how many columns
        columns: int
        gr1 = float(1.5)
        gr2 = float(2.8)
        gr3 = float(3.7)
        gr4 = float(4.7)
        gr5 = float(5.7)
        if 60 / float(longest_fact) <= gr1:
            columns = 1
        elif 60 / float(longest_fact) <= gr2:
            columns = 2
        elif 60 / float(longest_fact) <= gr3:
            columns = 3
        elif 60 / float(longest_fact) <= gr4: 
            columns = 4
        else:  #  60 / longest_fact > gr4
            columns = 5
        
        fact_list_parted = [[]]
        for fact in fact_list:
            if len(fact_list_parted[-1]) >= columns:
                fact_list_parted.append([])
            fact_list_parted[-1].append(fact)
        
        facts_as_str = f"Options: {len(fact_list)}\n"
        for facts in fact_list_parted:
            for fact in facts:
                facts_as_str += f"||`{fact}`|| "
            facts_as_str += "\n"
        if len(facts_as_str) > 2000:
            embed = hikari.Embed()
            for part in crumble(facts_as_str, 1024):
                embed.add_field("‌‌ ", part)
            await ctx.respond(embed=embed, **kwargs)
        else:
            await ctx.respond(facts_as_str, **kwargs)

@loader.listener(hikari.InteractionCreateEvent)
async def on_list_interaction(event: hikari.InteractionCreateEvent):
    color = "S"
    TAG_PACMAN_SPLIT = ";;"
    pacman_index = 0
    if not isinstance(event.interaction, hikari.ComponentInteraction):
        return
    
    custom_id = event.interaction.custom_id
    
    if not custom_id.startswith("shuffle-"):
        # not a shuffle button
        return
    
    resend = False
    if custom_id.startswith("shuffle-resend-"):
        resend = True
        custom_id = custom_id.removeprefix("shuffle-resend-")
    else:
        custom_id = custom_id.removeprefix("shuffle-")
    
    cmd_args = custom_id
    if TAG_PACMAN_SPLIT in cmd_args:
        cmd_args, pacman_index, color = cmd_args.split(TAG_PACMAN_SPLIT)
    ctx = get_context(event)

    if resend:
        await ctx.respond("Resending...", update=True)
        await ctx.delete_initial_response()
    else:
        ctx.update = True
    try:
        await ListCommand._callback(
            ctx, None,
            tag_with_list=cmd_args,
            pacman_index=int(pacman_index),
            color=color
        )
    except BotResponseError as e:
        await ctx.respond(**e.context_kwargs)

@loader.listener(hikari.InteractionCreateEvent)
async def on_list_add(event: hikari.InteractionCreateEvent):
    if not isinstance(event.interaction, hikari.ComponentInteraction):
        return
    
    if not event.interaction.custom_id.startswith("add-rnd-list-"):
        # add list as tag
        return
    rand_int = int(event.interaction.custom_id.removeprefix("add-rnd-list-"))
    fact_list = user_list_cache.get(rand_int)
    
    if not fact_list:
        # message from list command timed out
        ctx = get_context(event)
        await ctx.respond("Your list is too old. Please create a new one.")
        return 
    
    # resend message with list buttons
    ctx = get_context(event)
    name = None
    try:
        name = await _tag_add(ctx, name=None, value=", ".join(fact_list), tag_type=TagType.LIST)
    except BotResponseError as e:
        await ctx.respond(**e.context_kwargs)
    if not name:
        return
    
    components = PacmanButton.add(
        row = [
            MessageActionRowBuilder()
            .add_interactive_button(
                hikari.ButtonStyle.SECONDARY, 
                f"shuffle-{name};;3;;S",  # shuffle-<tag-name>;;<pacman-index>;;<color>
                emoji="🎲"
            )
        ],
        index = 3
    )
    await ctx.respond(
        f"Your list is now saved as tag: {name}  --- and you can shuffle now",
        components=components
    )

@loader.command
class DiceCommand(
    lightbulb.SlashCommand,
    name="dice",
    description="Roll a dice!",
    dm_enabled=False,
    default_member_permissions=None,
):
    eyes = lightbulb.integer("eyes", "How many eyes should the dice have? (1-6)", default=6)

    @lightbulb.invoke
    async def callback(self, _: lightbulb.Context, ctx: InuContext):
        await self._callback(ctx, self.eyes)
    
    @staticmethod
    async def _callback(ctx: InuContext, eyes: int):
        eyes = eyes
        if eyes < 1 or eyes > 6:
            await ctx.respond('I have dices with 1 to 6 sites. \
                \nI don\'t know, what kind of magic dices you have')
            return

        # creates discord formated dices 1 - eyes
        eye_ids = [
            f'{os.getcwd()}/inu/data/bot/dices/dice{n}.png' for n in range(1, eyes+1)
        ]
        all_eyes = [eye_ids[eye_num-1] for eye_num in range(1, eyes+1)]
        file_name = random.choice(all_eyes)

        def build_components(is_disabled: bool = False) -> List[MessageActionRowBuilder]:
            components = [
                MessageActionRowBuilder()
                .add_interactive_button(
                    hikari.ButtonStyle.SECONDARY, 
                    f"dice-roll-{eyes}", 
                    emoji="🎲",
                    is_disabled=is_disabled
                )
                .add_interactive_button(
                    hikari.ButtonStyle.SECONDARY,
                    f"dice-delete-{eyes}",
                    emoji="❌",
                    is_disabled=is_disabled
                )
            ]
            components = TimeButton.add(components)
            return components
        
        await ctx.respond(
            attachment=hikari.File(random.choice(all_eyes)),
            components=build_components(True)
        )
        await asyncio.sleep(3)
        await ctx.edit_last_response(
            components=build_components(False),
        )
        return

@loader.listener(hikari.InteractionCreateEvent)
async def on_dice_interaction(event: hikari.InteractionCreateEvent):
    if not isinstance(event.interaction, hikari.ComponentInteraction):
        return
    if not event.interaction.custom_id.startswith("dice-"):
        return
    eyes = event.interaction.custom_id.split("-")[-1]
    ctx = get_context(event)
    ctx.update = True
    if "dice-roll" in event.interaction.custom_id :
        await DiceCommand._callback(ctx, int(eyes))
    elif "dice-delete" in event.interaction.custom_id:
        await ctx.respond("Deleting...", update=True)
        await ctx.delete_initial_response()
    else:
        return

@loader.command
class CoinCommand(
    lightbulb.SlashCommand,
    name="coin",
    description="flips a coin",
    dm_enabled=False,
    default_member_permissions=None,
):
    @lightbulb.invoke
    async def callback(self, _: lightbulb.Context, ctx: InuContext):
        probability = [True for _ in range(0, 100)]
        probability.append(False)
        if random.choice(probability):
            coin = random.choice(["head", "tail"])
            await ctx.respond(
                attachment=hikari.File(
                    f'{os.getcwd()}/inu/data/bot/coins/{coin}.png'
                    ),
                content=coin
                )
            return
        await ctx.respond('Your coin stands! probability 1 in 100')
        return

@loader.command
class ProbabilityCommand(
    lightbulb.SlashCommand,
    name="probability",
    description="Rolles a dice with own probability. Dafault is 1/4 or 0.25",
    dm_enabled=False,
    default_member_permissions=None,
):
    number_1 = lightbulb.number("number_1", "The probability. Can be a single num like 0.75 which would mean 75%. Can also be used with a 2nd num")
    number_2 = lightbulb.integer("number_2", "needed if you choose to set propability with 2 numbers. like 3 4 wihch would mean 3 in 4 aka 75%", default=None)

    @lightbulb.invoke
    async def callback(self, _: lightbulb.Context, ctx: InuContext):
        def is_float_allowed(num):
            '''checks if number is to long'''
            if num is None:
                return True
            s_num = f"{num}"
            if "e" in s_num:
                return False
            if len(s_num) > 7:
                return False
            return True
        probability = self.number_1
        probability2 = self.number_2

        footer = ""
        # test if any number is too big -> avoid memoryError
        num1 = is_float_allowed(probability)
        num2 = is_float_allowed(probability2)
        if not (num1 and num2):
            # check failed - try to round the numbers and do the check again
            probability = round(probability, 4)
            if probability2:
                probability2 = round(probability2, 4)
            num1 = is_float_allowed(probability)
            num2 = is_float_allowed(probability2)
            if not (num1 and num2):
                await ctx.respond(
                    f'Your {"numbers are" if probability2 else "number is"} too big.'
                )
                return
            else:
                footer = "Your numbers are rounded because they were to small"
        # creating fraction
        if probability2:
            fraction = Fraction(f'{int(round(probability))}/{probability2}')
        else:
            fraction = Fraction(str(probability))
        d = fraction.denominator
        n = fraction.numerator
        prob_plus = [True for _ in range(n)]
        prob_minus = [False for _ in range(d - n)]
        probabilities = prob_plus + prob_minus
        symbol = random.choice([
            ('🟢', '🔴'), ('🔵', '🟠'), ('✅', '❌'),
            ('🎄', '🎃'), ('🔑', '🔒'), ('🏁', '🏳')
            ])

        # creating dc embed
        embed = hikari.Embed()
        embed.title = f'probability: {str(n)} in {str(d)}'
        embed.description = f'{symbol[0]} x {n}\n{symbol[1]} x {d - n}'
        embed.add_field(
            name='You got:', 
            value=f'{symbol[0] if random.choice(probabilities) else symbol[1]}'
        )
        embed.set_thumbnail(ctx.author.avatar_url)
        embed.color = hikari.Color(0x2A48A8)
        if footer:
            embed.set_footer(footer)
        await ctx.respond(embed=embed)
        return

@loader.command
class BoredCommand(
    lightbulb.SlashCommand,
    name="bored",
    description="get an idea, what you can do when you are bored",
    dm_enabled=False,
    default_member_permissions=None,
):
    @lightbulb.invoke
    async def callback(self, _: lightbulb.Context, ctx: InuContext):
        await ctx.respond(embed=(await BoredAPI.fetch_idea()).embed)


def randomize_colors(input_path):
    # Load the PNG image
    original_image = Image.open(input_path).convert("RGBA")
    
    # Get the image data as a list of RGBA tuples
    image_data = list(original_image.getdata())
    
    # Randomly change colors (excluding transparent pixels)
    amount = random.randint(0,255)
    modified_data = [
        (r, g, b, a) if a == 0 else (r + amount % 255, g + amount % 255, b + amount % 255, a)
        for r, g, b, a in image_data
    ]
    
    # Create a new image with the modified data
    modified_image = Image.new("RGBA", original_image.size)
    modified_image.putdata(modified_data)
    
    # Save the modified image to a buffer
    buffer = BytesIO()
    modified_image.save(buffer, format="PNG")
    buffer.seek(0)
    
    # Return the buffer containing the modified image
    return buffer


loader.command(random_group)