import os
from typing import Union, Dict, Any, List, Tuple
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
    ParseException,
    OneOrMore,
    FollowedBy,
    QuotedString,
    alphanums,
    NotAny
)
import math
import operator
import matplotlib
from pprint import pformat
import traceback
from abc import ABC, abstractmethod
# switch to pgf backend


import matplotlib.pyplot as plt
from io import BytesIO
import re
from PIL import Image
from pprint import pprint
import logging



PERIOD_START = " "

# update latex preamble
def swtich_backend():
    """
    Switches the backend of matplotlib to 'pgf' and updates the rcParams for LaTeX rendering.

    This function sets the necessary rcParams for using LaTeX with matplotlib's 'pgf' backend.
    It configures the LaTeX system, font, array stretch, and includes the eurosym package.

    Note: This function assumes that matplotlib and plt have been imported.

    Example usage:
    >>> swtich_backend()

    """
    plt.switch_backend('pgf')
    matplotlib.use('pgf')
    plt.rcParams.update({
        "text.usetex": True,
        "pgf.rcfonts": False,
        "pgf.texsystem": 'pdflatex', # default is xetex
        "pgf.preamble": "\n".join([
            r"\usepackage{amsmath}",
            r"\usepackage[T1]{fontenc}",
            r"\usepackage{mathpazo}",
            r"\renewcommand\arraystretch{1.4}",
            r"\usepackage[official]{eurosym}"
            ])
    })


class Element:
    def __init__(
        self, 
        element: str, 
        type_: str,
        negate: bool = False,
        unit: str | None = None,
        number: str | None = None,
        number_args: int | None = None,
    ):
        """
        Represents an element in LaTeX.

        Args:
            element (str): The element string.
            type_ (str): The type of the element.
            negate (bool, optional): Whether the element is negated. Defaults to False.
            unit (str | None, optional): The unit of the element. Defaults to None.
            number (str | None, optional): The number of the element. Defaults to None.
            number_args (int | None, optional): The number of arguments for the element. Defaults to None.
        """
        self.element = element
        self._type = type_
        self.negate = negate
        self.unit = unit
        self.number = number
        self.number_args = number_args
        self.children: List["Element"] = []
        self.parent: "Element" | None = None

    def add_child(self, child: "Element") -> None:
        """Adds one child element of type `Element`"""
        self.add_children([child])

    def add_children(self, children: List["Element"]) -> None:
        """Adds multiple children of type `Element`"""

        def set_parent(child: "Element") -> None:
            """Sets recursively parents"""
            if isinstance(child, Element):
                child.parent = self
            elif isinstance(child, list):
                for ch in child:
                    set_parent(ch)

        for child in children:
            set_parent(child)
        self.children.extend(children)
        logging.debug(f"children:{str(self)}: {[str(ch) for ch in children]}")

    @property
    def type(self) -> str:
        """
        Get the type of the element.

        Returns:
            str: The type of the element.
        """
        return self._type
    
    @property
    def is_negated(self) -> bool:
        """
        Check whether or not the element is negated.

        Returns:
            bool: True if the element is negated, False otherwise.
        """
        return self.negate
    
    @abstractmethod
    def to_latex(self) -> str:
        """
        Get the LaTeX representation of the element.

        Returns:
            str: The LaTeX representation of the element.
        """
        pass

    @staticmethod
    def unpack_array(op: "Element") -> "Element":
        """
        Remove the array from the given element if the array is not negated.

        Args:
            op (Element): The element to unpack.

        Returns:
            Element: The unpacked element.
        """
        if op.type == "array" and not op.is_negated:
            return op.children[0]
        return op
    
    def __repr__(self) -> str:
        return f"type: {self.type}, element: {self.element}"

    
class Unit(Element):
    """
    Represents a unit like `meter` or `megabyte`
    """
    def prepare_unit(self, unit: str) -> str:
        old_to_new = {
            " ": "\\ ",
            "μ": "\\mu ",
            "_": "\\_",
            "EUR": "\\text{€}",
            "celsius": "^\\circ C",
        }
        for old, new in old_to_new.items():
            unit = unit.replace(old, new)
        return unit
    
    def to_latex(self) -> str:
        return self.prepare_unit(self.element)
    

class Number(Element):
    """
    Represents a number like `8`, `56.55`, `234.3333...`, `pi`, `e`, `2E10`
    and so on
    """
    def prepare_number(self, number: str) -> str:
        if "E" in number:
            # replace E x with *10^{x}
            number, exponent = number.split("E")
            number = f"{number}\\cdot10^{{{exponent}}}"
        if "…" in number:
            # replace … with \overline
            if PERIOD_START in number:
                # decimal partially periodic
                num, period = number.split(PERIOD_START)
                period, after_period = period.split("…")
                number = f"{num}\\overline{{{period}}}{after_period}"
            else: 
                # decimal fully periodic
                num, period = number.split(".")
                period, after_period = period.split("…")
                number = f"{num}.\\overline{{{period}}}{after_period}"
        return number
    
    def to_latex(self) -> str:
        if self.element == "PI":
            return "\\pi"
        if self.element == "E":
            return "e"
        return self.prepare_number(self.element)
    

class Vector(Element):
    """
    Represents Vektors like `[1  2  3] or [1  2]`. The inner part can be any type of 
    expression
    """
    def to_latex(self) -> str:
        cols = int(self.element.split("x")[1])
        content = '\\\\'.join(ch.to_latex() for ch in self.children)
        return f"\\begin{{pmatrix}} {content} \\end{{pmatrix}}"
    

class Matrix(Element):
    """
    Represents Matrices like `[[1  2]; [3  4]]` or `[[1  sqrt(4)]; [sqrt(9)  6-2]]`
    """
    def to_latex(self) -> str:
        cols = int(self.element.split("x")[0])
        rows = int(self.element.split("x")[1])
        matrix_content = ""
        for i, col in enumerate(self.children):
            if i != 0:
                matrix_content += " \\\\"
            matrix_content += " & ".join(ch.to_latex() for ch in col)

        return f"\\begin{{pmatrix}} {matrix_content} \\end{{pmatrix}}"
    

class Equation(Element):
    """
    Represents any type of calculation with `=` or `≈` in between
    """
    op_to_latex = {
        "=": "=",
        "≈": "\\approx",
    }
    def to_latex(self) -> str:
        op1, op2 = self.children
        return f"{op1.to_latex()} {self.op_to_latex[self.element]} {op2.to_latex()}"


class Array(Element):
    """
    Represents parantheseses arround an expression like `(3+4)` or
    `-(sqrt(9) - 1)`
    """
    @property
    def type(self) -> str:
        if self.ignore_self:
            return self.children[0].type
        return self._type
    
    @property
    def ignore_self(self) -> bool: 
        """wether or not this parantheses are not mathematically relevant"""
        if self.is_negated or not self.children:
            # relevant: negated parantheses e.g. -(3+4)
            return False
        if type(self.parent) == Equation:
            # upper is equation
            return True
        child_type = self.children[0].type
        if child_type in ['array']:
            # array in array
            return True
        if child_type in  ['mulop', "implicit_mulop"] and not (self.parent and self.parent.type == "exp"):
            # multiplication in parantheses
            return True
        elif child_type in ['fraction'] and not (self.parent and self.parent.type == "exp"):
            # fraction in parantheses
            return True
        elif child_type in ['number', 'exp'] and not self.children[0].is_negated:
            # number or exp in parantheses
            return True
        return False
    
    def to_latex(self) -> str:
        negated = self.negate
        prefix = "- " if negated else ""
        expr = self.children[0]
        if self.ignore_self:
            return expr.to_latex()
        return f"{prefix}\\left( {expr.to_latex()} \\right)"


class Fraction(Element):
    """
    Represents a div operation `expr / expr` where `expr` are the children.
    Every div operation is displayed as fraction
    """
    def to_latex(self) -> str:
        op1, op2 = self.children
        return f"\\frac{{{op1.to_latex()}}}{{{op2.to_latex()}}}"


class AddOp(Element):
    """
    Represents an add operation `expr [+-] expr` where `expr` are the children.
    """
    op_to_latex = {
        "+": "+",
        "-": "-",
        "±": "\\pm",
    }
    def to_latex(self) -> str:
        op1, op2 = self.children
        return f"{op1.to_latex()} {self.op_to_latex[self.element]} {op2.to_latex()}"


class MulOp(Element):
    """
    Represents multiplication operations `expr [*] expr` without div since it's handled on its own
    """
    op_to_latex = {
        "*": "\\cdot",
        "×": "\\cdot",
        "·": "\\cdot",
        "/": "\\div",
    }
    def to_latex(self) -> str:
        op1, op2 = self.children
        if op1.type in ["number", "exp"] and op2.type == "unit":
            return f"{op1.to_latex()}\\ {op2.to_latex()}"
        return f"{op1.to_latex()} {self.op_to_latex[self.element]} {op2.to_latex()}"


class Exp(Element):
    """
    Represents an exp expression `factor^factor` where both factors are the children
    """
    def to_latex(self) -> str:
        op1, op2 = self.children
        return f"{op1.to_latex()}^{{{op2.to_latex()}}}"

class Placeholder(Element):
    """
    Represents an exp expression `factor^factor` where both factors are the children
    """
    def to_latex(self) -> str:
        return ""
    
class Function(Element):
    """
    Represents any type of fuction with it's arguments as children
    """
    def get_latex_fn(self, fn_name: str, number_args) -> str:
        if fn_name == "sin":
            return "\\sin({0})"
        elif fn_name == "cos":
            return "\\cos({0})"
        elif fn_name == "tan":
            return "\\tan({0})"
        elif fn_name == "e":
            return "\\exp({0})"
        elif fn_name == "log":
            return "\\log_{{{0}}}{1}"
        elif fn_name == "ln":
            return "\\ln({0})"
        elif fn_name == "sqrt":
            return "\\sqrt{{{0}}}"
        elif fn_name == "root":
            return "\\sqrt[{0}]{{{1}}}"
        elif fn_name == "abs":
            return "\\left| {0} \\right|"
        elif fn_name == "trunc":
            return "\\text{{trunc}}({0})"
        elif fn_name == "round":
            return "\\text{{round}}\\left( {0} \\right)"
        elif fn_name == "sgn":
            return "\\text{{sgn}}{0}"
        elif fn_name == "sum":
            return "\\sum_{{i={1}}}^{{{0}}} x_i={2}"
        elif fn_name == "product":
            return "\\prod_{{i={1}}}^{{{0}}} x_i={2}"
        elif fn_name == "integrate":
            return "\\int_{{{1}}}^{{{0}}} {2} \\,\\ dx"
        elif fn_name == "cross":
            return "{1} \\times {0}"
        elif fn_name == "dot":
            return "{1} \\cdot {0}"
        elif fn_name in ["hadamard", "multiply"]:
            return "{1} \\circ {0}"
        elif fn_name == "binomial":
            return "\\binom{{{1}}}{{{0}}}"
        elif fn_name == "adj":
            return "\\text{{adj}}{0}"
        elif fn_name == "inv":
            return "{0}^{{-1}}"
        elif fn_name == "det":
            return "\\text{{det}}{0}"
        elif fn_name in ["arcsin", "arccos", "arctan"]:
            return "\\texttt{{" + fn_name[3:] + "}}^{{-1}}\\left(" + "{0}\\right)"
        else:
            return (
                "\\texttt{{" + fn_name + "}}" +
                "\\Bigl( " +
                ', '.join(reversed(['{'+str(i)+'}' for i in range(number_args)])) +
                " \\Bigr)"
            )

    def to_latex(self) -> str:
        number_args = self.number_args
        format_values = [child.to_latex() for child in self.children]
        prefix = "- " if self.is_negated else ""
        return f"{prefix}{self.get_latex_fn(self.element, number_args).format(*format_values)}"
    
# \text{solve} \left( \left( -11 \cdot \left( 8 + 11  x \right) + 1 \cdot \left( -2 - x \right) 
# + 5 \cdot \left( -11 - 5  x \right) \right) \right)

# \text{solve} \left( \left( -11 \cdot \left( 8 + 11  x \right) + 1 \cdot \left( -2 - x \right) 
# + 5 \cdot \left( -11 - 5  x \right) \right)

class NumericStringParser(object):
    '''
    Most of this code comes from the fourFn.py pyparsing example

    '''

    def pushFirst(self, strg, loc, toks):
        logging.debug(f"pushFirst: {''.join(toks)}; all: {toks}")
        #number = self.prepare_number(toks[0])
        
        self.exprStack.append(
            Number(''.join(toks), "number")
        )

    def prepare_number(self, number: str) -> str:
        if "E" in number:
            # replace E x with *10^{x}
            number, exponent = number.split("E")
            number = f"{number}\\cdot10^{{{exponent}}}"
        if "…" in number:
            # replace … with \overline
            if PERIOD_START in number:
                # decimal partially periodic
                num, period = number.split(PERIOD_START)
                period, after_period = period.split("…")
                number = f"{num}\\overline{{{period}}}{after_period}"
            else: 
                # decimal fully periodic
                num, period = number.split(".")
                period, after_period = period.split("…")
                number = f"{num}.\\overline{{{period}}}{after_period}"
        return number
    
    def prepare_unit(self, unit: str) -> str:
        old_to_new = {
            " ": "\\ ",
            "μ": "\\mu ",
            "_": "\\_",
            "€": "EUR",

        }
        for old, new in old_to_new.items():
            unit = unit.replace(old, new)
        return unit
    
    def pushUnitFirst(self, strg, loc, toks):
        logging.debug(f"pushUnitFirst: {toks[0]}; all: {toks}")
        unit = self.prepare_unit(toks[0])
        self.exprStack.append(
            Unit(toks[0], "unit")
        )

    def pushArray(self, strg, loc, toks):
        logging.debug(f"Array: all: {toks}")
        negate = False
        if toks and toks[0] == '-':
            negate = True
        self.exprStack.append(
            Array("array", "array", negate=negate)
        )

    def pushFunction(self, strg, loc, toks):
        logging.debug(f"Function: {toks[0]}; all: {toks}")
        negate = False
        if toks and toks[0] == '-':
            negate = True
            toks = toks[1:]
        self.exprStack.append(
            Function(
                element=toks[0], 
                type_="function", 
                negate=negate, 
                number_args=self.fn.get(toks[0], None) or len(toks)-1
            )
        )
    
    def pushVector(self, strg, loc, toks):
        logging.debug(f"Vector 0x{len(toks[0])}: {toks}")
        self.exprStack.append(
            Vector(
                element=f"0x{len(toks[0])}",
                type_="vector"
            )
        )

    def pushMatrix(self, strg, loc, toks):
        logging.debug(f"Matrix {len(toks)}x{len(toks[0])}: {toks}")
        self.exprStack.append(
            Matrix(
                element=f"{len(toks)}x{len(toks[0])}",
                type_="matrix"
            )
        )
    
    def pushFactorFirst(self, strg, loc, toks):
        logging.debug(f"pushFactorFirst: {toks[0]}; all: {toks}")
        self.exprStack.append(
            Exp(toks[0], "exp")
        )

    def pushTermFirst(self, strg, loc, toks):
        logging.debug(f"pushTermFirst: {toks[0]}; all: {toks}")
        self.exprStack.append(
            MulOp(toks[0], "mulop")
        )

    def pushExprFirst(self, strg, loc, toks):
        logging.debug(f"pushExprFirst: {toks[0]}; all: {toks}")
        self.exprStack.append(
            AddOp(toks[0], "addop")
        )

    def pushImplicitMult(self, strg, loc, toks):
        logging.debug(f"pushImplicitMult: *; all: {toks}")
        self.exprStack.append(
            MulOp("*", "implicit_mulop")
        )

    def pushEquationFirst(self, strg, loc, toks):
        logging.debug(f"pushEquationFirst: {toks[0]}; all: {toks}")
        self.exprStack.append(
            Equation(toks[0], "equation")
        )

    def __init__(self):
        """
        expop   :: '^'
        multop  :: '*' | '/'
        addop   :: '+' | '-'
        integer :: ['+' | '-'] '0'..'9'+ ' '? '…'? 'x'?
        sep     :: [',' | ';']
        x       :: 'x' | integer + x
        atom    :: PI | E | real | x | fn '(' expr [sep expr]* ')' | '(' expr ')' | unit
        factor  :: atom [ expop factor ]*
        term    :: factor [ multop factor ]*
        expr    :: term [ addop term ]*
        equation:: expr ['=' expr]*
        """
        point = Literal(".")
        e = CaselessLiteral("E")
        x = Literal("x")
        i = Literal("i")
        space = Literal(" ")
        string_start = Literal('"')

        string = QuotedString('"', esc_char='""', unquote_results=True)
        binary_number_part = Combine(ZeroOrMore(Literal("b")) + Word("01"))
        binary_number = Combine(Optional(oneOf("+ -")) + binary_number_part + ZeroOrMore(Combine(space, binary_number_part)))
        
        plus = Literal("+") 
        minus = Literal("-")
        plusminus = Literal("±")
        mult = Literal("*") | Literal("×")
        div = Literal("/")

        fnumber = Combine(
            Optional(oneOf("+ -")) +
            Word(nums) +
            Optional(point + Optional(Word(nums))) +
            Optional(Combine(Word(PERIOD_START) + Word(nums, nums))) + # 0.1 666… -> support the period start sign
            Optional(Word("…")) +
            Optional(e + Word("+-" + nums, nums)) + 
            Optional(i)
        )
        

        

        lpar = Literal("(").suppress()
        rpar = Literal(")").suppress()
        lbrack = Literal("[").suppress()
        rbrack = Literal("]").suppress()
        semicolon = Literal(";").suppress()
        sep = Literal(",").suppress() | semicolon
        
        addop = plus | minus | plusminus
        multop = mult | div
        expop = Literal("^")
        pi = CaselessLiteral("PI")
        equals = Literal("=") | Literal("≈")

        expr = Forward()
        equation = Forward()

        ident = Word(alphas, alphas + "_$")
        unit = Word(alphas + "μ_€") + NotAny(lpar)
        xnumber = Combine(fnumber + Optional(Optional(space) + mult.suppress() + Optional(space)) + x) + NotAny(unit)  
        

        vec_row = Group(Combine(equation) + OneOrMore(Literal(",").suppress() + Combine(equation)))
        vec = lbrack + vec_row + rbrack 
        matrix = (
            (lbrack + vec_row + OneOrMore(semicolon + vec_row) + rbrack)
            ^ (lbrack + vec + OneOrMore(semicolon + vec) + rbrack)
        )
        parameter = Combine(equation) + ZeroOrMore(sep + Combine(equation))

        array = (Optional(oneOf("- +")) + ZeroOrMore(Literal(" ")) + Group(lpar + expr + rpar)).setParseAction(self.pushArray)
        function = (Optional(oneOf("- +")) + ZeroOrMore(space) + ident + lpar + parameter + rpar).setParseAction(self.pushFunction)
        
        unit.setParseAction(self.pushUnitFirst)
        # unit_chain = Combine(unit + ZeroOrMore(Optional(Literal(" ")) + unit))
        atom = (
              (function)
            #| (Optional(oneOf("-+")) + unit_number).setParseAction(self.pushUnitNumberFirst)
            | (Optional(oneOf("- +")) + ( pi | e | xnumber | fnumber | binary_number | x)).setParseAction(self.pushFirst)
            | (Optional(oneOf("-+")) + (unit))
            | (array)
            | (string).setParseAction(self.pushFirst)
            | (
                (Optional(oneOf("-+")) + matrix).setParseAction(self.pushMatrix)
                ^ (Optional(oneOf("-+")) + vec).setParseAction(self.pushVector)
            )  
        )
        # by defining exponentiation as "atom [ ^ factor ]..." instead of
        # "atom [ ^ atom ]...", we get right-to-left exponents, instead of left-to-right
        # that is, 2^3^2 = 2^(3^2), not (2^3)^2.
        factor = Forward()
        factor << atom + (
            ZeroOrMore(
                (expop + factor).setParseAction(self.pushFactorFirst)
                | (Optional(space) + (unit)).setParseAction(self.pushImplicitMult)
        ))
            #| ZeroOrMore(Optional(space) + unit).setParseAction(self.pushImplicitMult)
        
        term = factor + \
            ZeroOrMore((multop + factor).setParseAction(self.pushTermFirst))
 
        expr << term + \
            ZeroOrMore(
                (addop + term).setParseAction(self.pushExprFirst)
                | (Optional(space) + term).setParseAction(self.pushImplicitMult)
            )
            
        equation << expr + \
            ZeroOrMore((equals + expr).setParseAction(self.pushEquationFirst)) + \
            Optional(equals)
        # addop_term = ( addop + term ).setParseAction( self.pushFirst )
        # general_term = term + ZeroOrMore( addop_term ) | OneOrMore( addop_term)
        # expr <<  general_term
        self.bnf = equation
        # map operator symbols to corresponding arithmetic operations
        epsilon = 1e-12
        self.opn = {"+": operator.add,
            "-": operator.sub,
            "*": operator.mul,
            "×": operator.mul,
            "/": operator.truediv,
            "^": operator.pow,
            "±": None,
        }
        # map function names to amount of parameters
        self.fn = {"sin": 1,
            "cos": 1,
            "tan": 1,
            "exp": 1,
            "log": 2,
            "ln": 1,
            "abs": 1,
            "trunc": 1,
            "round": 1,
            "sgn": 1,
            "sqrt": 1,
            "√": 1,
            "sum": 3,
            "integrate": 3,
            "product": 3,
            "cross": 2,
            "dot": 2,
            "hadamard": 2,
            "multiply": 2,
            "binomial": 2,
            "adj": 1,
            "inv": 1,
            "det": 1,
            "root": 2,
        }
        
        self.op_to_latex = {
            "+": "+",
            "-": "-",
            "*": "\\cdot",
            "/": "\\div",
            "^": "^",
            "×": "\\cdot",
            "·": "\\cdot",
            "=": "=",
            "≈": "\\approx",
            "±": "\\pm",
        }

        self.needs_latex = False

    def evaluateStack(self, s: List[Element]) -> str:
        """
        converts the stack to latex
        """
        try:
            element = s.pop()
        except IndexError:
            return None
        op = element.element
        if element.type == "vector":
            self.needs_latex = True
            cols = int(op.split("x")[1])
            expressions = [self.evaluateStack(s) for _ in range(cols)]
            expressions.reverse()
            element.add_children(expressions)
            return element
        
        if element.type == "matrix":
            self.needs_latex = True
            cols = int(op.split("x")[0])
            rows = int(op.split("x")[1])
            expressions = []
            for _ in range(cols):
                expressions.append([])
                for _ in range(rows):
                    expressions[-1].append(self.evaluateStack(s))
                expressions[-1].reverse()
            expressions.reverse()

            element.add_children(expressions)
            return element
        
        if op in "=≈":
            op2 = self.evaluateStack(s)
            op1 = self.evaluateStack(s)
            element.add_children([op1, op2])
            return element
        
        if op == 'array':
            expr = self.evaluateStack(s)
            element.add_child(expr)
            return element
        
        if op in "/":
            self.needs_latex = True
            op2 = self.evaluateStack(s)
            op1 = self.evaluateStack(s)
            new = Fraction("/", "fraction")
            new.add_children([op1, op2])
            return new
        
        if op in "+-*×·=±":
            op_name = {
                "+": AddOp,
                "-": AddOp,
                "*": MulOp,
                "×": MulOp,
                "·": MulOp,
                "/": MulOp,
                "±": AddOp,
            }
            self.needs_latex = True
            op2 = self.evaluateStack(s)
            op1 = None
            try:
                op1 = self.evaluateStack(s)
            except IndexError:
                op1 = Placeholder("", "placeholder")
            
            element.add_children([op1, op2])
            return element

        
        if op in "^":
            self.needs_latex = True
            op2 = self.evaluateStack(s)
            op1 = self.evaluateStack(s)
            element.add_children([op1, op2])
            return element
        
        elif op == "PI":
            self.needs_latex = True
            return element
        
        elif op == "E":
            self.needs_latex = True
            return element
        
        elif element.type == "function":
            if element.element not in ["planet", "element"]:
                self.needs_latex = True
            number_args = element.number_args
            children = [self.evaluateStack(s) for _ in range(number_args)]
            element.add_children(children)
            return element

        else:
            return element

    def eval(self, num_string, parseAll=True) -> str:
        """
        Evaluates a mathematical expression given as a string and returns the result in LaTeX format.

        Args:
            num_string (str): The mathematical expression to evaluate.
            parseAll (bool, optional): Whether to parse the entire input string. Defaults to True.

        Returns:
            str: The result of the evaluation in LaTeX format.
        """
        self.exprStack: List[Element] = []
        results = self.bnf.parseString(num_string, parseAll)
        logging.debug("results")
        # results.pprint()
        logging.debug("exprStack")
        logging.debug(pformat(self.exprStack))
        val = self.evaluateStack(self.exprStack[:])
        logging.debug(f"{val}")
        # pprint(val)
        return val.to_latex()
    

def latex2image(
    latex_expression: str, image_size_in=(3, 2), fontsize=16, dpi=100, multiline=True
) -> BytesIO:
    """
    A simple function to generate an image from a LaTeX language string.

    Parameters
    ----------
    latex_expression : str
        Equation in LaTeX markup language.
    image_name : str or path-like
        Full path or filename including filetype.
        Accepeted filetypes include: png, pdf, ps, eps and svg.
    image_size_in : tuple of float, optional
        Image size. Tuple which elements, in inches, are: (width_in, vertical_in).
    fontsize : float or str, optional
        Font size, that can be expressed as float or
        {'xx-small', 'x-small', 'small', 'medium', 'large', 'x-large', 'xx-large'}.

    Returns
    -------
    fig : object
        Matplotlib figure object from the class: matplotlib.figure.Figure.

    """
    def check_if_split_allowed(lines: List[str]) -> bool:
        """
        Counts if on every line `\right` and `\left` are balanced for each substring.
        If any substring has unbalanced brackets, the split is not allowed.
        """
        for line in lines:
            if (
                line.count("\\left(") != line.count("\\right)")
                or line.count("gl(") != line.count("gr)") # for Big/big/bigg/Bigg commands
            ):
                return False
        return True

    # over multiple lines
    lines = []
    includes_matrix = "pmatrix" in latex_expression
    max_len = 50 if not includes_matrix else 300
    length = len(latex_expression.splitlines())
    for line in latex_expression.splitlines():
        if (
            re.match(r"^x [=≈]", line) 
            or len(line) < max_len 
            or length > 1 or not multiline
        ):
            # don't alter line
            lines.append(f"{line}")
            continue
        line_ = line.replace(" = ", "\n= ").replace(r"\approx", "\n \\approx")
        if not check_if_split_allowed(line_.splitlines()):
            # brackets would not be balanced
            lines.append(f"{line}")
            continue

        line = line_
        len_ = 0
        for i, l in enumerate(line.splitlines()):
            if len_ + len(l) < max_len and len(lines) > 0:
                lines[-1] = f"{lines[-1]}{l}"
                len_ += len(l)
            else:
                lines.append(f"{l}")
                len_ = len(l)
    lines = [f"${line}$" for line in lines]
    result = "\n".join(lines)


    swtich_backend()
    try:
        fig = plt.figure(figsize=image_size_in, dpi=dpi)
        fig.patch.set_alpha(0)
        text = fig.text(
            x=0.5,
            y=0.5,
            s=result,
            horizontalalignment="left",
            verticalalignment="center",
            fontsize=fontsize,
            color='white',  # Set text color to white
            linespacing=1.1 if includes_matrix else 1.7,
        )
        # Adjust image size based on the length of latex expression
        bbox = fig.get_window_extent().transformed(fig.dpi_scale_trans.inverted())
        width, height = bbox.width, bbox.height
        image_size_in = (width, height)
        
        fig.set_size_inches(image_size_in)
        buffer = BytesIO()
        plt.savefig(buffer, format='png', bbox_inches='tight', pad_inches=0.0)
        buffer.seek(0)

        return buffer
    except Exception as e:
        logging.error(f"LaTeX: {result}\nError:{traceback.format_exc()}")
        return None

from io import BytesIO

def evaluation2image(evaluation: str, multiline: bool = False) -> BytesIO:
    """
    Converts a mathematical evaluation string into an image using LaTeX.

    Args:
        evaluation (str): The mathematical evaluation string.
        multiline (bool, optional): Specifies whether the evaluation string contains multiple lines. 
            Defaults to False.

    Returns:
        BytesIO: The image representation of the evaluation in LaTeX format.
    """
    evaluations = [ev for ev in evaluation.splitlines()] if len(evaluation.splitlines()) > 1 else [evaluation]
    parser = NumericStringParser()
    evaluations = [parser.eval(ev) for ev in evaluations]
    if not parser.needs_latex:
        logging.debug("No latex needed")
        return None
    latex = "\n".join(evaluations)
    image = latex2image(latex, multiline=multiline)
    return image

def prepare_for_latex(result: str) -> str:
    """prepares the result for latex by removing unicode characters like √ or π"""
    result = result.replace("'", "") # remove number things for better readability
    if len(result.splitlines()) > 1 and "warning" in result[0]:
        result = result.split("\n")[-1] # remove warnings

    old_to_new = {
        "¹": "^1",
        "²": "^2",
        "³": "^3",
        "⁴": "^4",
        "⁵": "^5",
        "⁶": "^6",
        "⁷": "^7",
        "⁸": "^8",
        "⁹": "^9",
        "⁰": "^0",
        "−": "-",
        "√": "sqrt",
        "π": "pi",
        "×": "*",
        "÷": "/",
        ":": "/",
        "·": "*",
        "  ": ", ",
        "°C": "celsius",
        "€": "EUR"
    }
    for old, new in old_to_new.items():
        result = result.replace(old, new)
    return result


test_calculations = {
    "vectors": (
        "cross([1  2  3], [1  2  sqrt(9)]) = [0  0  0]", 
        r"\begin{pmatrix} 1\\2\\3 \end{pmatrix} \times \begin{pmatrix} 1\\2\\\sqrt{9} \end{pmatrix} = \begin{pmatrix} 0\\0\\0 \end{pmatrix}"
    ),
    "matrix": (
        "[1  2  3; 4  5  sqrt(4)*3; 7  8  9] + [1  2  3; sqrt(16)  5  6; 7  8  9] = [2  4  6; 8  10  12; 14  16  18]",
        r"\begin{pmatrix} 1 & 2 & 3 \\4 & 5 & \sqrt{4} \cdot 3 \\7 & 8 & 9 \end{pmatrix} + \begin{pmatrix} 1 & 2 & 3 \\\sqrt{16} & 5 & 6 \\7 & 8 & 9 \end{pmatrix} = \begin{pmatrix} 2 & 4 & 6 \\8 & 10 & 12 \\14 & 16 & 18 \end{pmatrix}"
    ),
    "matrix + function chained": (
        "adj([[1  2  sqrt(3)]; [(2 × (10^−3))  integrate(3 × x, 0, 5)  6]; [dot([1  3], [2  4])  det([1  2  3; 4  5  6; 7  8  10])  3]]) ≈ [355.5000000  −23.19615242  −52.95190528; 83.98200000  −15.24871131  −5.996535898; −525.0060000  31.00000000  37.49600000]",
        r"\text{adj}\begin{pmatrix} 1 & 2 & \sqrt{3} \\2 \cdot 10^{-3} & \int_{0}^{5} 3  x \,\ dx & 6 \\\begin{pmatrix} 1\\3 \end{pmatrix} \cdot \begin{pmatrix} 2\\4 \end{pmatrix} & \text{det}\begin{pmatrix} 1 & 2 & 3 \\4 & 5 & 6 \\7 & 8 & 10 \end{pmatrix} & 3 \end{pmatrix} \approx \begin{pmatrix} 355.5000000 & -23.19615242 & -52.95190528 \\83.98200000 & -15.24871131 & -5.996535898 \\-525.0060000 & 31.00000000 & 37.49600000 \end{pmatrix}"
    ),
    "physics 1": (
        "sqrt((((4 × ((10^5) meters)) / second)^2) + (((150 volts) × 1.6 × ((10^−19) coulombs) × 2) / (1.67 × ((10^−27) kilograms)))) ≈ 434.445065538 km/s",
        r"\sqrt{\left( \frac{4 \cdot 10^{5}\ meters}{second} \right)^{2} + \frac{150\ volts \cdot 1.6 \cdot 10^{-19}\ coulombs \cdot 2}{1.67 \cdot 10^{-27}\ kilograms}} \approx \frac{434.445065538\ km}{s}"
    ),
    "solve": (
        "solve((((−3) × x²) + (4 × x) + 12) = 0) = [(2/3 − (2/3) × √(10))  ((2/3) × √(10) + 2/3)] ≈ [−1.44151844011  2.77485177345]",
        r"\texttt{solve}\Bigl( -3 \cdot x^{2} + 4  x + 12 = 0 \Bigr) = \begin{pmatrix} \left( \frac{2}{3} - \frac{2}{3} \cdot \sqrt{10} \right)\\\left( \frac{2}{3} \cdot \sqrt{10} + \frac{2}{3} \right) \end{pmatrix} \approx \begin{pmatrix} -1.44151844011\\2.77485177345 \end{pmatrix}"
    ),
    "implicit multiplication": (
        "4 m sec / (2 sqrt(9) s^2) + 3(-5*5 m/s +3 m/s)",
        r"\frac{4\ m \cdot sec}{2 \cdot \sqrt{9} \cdot s^{2}} + 3 \cdot \left( \frac{-5 \cdot 5\ m}{s} + \frac{3\ m}{s} \right)"
    ),
    "temperature": (
        "((24 celsius) − ((x celsius) × ((0.17 celsius) / (15 minutes)))) = (21.94 celsius) = x ≈ 181.764705882 min/°C",
        r"24\ ^\circ C - x\ ^\circ C \cdot \frac{0.17\ ^\circ C}{15\ minutes} = 21.94\ ^\circ C = x \approx \frac{181.764705882\ min}{^\circ C}"
    ),
    "prices": (
        "5h * (3EUR / 1h) = 15EUR",
        r"5\ h \cdot \frac{3\ \text{€}}{1\ h} = 15\ \text{€}"
    ),
    "equation": (
        "(((80 kilometers) / hour) × x seconds) = ((((−120 kilometers) / hour) × x seconds) + (5 kilometers))\nx = 90",
        r"\frac{80\ kilometers}{hour} \cdot x\ seconds = \frac{-120\ kilometers}{hour} \cdot x\ seconds + 5\ kilometers" + "\n" +
        r"x = 90"
    ),
}




def tests(display: bool = False):
    parser = NumericStringParser()

    for name, test_pair in test_calculations.items():
        test, result = test_pair
        try:
            latex = "\n".join([NumericStringParser().eval(prepare_for_latex(c)) for c in test.splitlines() if c.strip()])
            if result:
                assert latex == result, f"Expected: {result}, got: {latex}"
            else:
                logging.info(f"result:\n{latex}")
            if display:
                image = latex2image(latex)
                img = Image.open(image)
                img.show()
            logging.info(f"Passed test: {name}")
        except Exception as e:
            logging.warning(f"Failed test: {name}")
            logging.error(traceback.format_exc())

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, 
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    try:
        tests(display=False)
        code = """
(((80 kilometers) / hour) × x seconds) = ((((−120 kilometers) / hour) × x seconds) + (5 kilometers))
x = 90"""
        #code = test_calculations["vectors"]
        # for name, code in test_calculations.items():
        #     logging.info(name)
        logging.info(prepare_for_latex(code))
        latex = "\n".join([NumericStringParser().eval(prepare_for_latex(c)) for c in code.splitlines() if c.strip()])
        logging.info(f"Latex: {latex}")
        image = latex2image(latex)
        img = Image.open(image)
        img.show()
        #("Press enter to continue")

    except ParseException as e:
        print(e.explain())


        
