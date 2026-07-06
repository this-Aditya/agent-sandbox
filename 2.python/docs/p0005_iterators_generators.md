# p0005 — Iterators, Generators, Comprehensions: root to leaf

> **Run the code first, then read this.** `uv run p0005_iterators_generators.py`
> Each part below matches a numbered block in `p0005_iterators_generators.py`.
> We start at the root — what a `for` loop *is* — and grow to the leaf: LLM streaming.

---

## The root question nobody asks

You've written `for x in something:` a hundred times. But what does it *actually do*? It feels like magic — "just give me each item." It is not magic, and once you see the machine underneath, generators and streaming stop being mysterious.

> **Python never loops a collection "directly." It always asks the collection for an *iterator* — a little producer object — and then pulls values out of it one at a time with `next()`, until the producer signals "no more."**

That one sentence is the root. Everything in this lesson is a branch off it.

---

## 1. What a `for` loop really is

A `for` loop is exactly three steps, done for you:

```python
it = iter(fruits)          # 1. ask the collection for an iterator
while True:
    try:
        item = next(it)    # 2. pull the next value
    except StopIteration:  # 3. this exception is the "no more values" signal
        break
    ...                    #    (loop body runs with `item`)
```

The program runs this by hand and it behaves identically to a normal `for`:

```text
  iter(fruits) -> <list_iterator object at 0x...>
  next(it) -> apple
  next(it) -> banana
  next(it) -> cherry
  next() raised StopIteration -> the loop ends here
```

Two things worth pausing on:

- **`iter(x)`** gives you an *iterator* — a separate little object whose only job is to remember "where am I" and hand you the next value.
- **`StopIteration`** is unusual: it's an **exception used as a signal.** When the iterator has nothing left, it *raises* `StopIteration`, and the `for` loop quietly catches it and stops. You normally never see it — the loop hides it. (You saw it earlier too: a generator raises it when it finishes.)

So `for` = `iter` + `next` until `StopIteration`. Remember that and the rest follows.

---

## 2. Iterable vs Iterator — the distinction that fixes everything

People use these two words interchangeably. They are **different**, and the difference explains a lot of "why did my loop behave weirdly" bugs.

- An **iterable** is anything you can get an iterator *from* — it has an `__iter__` method. A list, a dict, a string, a file: all iterable.
- An **iterator** is the producer itself — it has a `__next__` method, remembers its position, and is **used up once you drain it.**

The program proves the split:

```text
iter(nums) works -> <list_iterator ...>            (a list is ITERABLE)
next(nums) FAILS -> 'list' object is not an iterator   (a list is NOT an iterator)
next() on the iterator -> 10 20 30
```

A list is iterable but is *not its own iterator* — you can't `next()` a list. You must first get an iterator from it with `iter()`.

And here's the behavior that trips people up — **an iterator is single-use:**

```text
first pass  over the iterator: [10, 20, 30]
second pass over the SAME one : []             <- empty! it's used up
looping the LIST again        : [10, 20, 30]   <- reusable
```

Why? Because an **iterator holds a position.** Once it has walked to the end, there's nothing behind it and it does not reset. A **list has no position** — each time you loop it, `for` calls `iter()` again and gets a *fresh* iterator starting at the beginning. That's why you can loop a list forever but an iterator only once.

> This matters in real code: if you save a generator (an iterator) and loop it twice, the second loop gets nothing. If you need to reuse the values, turn it into a list first.

---

## 3. Building your own iterator — the protocol from inside

The whole protocol is just **two methods**. `Countdown` implements them:

```python
class Countdown:
    def __init__(self, start): self.n = start
    def __iter__(self):  return self        # "the iterator for me is... me"
    def __next__(self):                     # "give the next value, or signal done"
        if self.n <= 0:
            raise StopIteration
        value = self.n
        self.n -= 1
        return value
```

```text
Countdown(3) in a for-loop -> 3 2 1
```

When you write `for n in Countdown(3):`, Python calls `__iter__` to get the iterator, then `__next__` repeatedly until it raises `StopIteration`. That's it — implement those two methods and *any* object becomes loopable. Files, database cursors, API paginators are all just clever `__next__` implementations.

---

## 4. Generators — the easy way to make an iterator

Writing that class is a lot of ceremony for "count down." A **generator** does the same thing in three lines. Any function that uses **`yield`** is a generator:

```python
def countdown_gen(start):
    n = start
    while n > 0:
        yield n            # PAUSE, hand back one value, resume here on the next pull
        n -= 1
```

```text
Calling countdown_gen(3) runs NOTHING — it's lazy:
  type: generator  (a generator IS an iterator)
  next(g): 3
  next(g): 2
  a for-loop takes the rest -> 1
```

Notice three things, all of which you *already saw in p0004*:

1. **Calling it runs nothing.** `countdown_gen(3)` builds a generator object and freezes; the body hasn't started. (Same as calling a coroutine.)
2. **It IS an iterator.** It has `__next__` built in, so `next(g)` works, and so does `for n in g`.
3. **`yield` is a pause point.** `next(g)` runs the body until the next `yield`, hands back that value, and freezes again — remembering `n` and its position. This is the **exact same frame-suspension machinery** as `brew_gen` and coroutines from p0004: the generator's frame (its locals + current line) lives in a heap object and is resumed on each `next()`.

So a generator is simply: *a pausable function that hands back a value each time you pull it.* You get an iterator for free, without writing a class.

---

## 5. Laziness and memory — the real payoff

This is *why* generators matter, not just that they're shorter.

A generator is **lazy**: it computes each value only when you pull it, and holds nothing else. Two powers come from that.

**Power 1 — infinite sequences.** You can't build an infinite list (it would never finish and would eat all memory). A generator can *describe* one, and you take only what you need:

```text
An INFINITE generator. Take the first 5 with a break:
  first 5 -> [1, 2, 3, 4, 5]  (it never built an infinite list)
```

`naturals()` says "1, 2, 3, …forever," but it only ever produces the 5 values you actually pulled.

**Power 2 — tiny, constant memory.** A list holds *every* value at once. A generator holds *none* until asked. The size difference is not subtle:

```text
  list of 1,000,000 ints :  8,448,728 bytes
  generator expression   :        200 bytes  <- tiny, constant
```

The list is ~8 **megabytes**. The generator is 200 **bytes** — and it stays ~200 bytes whether it produces a thousand values or a trillion, because it makes them one at a time and forgets each after you take it. This is how you process a 10 GB file, or an endless stream of tokens, on a laptop: never hold it all at once.

---

## 6. `yield` hands back values — vs `await` handing back control

You now know two things that pause: generators (`yield`) and coroutines (`await`). They use the **same underlying frame machinery**, so it's worth stating their *difference* crisply, because it locks in both:

```text
  - generator: pauses to HAND BACK A VALUE to a for-loop / next().
  - coroutine: pauses to WAIT ON I/O, handing CONTROL to the event loop.
  `yield` = give a value.   `await` = wait for something.
```

- A **generator** pauses because it has *produced something* and wants to hand it to whoever is looping it. The consumer (a `for` loop) drives it by pulling.
- A **coroutine** pauses because it is *waiting on something slow* and wants to let other work run. The event loop drives it by resuming when the wait is over.

Same "freeze the frame, continue later" trick (p0004). Different reason for freezing: *give a value* vs *wait for one*. Keep those two verbs — **give** vs **wait** — and you'll never confuse `yield` and `await` again. (And in section 8 they combine.)

---

## 7. Comprehensions vs generator expressions

A **comprehension** is short syntax for "build a collection from a loop." The bracket you use decides *what* you build — and, crucially, whether it's **eager** or **lazy**:

```python
[x * x for x in range(5)]     # LIST comprehension  -> [0, 1, 4, 9, 16]   (eager)
(x * x for x in range(5))     # GENERATOR expression -> a generator        (lazy)
{name: len(name) for name in names}   # DICT comprehension
{name[0] for name in names}           # SET comprehension
```

```text
list comp [x*x ...] -> [0, 1, 4, 9, 16]  (computed now, all in memory)
gen expr  (x*x ...) -> <generator object ...>  (nothing computed yet)
  now consume the gen expr -> [0, 1, 4, 9, 16]
```

The only difference between the first two is `[]` vs `()`, but the behavior is exactly section 5:

- **`[...]` (list)** — computes *everything right now* and holds it all. Reusable, supports indexing, costs full memory.
- **`(...)` (generator)** — computes *nothing* until you consume it, one value at a time. Single-use, tiny memory, streamable.

Rule of thumb: **use `[]` when you need the whole thing (reuse it, index it, it's small); use `()` when you'll consume it once and want to save memory or stream it** — e.g. `sum(x*x for x in range(1_000_000))` never builds the million-item list.

Quick map: **`[]` eager list · `()` lazy generator · `{k: v}` dict · `{x}` set.**

---

## 8. The leaf: streaming (why this is on the AI path)

Here's where it all pays off. When an LLM answers, it doesn't compute the whole reply and hand it over — it produces **one token at a time**, and you want to show each token *the moment it's ready* (that typewriter effect). That is *exactly* a generator: a producer that yields values one at a time.

**Sync version** — a generator yielding "tokens":

```python
def stream_tokens(sentence):
    for word in sentence.split():
        time.sleep(0.12)      # pretend each token takes time to generate
        yield word

for token in stream_tokens(...):   # you handle each token AS IT ARRIVES
    print(token, ...)
```

Run it and you *see* the words appear one by one, not all at once. You never wait for the full reply — you process each piece as it's produced. That's streaming.

**Real version — an async generator.** Real LLM streaming waits on the *network* between tokens, so it combines both pausing ideas from this course: `await` (wait for the next chunk) **and** `yield` (hand that chunk to you). A function with both `async def` and `yield` is an **async generator**, consumed with **`async for`**:

```python
async def astream_tokens(sentence):
    for word in sentence.split():
        await asyncio.sleep(0.12)   # wait for the next chunk (network)
        yield word                  # hand it back to the consumer

async for token in astream_tokens(...):   # <- the shape of llm.astream()
    print(token, ...)
```

> **This is the punchline of Lessons 4 and 5 together:** `generators (yield values) + async (await I/O) = async generators = LLM token streaming.` When you later write `async for chunk in llm.astream(prompt):`, you'll know exactly what it is — an async generator that `await`s each network chunk and `yield`s you a token, driven by your `async for`.

---

## Run it, then break it (this part matters most)

1. **Feel the exhaustion (§2):** save `it = iter([1,2,3])`, then run `list(it)` twice. Second is empty. Now do it with the list itself — always full. That's iterator-vs-iterable in your hands.
2. **Watch a generator stay frozen (§4):** call `g = countdown_gen(5)`, then `next(g)` just twice, then `print(list(g))`. It resumes from 3 — the frame remembered where it paused.
3. **Break memory on purpose (§5):** change the gen expression `(x for x in range(1_000_000))` to a list `[x for x in range(1_000_000)]` and print `sys.getsizeof` of both. Watch 200 bytes become megabytes.
4. **Chain generators (§5/8):** write `evens = (x for x in naturals() if x % 2 == 0)` and take the first 5. Generators feed generators — a lazy pipeline, still ~0 memory.
5. **Turn streaming off (§8):** change `stream_tokens` to `return sentence.split()` (a plain list) instead of yielding. Re-run — now the whole answer appears at once, no streaming. That single change (`yield` → `return`) is the difference between streaming and not.

---

## What you now know

- **`for` is not magic:** it's `iter()` + `next()` until `StopIteration`. Every loopable thing plugs into this one protocol.
- **Iterable vs iterator:** an iterable *gives* you an iterator (reusable); an iterator *produces* values and is **single-use** because it holds a position.
- **The protocol is two methods** (`__iter__`, `__next__`) — you can build your own iterator, but you rarely need to.
- **A generator** (`yield`) is the easy iterator: a pausable function that hands back one value per pull — the same frame machinery as coroutines (p0004).
- **Laziness is the payoff:** infinite sequences and tiny constant memory (200 bytes vs 8 MB), because values are made on demand.
- **`yield` gives a value; `await` waits for one** — same pause, different purpose.
- **Comprehensions:** `[]` eager list, `()` lazy generator, `{k:v}` dict, `{x}` set.
- **Streaming = generators**, and **LLM streaming = async generators** (`async def` + `yield`, read with `async for`). That's `llm.astream()`.

**Next lesson — `p0006`: decorators.** The last core Python idea before the frameworks. A decorator is a function that *wraps* another function to add behavior — and it's the thing behind `@tool`, `@app.get`, and `@field_validator` (which you already used in p0002). You'll build one from scratch and watch the `@` symbol demystify itself.
