import os
from typing import Union
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
import matplotlib
import matplotlib.pyplot as plt
from io import BytesIO
import re
from PIL import Image


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
        sep     :: [',' | ';']
        x       :: 'x' | integer + x
        atom    :: PI | E | real | x | fn '(' expr [sep expr]* ')' | '(' expr ')'
        factor  :: atom [ expop factor ]*
        term    :: factor [ multop factor ]*
        expr    :: term [ addop term ]*
        equation:: expr ['=' expr]*
        """
        point = Literal(".")
        e = CaselessLiteral("E")
        x = Literal("x")
        fnumber = Combine(Word("+-" + nums, nums) +
                          Optional(point + Optional(Word(nums))) +
                          Optional(e + Word("+-" + nums, nums)) + 
                          Optional(x)
        )
        ident = Word(alphas, alphas + "_$")
        plus = Literal("+")
        minus = Literal("-")
        mult = Literal("*") | Literal("×")
        div = Literal("/")
        lpar = Literal("(").suppress()
        rpar = Literal(")").suppress()
        sep = Literal(",").suppress() | Literal(";").suppress()
        
        addop = plus | minus
        multop = mult | div
        expop = Literal("^")
        pi = CaselessLiteral("PI")
        equals = Literal("=") | Literal("≈")
        expr = Forward()
        atom = ((Optional(oneOf("- +")) +
                 (x | ident + lpar + expr + ZeroOrMore(sep + expr) + rpar | pi | e | fnumber).setParseAction(self.pushFirst))
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
        equation = expr + \
            ZeroOrMore((equals + expr).setParseAction(self.pushFirst))
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
            "^": operator.pow}
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
        }
        
        self.op_to_latex = {
            "+": "+",
            "-": "-",
            "*": "\\cdot",
            "/": "\\div",
            "^": "^",
            "×": "\\cdot"
        }
    @staticmethod
    def get_latex_fn(fn_name: str) -> str:
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
        elif fn_name == "abs":
            return "\\left|{0}\\right|"
        elif fn_name == "trunc":
            return "\\text{{trunc}}({0})"
        elif fn_name == "round":
            return "\\text{{round}}({0})"
        elif fn_name == "sgn":
            return "\\text{{sgn}}{0}"
        elif fn_name == "sum":
            return "\\sum_{{x={1}}}^{{{0}}} {2}"
        elif fn_name == "integrate":
            return "\\int_{{{1}}}^{{{0}}} {2} \\,\\ dx"
        else:
            return fn_name

    def evaluateStack(self, s) -> str:
        """
        converts the stack to latex
        """
        op = s.pop()
        if op in "=≈":
            op2 = self.evaluateStack(s)
            op1 = self.evaluateStack(s)
            return f"{op1} {op} {op2}"
        if op == 'unary -':
            return -self.evaluateStack(s)
        if op in "/":
            op2 = self.evaluateStack(s)
            op1 = self.evaluateStack(s)
            return f"\\frac{{{op1}}}{{{op2}}}"
        if op in "+-*×=":
            op2 = self.evaluateStack(s)
            op1 = self.evaluateStack(s)
            return f"{op1} {self.op_to_latex[op]} {op2}"
        if op in "^":
            op2 = self.evaluateStack(s)
            op1 = self.evaluateStack(s)
            return f"{op1}^{{{op2}}}"
        elif op == "PI":
            return "\pi"
        elif op == "E":
            return "e"
        elif op in self.fn:
            format_values = [self.evaluateStack(s) for _ in range(self.fn[op])]
            return self.get_latex_fn(op).format(*format_values)
            return self.fn[op](self.evaluateStack(s))
        elif op[0].isalpha():
            return str(op)
        else:
            return str(op)

    def eval(self, num_string, parseAll=True) -> Union[float, int]:
        self.exprStack = []
        results = self.bnf.parseString(num_string, parseAll)
        val = self.evaluateStack(self.exprStack[:])
        return val
    

def latex2image(
    latex_expression, image_size_in=(3, 2), fontsize=16, dpi=100, multiline=False
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
    # over multiple lines
    if multiline:
      result = latex_expression[1:-1]
      result = result.replace(" = ", "\n= ").replace(" ≈ ", "\n≈ ")
      result = "\n".join([f"${line}$" for line in result.split("\n")])
    else:
      result = latex_expression

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

def evaluation2image(evaluation: str, multiline: bool = False) -> BytesIO:
    latex = NumericStringParser().eval(evaluation)
    latex = f"${latex}$"
    image = latex2image(latex, multiline=multiline)
    return image


if __name__ == "__main__":
    #latex = NumericStringParser().eval("sqrt(sum(5x, 1, 10))")
    #latex = NumericStringParser().eval("3 + 5 * 6 * sum(sqrt((9x + 16.9999x) / (2 * 7)),2,20) - 8 = 3")  # 10.0
    #latex = NumericStringParser().eval("20 × x × log(sqrt(3), e) = 10 × ln(3) × x ≈ x^integrate(3x, 0, 10)")
    latex = NumericStringParser().eval("sqrt(3) + (log(1'000, 10) × (5 / 60)) + (3 / 4) − 2³ + sum(x, 1, 10) = 48 + √(3) ≈ 49.7320508076")
    latex = f"${latex}$"
    image = latex2image(latex)
    img = Image.open(image)
    img.show()