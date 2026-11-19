import pytest

from src.calculator_engine import (
    CalcError, CalcSession, EvalContext, evaluate_expression, exact_form, format_number,
)


def ev(expr, angle="deg", **variables):
    try:
        return format_number(evaluate_expression(expr, EvalContext(angle, variables)))
    except CalcError as exc:
        return exc.label


@pytest.mark.parametrize("expr,expected", [
    ("1+2×3", "7"), ("2(3+4)", "14"), ("-2^2", "-4"), ("2^-2", "0.25"), ("2^3^2", "512"),
    ("-3²", "-9"), ("2×-3", "-6"), ("0.1+0.2", "0.3"), ("1÷3", "0.3333333333"),
    ("sin(30)", "0.5"), ("sin(180)", "0"), ("cos(90)", "0"), ("tan(45)", "1"),
    ("tan(90)", "Math ERROR"), ("asin(1)", "90"), ("√(16)", "4"), ("∛(27)", "3"),
    ("3ˣ√27", "3"), ("5!", "120"), ("10nPr3", "720"), ("10nCr3", "120"),
    ("log(1000)", "3"), ("ln(e)", "1"), ("logb(2,8)", "3"), ("abs(-3)", "3"),
    ("10^(2)", "100"), ("2×10^3", "2000"), ("5%", "0.05"), ("2⁻¹", "0.5"),
    ("1÷0", "Math ERROR"), ("0^0", "Math ERROR"), ("√-1", "Math ERROR"),
    ("(-8)^(1÷3)", "Math ERROR"), ("(1+2", "3"), ("sin(30", "0.5"),
    ("1+", "Syntax ERROR"), ("1.2.3", "Syntax ERROR"), ("1×10^10", "1×10^10"),
    ("d/dx(X²,3)", "6"),
])
def test_expressions(expr, expected):
    assert ev(expr) == expected


def test_radians_and_pi():
    assert ev("sin(π/2)", "rad") == "1"
    assert ev("cos(π)", "rad") == "-1"
    assert ev("1÷2π") == "0.1591549431"  # implicit multiplication binds tighter than ÷


def test_integral_matches_reference_screenshot():
    assert ev("∫(cos(X),0,π÷2)", "rad") == "1"


def test_variables():
    assert ev("2A+B", A=3, B=4) == "10"


def test_exact_forms():
    assert exact_form(0.5) == "1/2"
    assert exact_form(3.141592653589793 / 2) == "π/2"
    assert exact_form(2 ** 0.5) == "√2"
    assert exact_form(4.0) is None


def keys(session, *ids):
    for k in ids:
        session.press(k)


def test_session_flow_ans_and_sto():
    s = CalcSession()
    keys(s, "2", "mul", "3", "eq")
    assert s.result_text == "6"
    keys(s, "add", "4", "eq")  # '+' after a result continues from Ans
    assert s.expression == "Ans+4" and s.result_text == "10"
    keys(s, "shift", "rcl", "neg")  # STO A
    assert s.vars["A"] == 10
    keys(s, "ac", "alpha", "neg", "mul", "2", "eq")
    assert s.result_text == "20"


def test_shift_hyp_and_del():
    s = CalcSession()
    keys(s, "shift", "sin", "1", "eq")  # closing bracket is optional, like a real Casio
    assert s.expression == "asin(1" and s.result_text == "90"
    keys(s, "ac", "hyp", "sin", "0", "eq")
    assert s.result_text == "0"
    keys(s, "ac", "1", "2", "del")
    assert s.expression == "1"


def test_sd_toggle_and_history():
    s = CalcSession()
    keys(s, "1", "div", "2", "eq", "sd")
    assert s.result_text == "1/2"
    keys(s, "sd")
    assert s.result_text == "0.5"
    keys(s, "ac", "up")
    assert s.expression == "1÷2"


def test_calc_prompt():
    s = CalcSession()
    keys(s, "alpha", "rpar", "sq", "add", "1", "calc", "3", "eq")
    assert s.result_text == "10"


def test_error_clears_on_edit():
    s = CalcSession()
    keys(s, "1", "div", "0", "eq")
    assert s.result_text == "Math ERROR"
    keys(s, "del", "5", "eq")
    assert s.result_text == "0.2"
