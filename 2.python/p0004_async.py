"""
p0004 — async / await, built from ZERO. No coroutine knowledge assumed.

Run me:
    uv run p0004_async.py
    (it takes ~9 seconds ON PURPOSE — the waiting IS the lesson)

Read me with the doc open next to you:
    docs/p0004_async.md

We build the idea in small steps, and each step is VISIBLE in the output:
    1. FREEZE a function by hand, then un-freeze it.     (the raw mechanism)
    2. WATCH the manager switch between two coroutines.  (the core mechanic)
    3. Calling a coroutine runs nothing until you await.  (lazy)
    4. Awaiting one-by-one is SLOW.                       (the trap)
    5. asyncio.gather runs them together — FAST.          (the payoff)
    6. It's all ONE thread.                               (concurrency != parallelism)
    7. A blocking call freezes everything.                (the sharp edge)

The one sentence to hold onto:
    `await` is the ONLY place a coroutine can pause. When it pauses, a manager
    called the "event loop" runs another coroutine, then comes back. One worker,
    never standing idle. That is the whole trick.
"""

import asyncio
import time
import threading


# A tiny stopwatch, so you can SEE when each thing happens.
_start = 0.0


def mark() -> None:
    global _start
    _start = time.monotonic()


def t() -> float:
    return time.monotonic() - _start


def section(title: str) -> None:
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


# ===========================================================================
# 1. A COROUTINE CAN PAUSE PARTWAY AND RESUME LATER.
#    This is THE new idea. A normal function runs top-to-bottom in one go and
#    cannot stop halfway. A coroutine (any `async def`) can stop at an `await`,
#    let other work happen, then continue from the exact same spot — with its
#    local variables still remembered.
# ===========================================================================
# The simplest "pausable function" is a GENERATOR (full lesson: p0005). The
# word `yield` is a PAUSE point: the function stops there, hands control back to
# whoever called next(), and FREEZES — keeping its exact position and all its
# local variables — until next() is called again. YOU drive the resume here.
# (async's `await` is this SAME machinery; the only difference is that the event
#  loop calls the resume for you, when your awaited thing becomes ready.)
def brew_steps():
    step = 0                                  # a local variable, kept across pauses
    step += 1
    print(f"      [inside the function] step {step}: put tea bag in cup")
    yield                                     # <-- PAUSE. control returns to the caller.
    step += 1
    print(f"      [inside the function] step {step}: pour hot water")
    yield                                     # <-- PAUSE again.
    step += 1
    print(f"      [inside the function] step {step}: remove tea bag — done")


async def demo_pause_resume() -> None:
    section("1. The raw mechanism: FREEZE a function, then UN-FREEZE it by hand")

    print("Calling it runs NOTHING — it just builds a paused object:")
    brew = brew_steps()
    print("  (notice: no '[inside the function]' line above — the body hasn't started)")

    print("\nnext(brew): run until the first `yield`, then FREEZE ->")
    next(brew)
    print("  >>> control is back with ME now. The function is frozen mid-way.")
    print("  >>> THIS line proves it: my code runs while the function sits paused.")

    print("\nnext(brew): RESUME from the exact spot it froze (watch step go 1 -> 2) ->")
    next(brew)
    print("  >>> frozen again, at the second `yield`. My code runs again.")

    print("\nnext(brew): resume once more, to the end ->")
    try:
        next(brew)
    except StopIteration:                     # a generator raises this when it finishes
        pass

    print("\n  You just PAUSED and RESUMED a function by hand. The '>>>' lines ran")
    print("  BETWEEN its steps — impossible unless the function truly froze and")
    print("  handed control back. And it remembered `step` (1->2->3) across pauses.")
    print("  `async`/`await` is this SAME trick — except the EVENT LOOP calls the")
    print("  'next()' for you, resuming your coroutine when its awaited thing")
    print("  (a timer, a network reply) is ready. Sections 2+ show that version.")


# ===========================================================================
# 2. WATCH THE MANAGER SWITCH BETWEEN TWO COROUTINES.
#    `asyncio.gather(x, y)` means "run these coroutines together". Watch what
#    the event loop does at each `await`.
# ===========================================================================
async def counter_with_yield(name: str) -> None:
    for i in (1, 2, 3):
        print(f"    {name}: step {i}")
        await asyncio.sleep(0)     # asyncio.sleep(0) = "pause; let others run NOW"


async def counter_no_yield(name: str) -> None:
    for i in (1, 2, 3):
        print(f"    {name}: step {i}")
        # NO await here — this coroutine never pauses, so it never lets go.


async def demo_switching() -> None:
    section("2. Watch the manager switch between tasks (only at `await`)")

    print("TWO counters, each with an `await` after every step -> they TAKE TURNS:")
    await asyncio.gather(counter_with_yield("A"), counter_with_yield("B"))

    print("\nSAME two counters, but with NO `await` inside -> NO taking turns.")
    print("A runs completely, THEN B — because A never pauses to let go:")
    await asyncio.gather(counter_no_yield("A"), counter_no_yield("B"))

    print("\n  THE ONE RULE: the manager can only switch coroutines at an `await`.")
    print("  No `await` = no switch. This rule explains every timing below.")


# This stands in for a slow network call, like asking an LLM.
async def fake_llm_call(name: str, seconds: float = 1.0) -> str:
    print(f"  [{t():4.2f}s] {name}: request sent, now WAITING ~{seconds:.0f}s for the model...")
    await asyncio.sleep(seconds)          # pause here; the loop can run others
    print(f"  [{t():4.2f}s] {name}: <-- response arrived")
    return f"answer({name})"


# ===========================================================================
# 3. CALLING A COROUTINE RUNS NOTHING. `await` is what runs it.
# ===========================================================================
async def demo_lazy() -> None:
    section("3. Calling a coroutine runs NOTHING until you await it")
    mark()

    print("about to CALL fake_llm_call(...). Watch: NO 'request sent' line appears.")
    recipe = fake_llm_call("demo", 0.3)   # this builds a coroutine; it does NOT run
    print(f"  we got a '{type(recipe).__name__}' object back — the body has NOT run.")
    print("now we AWAIT it — THIS is what actually runs the body:")
    result = await recipe
    print("  await gave us:", result)
    print("\n  `async def` writes a recipe. `await` cooks it.")


# ===========================================================================
# 4. AWAITING ONE-BY-ONE IS SLOW (this is the beginner trap).
# ===========================================================================
async def demo_sequential() -> None:
    section("4. One after another — SLOW (~3s)")
    mark()

    print("three calls, each fully awaited before the next one begins:")
    await fake_llm_call("A")
    await fake_llm_call("B")
    await fake_llm_call("C")
    print(f"\n  total: {t():.2f}s — they NEVER overlapped. `await` means 'wait right here'.")
    print("  Writing three awaits in a row is NOT concurrency. It's just... waiting, 3 times.")


# ===========================================================================
# 5. asyncio.gather RUNS THEM TOGETHER — FAST. The payoff.
# ===========================================================================
async def demo_concurrent() -> None:
    section("5. All at once with asyncio.gather — FAST (~1s)")
    mark()

    print("same three calls, started TOGETHER. Watch all 3 'request sent' lines")
    print("appear at 0.00s, then all 3 replies arrive at ~1.00s:")
    results = await asyncio.gather(
        fake_llm_call("A"),
        fake_llm_call("B"),
        fake_llm_call("C"),
    )
    print(f"\n  total: {t():.2f}s — all three WAITED AT THE SAME TIME.")
    print("  gather returns results in the order you asked:", results)


# ===========================================================================
# 6. IT'S ALL ONE THREAD (concurrency, not parallelism).
# ===========================================================================
async def worker(name: str) -> None:
    print(f"  {name} is running on thread: {threading.current_thread().name}")
    await asyncio.sleep(0.1)


async def demo_one_thread() -> None:
    section("6. It's all ONE thread — concurrency, not parallelism")

    await asyncio.gather(worker("A"), worker("B"), worker("C"))
    print("\n  All three printed the SAME thread name. No extra threads exist.")
    print("  One worker juggling many waits — not many workers running at once.")


# ===========================================================================
# 7. THE TRAP: a blocking call freezes the WHOLE loop.
# ===========================================================================
async def bad_call(name: str, seconds: float = 1.0) -> str:
    print(f"  [{t():4.2f}s] {name}: starting — using BLOCKING time.sleep()")
    time.sleep(seconds)                   # does NOT pause the coroutine; freezes the thread
    print(f"  [{t():4.2f}s] {name}: done")
    return name


async def demo_blocking_trap() -> None:
    section("7. The trap: a blocking call freezes everyone (~3s again)")
    mark()

    print("gather of three calls that use time.sleep() instead of asyncio.sleep():")
    await asyncio.gather(bad_call("A"), bad_call("B"), bad_call("C"))
    print(f"\n  total: {t():.2f}s — gather could NOT overlap them! Back to 3 seconds.")
    print("  Why: time.sleep() is not an `await`, so it never lets the manager")
    print("  switch. It holds the one thread hostage. Rule: inside `async`, every")
    print("  wait must be async-aware (asyncio.sleep, async HTTP clients, ...).")


async def main() -> None:
    await demo_pause_resume()
    await demo_switching()
    await demo_lazy()
    await demo_sequential()
    await demo_concurrent()
    await demo_one_thread()
    await demo_blocking_trap()
    print("\n" + "=" * 70)
    print("Done. Open docs/p0004_async.md — it explains each step from zero.")
    print("=" * 70)


if __name__ == "__main__":
    # asyncio.run() is the on-ramp from normal (sync) code INTO the async world.
    # It creates the event loop (the manager), runs main() until it finishes,
    # then shuts the loop down. You call it ONCE, at the very top.
    asyncio.run(main())
