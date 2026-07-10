"""
p0003 — THE AGENT LOOP (async — the real-world shape): many tools, parallel
        calls, multi-step, made robust. (Phase 4 capstone — a working agent.)

Run me:
    uv run p0003_agent_loop.py

Read me with the doc open next to you:
    docs/p0003_agent_loop.md

WHERE WE ARE
    p0001: the 4-step dance by hand. p0002: the real tools= API — ONE call, ONE
    round. Now we close the phase by wrapping steps 2-4 in a LOOP (an AGENT), and
    we write it the way real agents are written: ASYNC.

WHY ASYNC (and not the sync client from p0001-p0002)
    Agent work is almost all WAITING — on the model, on tool APIs, on databases
    (Python p0004). asyncio overlaps those waits so independent calls happen at
    once, and the stack you meet next (LangChain, LangGraph, FastAPI) is
    async-native. So this capstone uses:
        • AsyncOpenAI     — the async LLM client; `await` its network calls
        • async def tools — each `await`s its (here simulated) I/O
        • asyncio.gather  — run parallel tool_calls at once, with NO threads
    Everything else is IDENTICAL to the four steps you already know, just await-ed.
    (AsyncOpenAI does not replace asyncio — it REQUIRES it: you must `await` it
    inside an event loop started by asyncio.run at the bottom of this file.)

WHAT THIS LESSON ADDS ON TOP OF p0002
    1. A REGISTRY + dispatcher (run_tool) that CONTAINS failures: unknown tool,
       bad-JSON arguments, and a tool that raises all become an error STRING.
    2. PARALLEL tool calls: several tools in ONE response, run concurrently with
       asyncio.gather (watch two ~0.5s tools finish in ~0.5s, not ~1.0s).
    3. The LOOP: keep calling until finish_reason == "stop".
    4. MULTI-STEP: when a tool's result decides the NEXT tool, the loop runs
       several rounds.
    5. A MAX-ITERATIONS CAP so a confused model can't loop (and bill) forever.

THE ONE IDEA
    An agent is an (async) loop around p0002's four steps. The model drives; your
    loop awaits the tool(s) and feeds results back; a cap keeps it safe. That is
    the engine under every agent framework you will ever use.
"""

import asyncio
import json
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from _llm import build_async_client, MODEL, PROVIDER

# Real weather/time/DB calls take ~100-500ms. We simulate that wait with
# asyncio.sleep so the parallel speed-up is visible below. Set to 0 for instant.
SIMULATED_API_LATENCY = 0.5


def section(title: str) -> None:
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


# ===========================================================================
# ASYNC TOOLS. Each `await`s to model a real network/DB call that WAITS. Because
# they await (not block), the event loop can overlap them — no threads needed.
# get_current_time does NOT catch a bad timezone — it RAISES; containing that is
# the dispatcher's job (run_tool), not the tool's.
# ===========================================================================
async def get_current_time(timezone: str) -> str:
    """Real current time in an IANA timezone. Raises on a bad timezone."""
    await asyncio.sleep(SIMULATED_API_LATENCY)          # simulate a time-API call
    return datetime.now(ZoneInfo(timezone)).strftime("%A, %d %B %Y, %H:%M %Z")


async def get_weather(city: str) -> str:
    """Hardcoded weather for a city (pretend it's a weather API)."""
    await asyncio.sleep(SIMULATED_API_LATENCY)          # simulate a weather-API call
    fake = {"Tokyo": "18°C, light rain", "Paris": "24°C, clear sky",
            "London": "15°C, cloudy"}
    return fake.get(city, f"20°C, sunny (no data for {city})")


async def get_user_location() -> str:
    """Where the user is (pretend this reads their profile/GPS). Takes no args."""
    await asyncio.sleep(SIMULATED_API_LATENCY)          # simulate a profile lookup
    return "London"


TOOLS = {
    "get_current_time": get_current_time,
    "get_weather": get_weather,
    "get_user_location": get_user_location,
}

TOOL_SCHEMAS = [
    {"type": "function", "function": {
        "name": "get_current_time",
        "description": "Get the current real-world time in a given timezone.",
        "parameters": {
            "type": "object",
            "properties": {"timezone": {"type": "string",
                           "description": "An IANA name, e.g. 'Asia/Tokyo'."}},
            "required": ["timezone"], "additionalProperties": False,
        }}},
    {"type": "function", "function": {
        "name": "get_weather",
        "description": "Get the current weather for a city.",
        "parameters": {
            "type": "object",
            "properties": {"city": {"type": "string", "description": "City name."}},
            "required": ["city"], "additionalProperties": False,
        }}},
    {"type": "function", "function": {
        "name": "get_user_location",
        "description": "Get the city the user is currently in. Takes no arguments.",
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
    }},
]


# ===========================================================================
# 1. THE DISPATCHER — run one tool call, and CONTAIN every failure as a string.
# ===========================================================================
async def run_tool(name: str, arguments_json: str) -> str:
    # Guard 1: the model asked for a tool that does not exist.
    if name not in TOOLS:
        return f"ERROR: unknown tool {name!r}"
    # Guard 2: the arguments string was not valid JSON.
    try:
        args = json.loads(arguments_json)
    except json.JSONDecodeError as e:
        return f"ERROR: arguments were not valid JSON: {e}"
    # Guard 3: the tool itself raised while running.
    try:
        return str(await TOOLS[name](**args))
    except Exception as e:
        return f"ERROR: tool {name!r} failed: {type(e).__name__}: {e}"


async def demo_dispatcher_contains_errors() -> None:
    section("1. The dispatcher contains failures (no model needed to prove this)")
    print("run_tool turns every bad case into an ERROR STRING, never a crash:\n")
    cases = [
        ("get_weather",      '{"city": "Tokyo"}',        "happy path"),
        ("get_flights",      '{"from": "LHR"}',          "unknown tool"),
        ("get_weather",      '{"city": Tokyo}',          "invalid JSON (no quotes)"),
        ("get_current_time", '{"timezone": "Mars/Base"}', "tool RAISES (bad timezone)"),
    ]
    for name, raw_args, label in cases:
        result = await run_tool(name, raw_args)
        print(f"  [{label}]")
        print(f"    run_tool({name!r}, {raw_args!r})")
        print(f"    -> {result!r}\n")
    print("Because every result is a string, the loop can feed even a FAILURE")
    print("back to the model, which can then apologize, retry, or try another tool.")


# ===========================================================================
# 2. THE AGENT LOOP — steps 2-4 of p0002, wrapped in an async while-loop.
# ===========================================================================
def assistant_replay(msg) -> dict:
    """Rebuild the assistant message (with its tool_calls) to send back."""
    return {
        "role": "assistant",
        "content": msg.content,
        "tool_calls": [
            {"id": tc.id, "type": "function",
             "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
            for tc in msg.tool_calls
        ],
    }


async def run_agent(client, question: str, *, max_iters: int = 6) -> str:
    print(f'\nUSER: "{question}"')
    messages = [{"role": "user", "content": question}]

    for step in range(1, max_iters + 1):
        resp = await client.chat.completions.create(         # await the LLM call
            model=MODEL, messages=messages, tools=TOOL_SCHEMAS, temperature=0,
        )


        print("############")
        print(resp)
        print("############")
        choice = resp.choices[0]
        msg = choice.message

        # Model wrote a normal answer -> the loop is done.
        if choice.finish_reason != "tool_calls":
            print(f"  [iter {step}] finish_reason='{choice.finish_reason}' -> DONE")
            return msg.content or ""

        # Model wants one or MORE tools.
        names = [f"{tc.function.name}({tc.function.arguments})" for tc in msg.tool_calls]
        word = "tool" if len(names) == 1 else f"{len(names)} tools in parallel"
        print(f"  [iter {step}] model wants {word}: {names}")

        messages.append(assistant_replay(msg))               # replay the request
        # Run ALL requested calls at once with gather. It returns results in the
        # order passed in, so they line up 1:1 with tool_calls. No threads: each
        # tool `await`s its own I/O, and the event loop overlaps those waits.
        start = time.perf_counter()
        results = await asyncio.gather(*[
            run_tool(tc.function.name, tc.function.arguments) for tc in msg.tool_calls
        ])
        dt = time.perf_counter() - start
        if len(results) > 1:
            print(f"           ran {len(results)} tools concurrently in {dt:.2f}s "
                  f"(each ~{SIMULATED_API_LATENCY}s; one-by-one would be "
                  f"~{SIMULATED_API_LATENCY * len(results):.1f}s)")
        for tc, result in zip(msg.tool_calls, results):
            print(f"           {tc.function.name} -> {result!r}")
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})

    # Fell out of the loop = never reached 'stop' within max_iters.
    print(f"  [stopped] hit max_iters={max_iters} before the model finished")
    return "<<stopped: reached the tool-call limit>>"


# ===========================================================================
# 3. DEMOS that exercise the loop.
# ===========================================================================
async def demo_parallel(client) -> None:
    section("2. PARALLEL — two tools in ONE response, run concurrently (gather)")
    print("The question needs the time AND the weather (independent). Watch iter 1")
    print("return TWO tool_calls; gather runs both at once, so their waits overlap.")
    answer = await run_agent(client, "What time is it in Tokyo, and what's the weather there?")
    print(f"\nFINAL: {answer}")


async def demo_multistep(client) -> None:
    section("3. MULTI-STEP — one tool's result decides the NEXT tool")
    print("The model can't call get_weather until it knows the city. So it calls")
    print("get_user_location FIRST, reads the result, THEN calls get_weather —")
    print("two separate rounds of the loop, a real chain the model plans at run time.")
    answer = await run_agent(client, "What's the weather where I am right now?")
    print(f"\nFINAL: {answer}")


async def demo_cap(client) -> None:
    section("4. THE CAP — the same multi-step task, but max_iters=1")
    print("A loose loop can call tools forever (and bill forever). The cap stops")
    print("it. With max_iters=1 the chain above is cut off after the first round:")
    answer = await run_agent(client, "What's the weather where I am right now?", max_iters=1)
    print(f"\nFINAL: {answer}")
    print("\n(The model wanted a second round to call get_weather, but the cap")
    print("ended the loop first. In production you cap iterations AND tokens.)")


async def main() -> None:
    print(f"(provider: {PROVIDER}  model: {MODEL})  [async: AsyncOpenAI + async tools]")
    client = build_async_client()

    await demo_dispatcher_contains_errors()
    await demo_parallel(client)
    await demo_multistep(client)
    await demo_cap(client)

    print("\n" + "=" * 70)
    print("Done. You built an AGENT: an async loop around p0002's four steps.")
    print("  • a dispatcher that turns every failure into a string (no crashes)")
    print("  • parallel tool_calls run concurrently with asyncio.gather (no threads)")
    print("  • multi-step chains handled across iterations")
    print("  • a max-iterations cap so it can't loop forever")
    print("This IS the real-world shape. LangChain create_agent / LangGraph are")
    print("this same async loop with more features bolted on. Read the doc —")
    print("incl. the reference on Anthropic's tool_use shape and server tools.")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
