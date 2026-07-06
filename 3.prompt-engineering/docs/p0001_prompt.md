# p0001 — What a prompt *really* is

> **Run the code first, then read this.** `uv run p0001_prompt.py`
> Each part below matches a numbered block in `p0001_prompt.py`.
> We assume you know **nothing** about how an LLM call is shaped. We build it
> from the bottom.

---

## Why this lesson comes first

This whole phase is called "prompt engineering." You cannot *engineer* a thing
until you can see what the thing is made of. So before any technique — before
system prompts, few-shot, chain-of-thought — we answer one question:

> When you "send a prompt to an LLM," what actually gets sent?

The honest answer surprises most people. A prompt is **not** the text you type.
It is a small, strict data structure: **a list of messages, each tagged with a
role, serialized to JSON, and POSTed over HTTP.** Everything you learn later is
just "what do I put in that list." Get this picture right and the rest of the
phase is filling in details.

---

## The one mental model

Hold these four facts. The whole lesson is proving them.

1. **A prompt is a list.** Not a string. A Python `list` of small `dict`s.
2. **Each item has a role.** `system`, `user`, or `assistant`. The role is not
   decoration — the model was *trained* to treat them differently.
3. **The model's job is tiny.** Read the list, write **one** new message
   (`role="assistant"`). List in → one message out.
4. **The model is stateless.** It remembers nothing between calls. Any "memory"
   you see is *you* re-sending the earlier messages. There is no hidden storage
   on the other side.

---

## 1. A prompt is a LIST of messages — not a string

You type a sentence, so it *feels* like a string:

```text
What you TYPE feels like a plain string:
    'Explain what a token is in one sentence.'
```

But the API refuses a bare string. It wants a **list**, and your text has to be
wrapped into a message object that also says *who is speaking*:

```text
But the API will not accept a string. It accepts a LIST like this:
    [{"role": "user", "content": "Explain what a token is in one sentence."}]
```

Your one sentence became **one item in a list**. That list is the prompt.

Why a list and not a string? Because a real conversation has more than one turn,
and the model needs to know who said each part. A flat string throws that away.
A list keeps it. So from the very first call, the shape is already "a
conversation," even when there is only one line in it.

> **The reframing:** every technique in this phase — role instructions,
> examples, reasoning steps — is really the same move: *add or change items in
> this list, and choose the words inside them.* That is the entire job.

---

## 2. Every message has a ROLE: system, user, assistant

A fuller prompt is a whole conversation. Here is one, printed with the role of
each line on the left:

```text
    [0] role=system    content='You are a terse assistant. Answer in one short line.'
    [1] role=user      content='What is the capital of Japan?'
    [2] role=assistant content='Tokyo.'
    [3] role=user      content='And of France?'
```

Three roles, three jobs:

- **`system`** — your standing orders. Rules that apply to the *whole* chat:
  who the model should be, the format to use, what it must never do. It sits at
  the top and has the most influence. (Lesson p0003 is all about this one.)
- **`user`** — what the human said.
- **`assistant`** — what the model said **before**. This is the part that trips
  up beginners: the model's own past replies are fed *back to it* as history,
  each tagged `assistant`. That is how it can answer "and of France?" — item [2]
  reminds it that the game is "name capitals."

### Why does the role actually change anything? (the thing under the thing)

This is the first "but how does it REALLY work" moment, so let's not hand-wave.

The model is a **next-token predictor**. It only knows how to do one thing: given
some text, guess the text that comes next. It has no concept of a "list" or a
"role" by itself. So how can roles matter?

Because before the model sees your list, the server **flattens it into one long
string** using a fixed template, with special marker tokens around each role.
Simplified, your list above becomes something like:

```text
<|system|>You are a terse assistant. Answer in one short line.<|end|>
<|user|>What is the capital of Japan?<|end|>
<|assistant|>Tokyo.<|end|>
<|user|>And of France?<|end|>
<|assistant|>
```

Then the model is asked to **predict what comes after that final
`<|assistant|>`** — and the most likely continuation is `Paris.`

(The exact marker tokens differ per model family, and you never type them
yourself — the server adds them. The picture is what matters, not the exact
symbols.)

Two things fall out of this, and they explain a lot of later lessons:

- **Roles are real, learned structure.** During training the model saw millions
  of these role-marked conversations, and it learned that text after
  `<|system|>` is rules to obey, and text after `<|user|>` is the thing to
  answer. So putting instructions in the `system` role genuinely lands
  differently from putting them in a `user` message — not by magic, but because
  the model was trained that way.
- **"Predict the next token" and "have a conversation" are the same thing.** A
  chat is just a next-token prediction on a string that happens to be formatted
  as a dialogue. There is no separate "chat engine." This is the root under
  everything in this course.

We did not send this list. Section 3 sends a real one and shows the bytes.

---

## 3. Watch the real bytes leave — the list becomes JSON on the wire

Here is the reveal. We send a 2-message list and print the **actual HTTP
request** the SDK builds. (We do that with a small hook on the HTTP client —
normally the SDK hides all of this; we un-hid it once, on purpose.)

```text
  --- THE ACTUAL HTTP REQUEST YOUR CODE JUST SENT ---
  POST https://models.github.ai/inference/chat/completions
  a few headers (your token rides in 'authorization' — we redact it):
      host: models.github.ai
      authorization: <redacted — this is your secret token>
      accept: application/json
      content-type: application/json
  body (THIS JSON is your prompt — the messages list — serialized):
      {
        "messages": [
          {
            "role": "system",
            "content": "You are a terse assistant. One short sentence."
          },
          {
            "role": "user",
            "content": "What is the capital of Japan?"
          }
        ],
        "model": "openai/gpt-4o-mini",
        "temperature": 0
      }
  --- end of request ---
```

Read that slowly, because this single screen demystifies the whole thing. An LLM
call is an ordinary web request. From your backend eyes:

- **`POST`** to a URL. The `base_url` you set plus `/chat/completions`. That is
  the whole "API" — one endpoint.
- **Headers.** `content-type: application/json` says "my body is JSON."
  `authorization` carries your token — this is how the server knows the call is
  allowed. **Your secret lives in a header, not in the prompt.** (We redacted it
  in the print. It is never shown and never committed, because it comes from the
  gitignored `.env`.)
- **The body** is JSON. And look at what dominates it: a field named
  `"messages"` holding the exact list from section 1–2. Plus `model` (which
  model to run) and `temperature` (how random — lesson p0007).

> **This is the definition of prompt engineering, made literal:** it is the
> craft of shaping the `"messages"` array in this JSON body. Nothing more
> mystical than that. When later lessons say "add a system prompt" or "give it
> examples," they mean "add items to this array."

The SDK is not doing anything clever here. `client.chat.completions.create(...)`
takes your Python arguments, turns them into this JSON, POSTs it, waits, and
parses the reply. You could send the same bytes with `curl`. The SDK is a
convenience, not a black box.

The model replied `'Tokyo.'` — short, because the `system` message told it to be
terse. Your first proof that the `system` role does real work.

---

## 4. The reply is just the NEXT message (role = assistant)

We send one message and look closely at what comes back:

```text
The response carries a message object — the SAME shape we send:
    role    = 'assistant'
    content = 'Pong'
```

The reply is **a message object** — the exact same shape as the ones we send: a
`role` and a `content`. Its role is `assistant`. This closes the loop from
section 2: the model's past replies are `assistant` messages *because the model
produces `assistant` messages.* Output and history are the same shape.

So the model's entire contract is tiny:

> **Input:** a list of messages. **Output:** one new `assistant` message.

That is it. Every fancy agent you will build later is this one call, wrapped in a
loop, with tools and memory bolted around it. The call itself never gets more
complicated than "list in, one message out."

(You will also have noticed the model returned `'Pong'` with a capital P, even
though we asked for the single word `pong`. That is not a bug — it is a preview
of a real problem: models follow format instructions *loosely*. Fixing that
reliably is what lessons p0004–p0005 are for.)

### The token counts (a one-line bridge to p0002)

```text
  (It also reported token counts: prompt=14, reply=3.
```

Every response also reports how many **tokens** went in and came out. `prompt=14`
means our little list cost 14 tokens; the reply was 3. You pay per token, and the
context window is measured in tokens. We are ignoring this for now — the very
next lesson, p0002, is nothing but tokens.

---

## 5. "Memory" is an illusion — it is YOU re-sending the whole list

This is the most important section in the lesson. It is the fact that makes
"agent memory" a real engineering problem for the rest of the course.

We run the same question two ways. First we tell the model a fact and let it
reply:

```text
Turn 1 — we said:   "My name is Aditya and I like Kotlin. Just reply 'ok'."
         it replied: 'ok'
```

Now we ask "what is my name and what do I like?" — but **with the earlier
messages included**:

```text
Turn 2 WITH history (we resend all 3 messages):
    answer: 'Your name is Aditya, and you like Kotlin.'
```

It knows. Now the *same question*, but we send **only the question**, with no
history:

```text
Turn 2 WITHOUT history (we send only the question):
    answer: "I'm sorry, but I don't have access to personal information about you
             unless you've shared it in our conversation. ..."
```

It has no idea. Same model, same question, seconds apart. The only difference is
whether we re-sent the earlier messages.

### What this proves about the machinery

The server keeps **nothing** about you between calls. Each POST is judged on its
own body alone — remember section 3: the body is the *entire* input. There is no
session, no hidden profile, no memory on the far side. Every call starts from a
blank slate and sees only the list you sent *this time*.

So the "memory" in ChatGPT-style chats is not the model remembering. It is the
**client** keeping the growing list and re-sending it every turn:

```text
turn 1 request body: [user1]
turn 2 request body: [user1, assistant1, user2]
turn 3 request body: [user1, assistant1, user2, assistant2, user3]
...
```

The conversation you *see* is a picture your app maintains. The model is handed
the whole transcript each time and re-reads it from scratch.

This single fact drives a huge amount of later engineering:

- **Cost grows every turn** (p0002): a longer list = more tokens = more money and
  more latency, *every* call.
- **The context window is a hard wall** (p0002): the list can only get so long
  before it no longer fits, and the model literally cannot see the oldest turns.
- **All four kinds of "memory"** in the roadmap (keep-everything, save-to-DB,
  summarise-old-turns, retrieve-relevant-facts) are just different strategies for
  *which* messages to put back into this list, and how to shrink it when it grows
  too big.

When someone says "give the agent long-term memory," translate it in your head
to: *"decide what to put in the messages list before each call."* That
translation will keep you honest through the whole course.

---

## Run it, then break it (do these — this is where it sticks)

1. **Prove roles matter (§3).** In `demo_the_wire`, change the `system` message
   to `"You are a wordy assistant. Explain in three long paragraphs."` Re-run.
   The reply grows from `Tokyo.` into a lecture — same question, different
   `system`. You just moved the model's behavior by editing one list item.
2. **Delete the system message (§3).** Send only the `user` message. The answer
   still comes, but the terse style is gone. The `system` role was doing that
   work.
3. **Break the memory (§5).** In `demo_memory_is_resending`, in the
   `with_history` list, delete `turn1_user` (keep only the assistant line and the
   question). Re-run. Watch the answer get worse or wrong — you removed the fact
   the model needed. Memory is *exactly* the messages you choose to keep.
4. **Fake a memory that never happened (§5).** Add a handwritten assistant
   message to `with_history`, e.g.
   `{"role": "assistant", "content": "You told me you love Rust."}`, then ask the
   question. The model will happily "remember" loving Rust. Proof that the model
   trusts the list you give it — it has no other source of truth. (This is also
   why validating history matters in real systems.)
5. **See the wire for a second call.** Set `_print_next_request = True` again
   right before another `create(...)` call and watch that request too. Notice the
   body is always the same shape: `model`, `messages`, params.

---

## What you now know

- A **prompt is a list of messages**, not a string. Each message is a `dict`
  with a `role` and `content`.
- **Three roles:** `system` (standing orders, most power), `user` (the human),
  `assistant` (the model's past replies, fed back as history).
- Roles are **real, trained structure**: the server flattens your list into one
  role-marked string and the model predicts the continuation. "Chat" is
  next-token prediction on a formatted transcript.
- An LLM call is an **ordinary HTTP POST**: JSON body, `messages` array inside
  it, token in the `authorization` header. **Prompt engineering = shaping that
  `messages` array.**
- The reply is **one new `assistant` message**. The model's contract: list in,
  one message out.
- The model is **stateless**. "Memory" is you **re-sending the list**. Every
  memory technique later is a strategy for what to keep in that list — and why
  cost and the context window (p0002) push back on keeping everything.

*(Kotlin footnote, only if it helps: think of one message as a
`data class Message(val role: String, val content: String)`, and a prompt as a
`List<Message>`. The API call is a plain HTTP POST — the same `RestTemplate` /
`WebClient` request you already write in Spring, with a JSON body and a bearer
token header. The OpenAI SDK is just a typed client over that endpoint. Nothing
about it is special to "AI" — it is a web service that happens to answer in
English.)*

**Next lesson — `p0002`: tokens.** You saw `prompt=14, reply=3` fly by. The next
lesson slows that down and makes it visible: what a token is, how your text gets
chopped into tokens, why you pay per token, and why the context window is a wall
you keep hitting. It is the unit that everything in section 5 — cost, memory,
the window — is measured in.
