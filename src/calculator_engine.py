"""Cazio calculator engine.

Pure Python (no Qt). Two layers:

* ``evaluate_expression`` - a safe tokenizer + recursive-descent parser that
  understands Casio-style input (implicit multiplication, ``nPr``/``nCr``,
  ``∫(f,a,b)``, ``d/dx(f,x)``, angle modes, variables ...). It never uses
  ``eval``.
* ``CalcSession`` - the key-press state machine (SHIFT / ALPHA / STO / RCL /
  cursor editing / history) that the UI drives.
"""

from __future__ import annotations

import math
import random
import re
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Callable, Dict, List, Optional, Sequence, Tuple

# --------------------------------------------------------------------------
# Errors & constants
# --------------------------------------------------------------------------


class CalcError(Exception):
    label = "Math ERROR"


class MathError(CalcError):
    label = "Math ERROR"


class CalcSyntaxError(CalcError):
    label = "Syntax ERROR"


ANGLES = ("deg", "rad", "gra")
ANGLE_LABELS = {"deg": "D", "rad": "R", "gra": "G"}
ANGLE_NAMES = {"deg": "DEG", "rad": "RAD", "gra": "GRA"}
VARIABLES = "ABCDEFXYM"
MAX_ABS = 1e100

Token = Tuple[str, object]

# --------------------------------------------------------------------------
# Tokenizer
# --------------------------------------------------------------------------

_FUNC_WORDS = {
    "asinh": "asinh", "acosh": "acosh", "atanh": "atanh",
    "sinh": "sinh", "cosh": "cosh", "tanh": "tanh",
    "asin": "asin", "acos": "acos", "atan": "atan",
    "sin": "sin", "cos": "cos", "tan": "tan",
    "logb": "logb", "log": "log", "ln": "ln",
    "sqrt": "sqrt", "cbrt": "cbrt", "abs": "abs", "Abs": "abs",
    "diff": "diff", "d/dx": "diff", "Ran#": "ran",
    "√": "sqrt", "∛": "cbrt", "∫": "integ",
}
_OTHER_WORDS: Dict[str, Token] = {
    "Ans": ("ID", "Ans"),
    "pi": ("ID", "π"),
    "π": ("ID", "π"),
    "nPr": ("OP", "nPr"),
    "nCr": ("OP", "nCr"),
}
_WORDS = sorted(list(_FUNC_WORDS) + list(_OTHER_WORDS), key=len, reverse=True)
_SYMBOLS = {
    "+": "+", "-": "-", "−": "-", "×": "*", "*": "*", "÷": "/", "/": "/",
    "^": "^", "(": "(", ")": ")", ",": ",", "!": "!", "%": "%",
    "°": "°", "²": "²", "³": "³",
}
_NUM_RE = re.compile(r"\d+\.?\d*|\.\d+")


def tokenize(text: str) -> List[Token]:
    tokens: List[Token] = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch.isspace():
            i += 1
            continue
        m = _NUM_RE.match(text, i)
        if m:
            end = m.end()
            if end < n and text[end] == ".":
                raise CalcSyntaxError("two decimal points")
            tokens.append(("NUM", float(m.group())))
            i = end
            continue
        if text.startswith("⁻¹", i):
            tokens.append(("OP", "inv"))
            i += 2
            continue
        if text.startswith("ˣ√", i):
            tokens.append(("OP", "root"))
            i += 2
            continue
        word = next((w for w in _WORDS if text.startswith(w, i)), None)
        if word is not None:
            if word in _FUNC_WORDS:
                tokens.append(("FUNC", _FUNC_WORDS[word]))
            else:
                tokens.append(_OTHER_WORDS[word])
            i += len(word)
            continue
        if ch == "e" or ch in VARIABLES:
            tokens.append(("ID", ch))
            i += 1
            continue
        if ch in _SYMBOLS:
            tokens.append(("OP", _SYMBOLS[ch]))
            i += 1
            continue
        raise CalcSyntaxError(f"unexpected {ch!r}")
    return tokens


# --------------------------------------------------------------------------
# Math helpers
# --------------------------------------------------------------------------


@dataclass
class EvalContext:
    angle: str = "deg"
    variables: Dict[str, float] = field(default_factory=dict)
    ans: float = 0.0

    def lookup(self, name: str) -> float:
        if name == "π":
            return math.pi
        if name == "e":
            return math.e
        if name == "Ans":
            return self.ans
        if name in VARIABLES:
            return float(self.variables.get(name, 0.0))
        raise CalcSyntaxError(name)

    def with_var(self, name: str, value: float) -> "EvalContext":
        merged = dict(self.variables)
        merged[name] = value
        return EvalContext(self.angle, merged, self.ans)


def _turn(angle: str) -> float:
    """Size of one full turn in the given angle unit."""
    return {"deg": 360.0, "gra": 400.0}.get(angle, 2 * math.pi)


def _to_rad(x: float, angle: str) -> float:
    return x * 2 * math.pi / _turn(angle)


def _from_rad(x: float, angle: str) -> float:
    return x * _turn(angle) / (2 * math.pi)


def _trig(kind: str, x: float, angle: str) -> float:
    """sin/cos/tan with exact values at quarter turns (sin 180° = 0, not 1e-16)."""
    quarter = _turn(angle) / 4
    k = x / quarter
    if abs(k - round(k)) < 1e-11:
        q = int(round(k)) % 4
        if kind == "sin":
            return (0.0, 1.0, 0.0, -1.0)[q]
        if kind == "cos":
            return (1.0, 0.0, -1.0, 0.0)[q]
        if q % 2:
            raise MathError()
        return 0.0
    rad = _to_rad(x, angle)
    return {"sin": math.sin, "cos": math.cos, "tan": math.tan}[kind](rad)


def _pow(a: float, b: float) -> float:
    if a == 0 and b == 0:
        raise MathError()
    return math.pow(a, b)  # ValueError (neg ** frac, 0 ** neg) -> MathError upstream


def _root(x: float, n: float) -> float:
    if n == 0:
        raise MathError()
    if x < 0:
        if float(n).is_integer() and int(n) % 2 == 1:
            return -math.pow(-x, 1.0 / n)
        raise MathError()
    return math.pow(x, 1.0 / n)


def _factorial(x: float) -> float:
    if x < 0 or not float(x).is_integer() or x > 69:
        raise MathError()
    return float(math.factorial(int(x)))


def _int_arg(x: float) -> int:
    if x < 0 or not float(x).is_integer():
        raise MathError()
    return int(x)


def _cbrt(x: float) -> float:
    fn = getattr(math, "cbrt", None)
    if fn:
        return fn(x)
    return math.copysign(abs(x) ** (1 / 3), x)


def _snap(v: float) -> float:
    return 0.0 if abs(v) < 1e-14 else v


def apply_function(name: str, vals: Sequence[float], ctx: EvalContext) -> float:
    if name == "logb":
        if len(vals) != 2:
            raise CalcSyntaxError("logb needs two arguments")
        base, x = vals
        if base <= 0 or base == 1 or x <= 0:
            raise MathError()
        return math.log(x) / math.log(base)
    if len(vals) != 1:
        raise CalcSyntaxError(f"{name} takes one argument")
    x = vals[0]
    a = ctx.angle
    if name in ("sin", "cos", "tan"):
        return _trig(name, x, a)
    if name in ("asin", "acos"):
        if not -1 <= x <= 1:
            raise MathError()
        return _from_rad(math.asin(x) if name == "asin" else math.acos(x), a)
    if name == "atan":
        return _from_rad(math.atan(x), a)
    if name == "sinh":
        return math.sinh(x)
    if name == "cosh":
        return math.cosh(x)
    if name == "tanh":
        return math.tanh(x)
    if name == "asinh":
        return math.asinh(x)
    if name == "acosh":
        if x < 1:
            raise MathError()
        return math.acosh(x)
    if name == "atanh":
        if not -1 < x < 1:
            raise MathError()
        return math.atanh(x)
    if name == "log":
        if x <= 0:
            raise MathError()
        return math.log10(x)
    if name == "ln":
        if x <= 0:
            raise MathError()
        return math.log(x)
    if name == "sqrt":
        if x < 0:
            raise MathError()
        return math.sqrt(x)
    if name == "cbrt":
        return _cbrt(x)
    if name == "abs":
        return abs(x)
    raise CalcSyntaxError(name)


def simpson(f: Callable[[float], float], a: float, b: float, n: int = 1000) -> float:
    if a == b:
        return 0.0
    h = (b - a) / n
    total = f(a) + f(b)
    for i in range(1, n):
        total += f(a + i * h) * (4 if i % 2 else 2)
    return total * h / 3


# --------------------------------------------------------------------------
# Parser
# --------------------------------------------------------------------------


class Parser:
    """Recursive descent. Precedence (low -> high):

    ``+ -``  <  ``× ÷``  <  ``nPr nCr``  <  unary ``-``  <  implicit ``×``
    <  ``^`` / ``ˣ√``  <  postfix (``! ² ³ ⁻¹ % °``)  <  primary
    """

    def __init__(self, tokens: List[Token], ctx: EvalContext) -> None:
        self.t = tokens
        self.i = 0
        self.ctx = ctx

    # -- token helpers
    def peek(self) -> Optional[Token]:
        return self.t[self.i] if self.i < len(self.t) else None

    def take(self) -> Optional[Token]:
        tok = self.peek()
        self.i += 1
        return tok

    def _starts_factor(self) -> bool:
        tok = self.peek()
        if tok is None:
            return False
        return tok[0] in ("NUM", "ID", "FUNC") or tok == ("OP", "(")

    def sub(self, tokens: List[Token], ctx: Optional[EvalContext] = None) -> float:
        return Parser(tokens, ctx or self.ctx).parse()

    # -- grammar
    def parse(self) -> float:
        if not self.t:
            raise CalcSyntaxError("empty")
        value = self.expr()
        if self.peek() is not None:
            raise CalcSyntaxError("trailing tokens")
        return value

    def expr(self) -> float:
        v = self.term()
        while True:
            tok = self.peek()
            if tok == ("OP", "+"):
                self.take()
                v += self.term()
            elif tok == ("OP", "-"):
                self.take()
                v -= self.term()
            else:
                return v

    def term(self) -> float:
        v = self.perm()
        while True:
            tok = self.peek()
            if tok == ("OP", "*"):
                self.take()
                v *= self.perm()
            elif tok == ("OP", "/"):
                self.take()
                d = self.perm()
                if d == 0:
                    raise MathError()
                v /= d
            else:
                return v

    def perm(self) -> float:
        v = self.signed()
        while self.peek() in (("OP", "nPr"), ("OP", "nCr")):
            op = self.take()[1]  # type: ignore[index]
            r = self.signed()
            n_, r_ = _int_arg(v), _int_arg(r)
            if r_ > n_:
                raise MathError()
            v = float(math.perm(n_, r_) if op == "nPr" else math.comb(n_, r_))
        return v

    def signed(self) -> float:
        tok = self.peek()
        if tok == ("OP", "-"):
            self.take()
            return -self.signed()
        if tok == ("OP", "+"):
            self.take()
            return self.signed()
        return self.implicit()

    def implicit(self) -> float:
        v = self.power()
        while self._starts_factor():
            v *= self.power()
        return v

    def exponent(self) -> float:
        tok = self.peek()
        if tok == ("OP", "-"):
            self.take()
            return -self.exponent()
        if tok == ("OP", "+"):
            self.take()
            return self.exponent()
        return self.power()

    def power(self) -> float:
        base = self.postfix()
        tok = self.peek()
        if tok == ("OP", "^"):
            self.take()
            return _pow(base, self.exponent())
        if tok == ("OP", "root"):
            self.take()
            return _root(self.exponent(), base)
        return base

    def postfix(self) -> float:
        v = self.primary()
        while True:
            tok = self.peek()
            if tok is None or tok[0] != "OP":
                return v
            op = tok[1]
            if op == "!":
                v = _factorial(v)
            elif op == "²":
                v = v * v
            elif op == "³":
                v = v * v * v
            elif op == "inv":
                if v == 0:
                    raise MathError()
                v = 1.0 / v
            elif op == "%":
                v = v / 100.0
            elif op == "°":
                v = _from_rad(v * math.pi / 180.0, self.ctx.angle)
            else:
                return v
            self.take()

    def primary(self) -> float:
        tok = self.take()
        if tok is None:
            raise CalcSyntaxError("unexpected end")
        kind, val = tok
        if kind == "NUM":
            return float(val)  # type: ignore[arg-type]
        if kind == "ID":
            return self.ctx.lookup(str(val))
        if kind == "FUNC":
            return self.call(str(val))
        if tok == ("OP", "("):
            v = self.expr()
            nxt = self.peek()
            if nxt == ("OP", ")"):
                self.take()
            elif nxt is not None:
                raise CalcSyntaxError("expected )")
            return v
        raise CalcSyntaxError("unexpected token")

    # -- functions
    def read_args(self) -> List[List[Token]]:
        """Collect comma-separated argument token lists up to the matching ')'."""
        args: List[List[Token]] = [[]]
        depth = 0
        while True:
            tok = self.peek()
            if tok is None:  # auto-close at end of input, like a real Casio
                break
            if tok == ("OP", "("):
                depth += 1
            elif tok == ("OP", ")"):
                if depth == 0:
                    self.take()
                    break
                depth -= 1
            elif tok == ("OP", ",") and depth == 0:
                self.take()
                args.append([])
                continue
            args[-1].append(self.take())  # type: ignore[arg-type]
        return args

    def call(self, name: str) -> float:
        if name == "ran":
            return round(random.random(), 3)
        if self.peek() == ("OP", "("):
            self.take()
            args = self.read_args()
            if name == "integ":
                return self._integrate(args)
            if name == "diff":
                return self._differentiate(args)
            vals = [self.sub(a) for a in args]
        else:
            if name in ("integ", "diff"):
                raise CalcSyntaxError("missing (")
            vals = [self.exponent()]
        result = apply_function(name, vals, self.ctx)
        return _snap(result) if name in ("sin", "cos", "tan") else result

    def _integrate(self, args: List[List[Token]]) -> float:
        if len(args) != 3 or not args[0]:
            raise CalcSyntaxError("∫(f,a,b)")
        a, b = self.sub(args[1]), self.sub(args[2])
        body = args[0]
        return simpson(lambda x: self.sub(body, self.ctx.with_var("X", x)), a, b)

    def _differentiate(self, args: List[List[Token]]) -> float:
        if len(args) != 2 or not args[0]:
            raise CalcSyntaxError("d/dx(f,x)")
        x0 = self.sub(args[1])
        body = args[0]

        def f(x: float) -> float:
            return self.sub(body, self.ctx.with_var("X", x))

        h = 1e-3 * max(1.0, abs(x0))
        d = (-f(x0 + 2 * h) + 8 * f(x0 + h) - 8 * f(x0 - h) + f(x0 - 2 * h)) / (12 * h)
        return float(f"{d:.9g}")


def evaluate_expression(expr: str, ctx: Optional[EvalContext] = None) -> float:
    """Evaluate ``expr`` and return a float, or raise :class:`CalcError`."""
    ctx = ctx or EvalContext()
    tokens = tokenize(expr)
    try:
        value = Parser(tokens, ctx).parse()
    except CalcError:
        raise
    except (ZeroDivisionError, OverflowError, ValueError):
        raise MathError() from None
    except RecursionError:
        raise CalcSyntaxError("too deep") from None
    if not math.isfinite(value) or abs(value) >= MAX_ABS:
        raise MathError()
    return value + 0.0  # turns -0.0 into 0.0


# --------------------------------------------------------------------------
# Number formatting
# --------------------------------------------------------------------------


def format_number(v: float, digits: int = 10) -> str:
    if v == 0:
        return "0"
    s = f"{v:.{digits}g}"
    if "e" in s:
        mantissa, exp = s.split("e")
        return f"{mantissa}×10^{int(exp)}"
    return s


def format_eng(v: float, digits: int = 10) -> str:
    if v == 0:
        return "0"
    exp = int(math.floor(math.log10(abs(v))))
    e3 = exp - (exp % 3)
    mant = float(f"{v / 10 ** e3:.{digits}g}")
    if e3 == 0:
        return format_number(v, digits)
    return f"{format_number(mant, digits)}×10^{e3}"


def _sqrt_form(v: float) -> Optional[str]:
    sq = v * v
    f = Fraction(sq).limit_denominator(1000)
    if f.numerator <= 0 or abs(float(f) - sq) > 1e-9 * sq:
        return None
    n, d = f.numerator, f.denominator
    m = n * d
    if m > 10 ** 8:
        return None
    k, r, i = 1, m, 2
    while i * i <= r:
        while r % (i * i) == 0:
            r //= i * i
            k *= i
        i += 1
    if r == 1:
        return None
    g = math.gcd(k, d)
    k, d = k // g, d // g
    text = (str(k) if k != 1 else "") + f"√{r}"
    if d != 1:
        text += f"/{d}"
    return ("-" if v < 0 else "") + text


def exact_form(v: float) -> Optional[str]:
    """Fraction, multiple of π, or simple surd for the S⇔D key (None if no exact form)."""
    if v == 0 or not math.isfinite(v):
        return None
    f = Fraction(v).limit_denominator(1000)
    if abs(float(f) - v) <= 1e-12 * max(1.0, abs(v)):
        if f.denominator == 1:
            return None
        return f"{f.numerator}/{f.denominator}"
    p = Fraction(v / math.pi).limit_denominator(100)
    if p != 0 and abs(float(p) * math.pi - v) <= 1e-10 * abs(v):
        n, d = abs(p.numerator), p.denominator
        text = "π" if n == 1 else f"{n}π"
        if d != 1:
            text += f"/{d}"
        return ("-" if p < 0 else "") + text
    return _sqrt_form(v)


# --------------------------------------------------------------------------
# Key-press state machine
# --------------------------------------------------------------------------

DIGITS = "0123456789"

PLAIN: Dict[str, str] = {
    "dot": ".", "add": "+", "sub": "-", "mul": "×", "div": "÷", "neg": "-",
    "lpar": "(", "rpar": ")", "exp": "×10^", "ans": "Ans", "sq": "²", "inv": "⁻¹",
    "sqrt": "√(", "pow": "^", "log": "log(", "ln": "ln(", "sin": "sin(",
    "cos": "cos(", "tan": "tan(", "frac": "÷", "dms": "°", "logb": "logb(",
    "integ": "∫(",
}
PLAIN.update({d: d for d in DIGITS})

SHIFTED: Dict[str, str] = {
    "sin": "asin(", "cos": "acos(", "tan": "atan(", "log": "10^(", "ln": "e^(",
    "sqrt": "∛(", "sq": "³", "pow": "ˣ√", "inv": "!", "integ": "d/dx(",
    "rpar": ",", "mul": "nPr", "div": "nCr", "exp": "π", "dot": "Ran#",
    "frac": "Abs(",
}
HYP_PLAIN = {"sin": "sinh(", "cos": "cosh(", "tan": "tanh("}
HYP_SHIFT = {"sin": "asinh(", "cos": "acosh(", "tan": "atanh("}

# ALPHA / STO / RCL variable selection (same layout as a real fx-991).
VAR_KEYS = {
    "neg": "A", "dms": "B", "hyp": "C", "sin": "D", "cos": "E", "tan": "F",
    "rpar": "X", "sd": "Y", "mplus": "M",
}
# Atoms that continue a previous result ("Ans+" when pressed right after '=').
CONTINUES_ANS = {"+", "-", "×", "÷", "^", "²", "³", "⁻¹", "!", "nPr", "nCr", "ˣ√", "×10^"}


@dataclass
class HistoryEntry:
    atoms: List[str]
    value: float


class CalcSession:
    """All the state behind the calculator screen. Feed it key ids via :meth:`press`."""

    HISTORY_LIMIT = 50

    def __init__(self, angle: str = "deg") -> None:
        self.angle = angle if angle in ANGLES else "deg"
        self.atoms: List[str] = []
        self.cursor = 0
        self.shift = False
        self.alpha = False
        self.hyp = False
        self.pending: Optional[str] = None  # "sto" | "rcl"
        self.prompt: Optional[str] = None  # CALC variable prompt text
        self.value: Optional[float] = None  # last result
        self.ans = 0.0
        self.error = ""
        self.message = ""
        self.fresh = False  # a result is on screen
        self.show_exact = False
        self.eng = False
        self.vars: Dict[str, float] = {c: 0.0 for c in VARIABLES}
        self.history: List[HistoryEntry] = []
        self.hist_pos: Optional[int] = None

    # ------------------------------------------------------------- display
    @property
    def expression(self) -> str:
        return "".join(self.atoms)

    def expression_view(self) -> Tuple[str, int]:
        """Text and the cursor position (in characters) within it."""
        text = "".join(self.atoms)
        return text, len("".join(self.atoms[: self.cursor]))

    @property
    def result_text(self) -> str:
        if self.error:
            return self.error
        if self.value is None:
            return ""
        if self.show_exact:
            ex = exact_form(self.value)
            if ex:
                return ex
        if self.eng:
            return format_eng(self.value)
        return format_number(self.value)

    def status_left(self) -> List[str]:
        out = []
        if self.shift:
            out.append("S")
        if self.alpha:
            out.append("A")
        if self.hyp:
            out.append("hyp")
        if self.pending:
            out.append(self.pending.upper())
        if self.vars["M"] != 0:
            out.append("M")
        return out

    def status_right(self) -> List[str]:
        out = ["Math", ANGLE_LABELS[self.angle]]
        if self.history:
            out.append("▲")
        return out

    # --------------------------------------------------------------- state
    def context(self) -> EvalContext:
        return EvalContext(self.angle, self.vars, self.ans)

    def set_angle(self, angle: str) -> None:
        if angle in ANGLES:
            self.angle = angle

    def cycle_angle(self) -> str:
        self.angle = ANGLES[(ANGLES.index(self.angle) + 1) % len(ANGLES)]
        return self.angle

    def clear_memory(self) -> None:
        self.vars = {c: 0.0 for c in VARIABLES}
        self.history.clear()
        self.ans = 0.0
        self.message = "Memory Cleared"

    def _reset_edit(self) -> None:
        self.atoms, self.cursor = [], 0
        self.value, self.error = None, ""
        self.fresh = self.show_exact = self.eng = False
        self.hist_pos = None

    # ----------------------------------------------------------- insertion
    def insert_atom(self, atom: str, binary: Optional[bool] = None) -> None:
        """Insert one editable token at the cursor (public so the keyboard can use it)."""
        self.message = ""
        if binary is None:
            binary = atom in CONTINUES_ANS
        if self.error:
            self.error, self.value = "", None
        if self.fresh:
            keep = ["Ans"] if binary else []
            self._reset_edit()
            self.atoms = keep
            self.cursor = len(keep)
        self.hist_pos = None
        self.atoms.insert(self.cursor, atom)
        self.cursor += 1

    # --------------------------------------------------------------- press
    def press(self, key: str) -> Optional[str]:
        """Handle a key. Returns an event for the UI ('mode', 'setup', 'off', 'angle') or None."""
        self.message = ""
        if key == "shift":
            self.shift, self.alpha = not self.shift, False
            return None
        if key == "alpha":
            self.alpha, self.shift = not self.alpha, False
            return None
        shift, alpha = self.shift, self.alpha
        self.shift = self.alpha = False

        if key == "mode":
            return "setup" if shift else "mode"
        if key == "on":
            return "on"
        if key == "ac" and shift:
            return "off"
        if key == "ans" and shift:
            self.cycle_angle()
            return "angle"
        if key == "9" and shift:
            self.clear_memory()
            return None

        if self.prompt is not None:
            self._press_prompt(key)
            return None

        if self.pending:
            mode, self.pending = self.pending, None
            var = VAR_KEYS.get(key)
            if var:
                if mode == "sto":
                    self.vars[var] = self.ans
                    self.message = f"{var} = " + format_number(self.ans)
                else:
                    self.insert_atom(var, binary=False)
                return None
            # anything else cancels the pending STO/RCL and is handled normally

        if alpha:
            var = VAR_KEYS.get(key)
            if var:
                self.insert_atom(var, binary=False)
                return None
            if key == "exp":
                self.insert_atom("e", binary=False)
                return None

        if shift:
            if key == "rcl":
                self.pending = "sto"
                return None
            if key == "mplus":
                self._memory_add(-1)
                return None
            atom = SHIFTED.get(key)
            if atom:
                if self.hyp and key in HYP_SHIFT:
                    atom, self.hyp = HYP_SHIFT[key], False
                self.insert_atom(atom, binary=None if key != "neg" else False)
                return None

        if key == "hyp":
            self.hyp = not self.hyp
            return None
        if key in HYP_PLAIN and self.hyp:
            self.hyp = False
            self.insert_atom(HYP_PLAIN[key])
            return None
        if key in PLAIN:
            self.insert_atom(PLAIN[key], binary=None if key != "neg" else False)
            return None

        handler = {
            "del": self._del, "ac": self._ac, "eq": self.evaluate,
            "left": self._left, "right": self._right,
            "up": self._hist_up, "down": self._hist_down,
            "rcl": self._rcl, "eng": self._eng, "sd": self._toggle_exact,
            "mplus": lambda: self._memory_add(+1), "calc": self._calc,
        }.get(key)
        if handler:
            handler()
        return None

    # ----------------------------------------------------------- key logic
    def _del(self) -> None:
        if self.error:
            self.error, self.value = "", None
        if self.fresh:
            self.fresh, self.show_exact, self.eng = False, False, False
            self.value = None
            self.cursor = len(self.atoms)
        if self.cursor > 0:
            del self.atoms[self.cursor - 1]
            self.cursor -= 1

    def _ac(self) -> None:
        self._reset_edit()
        self.hyp = False
        self.pending = None

    def _left(self) -> None:
        if self.error:
            self.error, self.value = "", None
        if self.fresh:
            self.fresh = False
            self.cursor = len(self.atoms)
        else:
            self.cursor = max(0, self.cursor - 1)

    def _right(self) -> None:
        if self.error:
            self.error, self.value = "", None
        if self.fresh:
            self.fresh = False
            self.cursor = 0
        else:
            self.cursor = min(len(self.atoms), self.cursor + 1)

    def _hist_up(self) -> None:
        if not self.history:
            return
        pos = len(self.history) - 1 if self.hist_pos is None else max(0, self.hist_pos - 1)
        self._load_history(pos)

    def _hist_down(self) -> None:
        if self.hist_pos is None:
            return
        if self.hist_pos >= len(self.history) - 1:
            self._reset_edit()
            return
        self._load_history(self.hist_pos + 1)

    def _load_history(self, pos: int) -> None:
        entry = self.history[pos]
        self._reset_edit()
        self.atoms = list(entry.atoms)
        self.cursor = len(self.atoms)
        self.value = entry.value
        self.fresh = True
        self.hist_pos = pos

    def _rcl(self) -> None:
        self.pending = "rcl"

    def _eng(self) -> None:
        if self.value is not None and not self.error:
            self.eng = not self.eng
            self.show_exact = False

    def _toggle_exact(self) -> None:
        if self.value is None or self.error:
            return
        if self.show_exact:
            self.show_exact = False
        elif exact_form(self.value):
            self.show_exact, self.eng = True, False
        else:
            self.message = "No exact form"

    def _memory_add(self, sign: int) -> None:
        if self.error:
            return
        if self.atoms and not self.fresh:
            self.evaluate()
        if self.value is None or self.error:
            return
        self.vars["M"] += sign * self.value

    def _calc(self) -> None:
        if "X" in self.atoms and not self.fresh:
            self.prompt = ""
        else:
            self.evaluate()

    def _press_prompt(self, key: str) -> None:
        text = self.prompt or ""
        if key in DIGITS or key in ("dot", "sub", "neg", "add", "mul", "div", "lpar", "rpar",
                                    "exp", "ans"):
            atom = PLAIN.get(key, key)
            self.prompt = text + atom
        elif key == "shift" or key == "alpha":
            pass
        elif key == "del":
            self.prompt = text[:-1]
        elif key == "ac":
            self.prompt = None
        elif key == "eq":
            try:
                x = evaluate_expression(text or "0", self.context())
            except CalcError as exc:
                self.prompt = None
                self.error = exc.label
                return
            self.vars["X"] = x
            self.prompt = None
            self.evaluate()

    # ------------------------------------------------------------ evaluate
    def evaluate(self) -> None:
        expr = self.expression
        if not expr.strip():
            return
        self.hist_pos = None
        try:
            value = evaluate_expression(expr, self.context())
        except CalcError as exc:
            self.error = exc.label
            self.value = None
            self.fresh = False
            return
        self.error = ""
        self.value = value
        self.ans = value
        self.fresh = True
        self.show_exact = self.eng = False
        self.history.append(HistoryEntry(list(self.atoms), value))
        del self.history[: -self.HISTORY_LIMIT]
