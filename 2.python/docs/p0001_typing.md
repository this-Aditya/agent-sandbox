# p0001 — Type Hints: types are *notes*, not *rules*

> **Run the code first, then read this.** `uv run p0001_typing.py`
> Each part below matches a numbered block in `p0001_typing.py`.
> Read a part, look at that block's output, change a line, run it again.

---

## The main idea (read this twice)

In Kotlin, a type is a **rule**. The compiler checks it. If you write:

```kotlin
fun add(a: Int, b: Int): Int = a + b
```

and then call `add("foo", "bar")`, your code **will not compile**. The type stops you before the program even runs.

Python is different. In Python, a type hint is **not a rule**. It does not stop anything. It is just a **note**. Python saves that note in a small dictionary attached to your function. The note sits there while the program runs, and any code can read it.

So remember this one line:

> **A type hint in Python does not control your variable. It just writes down a fact about it. That fact is saved as data you can read while the program runs.**

That is the whole lesson. Everything below follows from it.

And here is why you should care. Pydantic, FastAPI, and dataclasses all work by **reading these notes**. There is no magic in them. They just read the dictionary. By section 8, you will write that same trick yourself in 12 lines.

---

## 1. A type hint is data stored on the function

```python
def greet(name: str, times: int = 1) -> str:
    ...
```

When Python creates this function, it builds a small dictionary and attaches it to the function. The dictionary is called `__annotations__`:

```text
{'name': <class 'str'>, 'times': <class 'int'>, 'return': <class 'str'>}
```

Look at the values. They are **not** the text `"str"`. They are the real `str` class — the same `str` you use to make a string. The demo proves it:

```text
is it literally the built-in str class? -> True
```

So the type you wrote is a real object. It sits in a dictionary. Your program can read it any time.

Here is the difference from Kotlin. In Kotlin you **cannot** ask a function "what type is your second parameter?" while the program runs — that information is gone after compiling. In Python you can, in one line. Hold on to this. It is the key to section 8.

---

## 2. Python does not check the hint

```python
def add(a: int, b: int) -> int:
    return a + b

add("foo", "bar")   # -> 'foobar', a str
```

The hint says `int + int -> int`. We pass two strings. Python does **not** check. It just runs `+`. On strings, `+` joins them. So you get back `'foobar'`, which is a `str` — from a function that said it returns `int`:

```text
add('foo', 'bar') = 'foobar' -> type: str
```

No error. No warning. Nothing.

This is the biggest change from Kotlin. Your habit says "the types keep me safe." While the program runs, in Python, **they do not.** Two other things keep you safe: a separate checker tool (section 3), and real checks at the risky spots (section 8).

---

## 3. The checker is a separate program

```python
def broken() -> int:
    return "I am clearly not an int"
```

Run the program. `broken()` returns a string, even though it says `-> int`. Python will never stop this.

So where is your safety? It comes from a **separate tool**. This tool reads your code **without running it**. It reads the notes and tells you where they don't match. The two common tools are **pyright** and **mypy**. Run one over this file (from inside the `2.python` folder):

```bash
uvx pyright p0001_typing.py
```

This file has **3 mistakes left in on purpose** — two in `add("foo", "bar")`, one in `broken()`. The checker finds all three:

```text
:73 - error: Argument of type "Literal['bar']" cannot be assigned to parameter "b" of type "int"
:84 - error: Type "Literal['I am clearly not an int']" is not assignable to return type "int"
3 errors, 0 warnings, 0 informations
```

Read that side by side with the point of this lesson:

- **`uv run p0001_typing.py`** (the program) → runs fine. Python does not care about the types.
- **`uvx pyright p0001_typing.py`** (the checker) → 3 errors. The checker cares a lot.

Same file. Two tools. They disagree. **That disagreement is the whole idea of section 3.**

### `# type: ignore` — how to make the checker quiet

Sometimes you *know* a line is fine but the checker still complains. You silence it by adding a comment at the end of that line:

```python
sneaky = add("foo", "bar")  # type: ignore
```

Now pyright skips that whole line. Try it: add `# type: ignore` to the end of line 73, run pyright again, and watch the count drop from **3 to 1**. (Why 1 and not 2? Line 73 holds *two* mistakes — one for `"foo"`, one for `"bar"` — and the comment silences the entire line at once.) Earlier I had left these comments in the file by default — which is why your first run showed *0 errors*. I took them out so the checker's job is visible. Use `# type: ignore` sparingly: each one is a spot where you turned the safety off.

Think of it this way:

- **Kotlin** puts the checker and the runtime together. You cannot run code with bad types.
- **Python** keeps them apart. The runtime never checks types. A separate tool does — but only if you run it.

So your job is simple: **always run the checker.** You use PyCharm (you have `.idea/` folders). PyCharm runs this checker live — those squiggly underlines are it. Turn them up and trust them.

---

## 4. The words you will actually use

These are the type hints you'll write every day. Modern Python (3.9+) lets you write them directly — no `from typing import List, Dict` needed:

| You write | Means | Kotlin version |
|---|---|---|
| `list[int]` | a list of ints | `List<Int>` |
| `dict[str, float]` | str keys, float values | `Map<String, Double>` |
| `tuple[str, int]` | exactly two slots: a str, then an int | `Pair<String, Int>` |
| `set[str]` | a set of strings | `Set<String>` |

And, just like section 1 said, these are **objects too**. `list[int]` is a value you can store in a variable and print:

```text
list[int] as a value -> list[int]  (type: GenericAlias )
```

Even your container types are just data.

---

## 5. `str | None` — "a string, or nothing"

Many bugs come from one mistake: you expected something to be there, and it wasn't. Python lets you write that possibility right into the type:

```python
def find_user(user_id: int) -> str | None:
    known = {1: "Ada", 2: "Linus"}
    return known.get(user_id)   # .get returns None if the key is missing
```

The return type `str | None` means "a string, **or** nothing (None)." Now watch what the checker makes the caller do:

```python
result = find_user(uid)          # result is: str or None
result.upper()                   # ❌ error: None has no .upper()

if result is None:
    ...                          # here the checker knows: result is None
else:
    result.upper()               # ✅ here it knows: result is a str — safe
```

That move has a name: **narrowing**. When you check `if result is None`, the checker learns that inside the `else` branch the value **cannot** be None. So it drops the "or nothing" part and treats `result` as a plain `str`. Now `.upper()` is allowed.

You already know this idea from Kotlin. `str | None` is the same as Kotlin's `String?`, and narrowing is the same as Kotlin's smart casts. The only difference: Kotlin checks it while compiling, Python checks it with the separate tool from section 3. Same habit for you: **`| None` means "handle the empty case now."**

---

## 6. `Any` — this turns checking off

```python
anything: Any = 42
anything = "now a string"
anything = [1, 2, 3]      # no complaints
```

`Any` means "stop checking this one; I'll take responsibility." It is the escape hatch. Sometimes you need it — for truly mixed data, or while you're still adding types to old code. But every `Any` is a **hole in your safety net.** Treat it like Kotlin's `!!` — sometimes needed, always a small risk. Reach for a real type first, and use `Any` last.

---

## 7. Aliases and generics — make your own words

Two small tools (Python 3.12+, and you're on 3.14, so use them):

**Alias** — give a clearer name to a type you already have:

```python
type UserId = int
uid: UserId = 7          # checks exactly like int, but reads with meaning
```

To the checker, `UserId` is just `int`. To a human, it says *what kind of int this is.* Same idea as a Kotlin type alias.

**Generic** — write one function that keeps the caller's type:

```python
def first[T](items: list[T]) -> T:
    return items[0]
```

`T` means "whatever type goes in, the same type comes out." Pass a `list[str]` and the checker knows you get back a `str`. Pass a `list[int]` and it knows `int`. This is the same as Kotlin's `fun <T> first(items: List<T>): T`. The `[T]` after the name is just the modern way to write it.

---

## 8. The payoff — you already understand Pydantic

Now it all comes together. We make a class with **bare annotations** — names with a type but no value:

```python
class Order:
    order_id: int
    customer: str
    amount: float
```

These lines do **not** create attributes. They do one thing: they fill in `Order.__annotations__` — the same notes dictionary from section 1, now on a class:

```text
Order's declared types -> {'order_id': <class 'int'>, 'customer': <class 'str'>, 'amount': <class 'float'>}
```

Because those types are readable data, we can write a function that **checks real input against them** — putting back the rule that Python left out, but only where it matters:

```python
def validate(cls: type, data: dict) -> dict:
    hints = get_type_hints(cls)                 # read the notes
    for field, expected in hints.items():       # for each declared field...
        value = data.get(field)
        if not isinstance(value, expected):     # ...check the real value's type
            raise TypeError(f"'{field}' must be {expected.__name__}, ...")
    return data
```

Good data passes. Bad data — a string where `order_id` should be an int — is rejected:

```text
validating BAD data: {'order_id': 'oops-not-an-int', ...}
  rejected -> 'order_id' must be int, got str: 'oops-not-an-int'
```

Stop and notice what you just did. In twelve lines, you built a thing that reads a class's declared types and rejects bad input. **That is what Pydantic does.** Pydantic adds a lot on top — it can fix small type mismatches for you, handle nested data, give nice error messages, and run very fast. But the core is exactly your function: **read the notes, then check the data at the edge.**

This is *why* type hints matter for AI agents. When an LLM sends your program some JSON, that JSON is untrusted — the model can get it wrong. Pydantic sits at that spot. It reads the shape you declared and turns messy model output into either a clean, typed object or a clear error. You now know how that works under the hood.

---

## Run it, then break it (this part matters most)

You don't learn this by reading. You learn it by changing the output. Try each one:

1. **See "no checking" (§2):** add `print(add(1.5, 2))` inside `demo_no_enforcement`. You said `int`, you passed a float, and it returns `3.5`. Python doesn't care.
2. **Meet the checker (§3):** run `uvx pyright p0001_typing.py`. It flags the 3 on-purpose mistakes. Now add `# type: ignore` to the end of line 73 and run pyright again — the count drops from 3 to 1 (that one line has two mistakes in it). Then remove the comment and both come back.
3. **Break narrowing (§5):** in `demo_optional`, call `result.upper()` *before* the `if result is None` check. It may still run for `uid=1`, but pyright will now flag it — because `result` might be None there. That red line is a real bug the checker caught for you.
4. **Extend the payoff (§8):** add `shipped: bool` to `Order`, then pass `{"shipped": "yes"}` to `validate`. It gets rejected — and you changed **no validator code**, only added one type. That's the power of types-as-data.

---

## What you now know

- A type hint is **data** (`__annotations__`), not a rule.
- **Python checks nothing at runtime.** A **separate tool** (pyright / mypy / PyCharm) is your checker — keep it on.
- The words: `list[int]`, `dict[str, float]`, `X | None` (with narrowing), `Any` (turns checking off), `type` aliases, `[T]` generics.
- The big one: **frameworks read your type notes.** You proved it by building a mini-Pydantic in 12 lines.

**Next lesson — `p0002`: Pydantic.** We take this same `Order` example and give it to the real Pydantic. You'll watch it do everything your `validate()` did — and then more: fixing small mismatches, handling nested data, and the error messages you'll see all through the rest of the path. You walk in already knowing the trick.
