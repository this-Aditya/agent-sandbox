"""
p0001 — What a prompt REALLY is. The foundation under all prompt engineering.

Run me:
    uv run p0001_prompt.py

Read me with the doc open next to you:
    docs/p0001_prompt.md

Before you can "engineer" a prompt, you have to SEE what a prompt actually is.
Most beginners think a prompt is "the text you type." It is not. This lesson
takes that idea apart and shows the real thing, step by step, in the output:

    1. A prompt is a LIST of messages, not a string.
    2. Every message has a ROLE: system, user, or assistant.
    3. Watch the real bytes leave your computer — the list becomes JSON on the wire.
    4. The reply is just the NEXT message. That is the model's whole job.
    5. "Memory" is an illusion: it is YOU re-sending the whole list every time.

The one sentence to hold onto:
    A prompt is a list of role-tagged messages. Prompt engineering is the craft
    of choosing what goes in that list. The model reads the list and writes the
    next message. Nothing more.
"""

import os
import json
from pathlib import Path

import httpx
from dotenv import load_dotenv
from openai import OpenAI

# Load the token from the .env file sitting next to this script. python-dotenv
# reads the file and puts AGENTIC_AI_LEARNING_GH_TOKEN into the environment for
# us. The token stays in the (gitignored) file — never in the code.
load_dotenv(Path(__file__).with_name(".env"))

MODEL = "openai/gpt-4o-mini"


def section(title: str) -> None:
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


# ===========================================================================
# A HOOK TO SEE THE WIRE.
# The OpenAI SDK sends HTTP requests for you and hides them. We attach a small
# "event hook" to the underlying HTTP client so we can print the REAL request
# bytes for one call (section 3). This is only for learning — you would never
# do this in real code. It is how we make the invisible visible.
# ===========================================================================
_print_next_request = False


def _show_request(request: httpx.Request) -> None:
    global _print_next_request
    if not _print_next_request:      # only print the one call we asked for
        return
    _print_next_request = False

    print("  --- THE ACTUAL HTTP REQUEST YOUR CODE JUST SENT ---")
    print(f"  {request.method} {request.url}")
    print("  a few headers (your token rides in 'authorization' — we redact it):")
    # The SDK adds ~10 headers; show only these four so the output stays clean.
    interesting = ("authorization", "content-type", "host", "accept")
    for name, value in request.headers.items():
        lname = name.lower()
        if lname not in interesting:
            continue                        # step 1: which headers to show at all
        if lname == "authorization":        # step 2: hide the value of the secret one
            value = "<redacted — this is your secret token>"
        print(f"      {name}: {value}")
    print("  body (THIS JSON is your prompt — the messages list — serialized):")
    body = json.loads(request.content)
    for line in json.dumps(body, indent=2).splitlines():
        print("      " + line)
    print("  --- end of request ---")


def build_client() -> OpenAI:
    token = os.environ.get("AGENTIC_AI_LEARNING_GH_TOKEN")
    if not token:
        raise SystemExit(
            "AGENTIC_AI_LEARNING_GH_TOKEN is not set.\n"
            "Put it in the .env file next to this script (see the .env template)."
        )
    # Hand the SDK a custom HTTP client carrying our request hook.
    http_client = httpx.Client(event_hooks={"request": [_show_request]})
    return OpenAI(
        base_url="https://models.github.ai/inference",
        api_key=token,
        http_client=http_client,
    )


# ===========================================================================
# 1. A PROMPT IS A LIST OF MESSAGES — NOT A STRING.
# ===========================================================================
def demo_prompt_is_a_list() -> None:
    section("1. A prompt is a LIST of messages — not a string")

    naive = "Explain what a token is in one sentence."
    print("What you TYPE feels like a plain string:")
    print(f"    {naive!r}")

    # The API does not accept a bare string. It accepts a LIST, where your text
    # is wrapped in a message object that also carries a role.
    messages = [{"role": "user", "content": naive}]
    print("\nBut the API will not accept a string. It accepts a LIST like this:")
    print("    " + json.dumps(messages))
    print("\n  Your one string became ONE item in a list. The LIST is the prompt.")
    print("  Every technique in this phase is really one question:")
    print("  what items do we put in this list, and what words go inside them?")


# ===========================================================================
# 2. EVERY MESSAGE HAS A ROLE: system, user, assistant.
# ===========================================================================
def demo_roles() -> None:
    section("2. Every message has a ROLE: system, user, assistant")

    conversation = [
        {"role": "system", "content": "You are a terse assistant. Answer in one short line."},
        {"role": "user", "content": "What is the capital of Japan?"},
        {"role": "assistant", "content": "Tokyo."},
        {"role": "user", "content": "And of France?"},
    ]
    print("A fuller prompt is a whole conversation. Watch the roles down the left:")
    for i, m in enumerate(conversation):
        print(f"    [{i}] role={m['role']:<9} content={m['content']!r}")

    print("\n  Three roles, three jobs:")
    print("    system    = your standing orders. Rules for the whole chat. Most power.")
    print("    user      = what the human said.")
    print("    assistant = what the model said before. Its OWN past replies come")
    print("                back to it as history, tagged 'assistant'.")
    print("\n  We did NOT send this list yet. Section 3 sends a real one and shows")
    print("  you the exact bytes that leave your machine.")


# ===========================================================================
# 3. WATCH THE REAL BYTES LEAVE — the list becomes JSON on the wire.
# ===========================================================================
def demo_the_wire(client: OpenAI) -> None:
    global _print_next_request
    section("3. Watch the real bytes leave — the list becomes JSON on the wire")

    messages = [
        {"role": "system", "content": "You are a terse assistant. One short sentence."},
        {"role": "user", "content": "What is the capital of Japan?"},
    ]
    print("We send this 2-message list to the model. The hook will print the REAL")
    print("HTTP request the SDK builds — so you watch your prompt become bytes:\n")

    _print_next_request = True       # arm the hook for exactly this one call
    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        temperature=0,
    )

    print("\n  Look at the body above. Your 'prompt' is literally the JSON field")
    print('  called "messages". Engineering a prompt = engineering that JSON.')
    print(f"\n  The model replied: {response.choices[0].message.content!r}")


# ===========================================================================
# 4. THE REPLY IS JUST THE NEXT MESSAGE (role = assistant).
# ===========================================================================
def demo_reply_is_a_message(client: OpenAI) -> None:
    section("4. The reply is just the NEXT message (role = assistant)")

    messages = [{"role": "user", "content": "Reply with the single word: pong"}]
    response = client.chat.completions.create(model=MODEL, messages=messages, temperature=0)
    msg = response.choices[0].message

    print("The response carries a message object — the SAME shape we send:")
    print(f"    role    = {msg.role!r}")
    print(f"    content = {msg.content!r}")
    print("\n  So the model's WHOLE job is tiny: read the messages list, write the")
    print("  next message (role='assistant'). List in, one message out.")

    usage = response.usage
    print(f"\n  (It also reported token counts: prompt={usage.prompt_tokens}, "
          f"reply={usage.completion_tokens}.")
    print("   Those counts are the entire subject of the next lesson, p0002. Skip them now.)")


# ===========================================================================
# 5. "MEMORY" IS AN ILLUSION — it is YOU re-sending the whole list.
# ===========================================================================
def demo_memory_is_resending(client: OpenAI) -> None:
    section("5. 'Memory' is an illusion — it is YOU re-sending the whole list")

    # Turn 1: we tell the model a fact.
    turn1_user = {"role": "user",
                  "content": "My name is Aditya and I like Kotlin. Just reply 'ok'."}
    r1 = client.chat.completions.create(model=MODEL, messages=[turn1_user], temperature=0)
    turn1_assistant = {"role": "assistant", "content": r1.choices[0].message.content}
    print(f"Turn 1 — we said:   {turn1_user['content']!r}")
    print(f"         it replied: {turn1_assistant['content']!r}")

    question = {"role": "user", "content": "What is my name and what do I like?"}

    # WITH history: we resend turn 1 (both messages) plus the new question.
    with_history = [turn1_user, turn1_assistant, question]
    r_with = client.chat.completions.create(model=MODEL, messages=with_history, temperature=0)
    print("\nTurn 2 WITH history (we resend all 3 messages):")
    print(f"    answer: {r_with.choices[0].message.content!r}")

    # WITHOUT history: we send ONLY the new question.
    without_history = [question]
    r_without = client.chat.completions.create(model=MODEL, messages=without_history, temperature=0)
    print("\nTurn 2 WITHOUT history (we send only the question):")
    print(f"    answer: {r_without.choices[0].message.content!r}")

    print("\n  Same model, same question. WITH history it knows; WITHOUT history it")
    print("  cannot. The model remembers NOTHING between calls — each call starts")
    print("  blank. 'Memory' is just you keeping the list and sending it again.")
    print("  Every 'memory' feature later in this course is a trick for building")
    print("  and trimming this one list. Hold on to that.")


def main() -> None:
    # Sections 1 and 2 need no network — pure structure.
    demo_prompt_is_a_list()
    demo_roles()

    # Sections 3–5 make real calls to the model.
    client = build_client()
    demo_the_wire(client)
    demo_reply_is_a_message(client)
    demo_memory_is_resending(client)

    print("\n" + "=" * 70)
    print("Done. Open docs/p0001_prompt.md — it explains each step from zero.")
    print("=" * 70)


if __name__ == "__main__":
    main()
