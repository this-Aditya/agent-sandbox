"""
p0001 — TYPE HINTS: what they really are, and why frameworks read them.

Run me:
    uv run p0001_typing.py

Read me with the doc open next to you:
    docs/p0001_typing.md

The point of this file: every claim in the doc is shown here by output you can
see. Change a line, run it again, watch what happens. That is how it sinks in.

The one idea to remember:
    A type hint in Python does not control your variable.
    It just writes down a fact about it. That fact is saved in a small
    dictionary on the function or class, and any code can read it while the
    program runs. Frameworks like Pydantic and FastAPI just read that
    dictionary. Types here are DATA, not rules.

NOTE: this file has 3 type errors ON PURPOSE (in add() and broken()), so you
can watch the two tools disagree:
    - Run the PROGRAM:   uv run p0001_typing.py       -> works fine, no crash.
    - Run the CHECKER:   uvx pyright p0001_typing.py  -> reports 3 errors.
    Python ignores the types; the checker does not. That gap is the point.
"""

from typing import Any, get_type_hints


def section(title: str) -> None:
    """Just prints a banner so the output is readable when you run the file."""
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


# ---------------------------------------------------------------------------
# 1. THE REVEAL: a type hint is a real object stored in a real dictionary.
# ---------------------------------------------------------------------------
def greet(name: str, times: int = 1) -> str:
    return (f"Hello, {name}! " * times).strip()


def demo_annotations_are_data() -> None:
    section("1. A type hint is DATA that lives on the function")

    # Every annotated function carries a __annotations__ dict. The types you
    # wrote are the VALUES in it. They are ordinary Python objects (classes).
    print("greet.__annotations__ =", greet.__annotations__)

    # Because they are just objects, you can pull one out and poke at it:
    name_type = greet.__annotations__["name"]
    print("the annotation for 'name' is the class:", name_type)
    print("is it literally the built-in str class? ->", name_type is str)


# ---------------------------------------------------------------------------
# 2. NOTHING IS ENFORCED: the hint says int, Python does not care.
# ---------------------------------------------------------------------------
def add(a: int, b: int) -> int:
    return a + b


def demo_no_enforcement() -> None:
    section("2. Python does NOT enforce the hint at runtime")

    good = add(2, 3)
    print("add(2, 3) =", good, "-> type:", type(good).__name__)

    # The signature PROMISES int + int -> int. We hand it two strings.
    # Python shrugs, runs '+' on strings (which means concatenation),
    # and hands back a str. The '-> int' was never checked.
    sneaky = add("foo", "bar")
    print("add('foo', 'bar') =", repr(sneaky), "-> type:", type(sneaky).__name__)
    print("The '-> int' was a promise nobody kept, and nobody complained.")


# ---------------------------------------------------------------------------
# 3. THE CHECKER IS A SEPARATE PROGRAM. Python runs broken types happily.
# ---------------------------------------------------------------------------
def broken() -> int:
    # A static type checker (pyright / mypy) flags this line: returning str
    # where int was declared. Python itself runs it without a whisper.
    return "I am clearly not an int"


def demo_checker_is_separate() -> None:
    section("3. The 'compiler' is opt-in and lives OUTSIDE Python")
    print("broken() returned:", repr(broken()), "-> type:", type(broken()).__name__)
    print("To catch this BEFORE running, run a checker in your terminal:")
    print("    uvx pyright p0001_typing.py")
    print("(or let PyCharm underline it). Python alone will never stop you.")


# ---------------------------------------------------------------------------
# 4. THE VOCABULARY: container types are also just objects.
# ---------------------------------------------------------------------------
def demo_vocabulary() -> None:
    section("4. The vocabulary — and it's all inspectable objects too")

    # Modern syntax (Python 3.9+): built-in generics. No 'List', 'Dict' imports.
    scores: list[int] = [90, 85, 100]
    prices: dict[str, float] = {"coffee": 3.5, "tea": 2.0}
    pair: tuple[str, int] = ("age", 30)
    tags: set[str] = {"python", "kotlin"}

    print("scores :", scores, "     hint: list[int]")
    print("prices :", prices, "  hint: dict[str, float]")
    print("pair   :", pair, "        hint: tuple[str, int]")
    print("tags   :", tags, "  hint: set[str]")

    # These generic hints are objects you can hold in a variable and print:
    hint_object = list[int]
    print("\nlist[int] as a value ->", hint_object, " (type:", type(hint_object).__name__, ")")


# ---------------------------------------------------------------------------
# 5. OPTIONAL / UNION / NONE — the type that says "or nothing".
# ---------------------------------------------------------------------------
def find_user(user_id: int) -> str | None:
    """Returns a name, or None if not found. The '| None' MAKES you handle both."""
    known = {1: "Ada", 2: "Linus"}
    return known.get(user_id)  # dict.get returns None when the key is missing


def demo_optional() -> None:
    section("5. `str | None` — unions, and why they force honesty")

    for uid in (1, 99):
        result = find_user(uid)

        # A type checker knows `result` is `str | None` here. To use it as a
        # str you must first PROVE it isn't None. This check "narrows" the type
        # from `str | None` down to `str` inside the if-branch.
        if result is None:
            print(f"user {uid}: not found")
        else:
            print(f"user {uid}: {result.upper()}")  # .upper() is safe now

    # A union is itself a printable object:
    print("\nthe annotation `int | None` is this object ->", int | None)
    print("isinstance(None, int/str | None) ->", isinstance(None, str | None))


# ---------------------------------------------------------------------------
# 6. Any — the escape hatch that turns checking OFF.
# ---------------------------------------------------------------------------
def demo_any() -> None:
    section("6. `Any` — turns the checker off")

    anything: Any = 42
    anything = "now a string"
    anything = [1, 2, 3]
    print("`Any` let this variable be int, str, then list with zero complaints.")
    print("current value:", anything)
    print("Use it as a last resort — it silences your safety net.")


# ---------------------------------------------------------------------------
# 7. TYPE ALIASES & GENERICS (modern 3.12+ syntax) — naming your own types.
# ---------------------------------------------------------------------------
type UserId = int  # a named alias; reads as documentation, checks as `int`


def first[T](items: list[T]) -> T:
    """A generic: whatever element type goes in, that same type comes out.
    Call it with list[str] and the checker knows the result is str."""
    return items[0]


def demo_aliases_and_generics() -> None:
    section("7. Type aliases and generics — vocabulary you invent yourself")

    uid: UserId = 7
    print("UserId is just int wearing a meaningful name:", uid)

    print("first(['a','b','c']) ->", first(["a", "b", "c"]), "(checker infers: str)")
    print("first([10, 20, 30])  ->", first([10, 20, 30]), "(checker infers: int)")


# ---------------------------------------------------------------------------
# 8. THE PAYOFF: build a 12-line 'mini-Pydantic' by READING annotations.
#    This is the whole reason type hints matter for the agent path.
# ---------------------------------------------------------------------------
class Order:
    # These are BARE annotations: names with a declared type but no value.
    # They don't create attributes — they only populate Order.__annotations__.
    order_id: int
    customer: str
    amount: float


def validate(cls: type, data: dict) -> dict:
    """A tiny runtime validator. It reads the class's declared types and
    checks a dict against them. This is EXACTLY the trick Pydantic is built on
    (Pydantic just adds coercion, nesting, errors, speed, and a thousand more)."""
    hints = get_type_hints(cls)  # {'order_id': int, 'customer': str, 'amount': float}
    for field, expected in hints.items():
        value = data.get(field)
        if not isinstance(value, expected):
            got = type(value).__name__
            raise TypeError(f"'{field}' must be {expected.__name__}, got {got}: {value!r}")
    return data


def demo_the_payoff() -> None:
    section("8. THE PAYOFF: frameworks are just READING your annotations")

    print("Order's declared types ->", get_type_hints(Order))

    good = {"order_id": 101, "customer": "Ada", "amount": 9.99}
    print("\nvalidating GOOD data:", good)
    print("  passed ->", validate(Order, good))

    bad = {"order_id": "oops-not-an-int", "customer": "Ada", "amount": 9.99}
    print("\nvalidating BAD data:", bad)
    try:
        validate(Order, bad)
    except TypeError as e:
        print("  rejected ->", e)

    print("\nThat 12-line function is the seed of Pydantic. You now know the trick.")


def main() -> None:
    demo_annotations_are_data()
    demo_no_enforcement()
    demo_checker_is_separate()
    demo_vocabulary()
    demo_optional()
    demo_any()
    demo_aliases_and_generics()
    demo_the_payoff()
    print("\n" + "=" * 70)
    print("Done. Now open docs/p0001_typing.md and read why each block behaves so.")
    print("=" * 70)


if __name__ == "__main__":
    main()
