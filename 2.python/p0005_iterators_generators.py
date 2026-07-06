"""
p0005 — ITERATORS, GENERATORS, COMPREHENSIONS: root to leaf.

Run me:
    uv run p0005_iterators_generators.py

Read me with the doc open next to you:
    docs/p0005_iterators_generators.md

We start at the ROOT — what a `for` loop actually IS — and grow to the LEAF:
LLM token streaming. The path:

    1. What `for` really does: iter() + next() + StopIteration   (the root)
    2. Iterable vs Iterator — two different things people confuse
    3. Build your own iterator (the protocol from the inside)
    4. Generators — the easy way to make an iterator (`yield`)
    5. Laziness & memory — the real payoff (infinite/huge sequences, tiny memory)
    6. `yield` hands back VALUES  (vs async's `await` handing back CONTROL)
    7. Comprehensions (eager) vs generator expressions (lazy)
    8. The payoff: STREAMING — sync generator, then async generator = llm.astream()

The one idea to remember:
    Python never loops a collection "directly". It always asks for an ITERATOR
    and pulls values one at a time with next() until StopIteration. A GENERATOR
    is just the easy way to build such a producer — a function that PAUSES at
    `yield`, hands back one value, and resumes on the next pull. That laziness
    (one value at a time, made on demand) is what makes streaming possible.
"""

import sys
import time
import asyncio


def section(title: str) -> None:
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


# ===========================================================================
# 1. THE ROOT: what a `for` loop REALLY does.
#    `for x in xs:` is not magic. It is exactly: get an iterator with iter(xs),
#    then call next() over and over until it raises StopIteration.
# ===========================================================================
def demo_for_internals() -> None:
    section("1. What a `for` loop REALLY is (iter + next + StopIteration)")

    fruits = ["apple", "banana", "cherry"]
    print("Running a `for` loop BY HAND over", fruits)

    it = iter(fruits)                     # step 1: ask the collection for an iterator
    print("  iter(fruits) ->", it)
    while True:
        try:
            item = next(it)               # step 2: pull the next value
        except StopIteration:             # step 3: this signal means "no more values"
            print("  next() raised StopIteration -> the loop ends here")
            break
        print("  next(it) ->", item)

    print("\n`for x in fruits:` does EXACTLY the three steps above, hidden for you.")


# ===========================================================================
# 2. ITERABLE vs ITERATOR — the distinction that clears up everything.
# ===========================================================================
def demo_iterable_vs_iterator() -> None:
    section("2. Iterable vs Iterator — two different things")

    nums = [10, 20, 30]

    # A list is ITERABLE: you can get an iterator FROM it.
    print("iter(nums) works ->", iter(nums), " (a list is ITERABLE)")

    # But a list is NOT itself an iterator: you cannot next() a list directly.
    try:
        next(nums)
    except TypeError as e:
        print("next(nums) FAILS ->", e, " (a list is not its own iterator)")

    # The iterator you get from it DOES support next():
    it = iter(nums)
    print("next() on the iterator ->", next(it), next(it), next(it))

    # An ITERATOR is single-use / exhaustible — once drained, it's empty:
    it2 = iter(nums)
    print("\nfirst pass  over the iterator:", list(it2))
    print("second pass over the SAME one :", list(it2), " <- empty! it's used up")

    # But the LIST (the iterable) is reusable — each `for` asks for a fresh iterator:
    print("looping the LIST again        :", list(nums), " <- reusable")


# ===========================================================================
# 3. BUILD YOUR OWN ITERATOR — the protocol is just two methods.
# ===========================================================================
class Countdown:
    def __init__(self, start: int) -> None:
        self.n = start

    def __iter__(self):                   # "how to get an iterator from me": it's me
        return self

    def __next__(self):                   # "give the next value, or say we're done"
        if self.n <= 0:
            raise StopIteration
        value = self.n
        self.n -= 1
        return value


def demo_custom_iterator() -> None:
    section("3. Build your own iterator (the protocol from the inside)")

    print("Countdown(3) in a for-loop ->", end=" ")
    for n in Countdown(3):
        print(n, end=" ")
    print("\nThat's the whole protocol: __iter__ (get the iterator) and")
    print("__next__ (produce a value, or raise StopIteration). `for` calls these.")


# ===========================================================================
# 4. GENERATORS — the easy way to make an iterator, using `yield`.
# ===========================================================================
def countdown_gen(start: int):
    n = start
    while n > 0:
        yield n                           # PAUSE, hand back one value, resume on next pull
        n -= 1


def demo_generator() -> None:
    section("4. Generators — the easy way to make an iterator (`yield`)")

    print("Calling countdown_gen(3) runs NOTHING — it's lazy:")
    g = countdown_gen(3)
    print("  type:", type(g).__name__, " (a generator IS an iterator)")
    print("  next(g):", next(g))          # 3
    print("  next(g):", next(g))          # 2
    print("  a for-loop takes the rest ->", end=" ")
    for n in g:                           # continues from where next() left off -> 1
        print(n, end=" ")
    print("\nSame 3,2,1 as the CLASS in section 3 — but 3 lines, no class.")
    print("(This `yield` pause/resume is the SAME machinery as brew_gen in p0004.)")


# ===========================================================================
# 5. LAZINESS & MEMORY — the real payoff.
# ===========================================================================
def naturals():
    n = 1
    while True:                           # INFINITE: impossible as a list, fine here
        yield n
        n += 1


def demo_laziness() -> None:
    section("5. Laziness & memory — the real payoff")

    print("An INFINITE generator. Take the first 5 with a break:")
    first5 = []
    for x in naturals():
        first5.append(x)
        if len(first5) == 5:
            break
    print("  first 5 ->", first5, " (it never built an infinite list)")

    # A list HOLDS every value in memory. A generator holds none until asked.
    big_list = [x for x in range(1_000_000)]     # builds 1,000,000 ints right now
    big_gen = (x for x in range(1_000_000))      # builds NOTHING yet
    print(f"\n  list of 1,000,000 ints : {sys.getsizeof(big_list):>10,} bytes")
    print(f"  generator expression   : {sys.getsizeof(big_gen):>10,} bytes  <- tiny, constant")
    print("  The generator produces each value on demand, one at a time.")


# ===========================================================================
# 6. `yield` HANDS BACK VALUES — vs async's `await` handing back CONTROL.
# ===========================================================================
def greet_each(names):
    for name in names:
        yield f"Hello, {name}!"           # hand a VALUE to whoever loops us


def demo_yield_values() -> None:
    section("6. `yield` hands back VALUES (vs async `await` hands back CONTROL)")

    for msg in greet_each(["Ada", "Linus"]):
        print("  got:", msg)

    print("\nSame pause/resume frame trick as an async coroutine — different PURPOSE:")
    print("  - generator: pauses to HAND BACK A VALUE to a for-loop / next().")
    print("  - coroutine: pauses to WAIT ON I/O, handing CONTROL to the event loop.")
    print("  `yield` = give a value.   `await` = wait for something.")


# ===========================================================================
# 7. COMPREHENSIONS (eager) vs GENERATOR EXPRESSIONS (lazy).
# ===========================================================================
def demo_comprehensions() -> None:
    section("7. Comprehensions (eager) vs generator expressions (lazy)")

    squares_list = [x * x for x in range(5)]     # [] = LIST comprehension  (eager)
    squares_gen = (x * x for x in range(5))      # () = GENERATOR expression (lazy)
    print("list comp [x*x ...] ->", squares_list, " (computed now, all in memory)")
    print("gen expr  (x*x ...) ->", squares_gen, " (nothing computed yet)")
    print("  now consume the gen expr ->", list(squares_gen))

    names = ["Ada", "Linus", "Grace"]
    lengths = {name: len(name) for name in names}   # {k: v} = DICT comprehension
    initials = {name[0] for name in names}          # {x}    = SET comprehension
    print("\ndict comprehension {name: len} ->", lengths)
    print("set  comprehension {name[0]}    ->", initials)
    print("\nRule:  [] eager list  ·  () lazy generator  ·  {k:v} dict  ·  {x} set")


# ===========================================================================
# 8. THE PAYOFF: STREAMING. Tokens one at a time, as they are produced.
# ===========================================================================
def stream_tokens(sentence: str):
    for word in sentence.split():
        time.sleep(0.12)                  # pretend each token takes time to generate
        yield word


def demo_streaming_sync() -> None:
    section("8a. The payoff: STREAMING — tokens as they arrive (sync generator)")

    print("A fake LLM 'streaming' its answer word by word:")
    print("  ", end="", flush=True)
    for token in stream_tokens("you see each token the moment it is produced"):
        print(token + " ", end="", flush=True)
    print("\n  You handled each token AS IT ARRIVED — no waiting for the full reply.")


async def astream_tokens(sentence: str):
    for word in sentence.split():
        await asyncio.sleep(0.12)         # async wait between tokens
        yield word                        # ASYNC generator = `async def` + `yield`


async def demo_streaming_async() -> None:
    section("8b. Real LLM streaming = an ASYNC generator (consumed with `async for`)")

    print("This is exactly the shape of `async for chunk in llm.astream(...)`:")
    print("  ", end="", flush=True)
    async for token in astream_tokens("generators plus async equals streaming"):
        print(token + " ", end="", flush=True)
    print("\n  Lesson 5 (generators) + Lesson 4 (async) = async generators = streaming.")


def main() -> None:
    demo_for_internals()
    demo_iterable_vs_iterator()
    demo_custom_iterator()
    demo_generator()
    demo_laziness()
    demo_yield_values()
    demo_comprehensions()
    demo_streaming_sync()
    asyncio.run(demo_streaming_async())
    print("\n" + "=" * 70)
    print("Done. Open docs/p0005_iterators_generators.md — root to leaf.")
    print("=" * 70)


if __name__ == "__main__":
    main()
