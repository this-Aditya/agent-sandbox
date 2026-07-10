# p0001 — Tool calling, built by hand (there is no magic)

> **Run the code first, then read this.** `uv run p0001_tools_by_hand.py`
> Each part below matches a numbered block in `p0001_tools_by_hand.py`.
> We assume you know **nothing** about tool calling. We build it from zero.

---

## First, the problem this solves

An LLM is a **text function**. You give it text (a list of messages), it gives
you text back. That is the whole thing. Read that again, because everything here
depends on it: **the model does not run code, open files, call APIs, or read a
clock.** It only produces the next tokens.

So ask yourself: how does a weather bot tell you today's weather? How does a
"book my flight" agent actually book anything? The model can't do any of that.
Something outside the model must do the real work.

That "something" is **your code**. Tool calling is the agreed way for the model
to say *"please run this function with these inputs"* and for your code to run it
and hand the answer back. The model never does the work. It only **asks**.

This lesson builds that whole conversation **by hand**, with no special API — just
a prompt and plain text. The next lesson (p0002) swaps in the provider's real
`tools=` feature. It does the exact same four steps; it just gives you cleaner
data. By building it yourself first, you remove all the mystery from the real API.

---

## The one new idea

> **"The model calls a tool" is a figure of speech. The model only ever writes
> text. When it "calls a tool" it is writing a REQUEST — a small message that
> says which function it wants and with which arguments. YOUR code reads that
> request, runs the real function, and sends the result back into the next
> message. Then the model writes its final answer using that result.**

Four steps, always the same:

1. **You describe the tools** to the model (names, what they do, what inputs).
2. **The model decides** and writes a request (still just text).
3. **You execute** — parse the request, run your real function.
4. **You return the result** to the model, which then answers.

Keep those four in your head. The rest of this phase — and every framework later
— is just this loop, dressed up.

---

## 0. The root: the model is blind

The program first asks the model, with no tools at all:

> "What is the exact current time in Tokyo right now, to the minute?"

The reply we captured:

```text
I'm unable to provide real-time information, including the current time.
However, you can easily find the current time in Tokyo by checking a world
clock... Tokyo is in the Japan Standard Time (JST) zone, which is UTC+9.
```

This is the proof. The model **has no clock**. It was trained once, in the past,
and frozen. "Now" is not a thing it can know. It can only refuse (as here) or
make up a number — and a made-up time is worse than no time.

The same is true for the weather, your database, a stock price, the contents of a
file: all of it lives **outside** the model. The model can reason about such
things in general, but it cannot *fetch* any specific live value. That gap is the
entire reason tools exist.

> **Backend intuition:** think of the model as a pure function with no I/O — no
> network, no disk, no system clock. To give it any effect on the world, you must
> pass effects in and out across its boundary. Tool calling is that boundary
> protocol.

---

## 1. STEP 1 — describe the tools (the system prompt)

We cannot give the model a clock. But we **can** tell it, in words, that certain
tools exist and how to ask for them. That is all "defining a tool" means at the
root: **text in the prompt** describing what is available.

In the code, two things make up Step 1:

**(a) The real functions.** Ordinary Python. Nothing special about them:

```python
def get_current_time(timezone: str) -> str:
    now = datetime.now(ZoneInfo(timezone))     # the REAL current time
    return now.strftime("%A, %d %B %Y, %H:%M:%S %Z")

def get_weather(city: str) -> str:
    ...                                         # hardcoded, like the course asks
```

`get_current_time` returns the *actual* time — that is why the final answer in
the run is real. `get_weather` returns canned data; a real one would call a
weather API. To the protocol, it makes no difference.

**(b) The description we hand the model** — the system prompt. It lists the tools
and invents our request format:

```text
Available tools:
- get_current_time(timezone): the current time. `timezone` is an IANA name...
- get_weather(city): the current weather in a city...

If the user asks for either, you MUST NOT guess. Instead reply with ONLY a
JSON object ... in exactly this shape:
{"tool": "<tool name>", "args": {"<arg name>": "<value>"}}
```

Three parts matter here, and they carry straight into the real API next lesson:

- **the name** (`get_current_time`) — so the model can say which one it wants;
- **what it does and its inputs** (`timezone`, an IANA name) — so the model knows
  *when* to use it and *how* to fill the arguments;
- **the output shape we demand** (that JSON) — so the model's answer is something
  our code can read back reliably.

We also keep a **registry** — a plain dict from tool name to function:

```python
TOOLS = {"get_current_time": get_current_time, "get_weather": get_weather}
```

Step 3 will look tools up in here by name. This is the same name→function map you
built with the `@tool` decorator in Python lesson p0006. Frameworks keep a
registry exactly like this one.

---

## 2. STEP 2 — the model decides (it writes a request; it runs nothing)

We send the system prompt plus the user question. The model's raw reply:

```text
{"tool": "get_current_time", "args": {"timezone": "Asia/Tokyo"}}
```

Look closely at what did **not** happen. The model did not fetch the time. It did
not run anything. It wrote a line of **text** that *describes* the call it wants.
That is the deep truth this lesson exists to show: a "tool call" is the model
**writing a request**, nothing more.

Notice one more thing it did on its own: the user said "Tokyo", but the model put
`"Asia/Tokyo"` — the IANA name our tool needs. It read our description and filled
the argument correctly. That small act — mapping a vague human request onto your
function's exact parameters — is most of what makes tool calling useful.

`parse_tool_request` then turns that text back into a Python dict. It also strips
` ```json ` fences defensively, in case the model wraps the JSON. In the real API
(p0002) you won't parse text like this — the provider hands you the fields
already separated. But doing it by hand once shows you what that convenience is
really doing under the covers.

---

## 3. STEP 3 — you execute (your real Python runs now)

Now, and only now, does any real work happen:

```text
parsed request  -> tool='get_current_time'  args={'timezone': 'Asia/Tokyo'}
running get_current_time(**{'timezone': 'Asia/Tokyo'})
  -> 'Thursday, 09 July 2026, 03:04:52 JST'
```

Two lines of code are the heart of it:

```python
func = TOOLS.get(tool_name)      # look the function up by name
result = func(**args)            # call it with the model's arguments
```

`func(**args)` spreads the dict into keyword arguments, so
`{"timezone": "Asia/Tokyo"}` becomes `get_current_time(timezone="Asia/Tokyo")`.
**This is your code, on your machine, under your control.** The model is not
running while this happens — it already handed control back to you when it wrote
the request. You decide whether to run the tool at all, whether the arguments are
safe, and what to do with the result. (That control point is exactly where, later,
you'll put permission checks before dangerous actions.)

The result `'Thursday, 09 July 2026, 03:04:52 JST'` is the *real* time — note it's
already the next day in Tokyo, since Japan is nine hours ahead.

---

## 4. STEP 4 — feed the result back; the model answers for real

The model still hasn't *seen* the result — we only just computed it. So we add it
to the conversation and ask the model again:

```python
messages.append({"role": "assistant", "content": raw})    # what the model asked
messages.append({"role": "user", "content":
    f"TOOL RESULT for {tool_name}: {result}\nNow answer my original question..."})
final = ask(client, messages)
```

The final answer:

```text
The current time in Tokyo is 03:04:52 JST on Thursday, 09 July 2026.
```

Real, correct, grounded in the tool result. Trace the full round trip once more,
because this shape never changes:

```
you: describe tools + ask  ->  model: "run get_current_time(Asia/Tokyo)"
                           <-
you: run it, send result   ->  model: "It is 03:04 JST in Tokyo."
                           <-
```

Two calls to the model, with your code doing real work in the middle. That
in-the-middle step is the only place anything actually happens. The model
bookends it: it decides before, and it explains after.

> **Why re-send everything?** Remember from prompt-engineering p0001: the model
> is **stateless**. It remembers nothing between calls. The only reason the second
> call knows about the question *and* the tool result is that the `messages` list
> carries the whole story each time. "Memory" is just you re-sending the list.

---

## 5. The same four steps, reused for weather

The weather demo runs the identical function `hand_built_tool_call`, only with a
different question:

```text
user asks: "What's the weather in Paris?"
  {"tool": "get_weather", "args": {"city": "Paris"}}
  -> '24°C, clear sky'
The current weather in Paris is 24°C with a clear sky.
```

Nothing in the machinery changed. Same describe → decide → execute → feed-back.
That is the payoff of a *protocol*: you write it once, and every new tool plugs
into the same four steps. Ten tools, a hundred tools — same loop. The model picks
which one by name; your registry runs it.

---

## Run it, then break it (this is where it sinks in)

Do these. Watching the output change is how the four steps become yours.

1. **Break the parse, see the model choose the tool (§2).** In `SYSTEM_PROMPT`,
   change the required shape to `{"call": ...}` instead of `{"tool": ...}` but
   leave `parse_tool_request` expecting `"tool"`. Re-run. The model now emits
   `{"call": ...}`, your parser returns `None`, and Step 3 never fires. Proof that
   the *only* thing linking model and code is a format you both agreed on.

2. **Feed a wrong result, watch it trust you (§4).** In `get_weather`, hardcode a
   return of `"500°C, raining fish"`. Re-run. The model will happily report it.
   The model cannot check your tool — it believes whatever result you send back.
   That is why *your* code, not the model, is responsible for correct tool output.

3. **Give it a bad timezone (§3).** Ask "What time is it in Gotham?" The model
   will invent something like `"America/Gotham"`; `get_current_time` returns its
   `ERROR: ... not a valid IANA timezone` string, and you'll see how the model
   reacts to an error result. (Handling errors well is lesson p0004.)

4. **Take the tools away (§0).** Comment out the two `messages.append(...)` tool
   lines in `hand_built_tool_call` and just print `raw`. You're back to a blind
   model. The tools are the only thing that changed it.

---

## What you now know

- An LLM is a **text function**: tokens in, tokens out. It cannot fetch anything
  live — not the time, not the weather, not your data. (§0)
- A **tool** is just a normal function you own, plus a **description** you put in
  the prompt so the model knows it exists and how to ask for it. (§1)
- **"Calling a tool" = the model writing a text request** (which tool, which
  arguments). It runs nothing. (§2)
- **Your code executes** the request — look up the function by name in a
  **registry**, run it with the model's arguments. This is the only step where
  real work happens, and it's fully under your control. (§3)
- You **feed the result back** into the `messages` list and call the model again;
  now it answers for real. The model is **stateless**, so the list carries the
  whole story. (§4)
- One **protocol**, any number of tools — the machinery never changes. (§5)

*(Kotlin footnote, only if it helps: think of the model's request as returning a
sealed `Command` object — `GetTime(tz)` / `GetWeather(city)` — and your registry
as a `when(command)` dispatcher that runs the matching handler. The model
proposes the command; your dispatcher executes it. The difference is the "sealed
type" here is just a shape described in English in the prompt, agreed by
convention, not enforced by a compiler.)*

**Next lesson — `p0002`: the real `tools=` API.** We hand the provider the same
three facts (name, description, parameter schema), but as a structured tool
definition instead of English. In return, the model's request comes back not as
JSON-you-parse but as a clean `tool_calls` array the SDK already split apart, with
`finish_reason == "tool_calls"` telling you it wants a tool. Same four steps you
just built — the provider just does the fiddly parts for you.
