# p0004b — async deep dive: overlap, delays, and the machinery

> **Run the code first, then read this.** `uv run p0004b_async_deep.py`
> This answers your exact question: *when A is waiting and B runs, does A get delayed?*
> Each part matches a numbered block in `p0004b_async_deep.py`.

---

## First, a wording fix that clears up half the confusion

You said *"one thread is now paused."* That phrasing is the source of a lot of confusion, so let's correct it precisely:

> **The single thread never pauses.** It is *always* running — running the manager (the event loop). What pauses is a **coroutine** (also called a **task**). When a task pauses, the thread doesn't stop; it just turns around and runs a *different* task.

So there is always exactly one thread, always busy running *something*. "Pausing" is a task stepping aside, not the thread stopping. Keep that picture and the rest falls into place.

---

## Your question, answered directly

> A is waiting (say ~2 seconds). While A waits, the manager starts B (say ~3 seconds). Does A get delayed until B finishes, or does A resume on time?

**The answer depends on one thing: what is B *doing* during those 3 seconds?** There are two completely different cases.

### Case 1 — B is also *waiting* (B uses `await`)

If B is *also* just waiting on something slow (a network call, a timer), then **A is NOT delayed.** Both A and B become "paused timers." The manager sets both aside and idles. When A's own 2-second wait ends, the manager wakes A immediately — B's longer wait is irrelevant. A finishes at ~2s, B at ~3s.

Demo 1 proves it:

```text
  [0.00s] A: start — will WAIT (await) ~2s
  [0.00s] B: start — will WAIT (await) ~3s
  [2.00s] A: FINISHED (its 2s wait is over)
  [3.00s] B: FINISHED (its 3s wait is over)
```

A finished at 2.00s, right on time. The waits overlapped.

### Case 2 — B is *working* (CPU or a blocking call, no `await`)

If B is doing real work — a heavy CPU loop, or a blocking call like `time.sleep()` — with no `await`, then **A IS delayed.** B never pauses, so B keeps the one thread the whole time. A's 2-second timer fires at t=2, but the manager is *busy running B* and can't act on it. A only resumes once B finishes at t=3.

Demo 2 proves it:

```text
  [0.00s] A: start — will WAIT (await) ~2s
  [0.00s] B: start — will WORK (blocking) ~3s
  [3.00s] B: FINISHED (its 3s of work is done)
  [3.00s] A: FINISHED (its 2s wait is over)
```

A finished at **3.00s**, not 2.00s. B's work delayed it by a full second.

### Your exact numbers (10s wait, 13s new work)

- If the 13-second new work is **waiting** (I/O): A finishes at **10s**, B at 13s. A is on time.
- If the 13-second new work is **CPU/blocking**: A's 10-second timer fires at t=10, but the thread is busy with B until t=13, so A resumes at **13s**. A is delayed by 3 seconds.

So the mental question to ask, always: **is the neighbor waiting, or working?** Waiting overlaps for free. Working blocks everyone.

---

## Case 3 — the fix: offload the work

What if B genuinely *has* heavy work to do, but you don't want it to delay A? You move the work off the manager's thread onto a **helper thread**, using `asyncio.to_thread`. Now B can `await` (pause) while a separate thread grinds:

```python
await asyncio.to_thread(time.sleep, seconds)   # runs the blocking call on another thread
```

Demo 3:

```text
  [0.00s] A: start — will WAIT (await) ~2s
  [0.00s] B: start — WORK offloaded to a helper thread
  [2.00s] A: FINISHED (its 2s wait is over)
  [3.02s] B: FINISHED (its 3s of work is done)
```

A is back to finishing at 2.00s. Because B `await`ed on `to_thread`, B paused and handed the manager's thread back — so A could wake on time. **Waiting overlaps by itself; working must be pushed onto another thread.**

---

## Case 4 — the subtle one: "async" is not a magic word

Here's the trap that catches people who *think* they understand. A task can be `async` and even use `await`, and *still* freeze everyone — if it does a long stretch of CPU work **between** its awaits:

```text
  [0.00s] timer: sleeping, asked to wake at ~1s
  [0.00s] hog: start; I DO have awaits, but now a CPU loop with none
  [2.00s] hog: done CPU loop
  [2.00s] timer: WOKE UP  (asked for 1s — check the real time!)
```

`timer` asked to wake at 1s. It actually woke at **2s**. Why? The `hog` task ran a 2-second CPU loop with no `await` in the middle. During that stretch, the manager had no chance to switch — so `timer`, though ready at 1s, sat waiting until `hog` finally hit its next pause at 2s.

> The lesson: it is not *being async* that lets others run. It is the **`await`** itself. Long CPU work between awaits blocks the whole program just as badly as a blocking call. Sprinkle `await asyncio.sleep(0)` into long loops, or offload them with `to_thread` — see Case 3.

---

## Is this like threads in Java? (the comparison you asked for)

This is the most useful comparison to nail, because Java has *several* models and asyncio is like only one of them.

**Java platform threads** (`new Thread()`, thread pools, one-thread-per-request servers):
- Each task is a real **operating-system thread**.
- The OS switches them **preemptively** — it can pause any thread at *any* instruction, without the code's permission.
- They give **true parallelism**: two threads can run on two CPU cores at the same instant.
- They're **expensive** (~1 MB of stack each), so tens of thousands is heavy.
- **asyncio is NOT this.** No OS thread per task, no preemption, no parallelism.

**Java virtual threads** (Project Loom, stable in Java 21):
- Millions of cheap, lightweight threads multiplexed onto a small pool of real "carrier" OS threads.
- When a virtual thread blocks on I/O, the JVM **automatically** parks it and runs another on the same carrier thread.
- **This is the closest cousin to asyncio in purpose** — many cheap I/O-bound tasks, very few real threads.
- The key difference: Loom yields **automatically and invisibly** (you write normal blocking-looking code, the runtime handles the pausing). asyncio makes you yield **explicitly** by writing `await`. In asyncio the pause points are *visible in your code*; in Loom they're hidden by the runtime.

**Kotlin coroutines:**
- Cooperative and explicit like asyncio (`suspend` functions are the pause points, like `await`).
- **But** they can run on a *multi-threaded dispatcher*, so two coroutines can truly run in parallel on different cores.
- asyncio is strictly **single-threaded** — one thread, no parallelism.

**Why Python went single-threaded — the GIL:**
CPython has a **Global Interpreter Lock**: only one thread may execute Python bytecode at a time. So even if you use real Python threads, your *pure-Python* code doesn't run on multiple cores in parallel — they take turns holding the GIL. (Threads still help for I/O, because the GIL is released while waiting.) Given that, Python embraced the single-threaded event loop for I/O concurrency, and uses **separate processes** (`multiprocessing`) when it needs real CPU parallelism. *(Python 3.13+ ships an experimental "free-threaded" build without the GIL, but standard CPython still has it.)*

| Model | Who switches, and when | True parallelism? | Cost per task | Like asyncio? |
|---|---|---|---|---|
| Java platform threads | OS, **preemptively** (anytime) | Yes (cores) | Heavy (~1 MB) | No |
| Java virtual threads (Loom) | Runtime, **automatically** on I/O | Limited (carriers) | Cheap | **Yes — in purpose** |
| Kotlin coroutines | You, **explicitly** (`suspend`) | Yes (multi-thread dispatcher) | Cheap | Close, but multi-threaded |
| **Python asyncio** | You, **explicitly** (`await`) | **No** (single thread) | Cheap | — |

One-line summary: **asyncio is like Java virtual threads in spirit (many cheap I/O tasks, one/few threads), but with explicit `await` instead of automatic yielding, and no parallelism at all.**

---

## The hidden engineering: what the event loop actually does

You don't strictly need this to use async, but you asked for the machinery, and it makes everything above obvious. The event loop keeps three things:

1. A **ready queue** — tasks that can run *right now*.
2. A set of **timers** — tasks waiting for a time to arrive (that's what `asyncio.sleep` registers).
3. A set of **I/O waiters** — tasks waiting for a socket/file to become readable or writable (that's what a network call registers).

One turn of the loop (a "tick") does this:

1. Run every task in the ready queue, one after another, until the queue is empty. Each runs until it hits an `await` (then it re-parks itself into timers or I/O waiters) or finishes.
2. Look at the timers and figure out how long until the *next* one is due.
3. Ask the operating system: *"put this thread to sleep until any of my registered sockets is ready, OR until that timeout elapses."* On Linux this is `epoll`, on macOS `kqueue`, on Windows `IOCP` — one efficient system call (the "selector").
4. When the OS wakes it (a socket became ready, or a timer came due), move those tasks into the ready queue. Go back to step 1.

Three consequences that explain the demos:

- **When every task is paused, the loop is not busy-looping.** It's asleep inside that OS call (step 3), using ~0% CPU, until a real event. That's why 1000 idle waiters cost almost nothing — this is the whole efficiency of async.
- **"Resume" means "get put on the ready queue," and a ready task only actually runs when the currently-running task yields.** If another task is mid-CPU-loop (no `await`), the ready task must wait for it — exactly demos 2 and 4. The manager is fair, but it can't preempt; it can only take over when a task *lets go*.
- **Bare `await` vs `gather` — why sequential awaits don't overlap.** When you write `await some_coroutine()`, that coroutine runs as *part of your current task* — there's no second task for the loop to switch to, so nothing overlaps (that's p0004 §4, the slow staircase). `asyncio.gather(...)` and `asyncio.create_task(...)` are different: they wrap each coroutine in its **own Task** and hand it to the loop, so now the loop has *several* tasks to interleave. **Overlap requires multiple tasks, and `gather`/`create_task` are how you create them.** That is the real reason `gather` is fast and three `await`s in a row are not.

---

## A mental checklist for real agent code

When you're staring at slow async code, ask in order:

1. **Did I actually create multiple tasks?** Three `await`s in a row = one task = no overlap. Use `gather` / `create_task`.
2. **Is every "wait" async-aware?** `await asyncio.sleep`, `httpx.AsyncClient`, async DB drivers — not `time.sleep`, not `requests`. One blocking call freezes all of it (Case 2).
3. **Is there heavy CPU work anywhere in a coroutine?** Even in an `async` function, a long CPU stretch between awaits blocks everyone (Case 4). Offload it with `asyncio.to_thread`, or a process pool for real number-crunching (Case 3).

For your path, the good news: LangChain's and the LLM SDKs' async methods (`ainvoke`, `astream`) are already written correctly for #2. Your job is mostly #1 (use `gather` to fan out) and #3 (don't do heavy CPU inside a coroutine).

---

## What you now know

- The **thread never pauses** — it always runs the manager. **Tasks** pause; the thread moves to another task.
- **When A waits and B runs, whether A is delayed depends on B:** if B is *waiting*, A resumes on time (waits overlap); if B is *working* (CPU/blocking), A is delayed until B lets go.
- **The fix** for necessary heavy work is `asyncio.to_thread` (or a process pool for CPU) — it lets the busy work happen off the manager's thread.
- **`async` is not magic** — it's the **`await`** that yields. CPU work *between* awaits blocks just as hard as a blocking call.
- **Java map:** asyncio ≈ virtual threads (Loom) in spirit, but explicit `await` and single-threaded; *not* like classic preemptive platform threads. The GIL is why Python leaned this way.
- **Under the hood:** the loop is a ready-queue + timers + I/O-waiters, parked in one efficient OS call (`epoll`/`kqueue`) when idle. "Resume" = "join the ready queue," and it can only actually run when the current task yields. Overlap needs multiple **tasks**, which is what `gather`/`create_task` create.

Back to the main path when you're ready: **`p0005` — comprehensions, iterators, and generators.** Generators are the same pause-and-resume idea from p0004 §1, but used to hand back *values* one at a time — the exact machinery behind `for token in stream:` streaming.
