"""
p0002 — THE REAL `tools=` API: the same four steps, now formalized.

Run me:
    uv run p0002_tools_api.py

Read me with the doc open next to you:
    docs/p0002_tools_api.md

WHERE WE ARE
    In p0001 we built tool calling BY HAND: we described the tools in English in
    the system prompt, the model wrote a JSON request as plain text, and we
    parsed that text ourselves. It worked — and it proved there is no magic.

    Now we use the provider's real `tools=` feature. It does the EXACT same four
    steps. The only difference: the provider formalizes them. You hand it
    structured tool definitions (JSON Schema) instead of English, and it hands
    you a structured `tool_calls` object instead of text you must parse.

THE FOUR STEPS, NOW WITH THE REAL API
    1. DEFINE  — pass tools=[...]: name, description, JSON-Schema parameters.
    2. DECIDE  — the response has finish_reason == "tool_calls" and a structured
                 message.tool_calls array (id, function.name, arguments-as-STRING);
                 message.content is None. The model still RAN nothing.
    3. EXECUTE — json.loads(arguments), look the function up, run it.
    4. RETURN  — append the assistant message (WITH its tool_calls) + one
                 {"role":"tool", "tool_call_id": id, "content": result} per call.
                 Call again -> finish_reason == "stop" + the final text.

THE ONE IDEA
    The `tools=` API is not a new concept. It is p0001's four steps with the
    provider writing the schema plumbing and doing the parsing for you. Learn the
    shape of the request and the response; that shape never changes.
"""

import json
from datetime import datetime
from zoneinfo import ZoneInfo

from _llm import build_client, MODEL, PROVIDER


def section(title: str) -> None:
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


# ===========================================================================
# THE REAL TOOLS — the same ordinary Python functions as p0001. Unchanged.
# ===========================================================================
def get_current_time(timezone: str) -> str:
    """Return the real current time in an IANA timezone like 'Asia/Tokyo'."""
    try:
        return datetime.now(ZoneInfo(timezone)).strftime("%A, %d %B %Y, %H:%M:%S %Z")
    except Exception:
        return f"ERROR: '{timezone}' is not a valid IANA timezone."


def get_weather(city: str) -> str:
    """Return a (hardcoded) weather report for a city."""
    fake = {"Tokyo": "18°C, light rain", "Paris": "24°C, clear sky",
            "London": "15°C, cloudy"}
    return fake.get(city, f"20°C, sunny (no data for {city}, using a default)")


# The registry STEP 3 runs against: tool name -> the real Python function.
TOOLS = {"get_current_time": get_current_time, "get_weather": get_weather}


# ---------------------------------------------------------------------------
# STEP 1, formalized: instead of describing tools in English (p0001), we hand
# the provider a machine-readable definition per tool. The `parameters` block
# is standard JSON Schema. `additionalProperties: False` + `required` make it
# strict-ready (see the doc's note on "strict": true).
# ---------------------------------------------------------------------------
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "Get the current real-world time in a given timezone.",
            "parameters": {
                "type": "object",
                "properties": {
                    "timezone": {
                        "type": "string",
                        "description": "An IANA timezone name, e.g. 'Asia/Tokyo'.",
                    },
                },
                "required": ["timezone"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get the current weather for a city.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "City name, e.g. 'Tokyo'."},
                },
                "required": ["city"],
                "additionalProperties": False,
            },
        },
    },
]


# ===========================================================================
# 1. STEP 1 — DEFINE the tools as JSON Schema (not English).
# ===========================================================================
def demo_tool_definition() -> None:
    section("1. STEP 1 — DEFINE tools as JSON Schema (the `tools=` argument)")
    print("In p0001 we DESCRIBED tools in English inside the system prompt.")
    print("Now we pass a structured definition per tool. Here is one of them:\n")
    print(json.dumps(TOOL_SCHEMAS[0], indent=2))
    print("\nSame three facts as p0001, now machine-readable:")
    print("  • name        -> which function the model may ask for")
    print("  • description -> WHEN to use it (the model reads this to decide)")
    print("  • parameters  -> the arguments, as JSON Schema (types + required)")
    print("\nNote: the tool descriptions moved OUT of the system prompt and INTO")
    print("`tools=`. We no longer need a system prompt to explain the protocol —")
    print("the provider already knows the tool-calling protocol.")


# ===========================================================================
# One full round of the REAL API, printed step by step (single tool call).
# ===========================================================================
def run_one_tool_round(client, question: str, *, verbose: bool) -> None:
    messages = [{"role": "user", "content": question}]

    # ---- STEP 2: DECIDE. Call with tools=; inspect the RAW response.
    if verbose:
        section("2. STEP 2 — DECIDE: call with tools=, read the raw response")
    print(f'user asks: "{question}"')
    resp = client.chat.completions.create(
        model=MODEL, messages=messages, tools=TOOL_SCHEMAS, temperature=0,
    )
    choice = resp.choices[0]
    msg = choice.message

    print(f"finish_reason : {choice.finish_reason!r}   "
          "<- the model wants a tool (not 'stop')")
    print(f"message.content: {msg.content!r}   <- no text answer yet")
    print(f"message.tool_calls: {len(msg.tool_calls)} call(s). The provider already")
    print("split the request into fields (in p0001 we parsed this out of raw text):")
    for tc in msg.tool_calls:
        print(f"    id        = {tc.id}")
        print(f"    name      = {tc.function.name}")
        print(f"    arguments = {tc.function.arguments!r}   "
              f"<- type is {type(tc.function.arguments).__name__}, a JSON STRING")

    # This lesson uses a single-tool question, so exactly one call comes back.
    # (Handling several at once is p0003.) We still loop, so the code is correct
    # either way.
    if verbose:
        section("3. STEP 3 — EXECUTE: json.loads the arguments, run the function")
    tool_result_messages = []
    for tc in msg.tool_calls:
        args = json.loads(tc.function.arguments)     # STRING -> dict
        print(f"json.loads(arguments) -> {args}   (now a {type(args).__name__})")
        result = TOOLS[tc.function.name](**args)     # run the real Python
        print(f"ran {tc.function.name}(**{args})")
        print(f"  -> {result!r}")
        # Each result becomes a message tagged with the SAME id as the request.
        tool_result_messages.append({
            "role": "tool",
            "tool_call_id": tc.id,      # MUST match the request's id
            "content": str(result),
        })

    # ---- STEP 4: RETURN. Append the assistant message (with tool_calls) + the
    # tool result message(s), then call again.
    if verbose:
        section("4. STEP 4 — RETURN the result(s); call again for the final answer")

    # The assistant message we replay must carry the tool_calls it asked for.
    assistant_message = {
        "role": "assistant",
        "content": msg.content,                       # None
        "tool_calls": [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,   # the SAME JSON string
                },
            }
            for tc in msg.tool_calls
        ],
    }
    messages.append(assistant_message)
    messages.extend(tool_result_messages)

    if verbose:
        print("the conversation we now send back (roles in order):")
        for m in messages:
            extra = ""
            if m["role"] == "assistant":
                extra = f"  (+{len(m['tool_calls'])} tool_calls, content={m['content']!r})"
            if m["role"] == "tool":
                extra = f"  (tool_call_id={m['tool_call_id']}, content={m['content']!r})"
            print(f"    role={m['role']!r}{extra}")

    resp2 = client.chat.completions.create(
        model=MODEL, messages=messages, tools=TOOL_SCHEMAS, temperature=0,
    )
    choice2 = resp2.choices[0]
    print(f"\nsecond call finish_reason: {choice2.finish_reason!r}   "
          "<- 'stop' = a normal text answer now")
    print("final answer:")
    print("  " + (choice2.message.content or "").replace("\n", "\n  "))


def demo_time_full(client) -> None:
    run_one_tool_round(client, "What time is it in Tokyo right now?", verbose=True)


def demo_weather_compact(client) -> None:
    section("5. The SAME machinery, one function, a different tool (weather)")
    print("Nothing changes but the question. The four steps are now a reusable")
    print("function. That is the whole win of the formal API.\n")
    run_one_tool_round(client, "What's the weather in Paris?", verbose=False)


def main() -> None:
    print(f"(provider: {PROVIDER}   model: {MODEL})")
    client = build_client()

    demo_tool_definition()
    demo_time_full(client)
    demo_weather_compact(client)

    print("\n" + "=" * 70)
    print("Done. The real `tools=` API is p0001's four steps, formalized:")
    print("  DEFINE (schema) -> DECIDE (finish_reason='tool_calls') ->")
    print("  EXECUTE (json.loads + run) -> RETURN (assistant + role:'tool').")
    print("Next (p0003): TWO tools at once (parallel tool_calls) and the loop —")
    print("keep calling until finish_reason == 'stop'. That is a working agent.")
    print("Read docs/p0002_tools_api.md — root to leaf.")
    print("=" * 70)


if __name__ == "__main__":
    main()
