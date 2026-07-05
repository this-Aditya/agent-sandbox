"""
p0002 — PYDANTIC: the real version of the 12-line validator you built in p0001.

Run me:
    uv run p0002_pydantic.py

Read me with the doc open next to you:
    docs/p0002_pydantic.md

Where we left off in p0001:
    You wrote a tiny function that read a class's type notes (__annotations__)
    and checked a dict against them. That is the whole idea of Pydantic.
    Here is the real library. It does the same thing, then a lot more:
    it converts values when it safely can, checks rules you declare, handles
    nested data, and turns JSON into typed objects and back.

The one idea to remember:
    A Pydantic model is a class where the type notes become REAL rules,
    checked the moment you build an object. Give it good data -> you get a
    clean, typed object. Give it bad data -> you get a clear error, not a
    silent bug. That is exactly what you want at the edge where an LLM hands
    you JSON.
"""

from pydantic import BaseModel, Field, ValidationError, field_validator


def section(title: str) -> None:
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


# ---------------------------------------------------------------------------
# 1. THE SAME `Order`, now a real Pydantic model.
#    In p0001 the type notes did nothing on their own. Add `BaseModel` and
#    those same notes become rules that run when you build the object.
# ---------------------------------------------------------------------------
class Order(BaseModel):
    order_id: int
    customer: str
    amount: float


def demo_basic_model() -> None:
    section("1. A model validates the moment you build it")

    order = Order(order_id=101, customer="Ada", amount=9.99)
    print("built:", order)
    print("typed access ->  order.customer =", order.customer)
    print("order.amount is a real float ->", order.amount, type(order.amount).__name__)


# ---------------------------------------------------------------------------
# 2. BAD DATA -> a clear, structured error (not a silent bug).
# ---------------------------------------------------------------------------
def demo_validation_error() -> None:
    section("2. Bad data raises ValidationError — and it's readable")

    try:
        Order(order_id="not-a-number", customer="Ada", amount="free")
    except ValidationError as e:
        print("Pydantic refused to build the object. It reported:")
        print(e)
        # .errors() gives you the SAME info as structured data you can log,
        # show in an API response, or feed back to an LLM to self-correct.
        print("\nas structured data (e.errors()):")
        for err in e.errors():
            print(f"  field={err['loc']}  problem={err['type']}  msg={err['msg']}")


# ---------------------------------------------------------------------------
# 3. COERCION — the big upgrade over your isinstance() check.
#    Your p0001 validator REJECTED the string "101" for an int field.
#    Pydantic instead CONVERTS it when the conversion is safe and obvious.
# ---------------------------------------------------------------------------
def demo_coercion() -> None:
    section("3. Coercion: Pydantic converts when it safely can")

    # "101" is a string, but it clearly means the number 101 -> Pydantic converts.
    o = Order(order_id="101", customer="Ada", amount=10)
    print('Order(order_id="101", amount=10) ->')
    print("  order_id became:", o.order_id, "(", type(o.order_id).__name__, ")  <- str turned into int")
    print("  amount became  :", o.amount, "(", type(o.amount).__name__, ")  <- int turned into float")

    # But nonsense is still refused. Coercion is helpful, not reckless.
    try:
        Order(order_id="oops", customer="Ada", amount=1.0)
    except ValidationError as e:
        print('\nOrder(order_id="oops", ...) -> refused:', e.errors()[0]["msg"])

    print("\n(This 'convert when safe' behavior matters a lot for LLM output,")
    print(" where a model may return \"5\" as a string instead of the number 5.)")


# ---------------------------------------------------------------------------
# 4. DEFAULTS & OPTIONAL FIELDS — a field with a default is optional.
# ---------------------------------------------------------------------------
class User(BaseModel):
    name: str                      # required — no default
    age: int = 0                   # optional — defaults to 0
    email: str | None = None       # optional — may be missing (None), see p0001 §5


def demo_defaults() -> None:
    section("4. Defaults and optional fields")

    u = User(name="Ada")           # only the required field
    print("User(name='Ada') ->", u)
    print("age used its default:", u.age, "  email used its default:", u.email)

    u2 = User(name="Linus", age=54, email="linus@example.com")
    print("fully specified     ->", u2)


# ---------------------------------------------------------------------------
# 5. FIELD CONSTRAINTS — declare RULES, not just types.
#    Field(...) lets you say "int, AND greater than 0", "str, AND not empty".
# ---------------------------------------------------------------------------
class Product(BaseModel):
    name: str = Field(min_length=1)         # non-empty name
    price: float = Field(gt=0)              # strictly greater than 0
    quantity: int = Field(ge=0, le=1000)    # between 0 and 1000 inclusive


def demo_constraints() -> None:
    section("5. Field(...) constraints — rules beyond the type")

    good = Product(name="Coffee", price=3.5, quantity=10)
    print("valid product ->", good)

    try:
        Product(name="", price=-2, quantity=5000)   # breaks all three rules
    except ValidationError as e:
        print(f"\ninvalid product -> {len(e.errors())} rules broken:")
        for err in e.errors():
            print(f"  {err['loc'][0]}: {err['msg']}")


# ---------------------------------------------------------------------------
# 6. NESTED MODELS — models inside models, validated all the way down.
# ---------------------------------------------------------------------------
class Address(BaseModel):
    street: str
    city: str


class Customer(BaseModel):
    name: str
    address: Address               # a field whose type is another model


def demo_nested() -> None:
    section("6. Nested models — validated all the way down")

    # You can pass a plain dict for the nested part; Pydantic turns it into
    # an Address and validates it too.
    c = Customer(name="Ada", address={"street": "1 Byte Rd", "city": "London"})
    # c = Customer(name="Ada", address=Address(street="1 Byte Rd", city="London"))
    print("built nested object ->", c)
    print("c.address is a real Address model ->", type(c.address).__name__)
    print("reach in with dots  -> c.address.city =", c.address.city)

    # A broken nested value is caught, and the error path points right at it.
    try:
        Customer(name="Ada", address={"street": "1 Byte Rd"})   # missing 'city'
    except ValidationError as e:
        print("\nbroken nested value -> error path:", e.errors()[0]["loc"])


# ---------------------------------------------------------------------------
# 7. THE JSON BRIDGE — the whole reason Pydantic matters for AI agents.
#    An LLM returns a JSON *string*. One call turns it into a typed object.
# ---------------------------------------------------------------------------
def demo_json_bridge() -> None:
    section("7. The JSON bridge — LLM text in, typed object out")

    # Pretend this string just came back from an LLM tool call:
    llm_output = '{"order_id": "5005", "customer": "Ada", "amount": "19.99"}'
    print("raw text from the 'LLM':", llm_output)

    # One call: parse the JSON AND validate it in the declared shape.
    order = Order.model_validate_json(llm_output)
    print("-> validated object:", order, "(order_id is now int:", type(order.order_id).__name__, ")")

    # And back out again, for storing or sending over the wire:
    print("\nback to a dict  (model_dump)      ->", order.model_dump())
    print("back to JSON    (model_dump_json) ->", order.model_dump_json())

    # If the LLM returns garbage, you get a clean error instead of a bad object.
    bad_llm_output = '{"order_id": "abc", "customer": "Ada", "amount": "19.99"}'
    try:
        Order.model_validate_json(bad_llm_output)
    except ValidationError as e:
        print("\nbad LLM output was rejected:", e.errors()[0]["msg"])


# ---------------------------------------------------------------------------
# 8. YOUR OWN RULE — @field_validator for checks Field(...) can't express.
# ---------------------------------------------------------------------------
class Signup(BaseModel):
    username: str
    password: str

    @field_validator("password")
    @classmethod
    def password_must_be_strong(cls, value: str) -> str:
        # Runs during validation. Return the (possibly cleaned) value, or raise.
        if len(value) < 8:
            raise ValueError("password must be at least 8 characters")
        return value


def demo_custom_validator() -> None:
    section("8. @field_validator — write your own rule")

    ok = Signup(username="ada", password="supersecret")
    print("strong password accepted ->", ok.username, "/", "*" * len(ok.password))

    try:
        Signup(username="ada", password="123")
    except ValidationError as e:
        print("weak password rejected  ->", e.errors()[0]["msg"])


def main() -> None:
    demo_basic_model()
    demo_validation_error()
    demo_coercion()
    demo_defaults()
    demo_constraints()
    demo_nested()
    demo_json_bridge()
    demo_custom_validator()
    print("\n" + "=" * 70)
    print("Done. Open docs/p0002_pydantic.md to read why each block behaves so.")
    print("=" * 70)


if __name__ == "__main__":
    main()
