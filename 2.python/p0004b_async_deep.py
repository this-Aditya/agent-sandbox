"""
p0004b — async DEEP DIVE: what REALLY happens when tasks overlap?

Run me:
    uv run p0004b_async_deep.py

Read me with the doc open next to you:
    docs/p0004b_async_deep.md

THE QUESTION this answers (your exact question):
    Task A is waiting (say ~2s). While A waits, the manager starts task B
    (say ~3s). Does A get delayed until B finishes, or does A resume on time?

THE ANSWER, in one line:
    It depends on what B is doing while those 3 seconds pass:
      - If B is WAITING too (it uses `await`)  -> A is NOT delayed. A resumes
        the instant its own wait is over. The two waits overlap.
      - If B is WORKING (CPU/blocking, no `await`) -> A IS delayed. B holds the
        one thread the whole time, so A can't resume until B lets go.
    The four demos below prove exactly this, with timestamps.

Small but important wording fix:
    It's not "a thread pauses". The single thread never pauses — it's always
    running the manager (event loop). What pauses is a COROUTINE/TASK. The
    thread just moves on to run a different task.
"""

import asyncio
import time


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


# A task that WAITS on something slow (like a network / LLM call). It uses
# `await`, so it PAUSES and lets the manager run other tasks meanwhile.
async def waiter(name: str, seconds: float) -> None:
    print(f"  [{t():4.2f}s] {name}: start — will WAIT (await) ~{seconds:.0f}s")
    await asyncio.sleep(seconds)
    print(f"  [{t():4.2f}s] {name}: FINISHED (its {seconds:.0f}s wait is over)")


# A task that WORKS — heavy CPU / a blocking call — with NO `await` inside.
# It never pauses, so it holds the single thread hostage until it's done.
async def worker_blocking(name: str, seconds: float) -> None:
    print(f"  [{t():4.2f}s] {name}: start — will WORK (blocking) ~{seconds:.0f}s")
    time.sleep(seconds)                      # stands in for a CPU-heavy loop; no await
    print(f"  [{t():4.2f}s] {name}: FINISHED (its {seconds:.0f}s of work is done)")


# Same heavy work, but handed to a HELPER THREAD via asyncio.to_thread, which
# lets THIS coroutine `await` (pause) while the helper thread grinds.
async def worker_offloaded(name: str, seconds: float) -> None:
    print(f"  [{t():4.2f}s] {name}: start — WORK offloaded to a helper thread")
    await asyncio.to_thread(time.sleep, seconds)
    print(f"  [{t():4.2f}s] {name}: FINISHED (its {seconds:.0f}s of work is done)")


# ===========================================================================
# 1. BOTH ARE WAITING. A wants ~2s, B wants ~3s. Does A wait for B? NO.
# ===========================================================================
async def demo_both_waiting() -> None:
    section("1. A waits 2s, B waits 3s — both WAIT. Is A delayed? NO.")
    mark()
    await asyncio.gather(waiter("A", 2), waiter("B", 3))
    print(f"\n  Look at the timestamps: A FINISHED at ~2s, B at ~3s. Total ~3s.")
    print("  A was NOT delayed. Both were just paused timers; the manager woke")
    print("  each one the moment its OWN wait ended. The two waits overlapped.")


# ===========================================================================
# 2. A WAITS 2s, B WORKS (blocking) 3s. Now A IS delayed — to 3s.
# ===========================================================================
async def demo_wait_vs_blocking() -> None:
    section("2. A waits 2s, B WORKS (blocking) 3s — Is A delayed? YES.")
    mark()
    await asyncio.gather(waiter("A", 2), worker_blocking("B", 3))
    print(f"\n  A's 2s wait ended at t=2 — but the manager was BUSY running B's")
    print("  blocking work until t=3, so A couldn't resume until ~3s.")
    print("  THIS is your scenario's danger: a 'working' neighbor delays a waiter.")


# ===========================================================================
# 3. THE FIX: run B's blocking work on a helper thread. A is on time again.
# ===========================================================================
async def demo_offload_fix() -> None:
    section("3. FIX: offload B's work to a helper thread — A on time again")
    mark()
    await asyncio.gather(waiter("A", 2), worker_offloaded("B", 3))
    print(f"\n  A FINISHED at ~2s again. Because B `await`ed on to_thread, B PAUSED")
    print("  (its grinding happened on another thread), so the manager stayed")
    print("  free to wake A on time. Waiting overlaps; working must be offloaded.")


# ===========================================================================
# 4. THE SUBTLE ONE: even an 'async' task freezes others during CPU work
#    that sits BETWEEN its awaits. Having awaits 'somewhere' is not enough.
# ===========================================================================
async def timer_task(name: str, wake_at: float) -> None:
    print(f"  [{t():4.2f}s] {name}: sleeping, asked to wake at ~{wake_at:.0f}s")
    await asyncio.sleep(wake_at)
    print(f"  [{t():4.2f}s] {name}: WOKE UP  (asked for {wake_at:.0f}s — check the real time!)")


async def cpu_between_awaits(name: str, seconds: float) -> None:
    print(f"  [{t():4.2f}s] {name}: start; I DO have awaits, but now a CPU loop with none")
    await asyncio.sleep(0)                    # yields once...
    end = time.monotonic() + seconds          # ...then a tight CPU loop, NO awaits:
    while time.monotonic() < end:
        pass
    print(f"  [{t():4.2f}s] {name}: done CPU loop")


async def demo_cpu_between_awaits() -> None:
    section("4. Subtle: CPU work BETWEEN awaits still freezes everyone")
    mark()
    await asyncio.gather(timer_task("timer", 1), cpu_between_awaits("hog", 2))
    print(f"\n  'timer' asked to wake at 1s but actually woke at ~2s. The 'hog'")
    print("  task had an await, yet its 2s CPU loop between awaits blocked the")
    print("  manager. Lesson: it's the AWAITS that matter, not being 'async'.")
    print("  Long CPU work needs awaits sprinkled in, or asyncio.to_thread.")


async def main() -> None:
    await demo_both_waiting()
    await demo_wait_vs_blocking()
    await demo_offload_fix()
    await demo_cpu_between_awaits()
    print("\n" + "=" * 70)
    print("Done. Open docs/p0004b_async_deep.md for the Java comparison + machinery.")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
