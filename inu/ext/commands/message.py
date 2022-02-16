from __future__ import division
import asyncio
import traceback
import typing
from typing import (
    List,
    Dict,
    Any,
    Optional,
    Union
)
import time as tm
import random
import logging

import asyncpraw
import hikari
import lightbulb
from lightbulb.context import Context
from lightbulb import commands
import re
from pyparsing import (
    Literal,
    CaselessLiteral,
    Word,
    Combine,
    Group,
    Optional,
    ZeroOrMore,
    Forward,
    nums,
    alphas,
    oneOf,
)
import math
import operator

from core import getLogger
from utils import Human

log = getLogger(__name__)


plugin = lightbulb.Plugin("Reddit things", include_datastore=True)

@plugin.listener(hikari.MessageCreateEvent)
async def on_message_create(event: hikari.MessageCreateEvent):
    await on_message(event.message)
    
@plugin.listener(hikari.MessageUpdateEvent)
async def on_message_update(event: hikari.MessageUpdateEvent):
    await on_message(event.message)

async def on_message(message: hikari.PartialMessage):
    text = str(message.content).lower()
    if "artur ist dumm" in str(message.content).lower():
        return await artur_ist_dumm(message)
    elif "arthur ist dumm" in str(message.content).lower():
        return await message.respond("Artur wird ohne h geschrieben")
    elif text.startswith("="):
        return await calc(message)

async def artur_ist_dumm(message: hikari.PartialMessage):
    with open("inu//data/other/users/ar_is_stupid.txt", "r", encoding="utf-8") as file_:
        txt = file_.read()
        await message.respond(f"Ich weiß\n{txt}")

async def calc(message: hikari.PartialMessage):
    text = str(message.content)
    try:
        text = (
            text
            .lower()
            .replace("x", "*")
            .replace(" ", "")
            .replace(":", "/")
            .replace("=", "")
            .replace(",", ".")
        )
        calculator = NumericStringParser()
        result = Human.number(str(calculator.eval(text)))
        result = result[:-2] if result.endswith(".0") and not "," in result else result
        await message.respond(
            hikari.Embed(title=result)
        )
    except:
        return
        

def load(bot: lightbulb.BotApp):
    bot.add_plugin(plugin)
    
    
class NumericStringParser(object):
    '''
    Most of this code comes from the fourFn.py pyparsing example

    '''

    def pushFirst(self, strg, loc, toks):
        self.exprStack.append(toks[0])

    def pushUMinus(self, strg, loc, toks):
        if toks and toks[0] == '-':
            self.exprStack.append('unary -')

    def __init__(self):
        """
        expop   :: '^'
        multop  :: '*' | '/'
        addop   :: '+' | '-'
        integer :: ['+' | '-'] '0'..'9'+
        atom    :: PI | E | real | fn '(' expr ')' | '(' expr ')'
        factor  :: atom [ expop factor ]*
        term    :: factor [ multop factor ]*
        expr    :: term [ addop term ]*
        """
        point = Literal(".")
        e = CaselessLiteral("E")
        fnumber = Combine(Word("+-" + nums, nums) +
                          Optional(point + Optional(Word(nums))) +
                          Optional(e + Word("+-" + nums, nums)))
        ident = Word(alphas, alphas + nums + "_$")
        plus = Literal("+")
        minus = Literal("-")
        mult = Literal("*")
        div = Literal("/")
        lpar = Literal("(").suppress()
        rpar = Literal(")").suppress()
        addop = plus | minus
        multop = mult | div
        expop = Literal("^")
        pi = CaselessLiteral("PI")
        expr = Forward()
        atom = ((Optional(oneOf("- +")) +
                 (ident + lpar + expr + rpar | pi | e | fnumber).setParseAction(self.pushFirst))
                | Optional(oneOf("- +")) + Group(lpar + expr + rpar)
                ).setParseAction(self.pushUMinus)
        # by defining exponentiation as "atom [ ^ factor ]..." instead of
        # "atom [ ^ atom ]...", we get right-to-left exponents, instead of left-to-right
        # that is, 2^3^2 = 2^(3^2), not (2^3)^2.
        factor = Forward()
        factor << atom + \
            ZeroOrMore((expop + factor).setParseAction(self.pushFirst))
        term = factor + \
            ZeroOrMore((multop + factor).setParseAction(self.pushFirst))
        expr << term + \
            ZeroOrMore((addop + term).setParseAction(self.pushFirst))
        # addop_term = ( addop + term ).setParseAction( self.pushFirst )
        # general_term = term + ZeroOrMore( addop_term ) | OneOrMore( addop_term)
        # expr <<  general_term
        self.bnf = expr
        # map operator symbols to corresponding arithmetic operations
        epsilon = 1e-12
        self.opn = {"+": operator.add,
                    "-": operator.sub,
                    "*": operator.mul,
                    "x": operator.mul,
                    "/": operator.truediv,
                    "^": operator.pow}
        self.fn = {"sin": math.sin,
                   "cos": math.cos,
                   "tan": math.tan,
                   "exp": math.exp,
                   #"log": math.log,
                   "abs": abs,
                   "trunc": lambda a: int(a),
                   "round": round,
                   "sgn": lambda a: abs(a) > epsilon and cmp(a, 0) or 0}

    def evaluateStack(self, s):
        op = s.pop()
        if op == 'unary -':
            return -self.evaluateStack(s)
        if op in "+-*/^x=":
            op2 = self.evaluateStack(s)
            op1 = self.evaluateStack(s)
            return self.opn[op](op1, op2)
        elif op == "PI":
            return math.pi  # 3.1415926535
        elif op == "E":
            return math.e  # 2.718281828
        elif op in self.fn:
            return self.fn[op](self.evaluateStack(s))
        elif op[0].isalpha():
            return 0
        else:
            return float(op)

    def eval(self, num_string, parseAll=True):
        self.exprStack = []
        results = self.bnf.parseString(num_string, parseAll)
        val = self.evaluateStack(self.exprStack[:])
        return val