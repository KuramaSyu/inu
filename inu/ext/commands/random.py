
import random
from fractions import Fraction
import os
import traceback
import typing
from typing import *
import logging

import hikari
import lightbulb
from lightbulb.context import Context
from lightbulb import Bucket, commands
from lightbulb import errors
from lightbulb import events
from lightbulb.commands import OptionModifier as OM

from core import getLogger

log = getLogger(__name__)

plugin = lightbulb.Plugin("Random Commands", "Extends the commands with commands all about randomness")


@plugin.command
@lightbulb.command("random", "group for random stuff", aliases=["r", "rnd"])
@lightbulb.implements(commands.PrefixCommandGroup, commands.SlashCommandGroup)
async def rnd(ctx: Context):
    '''
    Sends a randomized list
    Parameters:
    facts: Your input list of things - things must be seperated with comma ","
    '''
    pass

@rnd.child
@lightbulb.option("list", 'the list I should shuffle\nNOTE: seperate with comma ","', modifier=OM.CONSUME_REST)
@lightbulb.command("list", "shuffles a given list", aliases=["l", "facts"])
@lightbulb.implements(commands.PrefixSubCommand, commands.SlashSubCommand)
async def list_(ctx: Context):
    # I know - this command is fucking redundant. But understand me, that I really don't want
    # to rewrite that
    fact_list: List[str] = ctx.options.list.split(",")
    if fact_list[-1] in ["", " "]:
        fact_list.pop(-1)
    fact_list = [fact.strip() for fact in fact_list]
    random.shuffle(fact_list)
    random.shuffle(fact_list)

    longest_fact = max([len(fact) for fact in fact_list])
    shortest_fact = min([len(fact) for fact in fact_list])
    fact_list = [f"{fact:^{longest_fact}}" for fact in fact_list]

    # def len_compensation(fact_list=fact_list, longest_fact: int = longest_fact):
    #     for fact_i, fact in enumerate(fact_list):
    #         if int(len(fact)) < int(longest_fact):
    #             fact_list[fact_i] = f'{fact_list[fact_i]:^{longest_fact}}'
    #     return fact_list

    # fact_list = len_compensation(fact_list=fact_list, longest_fact=longest_fact)
 
    #how many columns
    columns: int
    gr1 = float(1.5)
    gr2 = float(2.8)
    gr3 = float(3.7)
    gr4 = float(4.7)
    gr5 = float(5.7)
    log.debug(60 / longest_fact)
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
    
    await ctx.respond(facts_as_str)
    
    



@plugin.command
@lightbulb.add_cooldown(10, 8, lightbulb.UserBucket)
@lightbulb.option("eyes", "How many eyes should the dice have? (1-6)", type=int, default=6)
@lightbulb.command("dice", "Roll a dice!", aliases=["cube"])
@lightbulb.implements(commands.PrefixCommand, commands.SlashCommand)
async def dice(ctx: Context) -> None:
    '''
    Roll a dice!
    Parameters:
    [Optional] eyes: how many eyes the cube should have (1-9)
    '''
    eyes = ctx.options.eyes
    log.debug(type(eyes))
    log.debug(eyes)
    if eyes < 1 or eyes > 6:
        await ctx.respond('I have dices with 1 to 6 sites. \
            \nI don\'t know, what kind of magic dices you have')
        return

    # creates discord formated dices 1 - eyes
    eye_ids = [
        f'{os.getcwd()}/inu/data/bot/dices/dice{n}.png' for n in range(1, eyes+1)
    ]
    all_eyes = [eye_ids[eye_num-1] for eye_num in range(1, eyes+1)]
    await ctx.respond(
        ".",
        attachment=hikari.File(random.choice(all_eyes))
        )
    return

@plugin.command
@lightbulb.add_cooldown(1, 2.5, lightbulb.UserBucket) #type: ignore
@lightbulb.command("coin", "flips a coin")
@lightbulb.implements(commands.PrefixCommand, commands.SlashCommand)
async def coin(ctx: Context) -> None:
    '''
    Flips a Coin - two sides + can stand
    Parameter:
    /
    '''

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


@plugin.command
@lightbulb.add_cooldown(120, 10, lightbulb.UserBucket)
@lightbulb.option(
    "number_2", 
    "needed if you choose to set propability with 2 numbers. like 3 4 wihch would mean 3 in 4 aka 75%",
    default=None,
    type=int,
    )
@lightbulb.option(
    "number_1", 
    ("The probability. Can be a single num like 0.75 which would mean 75%. Can also be used with a 2nd num"),
    type=float
    )
@lightbulb.command(
    "probability", 
    "Rolles a dice with own probability. Dafault is 1/4 or 0.25",
    aliases=["prob"]
)
@lightbulb.implements(commands.PrefixCommand, commands.SlashCommand)
async def probability(ctx: Context) -> None:
    '''
    Rolles a dice with own probability
    Parameters:
    [Optional] probability = your probability - default: 0.25'''

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
    probability = ctx.options.number_1
    probability2 = ctx.options.number_2

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

def load(bot: lightbulb.BotApp):
    bot.add_plugin(plugin)
