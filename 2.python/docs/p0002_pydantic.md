# p0002 — Pydantic: type notes that become real rules

> **Run the code first, then read this.** `uv run p0002_pydantic.py`
> Each part below matches a numbered block in `p0002_pydantic.py`.
> Read a part, look at that block's output, change a line, run it again.

---

## The main idea (read this twice)

In lesson 1 you learned: a type hint is just a **note**. Python saves it but never checks it. At the very end (§8) you wrote a small function that **read those notes and checked a dict against them**. That was a toy version of Pydantic.

Now here is the real thing. You take a normal class, make it inherit from `BaseModel`, and something changes:

> **In a Pydantic model, the type notes stop being just notes. They become real rules, checked the moment you build the object. Good data gives you a clean, typed object. Bad data gives you a clear error — not a silent bug.**

That is the whole library. Everything below is that one idea, plus convenience.

**Kotlin bridge:** a Pydantic model is very close to a Kotlin `data class`. You get typed fields, a nice `toString`, and equality — the same as Kotlin. But Pydantic adds two things a Kotlin data class does not: it **checks the data at runtime** when you build the object, and it can turn objects **to and from JSON** in one call. Those two extras are exactly what you need when an LLM hands you a blob of JSON you cannot trust.

---

## 1. The same `Order`, now a real model

```python
class Order(BaseModel):
    order_id: int
    customer: str
    amount: float

order = Order(order_id=101, customer="Ada", amount=9.99)
```

Notice: **same three lines** as the `Order` in lesson 1. The only change is `(BaseModel)`. That one word switches on all the checking.

Building the object runs the rules right away. Then you use it like any normal object, with real typed fields:

```text
built: order_id=101 customer='Ada' amount=9.99
typed access ->  order.customer = Ada
order.amount is a real float -> 9.99 float
```

`order.customer` gives you a `str`, `order.amount` gives you a `float`. Your editor and pyright know these types too, so you get autocomplete and checking — just like a Kotlin data class.

---

## 2. Bad data raises a clear error

```python
Order(order_id="not-a-number", customer="Ada", amount="free")
```

`order_id` should be an int, `amount` should be a float. Both are wrong here. Pydantic refuses to build the object and raises a `ValidationError`:

```text
2 validation errors for Order
order_id
  Input should be a valid integer, unable to parse string as an integer ...
amount
  Input should be a valid number, unable to parse string as a number ...
```

Look closely: it found **both** problems, not just the first one. Your toy validator in lesson 1 stopped at the first bad field. Pydantic collects **all** the errors in one go. That is a big deal in practice — you can show a user every problem at once, or hand the full list back to an LLM so it fixes everything in one retry.

You can also read the errors as **structured data** instead of text:

```python
for err in e.errors():
    print(err["loc"], err["type"], err["msg"])
```
```text
field=('order_id',)  problem=int_parsing  msg=Input should be a valid integer...
field=('amount',)    problem=float_parsing msg=Input should be a valid number...
```

`e.errors()` is a plain list of dicts. That is what you log, or return from an API, or feed back to a model. This is one reason Pydantic runs the whole agent world: its errors are machine-readable, not just human-readable.

---

## 3. Coercion — the big upgrade over your lesson-1 check

This is the most important difference from the toy validator, so slow down here.

Your lesson-1 validator used `isinstance`. It asked "is this value *already* an int?" So it **rejected** the string `"101"`. Pydantic is smarter. It asks "can I *safely turn* this into an int?" — and if yes, it **converts** it for you:

```python
Order(order_id="101", customer="Ada", amount=10)
```
```text
order_id became: 101 ( int )    <- the string "101" turned into the int 101
amount became  : 10.0 ( float ) <- the int 10 turned into the float 10.0
```

This is called **coercion** (Pydantic converting a value into the declared type). But it is careful, not reckless. Real nonsense is still refused:

```text
Order(order_id="oops", ...) -> refused: Input should be a valid integer...
```

**Why this matters so much for AI agents:** an LLM often returns numbers as **strings** — it gives you `"5"` when you wanted `5`, or `"19.99"` when you wanted `19.99`. Your toy validator would have rejected all of that. Pydantic quietly fixes it, so the model's slightly-messy output still becomes a clean typed object. You will lean on this constantly.

> **Note:** this "convert when safe" behavior is the default (called *lax* mode). If you ever want the strict `isinstance`-style behavior — "reject `"101"`, I want a real int only" — Pydantic has a **strict** mode (`Field(strict=True)`, or `Order.model_validate(data, strict=True)`). Default lax is usually what you want for LLM data.

---

## 4. Defaults and optional fields

```python
class User(BaseModel):
    name: str                    # required — no default
    age: int = 0                 # optional — defaults to 0
    email: str | None = None     # optional — may be missing (None)
```

The rule is simple: **a field with a default value is optional.** A field without one is required.

```text
User(name='Ada') -> name='Ada' age=0 email=None
```

We only passed `name`. `age` fell back to `0`, and `email` fell back to `None`.

Look at `email: str | None = None` carefully, because it has **two** separate parts:

- `str | None` is the **type** — "a string, or nothing." (This is the `| None` from lesson 1, §5.)
- `= None` is the **default** — "if it's missing, use None."

You need both to say "this field is optional and may simply not be there." A common beginner mistake is writing `email: str | None` with no `= None` — that still makes it **required** (you must pass it, even if you pass `None`). The default is what makes it skippable.

---

## 5. `Field(...)` — rules beyond the type

Types say "this is an int." Often you want more: "an int, **and** greater than zero." That extra rule goes in `Field(...)`:

```python
class Product(BaseModel):
    name: str = Field(min_length=1)       # not empty
    price: float = Field(gt=0)            # greater than 0
    quantity: int = Field(ge=0, le=1000)  # between 0 and 1000
```

Break all three at once and Pydantic reports all three:

```text
invalid product -> 3 rules broken:
  name: String should have at least 1 character
  price: Input should be greater than 0
  quantity: Input should be less than or equal to 1000
```

The common constraints (they read like their math symbols):

| In `Field(...)` | Means |
|---|---|
| `gt=0` / `ge=0` | greater than / greater-or-equal |
| `lt=100` / `le=100` | less than / less-or-equal |
| `min_length=1` / `max_length=50` | for strings and lists |
| `pattern=r"..."` | string must match a regex |

This is **declarative** validation: you *describe* the rule next to the field, and Pydantic enforces it. You don't write `if price <= 0: raise ...` by hand.

---

## 6. Nested models — validated all the way down

A model field can be *another model*:

```python
class Address(BaseModel):
    street: str
    city: str

class Customer(BaseModel):
    name: str
    address: Address        # a field that is itself a model
```

You can hand it a plain dict for the nested part, and Pydantic turns that dict into a real `Address` and checks it too:

```python
Customer(name="Ada", address={"street": "1 Byte Rd", "city": "London"})
```
```text
built nested object -> name='Ada' address=Address(street='1 Byte Rd', city='London')
c.address is a real Address model -> Address
reach in with dots  -> c.address.city = London
```

And if something deep inside is wrong, the error tells you the **exact path** to it:

```text
broken nested value -> error path: ('address', 'city')
```

`('address', 'city')` means "the `city` field, inside the `address` field." Real LLM output is often nested like this (an order with a list of line items, each with a product). Pydantic checks the whole tree and points straight at any bad leaf.

---

## 7. The JSON bridge — the whole reason this matters for agents

This is the section to remember. An LLM does not hand you a Python object. It hands you a **JSON string** — plain text. Pydantic crosses that gap in one call.

```python
llm_output = '{"order_id": "5005", "customer": "Ada", "amount": "19.99"}'
order = Order.model_validate_json(llm_output)
```
```text
-> validated object: order_id=5005 customer='Ada' amount=19.99 (order_id is now int)
```

One line did **two** jobs: it parsed the JSON text, *and* it validated it into your `Order` shape. Notice coercion (§3) also kicked in — `"5005"` and `"19.99"` were strings in the JSON, and came out as a real `int` and `float`.

Going the other way, for saving to a database or sending over the network:

```text
back to a dict  (model_dump)      -> {'order_id': 5005, 'customer': 'Ada', 'amount': 19.99}
back to JSON    (model_dump_json) -> {"order_id":5005,"customer":"Ada","amount":19.99}
```

And if the model returns junk, you get a clean error instead of a broken object silently flowing downstream:

```text
bad LLM output was rejected: Input should be a valid integer...
```

The four calls you will use all the time:

| Call | Direction | Input |
|---|---|---|
| `Model.model_validate(d)` | in | a Python `dict` |
| `Model.model_validate_json(s)` | in | a JSON **string** |
| `obj.model_dump()` | out | to a `dict` |
| `obj.model_dump_json()` | out | to a JSON **string** |

> **Names note:** these are the Pydantic **v2** names (you have v2). Old tutorials use `.dict()` and `.json()` and `.parse_obj()` — those are the v1 names, now deprecated. Use the `model_*` ones.

**This four-call bridge is the pattern for the whole rest of your path:** the LLM produces JSON → `model_validate_json` turns it into a typed, checked object (or a clear error you can handle or retry) → your code works with clean typed data. That single move is why the roadmap calls Pydantic the most important library after the LLM SDK itself.

---

## 8. `@field_validator` — write your own rule

`Field(...)` covers common rules. For anything custom, you write a small method:

```python
class Signup(BaseModel):
    username: str
    password: str

    @field_validator("password")
    @classmethod
    def password_must_be_strong(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("password must be at least 8 characters")
        return value
```

Pydantic runs this method during validation, passing the field's value. You either **return** the value (optionally cleaned up — e.g. trimmed or lowercased) or **raise `ValueError`** to reject it:

```text
strong password accepted -> ada / ***********
weak password rejected  -> Value error, password must be at least 8 characters
```

Two small things to notice:
- The `@classmethod` line under `@field_validator` is required — the validator gets the class (`cls`), not an instance, because the object doesn't exist yet (you're still building it).
- Your `raise ValueError(...)` shows up as a normal Pydantic error, right alongside the built-in ones. Your custom rules and Pydantic's rules live in the same error list.

---

## Run it, then break it (this part matters most)

1. **Feel coercion's edge (§3):** in `demo_coercion`, try `Order(order_id=1.5, customer="Ada", amount=1.0)`. A whole number like `2.0` may convert to an int, but `1.5` has a fraction and gets rejected — Pydantic won't silently throw away your `.5`.
2. **Watch errors pile up (§2):** add a fourth bad field or make `customer` a number too, and see the error count grow. Pydantic reports every problem in one run.
3. **Tighten a rule (§5):** change `price: float = Field(gt=0)` to `Field(gt=100)`, then build a `Product` with `price=3.5`. Watch the new rule fire.
4. **Break the JSON (§7):** in `demo_json_bridge`, delete `"customer": "Ada",` from `llm_output` and re-run. The error path will point right at the missing field — exactly what you'd send back to the LLM to fix.
5. **Add your own rule (§8):** add a `@field_validator("username")` that rejects names shorter than 3 characters. You just extended validation with a few lines.

---

## What you now know

- A **Pydantic model** = a class where type notes become **real rules**, checked when you build the object.
- Bad data → a **ValidationError** that lists **every** problem, as readable text *and* machine-readable `e.errors()`.
- **Coercion:** Pydantic **converts** safe values (`"101"` → `101`) instead of rejecting them — vital for messy LLM output. (Strict mode exists if you don't want this.)
- **Defaults** make fields optional; `str | None = None` = "a string, or nothing, and it may be missing."
- **`Field(...)`** adds rules (`gt`, `min_length`, ...); **nested models** validate all the way down and point at the exact bad field.
- **The JSON bridge** (`model_validate_json` / `model_dump_json`) turns LLM text into typed objects and back. This is the pattern you'll use for the rest of the path.
- **`@field_validator`** lets you write any custom rule.

**Next lesson — `p0003`: the environment and packaging (`uv`, `.venv`, `pyproject.toml`).** You've been running `uv run` and `uv add` on faith. Next we open the hood: why virtual environments exist at all (a problem the JVM solves differently), what `uv` actually does when you type those commands, and how `pyproject.toml` maps to the `build.gradle` you already know.

*(One thing you already did in this lesson without noticing: `uv add pydantic` edited your `pyproject.toml` and `uv.lock` for you. We'll explain exactly what happened there.)*
