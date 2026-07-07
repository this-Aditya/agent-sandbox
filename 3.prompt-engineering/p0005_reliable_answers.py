"""
p0005 — Reliable answers: chain-of-thought + temperature.

Run me:
    uv run p0005_reliable_answers.py

Read me with the doc open next to you:
    docs/p0005_reliable_answers.md

So far we shaped WHAT we send (roles, structure, examples). This lesson is about
getting the answer RIGHT and REPEATABLE. Two dials:

  CHAIN-OF-THOUGHT (accuracy on hard questions):
    1. Rushed answer is wrong; "think step by step" fixes it.  (reason first)
    2. Reason for accuracy, but PARSE only the final answer.   (reason + extract)

  TEMPERATURE (randomness):
    3. Same prompt: temp 0 repeats, high temp varies.          (the randomness dial)
    4. When to use temp 0 vs higher.                           (the rule)

This lesson makes only ~7 model calls on purpose — no big loops.

The one sentence to hold onto:
    Give the model room to REASON before it answers (it computes in the tokens it
    writes), and set TEMPERATURE to 0 when you want the same correct answer every
    time, higher when you want variety.
"""

import re

from _llm import PROVIDER, MODEL, build_client, ask


def section(title: str) -> None:
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def show(label: str, text: str) -> None:
    print(label)
    for line in text.splitlines() or [""]:
        print("      " + line)


# ===========================================================================
# 1. RUSHED ANSWER IS WRONG; "THINK STEP BY STEP" FIXES IT.
#    Counting letters is HARD for a model (p0002: it sees tokens, not letters).
#    Forcing it to spell the word out gives it the steps it needs.
# ===========================================================================
def demo_reason_first(client) -> None:
    section("1. Rushed answer is wrong; 'think step by step' fixes it")

    word = "strawberry raspberry cranberry"
    print(f"Task: count the letter 'r' in {word!r}. (The real answer is 6.)\n")

    # [A] Force a bare answer — no room to think.
    blurt = ask(client, [{"role": "user",
                          "content": f"How many times does the letter 'r' appear in "
                                     f"'{word}'? Reply with only the number, nothing else."}],
                )
    show("[A] RUSHED ('reply with only the number'):", blurt)
    print()

    # [B] Ask it to reason first — spell out, mark, then count.
    cot = ask(client, [
        {"role": "user",
                        "content": f"How many times does the letter 'r' appear in '{word}'? "
                                   f"Think step by step: write each word out letter by letter, "
                                   f"mark every 'r', then count the marks. Give the final count last."}],
              )
    show("[B] REASONED ('think step by step'):", cot)
    print()

    print("  The rushed answer is usually wrong; the reasoned one is usually right.")
    print("  Why? From p0002: the model reads TOKENS, not letters. It cannot 'see'")
    print("  the r's inside a token. Forcing it to spell the word out creates the")
    print("  letter-by-letter tokens it needs, so it can actually count. The reasoning")
    print("  is not decoration — the model literally computes IN the tokens it writes.")


# ===========================================================================
# 2. REASON FOR ACCURACY, BUT PARSE ONLY THE FINAL ANSWER.
#    You want the thinking (accuracy) but your code needs just the result.
# ===========================================================================
def demo_reason_and_extract(client) -> None:
    section("2. Reason for accuracy, but parse only the final answer")

    problem = ("I buy 3 notebooks at £2.75 each and 2 pens at £1.40 each, and pay "
               "with a £20 note. How much change do I get?")
    print(f"Problem: {problem}\n")

    reply = ask(client, [{"role": "user",
                          "content": problem + " Reason step by step. Then on the very "
                                               "last line write exactly: ANSWER: <amount>"}],
                )
    show("Full reply (reasoning + a marked final line):", reply)

    # Now CODE pulls out just the answer, using the ANSWER: marker.
    match = re.search(r"ANSWER:\s*(.+)", reply)
    final = match.group(1).strip() if match else "(marker not found)"
    print(f"\n  Code extracted just the final answer: {final!r}")
    print("  (Correct change is £8.95.)")

    print("\n  The trick: let the model REASON (it needs the steps to be accurate),")
    print("  but tell it to end with a fixed marker line ('ANSWER: ...'). Your code")
    print("  reads only that line. You get accuracy AND a clean value to use. This")
    print("  is the bridge to p0006, where we force the whole reply to be typed JSON.")


# ===========================================================================
# 3. SAME PROMPT: temp 0 REPEATS, HIGH temp VARIES.
#    Temperature controls how random the next-token choice is.
# ===========================================================================
def demo_temperature(client) -> None:
    section("3. Same prompt: temperature 0 repeats, high temperature varies")

    prompt = "Write a six-word story about the sea."
    print(f"Same prompt both times: {prompt!r}\n")

    print("temperature = 0  (pick the most likely token every time):")
    show("  run 1:", ask(client, [{"role": "user", "content": prompt}], temperature=0, ))
    show("  run 2:", ask(client, [{"role": "user", "content": prompt}], temperature=0, ))

    print("\ntemperature = 1.3  (sometimes pick less-likely tokens):")
    show("  run 1:", ask(client, [{"role": "user", "content": prompt}], temperature=1.3, ))
    show("  run 2:", ask(client, [{"role": "user", "content": prompt}], temperature=1.3, ))

    print("\n  temp 0: the two runs are the same (or nearly) — the model always takes")
    print("  the single most likely next token, so it repeats. High temp: the two")
    print("  runs differ — the model rolls a weighted dice and sometimes picks a")
    print("  less-likely token, which sends the story down a new path.")


# ===========================================================================
# 4. WHEN TO USE WHICH (no model calls — the rule).
# ===========================================================================
def demo_when_to_use() -> None:
    section("4. When to use temperature 0 vs higher (the rule)")

    print("  Use temperature = 0 when there is a RIGHT answer and you want it the")
    print("  same every time:")
    print("     - extraction (pull fields out of text)")
    print("     - classification (pick a label)")
    print("     - math / code / following a format")
    print("   This is why the phase build uses temp 0 for --classify and --extract.")
    print()
    print("  Use a HIGHER temperature (about 0.7-1.0) when you want variety or")
    print("  creativity, and there is no single right answer:")
    print("     - brainstorming names or ideas")
    print("     - creative writing")
    print("     - offering several different options")
    print()
    print("  Default for backend/agent work: keep it LOW (0-0.3). Predictable beats")
    print("  surprising when code depends on the output.")


def main() -> None:
    print(f"(backend: provider={PROVIDER}, model={MODEL})")
    client = build_client()
    demo_reason_first(client)
    demo_reason_and_extract(client)
    demo_temperature(client)
    demo_when_to_use()

    print("\n" + "=" * 70)
    print("Done. Open docs/p0005_reliable_answers.md — it explains each step from zero.")
    print("=" * 70)


if __name__ == "__main__":
    main()
