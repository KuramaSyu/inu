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
from pprint import pprint
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
            r"\usepackage{amsmath}",
            r"\usepackage[T1]{fontenc}",
            r"\usepackage{mathpazo}",
            r"\renewcommand\arraystretch{1.4}"
            ])
    })


class NumericStringParser(object):
    '''
    Most of this code comes from the fourFn.py pyparsing example

    '''

    def pushFirst(self, strg, loc, toks):
        # print(f"pushFirst: {toks[0]}; all: {toks}")
        self.exprStack.append(
            {
                "element": toks[0],
                "type": "number"
            }
        )
        
    def pushUnitFirst(self, strg, loc, toks):
        # print(f"pushUnitFirst: {toks[0]}; all: {toks}")
        
        if "E" in toks[0] and " " in toks[0]:
            a, b = toks[0].split(" ")
            # replace E x with *10^{x}
            part1, part2 = a.split("E")
            toks[0] = f"{part1}\\cdot10^{{{part2}}}"
        self.exprStack.append(
            {
                "element": toks[0],
                "type": "unit"
            }
        )

    def pushArray(self, strg, loc, toks):
        # print(f"Array: all: {toks}")
        if toks and toks[0] == '-':
            self.exprStack.append(
                {
                    "eleement": '-array',
                    "type": 'array'
                }
            )
        else:
            self.exprStack.append(
                {
                    "element": 'array',
                    "type": 'array'
                }
            )
    
    def pushVector(self, strg, loc, toks):
        # print(f"Vector: {toks}")
        self.exprStack.append(
            {
                "element": f"0x{len(toks[0])}",
                "type": "vector"
            }
        )
    def pushMatrix(self, strg, loc, toks):
        # print(f"Matrix: {toks}")
        self.exprStack.append(
            {
                "element": f"{len(toks)}x{len(toks[0])}",
                "type": "matrix"
            }
        )
    
    def pushFactorFirst(self, strg, loc, toks):
        # print(f"pushFactorFirst: {toks[0]}; all: {toks}")
        self.exprStack.append(
            {
                "element": toks[0],
                "type": "factor"
            }
        )

    def pushTermFirst(self, strg, loc, toks):
        # print(f"pushTermFirst: {toks[0]}; all: {toks}")
        self.exprStack.append(
            {
                "element": toks[0],
                "type": "term"
            }
        )

    def pushExprFirst(self, strg, loc, toks):
        # print(f"pushExprFirst: {toks[0]}; all: {toks}")
        self.exprStack.append(
            {
                "element": toks[0],
                "type": "expr"
            }
        )

    def pushEquationFirst(self, strg, loc, toks):
        # print(f"pushEquationFirst: {toks[0]}; all: {toks}")
        self.exprStack.append(
            {
                "element": toks[0],
                "type": "equation"
            }
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
        fnumber = Combine(Word("+-" + nums, nums) +
                          Optional(point + Optional(Word(nums))) +
                          Optional(Combine(Word(PERIOD_START) + Word(nums, nums))) + # 0.1 666… -> support the period start sign
                          Optional(Word("…")) +
                          Optional(e + Word("+-" + nums, nums)) + 
                          Optional(x)
        )
        ident = Word(alphas, alphas + "_$")
        unit_name = Word(alphas + "μ_")
        unit = unit_name
        space = Literal(" ")
        unit_number = Combine(fnumber + space + unit)
        
        plus = Literal("+") 
        minus = Literal("-")
        plusminus = Literal("±")
        mult = Literal("*") | Literal("×")
        div = Literal("/")
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

        vec_row = Group(Combine(expr) + OneOrMore(Literal(",").suppress() + Combine(expr)))
        vec = lbrack + vec_row + rbrack
        matrix = lbrack + vec_row + ZeroOrMore(semicolon + vec_row) + rbrack
        parameter = expr + ZeroOrMore(sep + expr)
        unit_chain = Combine(unit + ZeroOrMore(Optional(space) + unit))
        atom = (
              (Optional(oneOf("-+")) + (ident + lpar + parameter + rpar).setParseAction(self.pushFirst))
            | (Optional(oneOf("-+")) + unit_number).setParseAction(self.pushUnitFirst)
            | (Optional(oneOf("-+")) + ( pi | e | fnumber)).setParseAction(self.pushFirst)
            | (Optional(oneOf("-+")) + unit_chain).setParseAction(self.pushUnitFirst)
            | (Optional(oneOf("- +")) + ZeroOrMore(Literal(" ")) + Group(lpar + expr + rpar)).setParseAction(self.pushArray)
            | (Optional(oneOf("-+")) + vec).setParseAction(self.pushVector)
            | (Optional(oneOf("-+")) + matrix).setParseAction(self.pushMatrix)
            
        )
        # by defining exponentiation as "atom [ ^ factor ]..." instead of
        # "atom [ ^ atom ]...", we get right-to-left exponents, instead of left-to-right
        # that is, 2^3^2 = 2^(3^2), not (2^3)^2.
        factor = Forward()
        factor << atom + \
            ZeroOrMore((expop + factor).setParseAction(self.pushFactorFirst))
        term = factor + \
            ZeroOrMore((multop + factor).setParseAction(self.pushTermFirst))
        expr << term + \
            ZeroOrMore((addop + term).setParseAction(self.pushExprFirst))
        equation = expr + \
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
        else:
            return fn_name

    def evaluateStack(self, s) -> str:
        """
        converts the stack to latex
        """
        element = s.pop()
        op = element["element"]
        if element["type"] == "vector":
            cols = int(op.split("x")[1])
            expressions = reversed([self.evaluateStack(s) for _ in range(cols)])
            content = '\\\\'.join(expressions)
            return f"\\begin{{pmatrix}} {content} \\end{{pmatrix}}"
        if element["type"] == "matrix":
            rows = int(op.split("x")[0])
            cols = int(op.split("x")[1])
            matrix_content = ""
            expressions = []
            for _ in range(cols):
                expressions.append([])
                for _ in range(rows):
                    expressions[-1].append(self.evaluateStack(s))
                expressions[-1].reverse()
            expressions.reverse()

            for i, col in enumerate(expressions):
                if i != 0:
                    matrix_content += " \\\\"
                matrix_content += " & ".join(col)

            return f"\\begin{{pmatrix}} {matrix_content} \\end{{pmatrix}}"
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
        if op in "+-*×·=±":
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
            if "_" in op:
                op = op.replace("_", "\_")
            return str(op)
        elif element["type"] == "number":
            part1, part2 = None, None
            if "E" in op:
                # replace E x with *10^{x}
                part1, part2 = op.split("E")
                op = f"{part1} \\cdot 10^{{{part2}}}"
            if "…" in op:
                if PERIOD_START in op:
                    # decimal partially periodic
                    part1, part2 = op.split(PERIOD_START)
                    part3, part4 = part2.split("…")
                    op = f"{part1}\\overline{{{part3}}}{part4}"
                else: 
                    # decimal fully periodic
                    part1, part2 = op.split(".")
                    part3, part4 = part2.split("…")
                    op = f"{part1}.\\overline{{{part3}}}{part4}"
            return op
        else:
            return str(op)

    def eval(self, num_string, parseAll=True) -> str:
        self.exprStack = []
        results = self.bnf.parseString(num_string, parseAll)
        # print("results")
        # results.p# print()
        # print("exprStack")
        # p# print(self.exprStack)
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
    includes_matrix = "pmatrix" in latex_expression
    max_len = 50 if not includes_matrix else 250
    length = len(latex_expression.splitlines())
    for line in latex_expression.splitlines():
        if re.match(r"^x [=≈]", line) or len(line) < max_len or length > 1 or not multiline:
            lines.append(f"{line}")
            continue
        line = line.replace(" = ", "\n= ").replace(" ≈ ", "\n≈ ")
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
    fig = plt.figure(figsize=image_size_in, dpi=dpi)
    fig.patch.set_alpha(0)
    text = fig.text(
        x=0.5,
        y=0.5,
        s=result,
        horizontalalignment="left",
        verticalalignment="center",
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
        "  ": ", "
    }
    for old, new in old_to_new.items():
        result = result.replace(old, new)
    return result

if __name__ == "__main__":
    #latex = NumericStringParser().eval("sqrt(sum(5x, 1, 10))")
    #latex = NumericStringParser().eval("3 + 5 * 6 * sum(sqrt((9x + 16.9999x) / (2 * 7)),2,20) - 8 = 3")  # 10.0
    #latex = NumericStringParser().eval("20 × x × log(sqrt(3), e) = 10 × ln(3) × x ≈ x^integrate(3x, 0, 10)")
    try:
      vectors = """cross([1  2  3], [1  2  sqrt(9)]) = [0  0  0]"""
      matrices = """[1  2  3; 4  5  sqrt(4)*3; 7  8  9] + [1  2  3; sqrt(16)  5  6; 7  8  9] = [2  4  6; 8  10  12; 14  16  18]"""
      #code = """[1  2  (3 − 5); 2  2  2; 3  −5  2] + [1  2  (3 − 5); 2  2  2; 3  −5  2]"""
      code = "inv([1  2  3; 4  5  6; 7  8  10]) = [−(2/3)  −(4/3)  1; −(2/3)  11/3  −2; 1  −2  1] = [−0.6666666667  −1.333333333  1; −0.6666666667  3.666666667  −2; 1  −2  1]"
      # print(code)
      print(prepare_for_latex(code))
      latex = NumericStringParser().eval(prepare_for_latex(code))
      # print(latex)
      image = latex2image(latex)
      img = Image.open(image)
      img.show()
    except ParseException as e:
      print(e.explain())
