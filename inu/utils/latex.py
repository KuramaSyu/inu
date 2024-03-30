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
    ParseException,
    OneOrMore
)
import math
import operator
import matplotlib
# switch to pgf backend


import matplotlib.pyplot as plt
from io import BytesIO
import re
from PIL import Image
from pprint import pprint

PERIOD_START = " "

# update latex preamble
def swtich_backend():
    plt.switch_backend('pgf')
    matplotlib.use('pgf')
    plt.rcParams.update({
        "text.usetex": True,
        "pgf.rcfonts": False,
        "pgf.texsystem": 'pdflatex', # default is xetex
        "pgf.preamble": "\n".join([
            r"\usepackage[T1]{fontenc}",
            r"\usepackage{mathpazo}"
            ])
    })
swtich_backend()

class NumericStringParser(object):
    '''
    Most of this code comes from the fourFn.py pyparsing example

    '''

    def pushFirst(self, strg, loc, toks):
        # print(f"pushFirst: {toks[0]}; all: {toks}")
        self.exprStack.append(toks[0])
        
    def pushUnitFirst(self, strg, loc, toks):
        # print(f"pushUnitFirst: {toks[0]}; all: {toks}")
        self.exprStack.append(toks[0].replace(" ", "\\ "))

    def pushArray(self, strg, loc, toks):
        if toks and toks[0] == '-':
            self.exprStack.append('-array')
        else:
            self.exprStack.append('array')
    
    def pushVector(self, strg, loc, toks):
        # print(f"Vector: {toks}")
        self.exprStack.append(toks[0])

    def __init__(self):
        """
        expop   :: '^'
        multop  :: '*' | '/'
        addop   :: '+' | '-'
        integer :: ['+' | '-'] '0'..'9'+ ' '? '…'? 'x'?
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
        fnumber = Combine(Word("+ -" + nums, nums) +
                          Optional(point + Optional(Word(nums))) +
                          Optional(Combine(Word(PERIOD_START) + Word(nums, nums))) + # 0.1 666… -> support the period start sign
                          Optional(Word("…")) +
                          Optional(e + Word("+-" + nums, nums))
        )
        ident = Word(alphas, alphas + "_$")
        unit_name = Word(alphas + "μ")
        unit = unit_name
        space = Literal(" ")
        unit_number = Combine(fnumber + space + unit)
        
        plus = Literal("+") 
        minus = Literal("-")
        mult = Literal("*") | Literal("×")
        div = Literal("/")
        lpar = Literal("(")
        rpar = Literal(")")
        lbrack = Literal("[")
        rbrack = Literal("]")
        sep = Literal(",").suppress() | Literal(";").suppress()
        
        addop = plus | minus
        multop = mult | div
        expop = Literal("^")
        pi = CaselessLiteral("PI")
        equals = Literal("=") | Literal("≈")

        expr = Forward()


        vec_row = expr + OneOrMore(expr)
        vec = lbrack + vec_row + rbrack
        matrix = lbrack + vec_row + OneOrMore(Literal(";") + vec_row) + rbrack
        parameter = expr + ZeroOrMore(sep + expr)
        unit_chain = Combine(unit + ZeroOrMore(Optional(space) + unit))
        atom = (
              (Optional(oneOf("-+")) + (ident + lpar + parameter + rpar).setParseAction(self.pushFirst))
            | (Optional(oneOf("-+")) + unit_number).setParseAction(self.pushUnitFirst)
            | (Optional(oneOf("-+")) + ( pi | e | fnumber)).setParseAction(self.pushFirst)
            | (Optional(oneOf("-+")) + unit_chain).setParseAction(self.pushUnitFirst)
            | (Optional(oneOf("- +")) + ZeroOrMore(Literal(" ")) + Group(lpar + expr + rpar)).setParseAction(self.pushArray)
        )
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
            ZeroOrMore((equals + expr).setParseAction(self.pushFirst)) + \
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
            "^": operator.pow}
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
            return f"{op1} {self.op_to_latex[op]} {op2}"
        if op == 'array':
            return f"\\left( {self.evaluateStack(s)} \\right)"
        if op == '-array':
            return f"- \\left( {self.evaluateStack(s)} \\right)"
        if op in "/":
            op2 = self.evaluateStack(s).removeprefix(r"\left(").removesuffix(r"\right)")
            op1 = self.evaluateStack(s).removeprefix(r"\left(").removesuffix(r"\right)")
            return f"\\frac{{{op1}}}{{{op2}}}"
        if op in "+-*×·=":
            op2 = self.evaluateStack(s)
            op1 = self.evaluateStack(s)
            return f"{op1} {self.op_to_latex[op]} {op2}"
        if op in "^":
            op2 = self.evaluateStack(s)
            op1 = self.evaluateStack(s)
            return f"{op1}^{{{op2}}}"
        elif op == "PI":
            return "\\pi"
        elif op == "E":
            return "e"
        elif op in self.fn:
            format_values = [self.evaluateStack(s) for _ in range(self.fn[op])]
            return self.get_latex_fn(op).format(*format_values)
        elif str(op[0]).isalpha():
            return str(op)
        elif "…" in op:
            part1, part2 = None, None
            if PERIOD_START in op:
                # decimal partially periodic
                part1, part2 = op.split(PERIOD_START)
                part3, part4 = part2.split("…")
                return f"{part1}\\overline{{{part3}}}{part4}"
            else: 
                # decimal fully periodic
                part1, part2 = op.split(".")
                part3, part4 = part2.split("…")
                return f"{part1}.\\overline{{{part3}}}{part4}"
        else:
            return str(op)

    def eval(self, num_string, parseAll=True) -> str:
        self.exprStack = []
        results = self.bnf.parseString(num_string, parseAll)
        # print(f"results: {results}")
        # print(f"exprStack: {self.exprStack[:]}")
        val = self.evaluateStack(self.exprStack[:])
        return val
    

def latex2image(
    latex_expression: str, image_size_in=(3, 2), fontsize=16, dpi=100, multiline=False
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
    lines = []
    length = len(latex_expression.splitlines())
    for line in latex_expression.splitlines():
        if re.match(r"^x [=≈]", line) or len(line) < 50 or length > 1 or not multiline:
            lines.append(f"${line}$")
            continue
        line = line.replace(" = ", "\n= ").replace(" ≈ ", "\n≈ ")
        len_ = 0
        for i, l in enumerate(line.splitlines()):
            if len_ + len(l) < 50 and len(lines) > 0:
                lines[-1] = f"{lines[-1][:-1]}{l}$"
                len_ += len(l)
            else:
                lines.append(f"${l}$")
                len_ = len(l)
    

    result = "\n".join(lines)

    swtich_backend()
    fig = plt.figure(figsize=image_size_in, dpi=dpi)
    fig.patch.set_alpha(0)
    text = fig.text(
        x=0.5,
        y=0.5,
        s=result,
        horizontalalignment="left",
        verticalalignment="center",
        fontsize=16,
        color='white',  # Set text color to white
        linespacing=1.7,
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
    evaluations = [ev for ev in evaluation.splitlines()] if len(evaluation.splitlines()) > 1 else [evaluation]
    latex = "\n".join([NumericStringParser().eval(ev) for ev in evaluations])
    image = latex2image(latex, multiline=multiline)
    return image

def prepare_for_latex(result: str) -> str:
    """prepares the result for latex"""
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
    }
    for old, new in old_to_new.items():
        result = result.replace(old, new)
    return result

if __name__ == "__main__":
    #latex = NumericStringParser().eval("sqrt(sum(5x, 1, 10))")
    #latex = NumericStringParser().eval("3 + 5 * 6 * sum(sqrt((9x + 16.9999x) / (2 * 7)),2,20) - 8 = 3")  # 10.0
    #latex = NumericStringParser().eval("20 × x × log(sqrt(3), e) = 10 × ln(3) × x ≈ x^integrate(3x, 0, 10)")
    try:
      latex = NumericStringParser().eval(prepare_for_latex("""product(x, 1, 4) = 24"""))
      print(latex)
      image = latex2image(latex)
      img = Image.open(image)
      img.show()
    except ParseException as e:
      print(e.explain())
