# p0003 — The agent loop (Phase 4 capstone)

> **Run the code first, then read this.** `uv run p0003_agent_loop.py`
> Each part below matches a numbered block in `p0003_agent_loop.py`.
> This lesson merges two planned topics — the loop, and making it robust — plus
> a reference section on other provider shapes. It is the end of Phase 4.

---

## Where we are

- **p0001** built the four-step dance by hand: there is no magic.
- **p0002** used the real `tools=` API — but only **one** tool, **one** round.

A single round is not an agent. An **agent** is that round put in a loop:

> model decides → your code runs the tool(s) → feed the results back →
> model decides again → … → until the model stops asking for tools.

The model drives; your loop executes and feeds back. That is the entire engine
under LangChain's `create_agent`, LangGraph's `ToolNode`, and every agent product
you've used. This lesson builds it, then hardens it for the real world.

---

## The one idea

> **An agent is a `while`-loop around p0002's four steps.** The model chooses the
> path at run time (which tool, how many, in what order); your loop runs whatever
> it asks and feeds the results back; a cap keeps it from running forever. Master
> this loop and every framework is just this loop with extra features.

---

## 1. The dispatcher that contains failures

Before the loop, the piece that makes it survivable. `run_tool` runs one tool
call and turns **every** bad outcome into a plain error **string** instead of
crashing:

```text
  [happy path]        -> '18°C, light rain'
  [unknown tool]      -> "ERROR: unknown tool 'get_flights'"
  [invalid JSON]      -> 'ERROR: arguments were not valid JSON: Expecting value...'
  [tool RAISES]       -> "ERROR: tool 'get_current_time' failed: ZoneInfoNotFoundError: ..."
```

Three guards, matching the three things that go wrong in practice:

```python
def run_tool(name, arguments_json):
    if name not in TOOLS:                     # 1. model hallucinated a tool name
        return f"ERROR: unknown tool {name!r}"
    try:
        args = json.loads(arguments_json)     # 2. arguments weren't valid JSON
    except json.JSONDecodeError as e:
        return f"ERROR: arguments were not valid JSON: {e}"
    try:
        return str(TOOLS[name](**args))       # 3. the tool itself blew up
    except Exception as e:
        return f"ERROR: tool {name!r} failed: {type(e).__name__}: {e}"
```

Two design decisions worth internalizing:

- **The tool is naive; the loop is safe.** Look back at the tools: `get_current_time`
  does *not* catch a bad timezone — it lets `ZoneInfo` raise. Containing that is
  `run_tool`'s job, not the tool's. This keeps tools simple and puts all the
  safety in one place you can trust. (In p0001/p0002 the tool caught its own error
  to keep those lessons focused; here we do it properly.)
- **Return the error, don't raise it.** This is the key move. Because a failure
  comes back as a *string*, the loop can feed it to the model like any other tool
  result. The model then reads `"ERROR: unknown tool"` and can apologize, pick a
  different tool, or fix its arguments and try again. A crash gives the model no
  chance to recover; an error string gives it one. This is why the demo proves
  this section **without the model at all** — it's pure, deterministic Python.

> **Backend intuition:** this is the same instinct as never letting a raw
> exception escape a request handler. The tool-call boundary is a boundary like
> any other — validate at it, and translate failures into a response the caller
> (here, the model) can act on.

---

## 2. The loop itself

`run_agent` is p0002's steps 2–4, wrapped in a bounded loop — and written the way
real agents are: **async**. It uses `AsyncOpenAI` (from `build_async_client`), so
every LLM call and every tool is `await`-ed:

```python
async def run_agent(client, question, *, max_iters=6):
    messages = [{"role": "user", "content": question}]
    for step in range(1, max_iters + 1):
        resp = await client.chat.completions.create(          # await the LLM
            model=MODEL, messages=messages, tools=TOOL_SCHEMAS, temperature=0)
        choice = resp.choices[0]
        msg = choice.message

        if choice.finish_reason != "tool_calls":              # wrote text -> done
            return msg.content or ""

        messages.append(assistant_replay(msg))                # replay the request
        results = await asyncio.gather(*[                      # run ALL calls at once
            run_tool(tc.function.name, tc.function.arguments) for tc in msg.tool_calls])
        for tc, result in zip(msg.tool_calls, results):
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})
    return "<<stopped: reached the tool-call limit>>"
```

Read it as one sentence: *"Ask the model. If it wants tools, run them all at once,
add the results, and ask again. If it wrote an answer, stop. Never loop more than
`max_iters` times."* Four details carry the whole thing:

- **`await` before each network call.** `await client.chat...create(...)` pauses
  this coroutine during the model's network wait and lets the event loop do other
  work meanwhile — the whole reason we use `AsyncOpenAI` (which *requires* asyncio;
  see the demo at the bottom of the file, `asyncio.run(main())`).
- **`finish_reason` is the branch.** `"tool_calls"` → there is work to do, keep
  looping. Anything else (`"stop"`) → the model answered, return it. This one
  field is the loop's exit condition.
- **The `messages` list only grows.** Every round appends the assistant's request
  and the tool results, then re-sends the whole thing. The model is stateless
  (prompt p0001); the growing list *is* the agent's working memory for this task.
- **`asyncio.gather(...)` is what makes parallel calls fast.** It runs *every*
  requested tool at once and returns their results in order, so they line up 1:1
  with `msg.tool_calls`. Each result becomes one `role: "tool"` message matched by
  `tool_call_id`. (Recall from p0002: the API *requires* every tool_call to be
  answered.) The next section shows the overlap this buys.

---

## 3. Parallel — several tools in one response

```text
USER: "What time is it in Tokyo, and what's the weather there?"
  [iter 1] model wants 2 tools in parallel: [get_current_time(Asia/Tokyo), get_weather(Tokyo)]
           ran 2 tools concurrently in 0.50s (each ~0.5s; one-by-one would be ~1.0s)
           get_current_time -> 'Friday, 10 July 2026, 07:39 JST'
           get_weather -> '18°C, light rain'
  [iter 2] finish_reason='stop' -> DONE
FINAL: In Tokyo, it is currently ... 07:39 JST. The weather is 18°C with light rain.
```

The question has **two independent needs** — the time and the weather — and
neither depends on the other. So in a single response the model asked for **both**
tools at once (two entries in `msg.tool_calls`). The whole task took **two** model
calls, not three.

### Why the two tools finished in 0.5s, not 1.0s

Each tool here `await`s a simulated 0.5s "network" call (`SIMULATED_API_LATENCY` —
real weather/time APIs take ~100–500ms). Run one-by-one that's ~1.0s; but
`asyncio.gather` started **both at once**, so their waits *overlapped* and the pair
finished in ~0.5s. That is the whole point of running a parallel batch
concurrently — and exactly the p0004 lesson: **concurrency overlaps waiting, not
work.** Turn `SIMULATED_API_LATENCY = 0` and the speed-up vanishes, because instant
tools have nothing to overlap.

**How gather does it, and why not threads.** `asyncio.gather(*coros)` hands all the
tool coroutines to the event loop at once; each hits its `await asyncio.sleep(...)`
(standing in for a real `await httpx.get(...)`), yields, and the loop runs the next
one — so all the waits happen together on **one thread, no threads spawned**. This
is the real-world shape: agent work is I/O-bound, and `asyncio` overlaps thousands
of such waits far more cheaply than threads (which cost ~MBs each). It works
*because the whole stack is async* — `AsyncOpenAI` for the model, `async def` tools
for the I/O.

The one trap (p0004 §7): a **blocking** call inside async freezes the event loop.
So if you're ever forced to call a blocking library that has no async version, you
wrap *just that call* in `await asyncio.to_thread(blocking_fn)` — a thread pool
becomes the **fallback** for stubborn blocking code, not the default. **Rule of
thumb: match the concurrency tool to the stack** — async stack → `asyncio.gather`;
a lone blocking dependency → `asyncio.to_thread`. From Phase 5 on, LangChain and
LangGraph are async-native, so this is the world you'll live in.

---

## 4. Multi-step — a real chain across rounds

```text
USER: "What's the weather where I am right now?"
  [iter 1] model wants tool: [get_user_location({})]
           ran get_user_location -> 'London'
  [iter 2] model wants tool: [get_weather(city=London)]
           ran get_weather -> '15°C, cloudy'
  [iter 3] finish_reason='stop' -> DONE
FINAL: The current weather in London is 15°C and cloudy.
```

This is the opposite of parallel, and it's where "agent" really means something.
The model **cannot** call `get_weather` yet — it doesn't know the city. So it
calls `get_user_location` first, and only *after seeing* the result (`London`)
does it decide the next call, `get_weather("London")`. That's **three** rounds of
the loop, and the model chose the second tool *based on the first tool's output*.

Nobody wrote "first get location, then get weather." The model planned that path
at run time from the question. That run-time planning — the path isn't fixed in
your code — is the line between a **workflow** (fixed steps you wrote) and an
**agent** (the model picks the steps). Your loop just faithfully runs whatever the
model decides, round after round.

---

## 5. The cap — why the loop is *bounded*

```text
USER: "What's the weather where I am right now?"   (max_iters=1)
  [iter 1] model wants tool: [get_user_location({})]
           ran get_user_location -> 'London'
  [stopped] hit max_iters=1 before the model finished
FINAL: <<stopped: reached the tool-call limit>>
```

Same task as §4, but with the cap dialed to 1. The loop runs one round and stops —
before the model can call `get_weather`. The cap cut a real task short, on purpose,
so you can *see* it working.

Why you always cap: a confused or adversarial model can ask for tools forever —
call, get a result it doesn't like, call again, loop with no end. Every round is a
paid API call. An uncapped loop is an unbounded bill and a hung request. `max_iters`
is the seatbelt. In production you cap **both** iterations and total tokens, and
you decide what to do when the cap hits (return a partial answer, ask the user, log
an alert). You'll go deeper on this in Phase 8 (cost & loop control); for now, the
rule is simply: **never ship an unbounded agent loop.**

---

## Reference: the other provider shapes (so you recognize them later)

Everything above is the OpenAI / GitHub Models shape. The *concept* — the four
steps and the loop — is universal; only the JSON field names change. You don't
need to write these now, just recognize them.

**Anthropic's native shape.** Same dance, different names:

| step | OpenAI / GitHub Models (what you used) | Anthropic native |
|---|---|---|
| define | `tools=[{function:{name, description, parameters}}]` | `tools=[{name, description, input_schema}]` |
| "wants a tool" | `finish_reason == "tool_calls"` | `stop_reason == "tool_use"` |
| the request | a `tool_calls` array; `arguments` is a **JSON string** | a `tool_use` content block; `input` is already a **dict** |
| your reply | a `role:"tool"` message with `tool_call_id` | a `user` message with a `tool_result` block and `tool_use_id` |

Note the one real ergonomic difference: Anthropic hands you `input` as a parsed
dict, so there's no `json.loads` step. Otherwise it is the identical loop. If you
ever point this course's logic at Claude's native API, you're renaming fields, not
rethinking anything.

**Client tools vs server tools.** Everything in this phase was a **client tool**
(also called a custom or user-defined tool): *you* define it and *your* code runs
it. The provider only ever asks. But providers also offer **server tools** —
hosted tools that run on *their* infrastructure, where you just switch them on and
the provider executes them and injects the results. Common examples: hosted **web
search**, **code execution**, file search. The difference matters:

- **Client tool** — you own the four-step loop (this whole lesson). Use it for
  *your* logic: your DB, your APIs, your business rules.
- **Server tool** — the provider runs it; you don't see or write the execution.
  Convenient for generic capabilities (search the web) you don't want to build.

MCP tools (from the `demo_mcp_broker.py` side demo) are a third flavour: client
tools whose definition and execution live in a separate server your app brokers to.

---

## How this maps to the frameworks you'll learn next

You have now written, by hand, the thing every framework wraps:

- **LangChain `create_agent`** = this loop, with tools defined by a `@tool`
  decorator (the registry idea from Python p0006) and the message-appending done
  for you.
- **LangGraph** = this loop expressed as a graph: an LLM node, a `ToolNode` (your
  `run_tool` + the append), and a conditional edge that checks `finish_reason` to
  decide "loop again" vs "stop" — plus persistence, streaming, and human-in-the-loop
  bolted around it.

When you see those in Phase 5–6, map every piece back to this file. Nothing there
is new machinery; it's this loop with ergonomics.

---

## Run it, then break it

1. **Make failure recoverable (§1, §2).** Add a tool `book_flight(city)` that does
   `raise RuntimeError("payment API down")`, register it, and ask "Book me a flight
   to Paris." Watch the loop feed the error back and the model tell you it couldn't.
   Then delete the `try/except` in `run_tool` and re-run — now it crashes the whole
   program. That contrast is the lesson.

2. **Force a longer chain (§4).** Ask "What time is it where I am?" The model must
   call `get_user_location` → then `get_current_time` with London's timezone.
   Watch it reason out `Europe/London` from `London` on its own.

3. **Feel the cap boundary (§5).** Set `max_iters=2` and re-run the multi-step
   demo. Now it *just* finishes (location, weather, answer needs 3 rounds — so 2
   still cuts it off; try 3). Find the smallest cap that lets it complete.

4. **Remove a tool the model needs (§2).** Delete `get_user_location` from
   `TOOL_SCHEMAS` (leave it in `TOOLS`) and ask "weather where I am." The model
   can't see the tool, so it will guess a city or ask you. Proof that the model
   only knows the tools you *advertise* in `tools=`.

---

## What you now know

- An **agent is a bounded `while`-loop** around p0002's four steps: ask → run
  tools → feed back → ask again → until `finish_reason == "stop"`. (§2)
- A **dispatcher** should turn every failure — unknown tool, bad JSON, a raising
  tool — into an **error string** fed back to the model, never a crash. Tools stay
  naive; the loop stays safe. (§1)
- **Parallel:** the model can request several independent tools in one response;
  run them **concurrently** (a thread pool, because our tools/client are sync) and
  answer each by `tool_call_id`. Concurrency helps only I/O-bound tools — proven
  3× in `demo_parallel_tools.py`. (§3)
- **Multi-step:** when one result decides the next call, the loop runs several
  rounds and the model plans the path at run time. That run-time planning is what
  separates an **agent** from a fixed **workflow**. (§4)
- **Always cap** iterations (and, in production, tokens) — an unbounded loop is an
  unbounded bill. (§5)
- The concept is provider-agnostic (Anthropic `tool_use`/`tool_result`), and tools
  come in **client** (you run) vs **server** (the provider runs) flavours.
  (reference)

---

## Phase 4 complete

You built tool calling from the root: by hand → the real API → a robust agent
loop, and you can now point at where MCP fits. Per the path, *"after this works,
the conceptual rest is mostly assembly."* That is literally true — every later
phase adds a capability to this same loop.

**Next — Phase 5: LangChain.** You'll rebuild this exact agent in ~20 lines with
`create_agent` and `@tool`, and point the framework at GitHub Models with a
one-line model config. Because you built the loop by hand, the framework will feel
like *labeled convenience*, not magic — you'll know exactly which of these steps
each call is doing.
