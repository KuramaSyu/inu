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
        number_args: int | None = None
    ):
        self.element = element
        self.type = type_
        self.negate = negate
        self.unit = unit
        self.number = number
        self.number_args = number_args

    @property
    def is_negated(self) -> bool:
        return self.negate
    
class Unit(Element):
    ...
    



class NumericStringParser(object):
    '''
    Most of this code comes from the fourFn.py pyparsing example

    '''

    def pushFirst(self, strg, loc, toks):
        logging.debug(f"pushFirst: {toks[0]}; all: {toks}")
        number = self.prepare_number(toks[0])
        
        self.exprStack.append(
            {
                "element": number,
                "type": "number"
            }
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
            {
                "type": "unit",
                "element": unit,
                
            }
        )
    def pushUnitNumberFirst(self, strg, loc, toks):
        logging.debug(f"pushUnitNumberFirst: {toks[0]}; all: {toks}")
        array = toks[0].split(" ")
        number, unit = array[0], " ".join(array[1:])
        number = self.prepare_number(number)
        unit = self.prepare_unit(unit)

        self.exprStack.append(
            {
                "type": "unit",
                "unit": unit,
                "number": number,
                "element": f"{number}\\ {unit}",
                
            }
        )

    def pushArray(self, strg, loc, toks):
        logging.debug(f"Array: all: {toks}")
        negate = False
        if toks and toks[0] == '-':
            negate = True
        self.exprStack.append(
            {
                "type": 'array',
                "element": 'array',
                "negate": negate
            }
        )

    def pushFunction(self, strg, loc, toks):
        logging.debug(f"Function: {toks[0]}; all: {toks}")
        negate = False
        if toks and toks[0] == '-':
            negate = True
            toks = toks[1:]
        self.exprStack.append(
            {
                "element": toks[0],
                "type": "function",
                "negative": negate,
                "number_args": len(toks) -1
            }
        )
    
    def pushVector(self, strg, loc, toks):
        logging.debug(f"Vector 0x{len(toks[0])}: {toks}")
        self.exprStack.append(
            {
                "element": f"0x{len(toks[0])}",
                "type": "vector"
            }
        )
    def pushMatrix(self, strg, loc, toks):
        logging.debug(f"Matrix {len(toks)}x{len(toks[0])}: {toks}")
        self.exprStack.append(
            {
                "element": f"{len(toks)}x{len(toks[0])}",
                "type": "matrix"
            }
        )
    
    def pushFactorFirst(self, strg, loc, toks):
        logging.debug(f"pushFactorFirst: {toks[0]}; all: {toks}")
        self.exprStack.append(
            {
                "element": toks[0],
                "type": "factor"
            }
        )

    def pushTermFirst(self, strg, loc, toks):
        logging.debug(f"pushTermFirst: {toks[0]}; all: {toks}")
        self.exprStack.append(
            {
                "element": toks[0],
                "type": "term"
            }
        )

    def pushExprFirst(self, strg, loc, toks):
        logging.debug(f"pushExprFirst: {toks[0]}; all: {toks}")
        self.exprStack.append(
            {
                "element": toks[0],
                "type": "expr"
            }
        )

    def pushImplicitMult(self, strg, loc, toks):
        logging.debug(f"pushImplicitMult: *; all: {toks}")
        self.exprStack.append(
            {
                "element": "*",
                "type": "implicit_mult"
            }
        )

    def pushEquationFirst(self, strg, loc, toks):
        logging.debug(f"pushEquationFirst: {toks[0]}; all: {toks}")
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
            | (Optional(oneOf("-+")) + ( pi | e | xnumber | fnumber | binary_number)).setParseAction(self.pushFirst)
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

    @staticmethod
    def unpack_array(op: Dict[str, Any]) -> str:
        if op["type"] == "array" and op["negated"] == False:
            return op["old"][0]
        return op["content"]

    def get_latex_fn(self, fn_name: str, number_args) -> str:
        if fn_name not in ["planet", "element"]:
            self.needs_latex = True
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
            return "\\text{{" + fn_name[3:] + "}}^{{-1}}\\left(" + "{0}\\right)"
        else:
            return "\\text{{" + fn_name + "}}" + f"\\left( {', '.join(reversed(['{'+str(i)+'}' for i in range(number_args)]))} \\right)"

    def evaluateStack(self, s) -> str:
        """
        converts the stack to latex
        """
        element = s.pop()
        op = element["element"]
        if element["type"] == "vector":
            self.needs_latex = True
            cols = int(op.split("x")[1])
            expressions = reversed([self.evaluateStack(s)['content'] for _ in range(cols)])
            content = '\\\\'.join(expressions)
            return {
                "content": f"\\begin{{pmatrix}} {content} \\end{{pmatrix}}",
                "type": "vector",
                "old": expressions
            }
        
        if element["type"] == "matrix":
            self.needs_latex = True
            cols = int(op.split("x")[0])
            rows = int(op.split("x")[1])
            matrix_content = ""
            expressions = []
            for _ in range(cols):
                expressions.append([])
                for _ in range(rows):
                    expressions[-1].append(self.evaluateStack(s)['content'])
                expressions[-1].reverse()
            expressions.reverse()

            for i, col in enumerate(expressions):
                if i != 0:
                    matrix_content += " \\\\"
                matrix_content += " & ".join(col)

            return {
                "content": f"\\begin{{pmatrix}} {matrix_content} \\end{{pmatrix}}",
                "type": "matrix",
                "old": expressions
            }
        
        if op in "=≈":
            op2 = self.unpack_array(self.evaluateStack(s))
            op1 = self.unpack_array(self.evaluateStack(s))
            return {
                "content": f"{op1} {self.op_to_latex[op]} {op2}",
                "type": "equal",
                "old": [op1, op2]
            }
        
        if op == 'array':
            negated = element["negate"]
            prefix = "- " if negated else ""
            expr = self.evaluateStack(s)
            if not negated:
                if expr['type'] in ['array', 'fraction', 'mul']:
                    return expr
                elif expr['type'] in ['number', 'exp'] and not expr['content'].startswith("-"):
                    return expr
            return {
                "content": f"{prefix}\\left( {expr['content']} \\right)",
                "type": "array",
                "negated": element["negate"],
                "old": [expr['content']]
            }
        if op in "/":
            self.needs_latex = True
            op2 = self.unpack_array(self.evaluateStack(s))
            op1 = self.unpack_array(self.evaluateStack(s))
            return {
                "content": f"\\frac{{{op1}}}{{{op2}}}",
                "type": "fraction",
                "old": [op1, op2] 
            }
        
        if op in "+-*×·=±":
            op_name = {
                "+": "add",
                "-": "sub",
                "*": "mul",
                "×": "mul",
                "·": "mul",
                "/": "div",
                "=": "eq",
                "±": "pm",
            }
            self.needs_latex = True
            op2 = self.evaluateStack(s)['content']
            op1 = self.evaluateStack(s)['content']
            return {
                "content": f"{op1} {self.op_to_latex[op]} {op2}",
                "type": op_name[op],
                "old": [op1, op2]
            }
        
        if op in "^":
            self.needs_latex = True
            op2 = self.evaluateStack(s)['content']
            op1 = self.evaluateStack(s)['content']
            return {
                "content": f"{op1}^{{{op2}}}",
                "type": "exp",
                "old": [op1, op2]
            }
        
        elif op == "PI":
            self.needs_latex = True
            return {
                "content": "\\pi",
                "type": "number",
                "old": op
            }
        
        elif op == "E":
            self.needs_latex = True
            return {
                "content": "e",
                "type": "number",
                "old": op
            }
        
        elif element["type"] == "function":
            number_args = self.fn.get(op) or element["number_args"]
            format_values = [self.evaluateStack(s)['content'] for _ in range(number_args)]
            prefix = "- " if element["negative"] else ""
            return {
                "content": f"{prefix}{self.get_latex_fn(op, number_args).format(*format_values)}",
                "type": "function",
                "old": format_values
            }
        
        elif element["type"] in ["unit", "number"]:
            return {
                "content": op,
                "type": element["type"],
                "old": op
            }
        else:
            return {
                "content": op,
                "type": element["type"],
                "old": op
            }

    def eval(self, num_string, parseAll=True) -> str:
        self.exprStack = []
        results = self.bnf.parseString(num_string, parseAll)
        logging.debug("results")
        # results.pprint()
        logging.debug("exprStack")
        logging.debug(pformat(self.exprStack))
        val = self.evaluateStack(self.exprStack[:])
        # pprint(val)
        return val['content']
    

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
    # over multiple lines
    lines = []
    includes_matrix = "pmatrix" in latex_expression
    max_len = 50 if not includes_matrix else 300
    length = len(latex_expression.splitlines())
    for line in latex_expression.splitlines():
        if re.match(r"^x [=≈]", line) or len(line) < max_len or length > 1 or not multiline:
            lines.append(f"{line}")
            continue
        line = line.replace(" = ", "\n= ").replace(r"\approx", "\n \\approx")
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

def evaluation2image(evaluation: str, multiline: bool = False) -> BytesIO:
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

def tests():
    parser = NumericStringParser()
    tests = {
        "vectors": "cross([1  2  3], [1  2  sqrt(9)]) = [0  0  0]",
        "matrix": "[1  2  3; 4  5  sqrt(4)*3; 7  8  9] + [1  2  3; sqrt(16)  5  6; 7  8  9] = [2  4  6; 8  10  12; 14  16  18]",
        "matrix + function chained": "adj([[1  2  sqrt(3)]; [(2 × (10^−3))  integrate(3 × x, 0, 5)  6]; [dot([1  3], [2  4])  det([1  2  3; 4  5  6; 7  8  10])  3]]) ≈ [355.5000000  −23.19615242  −52.95190528; 83.98200000  −15.24871131  −5.996535898; −525.0060000  31.00000000  37.49600000]",
        "physics 1": "sqrt((((4 × ((10^5) meters)) / second)^2) + (((150 volts) × 1.6 × ((10^−19) coulombs) × 2) / (1.67 × ((10^−27) kilograms)))) ≈ 434.445065538 km/s",
        "solve": "solve((((−3) × x²) + (4 × x) + 12) = 0) = [(2/3 − (2/3) × √(10))  ((2/3) × √(10) + 2/3)] ≈ [−1.44151844011  2.77485177345]",
        "implicit multiplication": "4 m sec / (2 sqrt(9) s^2) + 3(-5*5 m/s +3 m/s)"
    }
    for name, test in tests.items():
        try:
            latex = parser.eval(prepare_for_latex(test))
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
        code = "pi pi * €"
        tests()
        logging.debug(prepare_for_latex(code))
        latex = NumericStringParser().eval(prepare_for_latex(code))
        print(latex)
        image = latex2image(latex)
        img = Image.open(image)
        img.show()

    except ParseException as e:
        print(e.explain())


        
