"""
p0004c — mapping `brew_steps` (the by-hand generator) onto REAL async/await.

Run me:
    uv run p0004c_generator_to_async.py

This exists to answer one question: "how does that brew_steps generator relate
to real async code?" Answer: it's the SAME machinery. We show the SAME brewing
logic three ways, so you can see exactly what maps to what:

    PART 1 — a generator (`yield`), and YOU drive it with next()
    PART 2 — the SAME logic as `async def` + `await`, driven BY HAND with .send()
    PART 3 — the SAME `async def`, driven by the real EVENT LOOP (real async)

First, clear up the words with a concrete picture:

    async def brew_async(): <- a coroutine FUNCTION (the definition)
        ...
    c = brew_async() <- calling it makes a COROUTINE OBJECT.
                                      THIS whole object is "a coroutine" = one
                                      unit of pausable work. Not a line, not the
                                      `await` — the WHOLE running instance.
    task = asyncio.create_task(c) <- the event loop wraps it in a TASK (its
                                      bookkeeping handle) and schedules it.

    The loop holds many Tasks and runs them ONE AT A TIME, taking turns at each
    `await`. That is CONCURRENT (overlapping), NOT parallel (never two at once).
"""

import asyncio


def section(title: str) -> None:
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


# ===========================================================================
# PART 1 — a GENERATOR. `yield` is the pause. YOU drive it with next().
# ===========================================================================
def brew_gen():
    step = 0
    step += 1
    print(f"    brew: step {step} — put tea bag in cup")
    yield                                  # PAUSE (hand control to the driver)
    step += 1
    print(f"    brew: step {step} — pour hot water")
    yield                                  # PAUSE
    step += 1
    print(f"    brew: step {step} — remove tea bag, done")


def part1_generator() -> None:
    section("PART 1 — generator (`yield`), and YOU step it with next()")

    g = brew_gen()
    print("g = brew_gen()      -> made the generator object; NOTHING ran yet")
    print("next(g)             -> run to the 1st `yield`:")
    next(g)
    print("      [driver] paused. I (the caller) am running now.")
    print("next(g)             -> resume to the 2nd `yield`:")
    next(g)
    print("      [driver] paused again. I'm running now.")
    print("next(g)             -> resume to the end:")
    try:
        next(g)
    except StopIteration:
        print("      [driver] StopIteration = the generator is finished.")


# ===========================================================================
# The pause primitive for the async version.
#   `await Pause()` bottoms out in a bare `yield` — literally the SAME pause
#   that the generator used. This is the hidden truth: `await` IS `yield`,
#   dressed up. (In real code you await real things — asyncio.sleep, a network
#   read — but every one of them ultimately yields control like this.)
# ===========================================================================
class Pause:
    def __await__(self):
        yield


# The SAME brew logic, now as a real coroutine. Compare it line-for-line to
# brew_gen above: `def`->`async def`, and each `yield`->`await Pause()`.
async def brew_async():
    step = 0
    step += 1
    print(f"    brew: step {step} — put tea bag in cup")
    await Pause()                          # PAUSE (hand control to the driver)
    step += 1
    print(f"    brew: step {step} — pour hot water")
    await Pause()                          # PAUSE
    step += 1
    print(f"    brew: step {step} — remove tea bag, done")


# ===========================================================================
# PART 2 — the SAME `async def`, but WE drive it by hand with .send().
#    This proves a coroutine is stepped exactly like a generator. The event
#    loop (Part 3) is nothing more than an automatic caller of .send().
# ===========================================================================
def part2_async_by_hand() -> None:
    section("PART 2 — SAME logic as `async def`+`await`, driven by hand (.send)")

    c = brew_async()
    print(f"c = brew_async()    -> made a '{type(c).__name__}' object; NOTHING ran yet")
    print("c.send(None)        -> run to the 1st `await`:")
    c.send(None)
    print("      [driver] paused at `await`. I'm running now.")
    print("c.send(None)        -> resume to the 2nd `await`:")
    c.send(None)
    print("      [driver] paused again. I'm running now.")
    print("c.send(None)        -> resume to the end:")
    try:
        c.send(None)
    except StopIteration:
        print("      [driver] StopIteration = the coroutine is finished.")

    print("\n  Identical to Part 1. So:")
    print("    `await`        is the same pause as `yield`")
    print("    `c.send(None)` is the same step as `next(g)`")
    print("  A coroutine is just a generator you step with .send() instead of next().")


# ===========================================================================
# PART 3 — the SAME coroutine, but the EVENT LOOP drives it (this is real async).
#    You never call .send(). The loop does — and it runs a SECOND coroutine in
#    the gaps. Watch them take turns (one line at a time — NOT parallel).
# ===========================================================================
async def narrator():
    # A second coroutine, so you can SEE what fills the gaps in real async.
    for msg in ("other: (serving tables 2 and 3 meanwhile)",
                "other: (still serving others)"):
        print(f"    {msg}")
        await Pause()


async def part3_real_loop() -> None:
    section("PART 3 — SAME `async def`, but the EVENT LOOP drives it (real async)")

    print("asyncio.gather(brew_async(), narrator()) hands TWO coroutines to the loop.")
    print("The loop steps each one (with .send, for you) until it hits `await`,")
    print("then switches to the other. Nobody runs .send() by hand. Watch them")
    print("interleave — brew, other, brew, other — ONE line at a time:\n")

    await asyncio.gather(brew_async(), narrator())

    print("\n  That interleaving is the loop taking turns at each `await`.")
    print("  It is CONCURRENT (overlapping), NOT parallel (never two at once).")


def main() -> None:
    part1_generator()
    part2_async_by_hand()
    asyncio.run(part3_real_loop())   # asyncio.run = start the loop, drive till done

    section("THE MAP — brew by hand  <->  real async")
    rows = [
        ("generator / by hand",          "real async / event loop"),
        ("-" * 30,                        "-" * 34),
        ("def brew_gen()",               "async def brew_async()"),
        ("yield",                         "await <something>"),
        ("g = brew_gen()  (make object)", "c = brew_async()  (make coroutine)"),
        ("YOU call next(g)",              "the LOOP calls c.send()  (for you)"),
        ("your code between next() calls","OTHER coroutines the loop runs"),
        ("StopIteration = done",          "the loop sees the Task finish"),
    ]
    for left, right in rows:
        print(f"  {left:<32}{right}")
    print("\n  'A coroutine' = the whole brew_async() instance (one unit of work).")
    print("  A 'Task' = the loop's handle around it. The loop juggles many Tasks,")
    print("  ONE AT A TIME, switching at each `await`. Concurrent, not parallel.")


if __name__ == "__main__":
    main()
