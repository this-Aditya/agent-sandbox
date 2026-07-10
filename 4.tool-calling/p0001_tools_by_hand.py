"""
p0001 — TOOL CALLING, BUILT BY HAND: there is no magic.

Run me:
    uv run p0001_tools_by_hand.py

Read me with the doc open next to you:
    docs/p0001_tools_by_hand.md

THE ROOT OF THE WHOLE PHASE
    An LLM is only a text function. Tokens in, tokens out. That is ALL it does.
    It cannot read a clock, open a database, or call an API. So how does an
    "AI agent" book a flight or check the weather? Through one fixed 4-step
    protocol called TOOL CALLING. Every framework you meet later (LangChain's
    @tool, LangGraph's ToolNode, MCP) is a wrapper over this exact protocol.

    Before we use the provider's real `tools=` feature (that is the next lesson,
    p0002), we build the whole thing BY HAND here, with no special API at all —
    just a system prompt and plain text. Once you have built it yourself, the
    real API has nothing left to hide.

THE PATH (root to leaf)
    0. Prove the model is blind: it cannot know the real time or weather.
    1. STEP 1 — define real Python tools, and DESCRIBE them to the model.
    2. STEP 2 — the model DECIDES: it writes a tool request (just text!).
    3. STEP 3 — WE execute: parse the request, run the real function.
    4. STEP 4 — feed the result back; the model answers using real data.
    5. Same 4 steps, reused for a second tool (weather) — it is a pattern.

THE ONE IDEA TO REMEMBER
    "Tool calling" is not the model doing things. The model only ever writes
    text. When it "calls a tool" it is asking YOUR code to do the work and hand
    the result back. Four steps: you describe tools -> model requests one ->
    you run it -> you return the result. That is the entire mechanism.
"""

import json
from datetime import datetime
from zoneinfo import ZoneInfo

from _llm import build_client, ask, MODEL, PROVIDER


def section(title: str) -> None:
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


# ===========================================================================
# THE REAL TOOLS — ordinary Python functions. Nothing about them is special.
# get_current_time returns the ACTUAL time (real datetime). get_weather is
# hardcoded, exactly like the course build asks.
# ===========================================================================
def get_current_time(timezone: str) -> str:
    """Return the real current time in an IANA timezone like 'Asia/Tokyo'."""
    try:
        now = datetime.now(ZoneInfo(timezone))
        return now.strftime("%A, %d %B %Y, %H:%M:%S %Z")
    except Exception:
        return f"ERROR: '{timezone}' is not a valid IANA timezone."


def get_weather(city: str) -> str:
    """Return a (hardcoded) weather report for a city."""
    fake = {
        "Tokyo": "18°C, light rain",
        "Paris": "24°C, clear sky",
        "London": "15°C, cloudy",
    }
    return fake.get(city, f"20°C, sunny (no data for {city}, using a default)")


# A registry: tool name -> the real Python function. STEP 3 looks tools up here.
# (This is the same name->function idea you built with the @tool decorator in
# Python lesson p0006. Frameworks keep a registry exactly like this.)
TOOLS = {
    "get_current_time": get_current_time,
    "get_weather": get_weather,
}


# The system prompt is where we DESCRIBE the tools and invent our protocol:
# "if you need a tool, answer with JSON only". This is STEP 1 done by hand.
SYSTEM_PROMPT = """You are an assistant that can use tools to get real-world \
data you do not know.

Available tools:
- get_current_time(timezone): the current time. `timezone` is an IANA name \
like "Asia/Tokyo" or "Europe/Paris".
- get_weather(city): the current weather in a city. `city` is a plain name \
like "Tokyo".

You do NOT know the real current time or the real weather. If the user asks \
for either, you MUST NOT guess. Instead reply with ONLY a JSON object, no \
other words and no markdown fences, in exactly this shape:
{"tool": "<tool name>", "args": {"<arg name>": "<value>"}}

Once a TOOL RESULT is given to you, use it to answer the user in one normal \
sentence (plain text, no JSON)."""


def parse_tool_request(text: str) -> dict | None:
    """Try to read the model's text as a {"tool", "args"} request.

    Returns the parsed dict, or None if the text was a normal answer instead.
    We defensively strip ```json fences in case the model adds them.
    """
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.startswith("json"):
            cleaned = cleaned[len("json"):]
        cleaned = cleaned.strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return None
    if isinstance(data, dict) and "tool" in data and "args" in data:
        return data
    return None


# ===========================================================================
# 0. THE ROOT: the model alone is blind. Prove it can't know the real time.
# ===========================================================================
def demo_model_is_blind(client) -> None:
    section("0. The root — the model is a text function. It cannot know 'now'.")

    question = "What is the exact current time in Tokyo right now, to the minute?"
    print("We ask the model directly, with NO tools:")
    print(f'  user: "{question}"\n')

    answer = ask(client, [{"role": "user", "content": question}])
    print("model's reply:")
    for line in answer.splitlines():
        print("  " + line)

    print("\nWhatever it said, it has no clock and no internet. It can only")
    print("refuse or guess. To answer for real, it needs a TOOL — and a way to")
    print("ask us to run it. That way is the 4-step protocol below.")


# ===========================================================================
# One full round of the hand-built protocol, printed step by step.
# ===========================================================================
def hand_built_tool_call(client, question: str, *, verbose: bool) -> None:
    # STEP 1 was static: the SYSTEM_PROMPT already describes the tools.
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]

    # ---- STEP 2: the model DECIDES. It writes a tool request. It runs nothing.
    if verbose:
        section("2. STEP 2 — the model DECIDES (it writes a request; runs nothing)")
    print(f'user asks: "{question}"')
    raw = ask(client, messages)
    print("the model's raw reply (this is just TEXT the model wrote):")
    print("  " + raw.replace("\n", "\n  "))

    request = parse_tool_request(raw)
    if request is None:
        print("\n(The model answered directly instead of requesting a tool.)")
        return

    if verbose:
        print("\nThat text is a REQUEST, not an action. The model asked US to run,", raw)
        print("a tool. Nothing has actually happened yet.")

    # ---- STEP 3: WE execute the tool. Our real Python runs now.
    if verbose:
        section("3. STEP 3 — WE execute the tool (our real Python runs now)")
    tool_name = request["tool"]
    args = request["args"]
    print(f"parsed request  -> tool={tool_name!r}  args={args}")

    func = TOOLS.get(tool_name)
    if func is None:
        result = f"ERROR: no such tool {tool_name!r}"
    else:
        result = func(**args)
    print(f"running {tool_name}(**{args})")
    print(f"  -> {result!r}")

    # ---- STEP 4: feed the result back; the model answers with real data.
    if verbose:
        section("4. STEP 4 — feed the result back; the model answers for real")
    messages.append({"role": "assistant", "content": raw})
    messages.append({
        "role": "user",
        "content": f"TOOL RESULT for {tool_name}: {result}\n"
                   f"Now answer my original question in one normal sentence.",
    })
    final = ask(client, messages)
    print("the model's final answer (now grounded in the real tool result):")
    print("  " + final.replace("\n", "\n  "))


def demo_time_full(client) -> None:
    section("1. STEP 1 — we DESCRIBE the tools to the model (the system prompt)")
    print("We can't hand the model a clock. So we TELL it what tools exist and")
    print("ask it to request one in JSON. Here is the system prompt that does it:")
    print()
    for line in SYSTEM_PROMPT.splitlines():
        print("  | " + line)
    print("\nNow watch the four steps play out for a real question.")

    hand_built_tool_call(
        client,
        "What time is it in Tokyo right now?",
        verbose=True,
    )


def demo_weather_reuse(client) -> None:
    section("5. The SAME four steps, reused for a different tool (weather)")
    print("Nothing above was special to time. The identical machinery — describe,")
    print("decide, execute, feed back — now runs a different tool. That reuse is")
    print("the whole point: one protocol, any number of tools.\n")

    hand_built_tool_call(
        client,
        "What's the weather in Paris?",
        verbose=False,
    )


def main() -> None:
    print(f"(provider: {PROVIDER}   model: {MODEL})")
    client = build_client()

    demo_model_is_blind(client)
    demo_time_full(client)
    demo_weather_reuse(client)

    print("\n" + "=" * 70)
    print("Done. You just built tool calling with NOTHING but a prompt and text.")
    print("The 4 steps: describe tools -> model requests -> you run -> you return.")
    print("Next (p0002): the provider's real `tools=` API does these SAME 4 steps,")
    print("but hands you clean structured data instead of JSON you parse by hand.")
    print("Read docs/p0001_tools_by_hand.md — root to leaf.")
    print("=" * 70)


if __name__ == "__main__":
    main()
