# p0002 — The real `tools=` API (the same four steps, formalized)

> **Run the code first, then read this.** `uv run p0002_tools_api.py`
> Each part below matches a numbered block in `p0002_tools_api.py`.
> This lesson assumes you did p0001. We build directly on it.

---

## Where we are

In p0001 you built tool calling with your bare hands:

- **Step 1** you described the tools in **English**, inside the system prompt.
- **Step 2** the model wrote a request as **plain text** (`{"tool": ...}`).
- **Step 3** you **parsed that text yourself** with `json.loads`.
- **Step 4** you fed the result back as an ordinary message.

It worked, and that was the point: there is no magic. Now we replace the
hand-rolled parts with the provider's real `tools=` feature. **The four steps do
not change.** What changes is who does the plumbing:

| | p0001 (by hand) | p0002 (real API) |
|---|---|---|
| describe a tool | English in the system prompt | a JSON-Schema object in `tools=` |
| the model's request | text you must find and parse | a structured `tool_calls` array |
| "it wants a tool" | you guess from the text | `finish_reason == "tool_calls"` |
| the result you send | a normal user message | a `role: "tool"` message with an id |

Same dance. The provider just writes the boring parts for you and gives you clean
fields instead of text to scrape.

---

## The one idea

> **The `tools=` API is not a new concept. It is p0001's four steps with the
> provider doing the schema plumbing and the parsing.** Learn the exact shape of
> the request you send and the response you get back. That shape never changes —
> across every model, every framework, the rest of your career.

---

## 1. STEP 1 — DEFINE the tools as JSON Schema

Instead of English, each tool is now a structured object. Here is the one the
program printed:

```json
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
          "description": "An IANA timezone name, e.g. 'Asia/Tokyo'."
        }
      },
      "required": ["timezone"],
      "additionalProperties": false
    }
  }
}
```

It carries the **same three facts** as your English description in p0001, only
now machine-readable:

- **`name`** — which function the model may ask for. This is the string that will
  come back in the request, and the key you look up in your registry.
- **`description`** — *when* to use it. This is not decoration. The model reads it
  to decide whether this tool fits the user's question. A vague description makes
  the model call the wrong tool or none. Write it like a docstring for the model.
- **`parameters`** — the arguments, described in **JSON Schema**: a `type: object`
  with `properties` (each argument, its type, its own description) and `required`.
  This is the same JSON Schema idea you met in prompt-engineering p0006 for typed
  output. Here it constrains the *arguments the model may send you*.

Two things worth noticing:

- **The tool descriptions moved out of the system prompt and into `tools=`.** In
  the run there is **no system prompt at all** — just the user question plus
  `tools=`. You no longer teach the model the protocol; the provider already
  knows it. Your job shrank to describing *your* tools.
- **`additionalProperties: false` + `required`** make this schema *strict-ready*
  (see the note at the end). It says: exactly these arguments, no extras.

---

## 2. STEP 2 — DECIDE (read the raw response)

We call the model with `tools=TOOL_SCHEMAS` and look at the raw response:

```text
finish_reason : 'tool_calls'   <- the model wants a tool (not 'stop')
message.content: None          <- no text answer yet
message.tool_calls: 1 call(s)
    id        = call_Y4WPTF2q5BjL4YboIXZ8syXm
    name      = get_current_time
    arguments = '{"timezone":"Asia/Tokyo"}'   <- type is str, a JSON STRING
```

Three fields decide everything from here:

**`finish_reason`** — this is how you *know* the model wants a tool. `"tool_calls"`
means "I am asking for one or more tools." `"stop"` means "I wrote a normal
answer, I'm done." Your whole loop (next lesson) branches on this one value. It is
the formal replacement for p0001's "try to parse the text and see if it's a
request."

**`message.content` is `None`** — when the model calls a tool, it usually writes
no text. There is no answer yet, because it hasn't seen the tool result. Don't try
to print `content` here; it's empty on purpose.

**`message.tool_calls`** — a list. Each entry is one requested call, already split
into fields for you:

- **`id`** (`call_Y4WPT...`) — a unique handle for *this specific call*. Memorize
  its job: in Step 4 you must send the result back tagged with this exact id, so
  the model knows which request the result answers. In p0001 there were no ids
  because there was only ever one hand-made call; the real API needs ids because a
  model can ask for several at once (p0003).
- **`function.name`** — the tool it wants (`get_current_time`).
- **`function.arguments`** — the arguments. **Read this carefully: it is a
  `str`, not a dict.** It is JSON *text* the model wrote: `'{"timezone":"Asia/Tokyo"}'`.
  This trips up nearly everyone. `tc.function.arguments["timezone"]` fails —
  you must `json.loads` it first. (Why a string? Because the model literally
  generates it token by token as text; the SDK hands it to you exactly as
  produced. Whether it's valid JSON is a separate question — that's what `strict`
  fixes.)

And the deep point, unchanged from p0001: **the model ran nothing.** It produced a
structured *request*. All the work is still yours.

---

## 3. STEP 3 — EXECUTE (parse the arguments, run the function)

```text
json.loads(arguments) -> {'timezone': 'Asia/Tokyo'}   (now a dict)
ran get_current_time(**{'timezone': 'Asia/Tokyo'})
  -> 'Thursday, 09 July 2026, 03:45:25 JST'
```

Two moves, and they are the heart of every agent:

```python
args = json.loads(tc.function.arguments)     # STRING -> dict
result = TOOLS[tc.function.name](**args)      # look up by name, run it
```

`json.loads` turns the JSON string into a real dict. Then the registry
(`TOOLS[name]`) — the same name→function map from p0001 — gives you the function,
and `**args` spreads the dict into keyword arguments. This is your code, your
machine, your control. Exactly as before; only the *source* of `args` changed
(from your own text-parsing to the SDK's field).

Each result is packaged into a message for Step 4:

```python
{"role": "tool", "tool_call_id": tc.id, "content": str(result)}
```

`content` must be a **string** (the model reads text), so wrap non-string results
with `str(...)` or `json.dumps(...)`.

---

## 4. STEP 4 — RETURN the result, get the final answer

Now we send the conversation back. Look at the exact roles the program replayed:

```text
    role='user'
    role='assistant'  (+1 tool_calls, content=None)
    role='tool'  (tool_call_id=call_Y4WPT..., content='Thursday, 09 July 2026, 03:45:25 JST')
```

There are **two** messages you must add, and both are required:

1. **The assistant message that made the request** — replayed *with its
   `tool_calls`*. You are reminding the model "here is what you asked for."
2. **One `role: "tool"` message per call** — carrying the result, tagged with
   `tool_call_id` equal to the request's `id`.

Why both? Two reasons, and they're the same reason underneath:

- **The model is stateless** (prompt-engineering p0001). The second API call is a
  brand-new request. The only way the model knows it asked for a tool *and* what
  came back is that the `messages` list tells the whole story.
- **The API validates the pairing.** Every `role: "tool"` message must answer a
  `tool_calls` entry in the *immediately preceding assistant message*, matched by
  id. Drop the assistant message, or mismatch an id, and you get a 400 error. The
  id is the glue between "the ask" and "the answer."

Then we call again — same `tools=`, because the model might want *another* tool.
This time it doesn't:

```text
second call finish_reason: 'stop'   <- a normal text answer now
final answer:
  The current time in Tokyo is 03:45 AM on Thursday, July 9, 2026.
```

`finish_reason: 'stop'` — the model saw the real result and wrote the final
sentence. The round trip, in full:

```
you: question + tools=          ->  model: finish_reason='tool_calls'
                                            tool_calls=[get_current_time(Asia/Tokyo)]
you: replay assistant + role:tool result  ->  model: finish_reason='stop'
                                                       "It is 03:45 in Tokyo."
```

Two model calls, your code running the tool in the middle. Identical to p0001 —
only the field names got formal.

---

## 5. The same machinery, reused for weather

Section 5 runs the identical `run_one_tool_round` with a different question and
you see the same shape: `finish_reason='tool_calls'` →
`get_weather(city="Paris")` → run it → `finish_reason='stop'` → the sentence. The
four steps are now a **reusable function**. That reuse — one function, any tool —
is the whole payoff of the formal API over hand-rolling.

---

## The reliability upgrade: `"strict": true`

Our schema already has `additionalProperties: false` and `required`. Add one more
field to the function definition:

```python
"function": {
    "name": "get_current_time",
    "strict": True,          # <- guarantee the arguments match the schema
    "description": ...,
    "parameters": { ... },
}
```

Without `strict`, `arguments` is *usually* valid JSON that fits your schema, but
the model can occasionally send a malformed or extra field — and then your
`json.loads` or `**args` blows up. With `strict: true`, the provider constrains
the model's decoding so the `arguments` string is **guaranteed** to be valid JSON
matching your schema exactly (this is the same *constrained decoding* idea as
`json_schema` structured output in prompt-engineering p0006). For a backend dev
this is the difference between "parse and pray" and "typed input I can trust."
Strict requires a strict-ready schema — every property `required` and
`additionalProperties: false` — which is why we wrote it that way. (Support is a
provider detail; GitHub Models / OpenAI support it. We left it off in the runnable
so the lesson works everywhere, but turning it on is a one-line reliability win.)

---

## A note on portability (the other provider shape)

The *concept* here is universal, but the field names are OpenAI's. Anthropic's
native API expresses the same four steps differently: the model returns a
`tool_use` block (not `tool_calls`) with `stop_reason: "tool_use"`, and you reply
with a `tool_result` block (not a `role: "tool"` message). Same dance — describe,
decide, execute, return — different JSON. You'll meet this shape properly in
p0004. For now: don't memorize field names as if they're the concept. The concept
is the four steps.

---

## Run it, then break it

1. **Forget to parse (§2).** Replace `args = json.loads(tc.function.arguments)`
   with `args = tc.function.arguments`, then `**args`. Watch it fail — `arguments`
   is a *string*. This is the number-one beginner bug; feel it once.

2. **Break the id link (§4).** In the `tool_result_messages`, change
   `"tool_call_id": tc.id` to `"tool_call_id": "wrong_id"`. Re-run. The provider
   rejects it with a 400 — proof the id is what pairs the answer to the ask.

3. **Drop the assistant replay (§4).** Comment out
   `messages.append(assistant_message)` (keep the tool message). Re-run. Another
   400: a tool message with no preceding `tool_calls` to answer.

4. **Weaken a description (§1).** Change `get_current_time`'s description to just
   `"a tool"`. Ask the time again. The model may now fail to pick it, or fill the
   timezone wrong. Proof that `description` is real prompt engineering, not a
   label.

5. **Watch the model fill arguments (§2).** Ask *"What time is it in New York?"*
   The `arguments` string comes back with `"America/New_York"` — the model mapped
   the city to the IANA zone your schema asked for. That mapping is the value.

---

## What you now know

- The `tools=` API is p0001's **four steps, formalized** — the provider writes the
  schema plumbing and parses the request for you. (§where-we-are)
- **Step 1 / DEFINE:** each tool is a JSON-Schema object — `name`, `description`
  (the model reads it to decide), `parameters`. The descriptions live in `tools=`,
  not the system prompt. (§1)
- **Step 2 / DECIDE:** `finish_reason == "tool_calls"` is how you know; `content`
  is `None`; `tool_calls` gives you `id`, `function.name`, and
  `function.arguments` — which is a **JSON string** you must `json.loads`. (§2)
- **Step 3 / EXECUTE:** `json.loads` the arguments, look the function up by name,
  run it. Your code, your control. (§3)
- **Step 4 / RETURN:** append the **assistant message with its `tool_calls`** plus
  one **`role: "tool"`** message per call, matched by **`tool_call_id`**. Call
  again → `finish_reason == "stop"` → the text. The id is the glue; the API
  validates it. (§4)
- **`strict: true`** guarantees the arguments match your schema — "parse and pray"
  becomes typed input you can trust.
- The concept is provider-agnostic; only field names differ (Anthropic:
  `tool_use` / `tool_result`).

**Next lesson — `p0003`: two tools and the loop.** We ask one question that needs
*both* tools and watch the model return **two `tool_calls` in a single response**
(parallel). Then we wrap Steps 2–4 in a `while` loop that runs until
`finish_reason == "stop"`, with a cap on iterations. That loop — model decides,
you run tools, feed back, repeat — *is* an agent. Everything so far has been
building to it.
