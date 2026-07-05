"""
p0003 — ENVIRONMENT & PACKAGING: where your code and its libraries actually live.

Run me the normal way:
    uv run p0003_environment.py

Then run me a DIFFERENT way to see the whole point (from this folder):
    /usr/bin/python3 p0003_environment.py
    -> a different Python, with NO pydantic. That gap is the lesson.

Read me with the doc open next to you:
    docs/p0003_environment.md

The problem this all solves:
    There is usually ONE Python on your computer, and by default ONE shared
    folder where libraries get installed. So project A wanting pydantic v1 and
    project B wanting pydantic v2 would COLLIDE. A "virtual environment" (.venv)
    fixes this: it gives THIS project its own private Python + its own private
    library folder. `uv` is the tool that builds and manages all of it.

The one idea to remember:
    `uv run` does NOT use "the Python on your PATH". It uses the private Python
    inside this project's .venv, whose imports come from this project's own
    library folder. Isolation, proven below by the program printing where it is.

Kotlin bridge:
    On the JVM, Gradle/Maven give each project its own dependency set via the
    classpath — you never think about it. Python has no per-project classpath,
    so the .venv IS that isolation, and `uv` is roughly Gradle + a JVM version
    manager rolled into one fast tool.
"""

import sys
from pathlib import Path


def section(title: str) -> None:
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


# ---------------------------------------------------------------------------
# 1. WHICH Python is running me right now?
# ---------------------------------------------------------------------------
def demo_which_python() -> None:
    section("1. Which Python is actually running this file?")

    # sys.executable = the exact interpreter binary running this program.
    print("sys.executable =", sys.executable)
    print("version        =", sys.version.split()[0])

    if ".venv" in sys.executable:
        print("\n-> It's the python INSIDE this project's .venv folder.")
        print("   `uv run` chose it for you. You never typed its path.")
    else:
        print("\n-> This is NOT the project's .venv python (see the doc's experiment).")


# ---------------------------------------------------------------------------
# 2. PROOF it's a virtual environment: prefix vs base_prefix.
# ---------------------------------------------------------------------------
def demo_isolation_proof() -> None:
    section("2. Proof this is a virtual environment")

    # A venv is a thin folder that BORROWS a real Python underneath it.
    #   sys.prefix      -> the venv (where THIS project's stuff lives)
    #   sys.base_prefix -> the real Python the venv was built from
    # If they differ, you are inside a venv.
    print("sys.prefix      =", sys.prefix)
    print("sys.base_prefix =", sys.base_prefix)

    in_venv = sys.prefix != sys.base_prefix
    if in_venv:
        print("\nprefix != base_prefix  ->  YES, you are inside a virtual environment.")
        print("The venv didn't copy all of Python — it reuses the real one")
        print("(base_prefix) and just adds its OWN private library folder on top.")
    else:
        print("\nprefix == base_prefix  ->  NO venv: this is a plain Python install.")
        print("(You'll see this when you run me with the raw system python.)")


# ---------------------------------------------------------------------------
# 3. WHERE do imported libraries come from?
# ---------------------------------------------------------------------------
def demo_where_imports_come_from() -> None:
    section("3. Where does `import pydantic` actually load from?")

    try:
        import pydantic
    except ModuleNotFoundError:
        print("Could NOT import pydantic from this Python.")
        print("That is not an error in your setup — it's the whole point:")
        print("this Python has its OWN library folder, and pydantic isn't in it.")
        print("(You are seeing this because you ran me WITHOUT `uv run`.)")
        return

    print("pydantic.__version__ =", pydantic.__version__)
    print("pydantic.__file__    =", pydantic.__file__)
    print("\n-> Notice the path runs through THIS project's")
    print("   .venv/lib/.../site-packages/ — its own private library folder.")
    print("   Another project's .venv could hold a totally different version.")


# ---------------------------------------------------------------------------
# 4. HOW does Python decide where to look? sys.path.
# ---------------------------------------------------------------------------
def demo_search_path() -> None:
    section("4. The import search path (how `import` finds things)")

    # On `import X`, Python walks sys.path top-to-bottom and uses the first
    # place it finds X. The venv's site-packages is on this list — that's the
    # mechanism that makes isolation work.
    print("Python searches these places, in order:")
    for entry in sys.path:
        shown = entry if entry else "(the current folder)"
        mark = ""
        if "site-packages" in entry and ".venv" in entry:
            mark = "   <<< THIS project's private libraries"
        print("  ", shown, mark)


# ---------------------------------------------------------------------------
# 5. THE PROJECT FILES: pyproject.toml (what you want) vs the lock (what you got).
# ---------------------------------------------------------------------------
def demo_project_files() -> None:
    section("5. pyproject.toml (declared) vs uv.lock (exact)")

    try:
        import tomllib  # built into Python 3.11+; reads .toml files
    except ModuleNotFoundError:
        print("(This Python is older than 3.11, so it can't read TOML. Skipping.)")
        return

    here = Path(__file__).parent
    data = tomllib.loads((here / "pyproject.toml").read_text())
    project = data["project"]

    print("pyproject.toml — the MANIFEST you edit (like build.gradle):")
    print("  name            =", project["name"])
    print("  requires-python =", project["requires-python"])
    print("  dependencies    =", project["dependencies"])

    # The dependency line is a CONSTRAINT (a range), not an exact version.
    try:
        import pydantic
        print(f"\nYou declared a range like 'pydantic>=2.13.4' (a CONSTRAINT).")
        print(f"uv.lock pinned the EXACT version, and that's what is installed:")
        print(f"  actually installed pydantic == {pydantic.__version__}")
        print("Constraint = what you'll accept. Lock = what you actually used.")
    except ModuleNotFoundError:
        pass


def main() -> None:
    demo_which_python()
    demo_isolation_proof()
    demo_where_imports_come_from()
    demo_search_path()
    demo_project_files()
    print("\n" + "=" * 70)
    print("Done. Open docs/p0003_environment.md — especially the uv command map.")
    print("=" * 70)


if __name__ == "__main__":
    main()
