# p0003 — Environment & Packaging: where your code and its libraries live

> **Run the code two ways, then read this.**
> ```bash
> uv run p0003_environment.py        # the normal way
> /usr/bin/python3 p0003_environment.py   # the raw system python — see it break
> ```
> Each part below matches a numbered block in `p0003_environment.py`.

---

## The main idea (read this twice)

On the JVM you never worry about this, so it needs saying plainly:

> By default, your computer has **one** Python and **one** shared folder where libraries get installed. So if project A needs an old version of a library and project B needs a new one, they **collide** — the second install overwrites the first.

A **virtual environment** (the `.venv` folder) fixes this. It gives *one project* its **own private Python and its own private library folder.** Nothing leaks between projects.

And `uv` is the tool that builds and runs all of it. So the one line to remember:

> **`uv run` does not use "the Python on your PATH". It uses the private Python inside this project's `.venv`, and imports come from this project's own library folder. The program proves this by printing exactly where it is running.**

**Kotlin bridge — this is the clearest way to get it:**

| On the JVM (what you know) | In Python (what's new) |
|---|---|
| One global JDK, but Gradle/Maven give **each project its own classpath** | One global Python, but each project gets its own **`.venv`** |
| You never think about isolation — the build tool computes the classpath | The `.venv` **is** the isolation; you (well, `uv`) set it up |
| `build.gradle` declares dependencies | `pyproject.toml` declares dependencies |
| `gradle.lockfile` pins exact versions | `uv.lock` pins exact versions |
| `./gradlew run` runs with the right classpath | `uv run` runs with the right `.venv` |

So: **Gradle's per-project classpath is a computed thing you never see. Python's version is a real folder (`.venv`) sitting in your project.** `uv` is roughly *Gradle + a JVM version manager (like sdkman) rolled into one very fast tool.*

---

## 1. Which Python is actually running me?

```text
sys.executable = /Users/.../2.python/.venv/bin/python3
version        = 3.14.5
```

`sys.executable` is the exact Python program running your code. When you type `uv run`, it is the one **inside `.venv`** — you never typed that path. `uv` found it for you.

Now run the same file the raw way (`/usr/bin/python3 p0003_environment.py`) and you get a *completely different* answer:

```text
sys.executable = /Library/Developer/CommandLineTools/usr/bin/python3
version        = 3.9.6
```

Different program. **Different version even** (3.9.6, an old macOS built-in). Same file, two different Pythons. This is the whole lesson in one comparison: *"python" is not one thing on your machine — it depends entirely on how you launch it.* `uv run` removes that guesswork by always choosing your project's own.

---

## 2. Proof it's a virtual environment

A `.venv` is not a full copy of Python. It's a thin folder that **borrows** a real Python underneath and adds its own library folder. Two values reveal this:

- `sys.prefix` — where **this** Python keeps its stuff.
- `sys.base_prefix` — the **real** Python it was built from.

Inside a venv, they differ:

```text
sys.prefix      = /Users/.../2.python/.venv
sys.base_prefix = /opt/homebrew/opt/python@3.14/.../3.14
prefix != base_prefix  ->  YES, you are inside a virtual environment.
```

Run the raw system Python and they're the **same** (no venv):

```text
sys.prefix      = /Library/.../Versions/3.9
sys.base_prefix = /Library/.../Versions/3.9
prefix == base_prefix  ->  NO venv: this is a plain Python install.
```

That's what a venv really is: **a small folder that reuses the base Python (`base_prefix`) but points `prefix` at its own private library area.** Cheap to make, cheap to delete, one per project.

---

## 3. Where does `import pydantic` load from?

This is the payoff of isolation. Under `uv run`:

```text
pydantic.__version__ = 2.13.4
pydantic.__file__    = /Users/.../2.python/.venv/lib/python3.14/site-packages/pydantic/__init__.py
```

The library loads from **this project's own** `.venv/.../site-packages/` folder. A *different* project's `.venv` could hold a different pydantic version, and neither would disturb the other. That's the collision problem, solved.

Under the raw system Python:

```text
Could NOT import pydantic from this Python.
```

Not a bug — the point. That Python has its **own** (empty of pydantic) library folder. You installed pydantic into the project's `.venv`, not into the system Python. So only `uv run` can see it.

> `site-packages` is simply "the folder where installed third-party libraries live." Every Python has one. The venv's job is to give your project a private one.

---

## 4. How Python finds imports: `sys.path`

When you write `import pydantic`, Python walks a list of folders called `sys.path`, top to bottom, and uses the first place it finds it:

```text
   /Users/.../2.python                                    (your project folder)
   .../python3.14                                         (Python's own standard library)
   .../2.python/.venv/lib/python3.14/site-packages    <<< THIS project's private libraries
```

That last line is the mechanism behind everything in this lesson. Isolation isn't magic — it's just that **the venv's `site-packages` is on `sys.path`, and the system one is not.** Change which Python runs, and this list changes, and so does what you can import.

---

## 5. `pyproject.toml` (what you want) vs `uv.lock` (what you got)

Two files describe your dependencies, and the difference matters:

```text
pyproject.toml — the MANIFEST you edit (like build.gradle):
  name            = 2-python
  requires-python = >=3.14
  dependencies    = ['pydantic>=2.13.4']

You declared a range like 'pydantic>=2.13.4' (a CONSTRAINT).
uv.lock pinned the EXACT version, and that's what is installed:
  actually installed pydantic == 2.13.4
```

- **`pyproject.toml`** is the file *you* edit. It lists **constraints** — ranges, like `pydantic>=2.13.4`, meaning "any version from 2.13.4 up is fine with me." This is your `build.gradle`.
- **`uv.lock`** is generated by `uv`. It records the **exact** version of every library — *including* the libraries your libraries pulled in (pydantic quietly brought `pydantic-core`, `annotated-types`, `typing-extensions`, and more). This is your `gradle.lockfile`.

Why two files? So builds are **reproducible**. The constraint says what you'd *accept*; the lock says what you *actually used*. You commit both to git, and anyone who runs `uv sync` gets the byte-for-byte same versions you had — no "works on my machine."

> The program reads `pyproject.toml` using `tomllib`, which is built into Python 3.11+. That's why the raw 3.9 Python skipped this section — it's too old to have `tomllib`.

---

## The `uv` command map (keep this handy)

Everything you'll do, and its Gradle/Maven cousin:

| `uv` command | What it does | JVM cousin |
|---|---|---|
| `uv init` | start a new project (makes `pyproject.toml`, `.venv`, `.python-version`) | `gradle init` |
| `uv add <pkg>` | add a dependency: edit `pyproject.toml`, update `uv.lock`, install into `.venv` | add a line to `dependencies {}` |
| `uv remove <pkg>` | the reverse of `add` | remove that line |
| `uv sync` | make `.venv` **exactly** match `uv.lock` (install/remove as needed) | `./gradlew build` resolving deps |
| `uv lock` | re-resolve `pyproject.toml` and rewrite `uv.lock` | refresh the lockfile |
| `uv run <cmd>` | run a command inside `.venv` (auto-syncs first — no "activate" step) | `./gradlew run` |
| `uvx <tool>` | run a CLI tool in a throwaway temp env (e.g. `uvx pyright`) | `npx` / `pipx run` |
| `uv python install 3.14` | download/manage a Python **version** itself | sdkman / jenv |

The two you'll type most: **`uv add`** (get a library) and **`uv run`** (run your code). You never manually "activate" anything — that older Python ritual is what `uv run` does for you every time.

---

## What `uv add pydantic` actually did (back in lesson 2)

Remember this line from p0002? Here's everything it did in one shot:

1. **Edited `pyproject.toml`** — added `"pydantic>=2.13.4"` to `[project].dependencies`.
2. **Resolved the full graph** — figured out that pydantic needs `pydantic-core`, `annotated-types`, `typing-extensions`, `typing-inspection`, and picked versions of all of them that fit together.
3. **Wrote `uv.lock`** — recorded those exact versions (with hashes, so a tampered download is caught).
4. **Installed into `.venv`** — copied those packages into `.venv/lib/python3.14/site-packages/`.

That's why, immediately after, `import pydantic` just worked in lesson 2 — step 4 had put it exactly where `sys.path` (section 4) looks.

---

## Run it, then break it (this part matters most)

1. **The headline experiment:** run it both ways and compare sections 1–3.
   ```bash
   uv run p0003_environment.py         # its own python, pydantic works
   /usr/bin/python3 p0003_environment.py   # different python + version, no pydantic
   ```
   That difference *is* isolation. Sit with it.
2. **Add and remove a library:** run `uv add rich`, then look at `pyproject.toml` and `uv.lock` — both changed. Now `uv run python -c "import rich; print(rich.__file__)"` works. Then `uv remove rich` and watch it undo. (`rich` is a pretty-printing library; harmless to try.)
3. **Look inside the box:** `ls .venv/lib/python3.14/site-packages/` — every installed library is a real folder here. This is the "private library folder" from sections 2–3, made concrete.
4. **Prove `.venv` is disposable:** delete it entirely (`rm -rf .venv`), then run `uv sync`. `uv` rebuilds the whole thing from `uv.lock` in seconds. That's why `.venv` is in `.gitignore` and never committed — it's fully rebuildable from the lock.
5. **Read the lock:** open `uv.lock`. You'll see every package pinned to an exact version with a hash. This is the file that makes your project reproducible on any machine.

---

## What you now know

- Your computer has one global Python; a **`.venv`** gives each project its **own private Python + library folder**, so projects never collide. On the JVM, Gradle's classpath did this invisibly; in Python it's a real folder.
- **`uv run`** uses the `.venv` Python, not whatever's on your PATH — proven by `sys.executable` and `pydantic.__file__` both pointing inside `.venv`.
- A venv is a thin layer: `sys.prefix` (its own area) differs from `sys.base_prefix` (the real Python it borrows).
- **`import` finds libraries via `sys.path`**, and the venv's `site-packages` is on that list. That's the whole isolation mechanism.
- **`pyproject.toml`** = your editable manifest of constraints (`build.gradle`). **`uv.lock`** = exact pinned versions for reproducibility (`gradle.lockfile`). Commit both; never commit `.venv`.
- The commands: **`uv add`** to get a library, **`uv run`** to run your code, `uv sync` to rebuild from the lock, `uvx` to run a tool once.

**Next lesson — `p0004`: `async` / `await`.** This is the one place your Kotlin background gives you a real head start — Python's `async` is close to Kotlin coroutines, but with one big twist (a single-threaded "event loop"). We'll build a runnable program that shows *why* async makes an agent that calls several tools or LLMs feel many times faster, and exactly when it does nothing at all.
