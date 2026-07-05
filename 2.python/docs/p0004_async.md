# p0004 — async / await, explained from zero

> **Run the code first, then read this.** `uv run p0004_async.py`
> It takes ~9 seconds on purpose — the waiting *is* the lesson.
> Each part below matches a numbered block in `p0004_async.py`.
> We assume you know **nothing** about coroutines. We build it up slowly.

---

## First, the problem this solves

Imagine **one cook** in a kitchen. There is only one cook — remember that, it matters.

A normal program is a cook who does one instruction at a time, top to bottom. Now suppose a recipe says *"boil water — takes 10 minutes."* A normal cook **stands and stares at the pot for 10 minutes**, doing nothing else. If three recipes each need 10 minutes of boiling, the cook stands around for 30 minutes total.

That is silly. A real cook would start the first pot, and *while it boils*, start the second, and the third. The boiling **overlaps**. All three finish in about 10 minutes, not 30. Still one cook — the cook was just never standing idle.

That second cook is what `async` gives you. And here's the key: the speed-up is **only** because the cook was *waiting* (for the water to boil). If instead each recipe needed the cook to *chop vegetables by hand* for 10 minutes — real work, not waiting — one cook could not overlap that. Async helps with **waiting**, not with **work**.

Why you care: almost everything an AI agent does is **waiting** — waiting for the LLM to answer over the network, waiting for a database, waiting for a tool's API. That waiting is exactly what async lets you overlap.

---

## What a coroutine actually *is* (the one new idea)

Everything in async rests on one unusual ability. So let's be very precise about it.

A **normal function** runs from its first line to its last line in **one uninterrupted go**. It cannot stop in the middle, let something else happen, and continue later. Once it starts, it runs to the end (or returns).

A **coroutine** — which is any function you write with `async def` — is different:

> **A coroutine can PAUSE itself partway through, hand control away, and later RESUME from the exact spot it paused — with all its local variables still remembered.**

That's the capability. But now the subtlety that trips people up — and it's worth stating loudly:

> With only **one** function running and nothing else to do, a pause is **invisible**. "Run step 1, pause, resume, run step 2" produces the *exact same output* as plain "run step 1, run step 2." You literally cannot tell them apart from the output.

So to actually *prove* a function paused, you must run **other code during the pause** and watch it happen in the gap. Section 1 of the program does exactly that — it freezes a function by hand and runs its own code in between. That's the next section.

---

## The three players

Only three things are involved. Learn these three words and you understand async.

1. **The coroutine** — a function that can pause and resume (`async def`). Think of it as *one recipe being cooked*.

2. **The event loop** — the **manager**. It's honestly just a `while` loop that keeps a list of coroutines and says: *"run this one until it pauses, then run the next ready one until it pauses, then the next..."* forever, until they're all done. **There is exactly one manager, and it is the single cook.** When people say "the event loop," picture this manager with a clipboard.

3. **`await`** — this word does two jobs, and both matter:
   - It is the **only** place a coroutine is allowed to pause. (No `await`, no pause.)
   - It means *"I'm now waiting for this slow thing; manager, wake me when it's done, and go run someone else meanwhile."*

So the full picture: the manager runs a coroutine. The coroutine hits an `await` (say, waiting for the network). It pauses and hands control back to the manager. The manager runs a *different* coroutine until *it* hits an `await`. When the first coroutine's slow thing finishes, the manager resumes it where it paused. One manager, one cook, many recipes overlapping — because nobody stands idle while waiting.

---

## 1. The raw mechanism: freeze a function, then un-freeze it

The clearest way to *see* pause/resume is a **generator** — the simplest pausable function. (Generators get their own full lesson in p0005; here we borrow one just to expose the machinery, because `async` is built on this exact mechanism.) The keyword `yield` is a pause point:

```python
def brew_steps():
    step = 0
    step += 1
    print(f"      [inside the function] step {step}: put tea bag in cup")
    yield                     # <-- PAUSE. control returns to the caller.
    step += 1
    print(f"      [inside the function] step {step}: pour hot water")
    yield                     # <-- PAUSE again.
    step += 1
    print(f"      [inside the function] step {step}: remove tea bag — done")
```

We drive it **by hand** with `next()`, printing our own lines in between:

```text
Calling it runs NOTHING — it just builds a paused object:
  (notice: no '[inside the function]' line above — the body hasn't started)

next(brew): run until the first `yield`, then FREEZE ->
      [inside the function] step 1: put tea bag in cup
  >>> control is back with ME now. The function is frozen mid-way.
  >>> THIS line proves it: my code runs while the function sits paused.

next(brew): RESUME from the exact spot it froze (watch step go 1 -> 2) ->
      [inside the function] step 2: pour hot water
  >>> frozen again, at the second `yield`. My code runs again.

next(brew): resume once more, to the end ->
      [inside the function] step 3: remove tea bag — done
```

**This is the proof you asked for.** Read the interleaving:

- The `[inside the function]` lines come from *inside* `brew_steps`.
- The `>>>` lines come from the *caller*.
- They **alternate**. The caller's code ran *between* the function's steps. A normal function can't allow that — it runs all the way to its end before the caller gets control back. So `brew_steps` genuinely **froze** at each `yield`, handed control back, and continued from the same spot on the next `next()`.

Also note `step` counted 1 → 2 → 3 across the freezes — the local variable survived each pause. (And, like coroutines, *calling* `brew_steps()` ran nothing; it just built a paused object. `next()` is what runs it.)

### How does it "remember"? (the actual mechanism)

No magic. Here's what really happens:

- When you call a **normal** function, Python builds a **frame** for it — a small box holding its local variables and a marker for "which line am I on." The function runs, and when it returns, **that frame is destroyed.** *That* is why a normal function can't resume: the box is gone.
- When you call a **generator** (or an **`async`**) function, Python builds the frame **but does not run it** — it stores that frame inside the returned object, which lives on the heap. Each `yield` / `await` **suspends**: it records "which line" in the frame and returns to the caller — *but keeps the frame alive.* The next `next()` (or the event loop resuming you) re-enters that stored frame and continues from the recorded line. When the function finally returns, the frame is thrown away and Python raises `StopIteration`.

So "it remembered where it was and what its variables held" simply means: **its frame (local variables + current line) is stored in a heap object that outlives each pause.** That is the entire trick behind coroutines.

### Where `async` fits in

`async` / `await` is this *exact* machinery, with one change: **you don't call `next()` — the event loop does.** `await something` means: *"suspend my frame, and tell the event loop to resume me when `something` is ready."*

- `yield` + `next()` → **you** control the pause and the resume (what you just saw).
- `await` + event loop → the **loop** controls the resume, and it wakes you when your awaited thing (a timer, a network reply) is done.

Same freeze-and-continue, different driver. Everything from section 2 onward is the event-loop-driven version of what you just did by hand.

---

## 2. Watch the manager switch (this is the heart of the lesson)

This is the most important block to understand. We run **two** counters "together" using `asyncio.gather(x, y)` — which just means *"manager, run both of these."*

**First version**, where each counter says `await` after every step:

```text
    A: step 1
    B: step 1
    A: step 2
    B: step 2
    A: step 3
    B: step 3
```

They **take turns**. Read it slowly: A runs step 1, then hits `await` and pauses. The manager runs B's step 1, then B hits `await` and pauses. Back to A for step 2. And so on. The `await` after each step is A and B *voluntarily letting go* so the other can run.

**Second version**, the *same* two counters but with **no `await`** inside:

```text
    A: step 1
    A: step 2
    A: step 3
    B: step 1
    B: step 2
    B: step 3
```

No taking turns at all. A runs **completely**, then B runs completely. Why? Because A never hits an `await`, so A **never pauses**, so the manager **never gets a chance to switch** to B. A finishes all three steps before B even begins.

Put those two outputs side by side and you've learned the single rule that explains all of async:

> **The manager can only switch coroutines at an `await`. No `await` = no switch.** A coroutine keeps the cook entirely to itself until it chooses to pause with `await`.

Everything below is just consequences of this one rule.

---

## 3. Calling a coroutine runs *nothing* (it's lazy)

Now a smaller but sneaky fact. When you **call** an `async def` function, its body does **not** run. You get back a *coroutine object* — think of it as a **written recipe**, not a cooked dish:

```text
about to CALL fake_llm_call(...). Watch: NO 'request sent' line appears.
  we got a 'coroutine' object back — the body has NOT run.
now we AWAIT it — THIS is what actually runs the body:
  [0.00s] demo: request sent, now WAITING ~0s for the model...
```

The very first line *inside* the function (`request sent`) only appears **after** we `await` — not when we call. So two separate steps:

- **`async def` + calling it** → writes a recipe (makes a coroutine object).
- **`await`** → cooks the recipe (actually runs it, and waits for the result).

**Common beginner bug:** if you call a coroutine but forget to `await` it, the body never runs, and Python warns *"coroutine was never awaited."* If your async code "did nothing," a missing `await` is the first suspect.

---

## 4. Awaiting one-by-one is SLOW (the trap everyone hits)

Here's where people misunderstand. Writing `await` three times in a row does **not** overlap anything:

```text
  [0.00s] A: request sent, now WAITING ~1s ...
  [1.00s] A: <-- response arrived
  [1.00s] B: request sent, now WAITING ~1s ...
  [2.00s] B: <-- response arrived
  [2.00s] C: request sent, now WAITING ~1s ...
  [3.00s] C: <-- response arrived
  total: 3.00s
```

Read the timestamps as a staircase: A takes 0→1, then B takes 1→2, then C takes 2→3. Three seconds.

Why no overlap? Because `await` means **"wait right here until this is done."** When you write:

```python
await fake_llm_call("A")   # wait right here for A to fully finish
await fake_llm_call("B")   # only NOW start B, wait right here for it
await fake_llm_call("C")
```

you told the manager to finish A completely before line 2 even begins. There was never a second coroutine waiting at the same time, so there was nothing to switch to. This is `async` code that is exactly as slow as ordinary code.

> **`await` by itself does not make things fast. `await` means "wait." Speed comes from having several things paused *at the same time* — which needs section 5.**

---

## 5. `asyncio.gather` runs them together — FAST

Same three calls. One change: hand all three to `asyncio.gather`, which starts them **all at once** and then waits for all of them:

```python
results = await asyncio.gather(
    fake_llm_call("A"),
    fake_llm_call("B"),
    fake_llm_call("C"),
)
```

```text
  [0.00s] A: request sent, now WAITING ~1s ...
  [0.00s] B: request sent, now WAITING ~1s ...
  [0.00s] C: request sent, now WAITING ~1s ...
  [1.00s] A: <-- response arrived
  [1.00s] B: <-- response arrived
  [1.00s] C: <-- response arrived
  total: 1.00s
```

All three "request sent" at **0.00s**, all three replies at **1.00s**. Three seconds became one.

Trace it with the rule from section 2: `gather` gives the manager all three coroutines. It starts A; A sends its request and hits `await` (waiting for the model) → pauses. The manager starts B; B pauses at its `await`. Then C; C pauses. Now **all three are paused, all three waiting on the model at the same time.** One second later all three replies arrive and the manager resumes each. The waiting overlapped — exactly the cook starting three pots.

Two things to remember about `gather`:
- It **starts everything, then waits for all of them together.** That overlap is the entire point.
- It returns results **in the order you passed them in** (`[A, B, C]`), not the order they finished. So you can trust the positions.

For an agent, this is how you call three tools at once, or fire several retrieval queries in parallel, instead of one-at-a-time.

---

## 6. It's all ONE thread (concurrency, not parallelism)

You might suspect the manager secretly spawns extra threads. It does not. Each task prints the thread it's on:

```text
  A is running on thread: MainThread
  B is running on thread: MainThread
  C is running on thread: MainThread
```

All the same thread. This is the "one cook" from the very beginning, made literal. Two words to separate:

- **Concurrency** — many tasks making progress by **overlapping their waits**, taking turns on one worker. *This is what asyncio does.*
- **Parallelism** — many tasks **computing at the same instant** on different CPU cores. *That needs threads or processes, not asyncio.*

And single-worker is perfectly fine for an agent, because the job is **waiting**, not computing. You don't need three cooks to watch three pots boil — you need one cook who doesn't stand frozen in front of the first pot. The manager *is* that cook.

---

## 7. The trap: a blocking call freezes everyone

This is the sharp edge you *will* cut yourself on. Same `gather` as section 5, but each call uses `time.sleep()` (an ordinary, blocking wait) instead of `asyncio.sleep()`:

```text
  [0.00s] A: starting — using BLOCKING time.sleep()
  [1.00s] A: done
  [1.00s] B: starting — using BLOCKING time.sleep()
  [2.00s] B: done
  [2.00s] C: starting — using BLOCKING time.sleep()
  [3.01s] C: done
  total: 3.01s
```

The staircase is back — no overlap. Apply the rule one more time: **the manager can only switch at an `await`.** `time.sleep()` is **not** an `await`. It just freezes the one thread — the one cook — for a full second and never hands control back. So while A is sleeping, the manager is stuck; B and C can't even start.

This is called **cooperative** multitasking: coroutines must *cooperate* by pausing at `await`. One coroutine that refuses to pause — a blocking call, or a long CPU loop with no `await` — holds the entire program hostage. (Compare ordinary threads, where the operating system can interrupt anything at any moment. That's *preemptive*, and it's why threads have so many surprise bugs. async trades that away: switches happen only at `await`, where you can see them.)

**The practical rules that follow:**
- Inside `async`, every wait must be **async-aware**: `asyncio.sleep` (not `time.sleep`), an async HTTP client like `httpx.AsyncClient` (not blocking `requests`), async database drivers, and so on. The OpenAI and LangChain async methods are already written this way.
- If you're forced to call a blocking function that has no async version, don't call it directly — wrap it: `await asyncio.to_thread(blocking_func, args)`. That hands the blocking work to a separate helper thread so the manager stays free.
- Heavy CPU work has the same problem (nothing to `await`). async is for **I/O-bound** work (waiting on the outside world), never for **CPU-bound** work (grinding numbers).

---

## Why this shows up all over LangChain and LangGraph

An agent is mostly waiting: it calls the LLM, then maybe three tools, then a search, then the LLM again. async lets it **overlap** the independent calls (section 5), **stream** the LLM's answer token-by-token as it arrives instead of waiting for the whole thing, and — in a web server — handle **many users at once** while each one waits on its own LLM.

That's why LangChain gives most operations **two** versions: a normal one, and an async one with an **`a` prefix**:

| normal (sync) | async |
|---|---|
| `agent.invoke(...)` | `await agent.ainvoke(...)` |
| `agent.stream(...)` | `async for chunk in agent.astream(...)` |
| `chain.batch(...)` | `await chain.abatch(...)` |

When you meet `await agent.ainvoke(...)` in a later phase, you'll now read it correctly: *"this is a slow call to the model — pause here, and let other work run while we wait."*

---

## Run it, then break it (this part matters most)

Do these — changing the output is how the rule sinks in.

1. **Make the switching stop (§2):** in `counter_with_yield`, delete the `await asyncio.sleep(0)` line. Re-run. The interleaved `A,B,A,B` collapses into `A,A,A,B,B,B`. You just proved "no await = no switch" with your own hands.
2. **Make fast slow (§5):** turn the `gather` in `demo_concurrent` back into three separate `await` lines. Watch 1 second become 3. Then undo it.
3. **The one-word fix (§7):** in `bad_call`, change `time.sleep(seconds)` to `await asyncio.sleep(seconds)`. Re-run — section 7 drops from ~3s to ~1s. That single word `await` is the whole difference.
4. **Overlap with uneven times (§5):** add a fourth call `fake_llm_call("D", 2.0)` to the gather. Total becomes ~2s (the *longest* one), not 5s (the sum). Concurrency = you wait as long as the slowest, not the total.
5. **See the "never awaited" warning (§3):** in `demo_lazy`, add `fake_llm_call("orphan", 1.0)` with no `await`. Run it and read the warning — that's the section-3 gotcha, live.

---

## What you now know

- A **coroutine** (`async def`) is a function that can **pause and resume**, remembering its variables. That's the one new idea.
- The **event loop** is a single manager (one thread, one cook) that runs coroutines and switches between them.
- **`await`** is the *only* place a coroutine can pause, and it means "wait for this; manager, run someone else meanwhile."
- **The one rule:** the manager can only switch **at an `await`**. Section 2 shows it: `await` → they take turns; no `await` → one runs to the end first.
- **Calling a coroutine is lazy** — it makes a recipe; `await` cooks it. Forget to await → nothing runs.
- **Three `await`s in a row are still slow** (a staircase). **`asyncio.gather`** starts them together so the waits overlap — that's the speed-up (3s → 1s).
- It's **one thread**: concurrency (overlapping waits), not parallelism (many CPUs). Great for waiting, useless for heavy compute.
- A **blocking call** (`time.sleep`, `requests`, a CPU loop) freezes the one cook and kills all overlap. Use async-aware waits, or `asyncio.to_thread`.

*(Kotlin footnote, if it helps: `async def` ≈ `suspend fun`, `asyncio.gather` ≈ `awaitAll`, `asyncio.run` ≈ `runBlocking`. But the big difference — Python's asyncio is single-threaded, while Kotlin can spread coroutines across threads — is exactly why we built this from the "one cook" idea instead.)*

**Next lesson — `p0005`: comprehensions, iterators, and generators.** Generators are close cousins of what you just learned — they're functions that also **pause and resume**, but to hand back *values* one at a time instead of waiting. They are the exact machinery behind `for token in stream:` when an LLM streams its answer. Your section-1 "pause and resume" intuition will carry straight over.
