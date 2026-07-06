"""
p0003 — The system prompt: your main control surface.

Run me:
    uv run p0003_system_prompt.py

Read me with the doc open next to you:
    docs/p0003_system_prompt.md

From p0001 you know a prompt is a list of role-tagged messages. From p0002 you
know it is counted in tokens. This lesson zooms into the single most powerful
item in that list: the `system` message. It is your "standing orders" — rules
that steer the whole conversation. We prove, live, what it can do:

    1. Same question, different system prompt -> different answer.  (the dial)
    2. The system prompt sets rules for the WHOLE chat.             (standing orders)
    3. Does the SLOT change the answer? An honest experiment.       (system vs user)
    4. The system rule persists across turns.                      (why "standing")
    5. Weak vs strong system prompt for the same task.             (the craft)

The one sentence to hold onto:
    The system message is text placed first, in a privileged role the model was
    trained to obey. Change it and you change the model's role, format, and
    limits for every turn — without touching the user's question.
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(Path(__file__).with_name(".env"))

MODEL = "openai/gpt-4o-mini"


def section(title: str) -> None:
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def show(label: str, text: str) -> None:
    """Print a possibly multi-line answer, indented, under a label."""
    print(label)
    for line in text.splitlines() or [""]:
        print("      " + line)


def build_client() -> OpenAI:
    token = os.environ.get("AGENTIC_AI_LEARNING_GH_TOKEN")
    if not token:
        raise SystemExit(
            "AGENTIC_AI_LEARNING_GH_TOKEN is not set.\n"
            "Put it in the .env file next to this script (see the .env template)."
        )
    return OpenAI(base_url="https://models.github.ai/inference", api_key=token)


def ask(client: OpenAI, messages: list, **kw) -> str:
    # temperature=0 so re-runs are stable and the ONLY thing changing is the prompt.
    kw.setdefault("temperature", 0)
    resp = client.chat.completions.create(model=MODEL, messages=messages, **kw)
    return resp.choices[0].message.content


# ===========================================================================
# 1. SAME QUESTION, DIFFERENT SYSTEM PROMPT -> DIFFERENT ANSWER.
# ===========================================================================
def demo_same_question(client: OpenAI) -> None:
    section("1. Same question, different system prompt -> different answer")

    question = "What is a database index?"
    print(f"User question (IDENTICAL every time): {question!r}\n")

    # A) no system message at all
    a = ask(client, [{"role": "user", "content": question}], max_tokens=110)
    show("[A] NO system message:", a)
    print()

    # B) terse expert
    sys_b = "You are a senior engineer. Answer in ONE short sentence. No preamble."
    b = ask(client, [{"role": "system", "content": sys_b},
                     {"role": "user", "content": question}], max_tokens=110)
    show(f"[B] system = {sys_b!r}", b)
    print()

    # C) pirate — obviously different, so the steering is undeniable
    sys_c = "You are a pirate. Answer in pirate speak, matey. Keep it short."
    c = ask(client, [{"role": "system", "content": sys_c},
                     {"role": "user", "content": question}], max_tokens=110)
    show(f"[C] system = {sys_c!r}", c)
    print()

    print("  The user question never changed. The ONLY change was the system message,")
    print("  and it moved length, tone, and voice. That is your main steering dial.")


# ===========================================================================
# 2. THE SYSTEM PROMPT SETS RULES FOR THE WHOLE CHAT.
#    One rule governs many different user inputs -> the basis of guardrails.
# ===========================================================================
def demo_rules_for_whole_chat(client: OpenAI) -> None:
    section("2. The system prompt sets rules for the WHOLE chat")

    sys = ("You are a cooking assistant. You ONLY answer questions about cooking. "
           "For anything not about cooking, reply with exactly: I only help with cooking.")
    print(f"system = {sys!r}\n")

    for q in [
        "How do I boil a perfect egg?",
        "What is the capital of France?",
        "Write a Python function to sort a list.",
    ]:
        a = ask(client, [{"role": "system", "content": sys},
                         {"role": "user", "content": q}], max_tokens=110)
        print(f"  user: {q!r}")
        show("  ->", a)
        print()

    print("  One system rule, three very different questions. It answered the cooking")
    print("  one and refused the others with the EXACT line we specified. A system")
    print("  message is standing orders applied to every input — the root of guardrails.")


# ===========================================================================
# 3. DOES THE SLOT CHANGE THE ANSWER? AN HONEST EXPERIMENT.
#    Common belief: "system is powerful, user is ignored." Let's TEST it, and
#    report the real result instead of asserting a myth.
# ===========================================================================
def demo_slot_experiment(client: OpenAI) -> None:
    section("3. Does the SLOT change the answer? An honest experiment")

    rule = "You must reply with exactly one word: PING."
    question = "What is the capital of France? Answer in a full sentence."
    n = 8

    print("A common belief: 'system is obeyed, user is ignored.' Let's TEST it, not")
    print("assert it. We pit a RULE ('reply only PING') against a QUESTION that wants")
    print(f"a full sentence, and run it {n} times per slot (temperature=1, so it varies).")
    print("The rule 'wins' when the answer is PING and not 'Paris'.\n")

    for role in ("system", "user"):
        wins = 0
        samples: list[str] = []
        for _ in range(n):
            out = ask(client,
                      [{"role": role, "content": rule},
                       {"role": "user", "content": question}],
                      temperature=1, max_tokens=20)
            if "paris" not in out.lower():
                wins += 1
            samples.append(out.strip())
        print(f"  rule in {role.upper():6}: PING won {wins}/{n}   e.g. {samples[:3]}")

    print("\n  Honest result: a clear instruction is obeyed almost every time in BOTH")
    print("  slots. The system slot is not 'magic power' that makes user text ignored,")
    print("  and obedience is probabilistic — you may see a rare miss. So why still")
    print("  prefer system for standing rules? Three real reasons:")
    print("   1. PERSISTENCE — system rides at item 0 and is resent every turn (see")
    print("      section 4). It is your app's fixed configuration.")
    print("   2. PRECEDENCE  — the model is trained to prefer system over user when they")
    print("      truly CONFLICT; that shows up against hostile input, not benign asks.")
    print("   3. TRUST       — system is YOUR text; user is untrusted outside input.")
    print("      Keeping rules out of the user slot is what blocks prompt injection (p0004).")


# ===========================================================================
# 4. THE SYSTEM RULE PERSISTS ACROSS TURNS.
#    It rides at position 0 of the list we resend every turn (p0001 / p0002).
# ===========================================================================
def demo_persists_across_turns(client: OpenAI) -> None:
    section("4. The system rule persists across turns (it is resent as item 0)")

    sys = "End every reply with the exact marker [OK]. Keep replies to a few words."
    print(f"system = {sys!r}\n")

    convo: list[dict] = [{"role": "system", "content": sys}]
    for q in ["Name a color.", "Now name an animal.", "Now name a country."]:
        convo.append({"role": "user", "content": q})
        a = ask(client, convo, max_tokens=20)
        convo.append({"role": "assistant", "content": a})
        print(f"  turn user: {q!r}")
        show("  ->", a)
        print()

    print("  Three turns, one system rule, obeyed every time. Why? The system message")
    print("  sits at position 0 of the list we resend each turn (p0001 memory,")
    print("  p0002 tokens). Persistent rules cost tokens every turn — the price of 'standing'.")


# ===========================================================================
# 5. WEAK vs STRONG SYSTEM PROMPT FOR THE SAME TASK.
# ===========================================================================
def demo_weak_vs_strong(client: OpenAI) -> None:
    section("5. Weak vs strong system prompt for the SAME task")

    ticket = ("Hi, I was charged twice for my subscription this month and I'm really "
              "upset. Please fix it now.")
    print(f"Ticket (same for both): {ticket!r}\n")

    weak = "You help with support tickets."
    w = ask(client, [{"role": "system", "content": weak},
                     {"role": "user", "content": ticket}], max_tokens=200)
    show(f"[WEAK]   system = {weak!r}", w)
    print()

    strong = (
        "You are a support-triage assistant. For the user's message, output EXACTLY "
        "three lines and nothing else:\n"
        "Category: one of [billing, technical, account, other]\n"
        "Urgency: one of [low, medium, high]\n"
        "Reply: a single polite sentence to the customer."
    )
    s = ask(client, [{"role": "system", "content": strong},
                     {"role": "user", "content": ticket}], max_tokens=200)
    show("[STRONG] system = role + task + allowed values + exact format", s)
    print()

    print("  Same ticket. The weak prompt rambles; the strong prompt returns clean,")
    print("  predictable lines you could parse in code. Specific role + rules + format")
    print("  = reliability. This is the bridge to p0004 (structure) and p0008 (typed output).")


def main() -> None:
    client = build_client()
    demo_same_question(client)
    demo_rules_for_whole_chat(client)
    demo_slot_experiment(client)
    demo_persists_across_turns(client)
    demo_weak_vs_strong(client)

    print("\n" + "=" * 70)
    print("Done. Open docs/p0003_system_prompt.md — it explains each step from zero.")
    print("=" * 70)


if __name__ == "__main__":
    main()
