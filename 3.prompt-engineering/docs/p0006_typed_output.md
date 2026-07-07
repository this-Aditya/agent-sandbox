# p0006 — Typed output: JSON → Pydantic (the finale + the build)

> **Run the code first, then read this.**
> `uv run p0006_typed_output.py` and `uv run prompt_lab.py --classify "..."`
> Output captured from RADAR `qwen3-30b`. This lesson uses Phase 2's Pydantic and
> everything from p0001–p0005.

---

## Why this is the finale

Every earlier lesson shaped the *conversation*. But an LLM still returns **text**,
and your code wants **data** — a number you can multiply, a list you can loop, a
label you can branch on. p0005 got one value out with a fragile regex. This lesson
closes the gap properly:

> **Make the model reply in JSON, then let Pydantic turn that JSON into a typed,
> validated object.** Now the model's answer is real Python data your code can
> trust.

Four steps, then the build:

1. Text → JSON → a typed Pydantic object.
2. Strict schema mode — the shape is guaranteed, not hoped for.
3. Validation catches bad output (your safety net).
4. The build: `prompt_lab.py` (`--classify` / `--extract` / `--reason`).

---

## 1. Text → JSON → a typed Pydantic object

We define the **shape we want** as a Pydantic model:

```python
class Sentiment(BaseModel):
    label: Literal["positive", "negative", "neutral"]
    confidence: float = Field(ge=0, le=1)
```

Then we ask the model, with `response_format={"type": "json_object"}` — which
tells the endpoint *"your reply must be valid JSON, no prose, no ```json fences."*

```text
The model returned this TEXT (which happens to be JSON):
    '{\n  "label": "positive",\n  "confidence": 0.98\n}'

Parsed into a Sentiment object — a real typed Python value:
    type(s)      = Sentiment
    s.label      = 'positive'   (a str, one of the 3 allowed)
    s.confidence = 0.98   (a float, not a piece of a string)
```

The reply comes back as text — but it's JSON text. Then **one line** turns it into
a typed object:

```python
s = Sentiment.model_validate_json(raw)   # text -> typed object
```

Now `s.confidence` is a real `float`. You can write `s.confidence * 100` and it
just works. Compare that to p0005, where we regex-matched an `ANSWER:` line and
got a *string* we'd have to clean and convert ourselves. This is the difference
between "pick apart a string" and "receive typed data."

> This is the bridge the whole Phase-2 Pydantic lesson was building toward: **LLM
> text in, typed validated object out.** Every later framework (LangChain,
> LangGraph) does exactly this under the hood.

---

## 2. Strict schema mode: the shape is guaranteed

`json_object` guarantees *valid* JSON, but not *your* JSON — the model could still
return `{"mood": "happy"}`. To lock the shape, hand your Pydantic schema to the
model with `response_format={"type": "json_schema", ...}`:

```text
Pydantic can hand its schema straight to the model:
    {"properties": {"label": {"enum": ["positive","negative","neutral"], ...},
     "confidence": {"maximum": 1, "minimum": 0, "type": "number"}, ...},
     "required": ["label","confidence"], "type": "object"}

With response_format=json_schema, the reply is forced to fit that shape:
    '{ "label": "neutral", "confidence": 0.85 }'
    parsed: label='neutral', confidence=0.85
```

`Sentiment.model_json_schema()` produces a JSON Schema (note `enum` for the label,
`minimum`/`maximum` for the confidence). The endpoint uses it to **constrain**
generation, so the reply must fit.

Two levels of "give me JSON":
- **`json_object`** → the reply is guaranteed **valid JSON** (any shape).
- **`json_schema`** → the reply is guaranteed to fit **your exact shape**.

qwen3-30b supports both. `json_schema` is the strongest.

### How can the API *force* a shape? (the thing under the thing)

This is worth understanding, because it looks like magic. Recall p0005: at each
step the model scores every possible next token and samples one. **Schema mode
adds a mask.** Before sampling, the server looks at the schema and the JSON so far,
and **removes every token that would break the rules** — then the model samples
only from what's left. Right after `"label": "` the only allowed next tokens are
`positive`, `negative`, or `neutral`; nothing else is even on the table. So the
wrong shape isn't "discouraged," it is **literally impossible to generate** —
because the tokens that would produce it were deleted from the choices. This is
called *constrained decoding*. It's the same next-token sampling from p0005, with
a filter over the choices.

---

## 3. Pydantic validation catches bad output (your safety net)

Even with JSON mode, you want a guard in your own code. Pydantic *is* that guard.
This section makes **no model call** — it just feeds hand-written JSON to
`Sentiment`:

```text
Good JSON parses into a clean object:
    label='positive' confidence=0.9

Bad JSON is REFUSED, with a clear reason:
  REJECTED — confidence is text: Input should be a valid number, unable to parse string as a number
  REJECTED — confidence out of 0..1: Input should be less than or equal to 1
  REJECTED — label not allowed: Input should be 'positive', 'negative' or 'neutral'
```

Your `Sentiment` model refuses:
- `"confidence": "very high"` — not a number.
- `"confidence": 5` — outside the `0..1` range you declared with `Field(ge=0, le=1)`.
- `"label": "amazing"` — not one of the `Literal` values.

The model *can* still surprise you (a different provider, an edge case, a
non-strict mode). Validation means bad data **stops at your door** with a clear
error instead of flowing into your program. In production you catch that error and
retry — which is exactly what the build does next.

---

## The build: `prompt_lab.py`

The phase deliverable. A CLI that turns text into typed data, using **every**
technique from the phase. The core helper forces JSON, parses into a Pydantic
model, and **retries once** if validation fails (feeding the error back to the
model):

```python
def ask_typed(model_cls, system, user, temperature=0.0):
    for _ in range(2):
        resp = client.chat.completions.create(..., response_format={"type": "json_object"})
        try:
            return model_cls.model_validate_json(resp.choices[0].message.content)
        except ValidationError as e:
            # tell the model what was wrong and ask again
            ...
```

### `--classify` (Sentiment; temperature 0)

```text
$ uv run prompt_lab.py --classify "I love the design, but the battery dies fast."
label      : neutral
confidence : 0.75
```

A mixed review — praise *and* a complaint — so `neutral` is a fair call. Note
temperature 0: same text always gives the same label, which is what you want when
code depends on it (p0005).

### `--extract` (Entities; temperature 0)

```text
$ uv run prompt_lab.py --extract "Tim Cook met UN officials in Paris on 3 May 2024."
people        : ['Tim Cook']
organizations : ['UN']
dates         : ['3 May 2024']
```

Three real Python lists, ready to loop over — not a sentence you have to parse.

### `--reason` (Reasoning; chain-of-thought)

```text
$ uv run prompt_lab.py --reason "A bat and ball cost £1.10; the bat is £1.00 more than the ball. How much is the ball?"
--- reasoning ---
Let the cost of the ball be x pounds.
... 2x + 1.00 = 1.10 ... 2x = 0.10 ... x = 0.05
Check: Ball = £0.05, Bat = £1.05, Total = £1.10 — correct.

--- answer ---
0.05
```

This is the famous trap question — the "obvious" answer is £0.10, which is
**wrong**. Because we asked for reasoning first (p0005) and captured it in a
`reasoning` field separate from `answer`, the model worked it out and landed on
the correct **£0.05**. The `Reasoning` model gives us both parts as typed fields,
so the CLI can print the thinking and the answer separately.

Together, one small CLI uses: a **system prompt** (p0003), **few-shot** examples in
classify (p0004), a **stated JSON shape** (p0004), **temperature 0** for stable
extraction (p0005), **chain-of-thought** for reasoning (p0005), and **JSON →
Pydantic** typing with a validation **retry** (p0006).

---

## Run it, then break it (we're on an unlimited model now)

1. **Force a wrong shape (§2).** Ask the model (in `json_object` mode) for
   `{"mood": ...}` instead, then parse with `Sentiment`. Watch Pydantic reject it —
   then switch to `json_schema` mode and watch the wrong shape become impossible.
2. **Trigger the retry (build).** In `prompt_lab.py`, change the classify system
   prompt to ask for `score (1 to 10)` instead of `confidence (0 to 1)`. The first
   reply now fails the `0..1` rule, and you'll see the retry fix it (or give up
   with a clear error).
3. **Reason without CoT.** In `reason()`, drop "First think step by step" and keep
   only "give the answer." Ask the bat-and-ball question. It's more likely to fall
   for the £0.10 trap — proof that the reasoning field is doing real work.
4. **Add a field.** Give `Entities` a `locations: list[str] = []` field and update
   the prompt. Re-run `--extract` on the Paris sentence — `Paris` should appear.

---

## What you now know — and the whole of Phase 3

- **Force JSON** with `response_format` (`json_object` = valid JSON; `json_schema`
  = your exact shape), and **parse it into a typed Pydantic object** with
  `model_validate_json` (§1–2).
- The API enforces shape by **masking out illegal tokens before sampling** —
  constrained decoding (§2).
- **Pydantic validation** is your own guardrail: bad data is refused with a clear
  error you can catch and retry (§3, build).

**Phase 3 recap — you now have the full prompt-engineering toolkit:**

| Lesson | The tool |
|---|---|
| p0001 | A prompt is a **list of role-tagged messages**; the model is stateless. |
| p0002 | It reads **tokens**, not letters — cost, context, and the letter-counting trap. |
| p0003 | The **system prompt** steers role, format, and rules for the whole chat. |
| p0004 | **Structure** (delimiters) separates instructions from data; **few-shot** shows the task. |
| p0005 | **Chain-of-thought** for hard answers; **temperature** for repeatable vs varied. |
| p0006 | **Typed output**: JSON → Pydantic, the bridge from LLM text to real data. |

*(Kotlin/Spring footnote: `response_format=json_schema` + `model_validate_json` is
the LLM version of a typed `@RequestBody` with Bean Validation. You declare the
shape and constraints once (the Pydantic model = your DTO), and anything that
doesn't fit is rejected at the boundary with a clear error — instead of you
parsing a `String` by hand.)*

**Phase 3 is complete. ✅** Next is **Phase 4 — Tool Calling (raw)**: the most
important phase. So far the model only *talks*. Next, you give it **tools** — it
asks your code to run a function, you run it, you feed the result back, and it
continues. That loop is what turns a chatbot into an agent, and every framework
later is built on it. Everything you just learned (JSON in/out, schemas, typed
parsing) is exactly how tool calls are described and returned.
