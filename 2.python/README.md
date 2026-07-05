# Phase 2 — Python for a Kotlin/JVM backend dev

A hands-on, run-it-yourself course. Each lesson is **a runnable program that
proves its own claims** plus a deep written explanation. You come from
Kotlin/Spring — every lesson bridges from what you already know.

## How to use this

For each lesson `pNNNN`:

1. **Run the code** and watch the output:
   ```bash
   uv run pNNNN_topic.py
   ```
2. **Read the doc** in `docs/pNNNN_topic.md` — it explains *why* each block
   behaves the way it does, section-for-section with the code.
3. **Break it.** Every doc ends with experiments. Edit a line, re-run, watch
   reality change. That loop is where understanding actually happens.
4. Optionally run the type checker over any lesson:
   ```bash
   uvx pyright pNNNN_topic.py
   ```

## Lessons

| # | Topic | Code | Doc | The one idea |
|---|-------|------|-----|--------------|
| 1 | Type hints | [`p0001_typing.py`](p0001_typing.py) | [`docs/p0001_typing.md`](docs/p0001_typing.md) | Types are **runtime data**, not compile-time walls — frameworks read them |
| 2 | Pydantic | [`p0002_pydantic.py`](p0002_pydantic.py) | [`docs/p0002_pydantic.md`](docs/p0002_pydantic.md) | Type notes become **real rules**: LLM JSON → typed, validated objects |
| 3 | Environment & packaging (`uv`, `.venv`, `pyproject.toml`) | [`p0003_environment.py`](p0003_environment.py) | [`docs/p0003_environment.md`](docs/p0003_environment.md) | Why virtual envs exist (`.venv` = Gradle's classpath, made a folder) |
| 4 | `async` / `await` | [`p0004_async.py`](p0004_async.py) | [`docs/p0004_async.md`](docs/p0004_async.md) | One thread + an event loop; `gather` overlaps waits (3s → 1s), proven by timing |
| 4b | async deep dive: overlap, delays, Java comparison | [`p0004b_async_deep.py`](p0004b_async_deep.py) | [`docs/p0004b_async_deep.md`](docs/p0004b_async_deep.md) | When A waits and B runs, is A delayed? Depends: is B *waiting* or *working*? |
| 4c | from generator to real async (the mapping) | [`p0004c_generator_to_async.py`](p0004c_generator_to_async.py) | _(code comments)_ | Same `brew` shown 3 ways: `yield`+`next()` = `await`+`.send()` = the event loop |
| 5 | Comprehensions, iterators, generators | _next_ | _next_ | Lazy sequences — the machinery behind LLM token streaming |
| 6 | Decorators | _planned_ | _planned_ | Functions that wrap functions — how `@tool` and `@app.post` really work |

## Environment

- Python **3.14** (see `.python-version`), managed by [`uv`](https://docs.astral.sh/uv/).
- `uv run <file>` runs a file inside this project's `.venv` automatically —
  you never manually activate anything.
