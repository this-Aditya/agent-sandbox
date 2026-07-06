# p0002 — Tokens: the unit the model reads, and the unit you pay for

> **Run the code first, then read this.** `uv run p0002_tokens.py`
> Each part below matches a numbered block in `p0002_tokens.py`.
> We assume you know **nothing** about tokenization. We build it from bytes up.

---

## Why this lesson comes second

In p0001 you saw a line fly by: `prompt=14, reply=3`. Those are **token counts**.
Tokens are the single most practical idea in this whole path, because:

- You **pay per token** (input + output).
- The **context window** — the most the model can read at once — is measured in
  tokens.
- **Latency** roughly tracks tokens: more tokens in and out = slower.

So when an agent feels slow, expensive, or "forgets" old messages, the honest
first question is always *"how many tokens?"* This lesson makes tokens visible so
that question stops being abstract.

---

## The one mental model

> The model does **not** read letters or words. It reads **tokens** — plain
> integers. A **tokenizer** turns your text into a list of integers before the
> model sees anything, and turns the model's integer output back into text. Every
> cost, every limit, every speed number is counted in these tokens.

Four facts, proven below:

1. Text ⇄ tokens is a fixed two-way dictionary. The network only sees integers.
2. A token is **not** a word and **not** a character. It's a common *chunk*.
3. Roughly **4 characters per token** for English — a planning guess, not a law.
4. Both your **prompt** and the model's **reply** cost tokens, and a chat's token
   count **grows every turn**.

---

## 1. Text becomes tokens (integers), and back again

```text
Your text:     'Prompt engineering is fun!'
As token IDs:  [51905, 16411, 382, 2827, 0]
That is 5 tokens. The neural network ONLY ever sees these integers.

Each integer maps back to a piece of text. Split apart:
      51905  ->  'Prompt'
      16411  ->  ' engineering'
        382  ->  ' is'
       2827  ->  ' fun'
          0  ->  '!'

Decode the integers back:  'Prompt engineering is fun!'
```

Read what happened. Your sentence became **five integers**. That is literally all
the model ever receives — a list of numbers. `16411` *means* `' engineering'` only
because the tokenizer's dictionary says so. Decode the five numbers and you get
your sentence back, exactly. So the tokenizer is a **fixed two-way dictionary**:
text → integers on the way in, integers → text on the way out. It was built once
when the model was made, and never changes.

Notice already something odd: `' engineering'`, `' is'`, `' fun'` all include a
**leading space**. Spaces are not separate; they ride *inside* the next token.
Section 2 shows why that matters, and the "how the tokenizer is built" part below
explains why it happens.

---

## 2. A token is not a word, and not a character

```text
             'cat'  ->  1 token(s): ['cat']
            'cats'  ->  1 token(s): ['cats']
            ' cat'  ->  1 token(s): [' cat']
    'tokenization'  ->  2 token(s): ['token', 'ization']
   'Reinforcement'  ->  3 token(s): ['Re', 'in', 'forcement']
           'naïve'  ->  3 token(s): ['na', 'ï', 've']
      '1234567890'  ->  4 token(s): ['123', '456', '789', '0']
               '🙂'  ->  1 token(s): ['🙂']
              '🇯🇵'  ->  4 token(s): ['�', '�', '�', '�']
```

Every line breaks a naive assumption:

- **`cat` and `cats` are both single tokens** — but *different* tokens. So a token
  isn't "a word stem plus an ending." Common whole words, plurals included, each
  get their own single token because they appear so often.
- **`' cat'` (leading space) is a different single token** from `'cat'`. Spaces
  belong to the token after them. This is why joining or splitting words changes
  your token count — `"foo bar"` and `"foobar"` tokenize differently.
- **`tokenization` and `Reinforcement` split into pieces.** Longer or less common
  words break into "word-pieces" (`token` + `ization`). `naïve` splits into
  `na` + `ï` + `ve` because `ï` is not a plain ASCII letter — non-English text
  usually costs more tokens.
- **Digits chunk**, often three at a time (`123`, `456`, `789`, `0`). This is why
  models are famously shaky at arithmetic: they don't see the number `1234567890`,
  they see four unrelated chunks.
- **`🙂` is a single clean token**, but **`🇯🇵` becomes four `�` tokens.** That `�`
  is the "I can't show this as text" symbol. It appears because those tokens are
  **fragments of raw bytes**, not whole characters. A token can be *smaller than
  one character.* The next part explains exactly why.

### How does the tokenizer decide the pieces? (byte-pair encoding — the root)

This is the "but how does it REALLY work" answer. The method is called **BPE
(byte-pair encoding)**, and it's simpler than it sounds.

Start from the bottom:

1. **Text is stored as bytes.** Your computer already stores text as bytes using
   UTF-8. `A` is 1 byte. `ï` is 2 bytes. `🙂` is 4 bytes. `🇯🇵` is several bytes.
   So the *true* raw material is a stream of bytes, and there are only 256
   possible byte values.

2. **Begin with 256 base tokens** — one per possible byte. At this point every
   piece of text could be tokenized, but everything would be tiny (one token per
   byte). That's correct but wasteful.

3. **Merge the most common pair, over and over.** Take a giant pile of text. Find
   the **most frequent adjacent pair** of tokens and glue it into one new token.
   Repeat about 200,000 times. Early merges build things like `t`+`h` → `th`, then
   `th`+`e` → `the`, then ` `+`the` → ` the`. Very common words and word-pieces
   grow into single tokens; the space gets merged in because " word" patterns are
   everywhere in real text.

4. **Stop at ~200,000 tokens.** That final set is the vocabulary. For gpt-4o and
   gpt-4o-mini it is called **`o200k_base`** — "o200k" ≈ *around 200 thousand*.
   (That is the exact vocabulary we loaded with `tiktoken.get_encoding`, which is
   why our local counts match the real model.)

Now every result in the output makes sense:

- `cats`, `running`, ` the` are **common**, so they survived as single merged
  tokens → 1 token each.
- `Reinforcement`, `tokenization` are **less common**, so only their frequent
  *parts* got merged → a few tokens.
- `ï` and the flag `🇯🇵` are **rare**, so they were **never merged into a bigger
  token** and fall back to their raw UTF-8 **bytes**. A single byte of a 4-byte
  emoji is not a valid character on its own, so it prints as `�`. That is the
  byte-fragment case, seen live.

The one-line takeaway: **common = few tokens (cheap); rare = many tokens
(expensive).** Plain English is cheap. Emoji, rare names, other alphabets, and
dense code are expensive. You now know *why*, from the bytes up.

---

## 3. The planning rule of thumb: ~4 characters per token

```text
Characters: 181
Tokens:     37
Ratio:      4.89 characters per token
```

For ordinary English, a token averages **about 4 characters** (here 4.89). This
is the number you use to *estimate* — "this 8,000-character document is roughly
2,000 tokens, so it fits a small context window." It is a guess, not a law:
section 2 already showed code, digits, emoji, and other languages all push the
ratio around. When money or the context window is on the line, **count** tokens
(with `tiktoken`) instead of guessing.

---

## 4. Your local count vs the API's own count

```text
Tokens in just the CONTENT text of the 2 messages: 17
Tokens the API says the PROMPT cost:               28
Extra tokens the API counted:                      11
```

We tokenized just the **content strings** of two messages: 17 tokens. Then we
asked the real API, and it billed the prompt at **28**. Where did the extra **11**
come from?

Straight back to p0001. Before the model sees your list, the server **flattens it
into one string with role markers** around each message — something like
`<|im_start|>system … <|im_end|><|im_start|>user … <|im_end|><|im_start|>assistant`.
Those markers are **real tokens**. Two messages plus the assistant "your turn"
marker add up to that overhead. So:

> **Your true prompt size = the content tokens + a few formatting tokens per
> message.** The structure from p0001 is not free — you can now *see* its cost.

Practical effect: many tiny messages cost more than one bigger message with the
same words, because every message pays the per-message marker tax. It's small
here (11 tokens), but across a long agent loop it adds up.

---

## 5. Output is built one token at a time — max_tokens caps it

```text
We asked for a long answer but set max_tokens=6:
    reply:         '1. **Mango**'
    finish_reason: 'length'
    output tokens: 6
```

We asked for three fruits with full sentences — a long answer — but set
`max_tokens=6`. The reply stops dead at `'1. **Mango**'`, exactly 6 tokens, and
`finish_reason` is **`'length'`**.

That `finish_reason` is the key. It has two common values:

- **`'stop'`** — the model decided it was **done** on its own.
- **`'length'`** — the model was **cut off** because it hit `max_tokens` (or the
  context window). It was *not* finished; you chopped it.

Why can it be chopped cleanly at exactly 6 tokens? Because the model generates
**one token at a time**, feeding each new token back in to decide the next — this
is called being **autoregressive**:

```text
prompt -> token1
prompt + token1 -> token2
prompt + token1 + token2 -> token3
... until it emits a "stop" token OR hits max_tokens
```

Two things follow from this:

- **`max_tokens` is a hard safety cap on cost.** Output tokens are usually the
  *expensive* ones. Capping them bounds the price of a runaway reply. (You'll use
  this to stop agent loops from spending forever, much later in the path.)
- **Streaming is possible** *because* generation is token-by-token. The tokens
  already exist one at a time, so the server can send each one to you the instant
  it's made — that's the live "typing" effect. (It's the same pause/resume
  streaming idea from your Phase 2 generators lesson, applied to model output.)

---

## 6. Why tokens bite: a chat's cost climbs every turn

```text
    turn 1: the list you send is now ~9 tokens
    turn 2: the list you send is now ~39 tokens
    turn 3: the list you send is now ~70 tokens
    turn 4: the list you send is now ~99 tokens
    turn 5: the list you send is now ~131 tokens
```

This is p0001 §5 turned into numbers. Remember: the model is stateless, so
"memory" means **re-sending the whole history every turn.** Watch the token count
climb — 9 → 39 → 70 → 99 → 131 — because the list only ever grows. You are paying
to make the model **re-read the entire past on every single call.** Two hard walls
come straight out of this:

- **Cost.** Price is per token, and the token count rises each turn, so a long
  conversation gets steadily more expensive — the *last* turn of a long chat can
  cost many times the first.
- **The context window.** Every model can only read so many tokens at once (tens
  to hundreds of thousands, depending on the model). Once the growing list passes
  that limit, the oldest turns must be **dropped or summarized** — they literally
  stop existing for the model. This is the hard reason "agent memory" is an
  engineering problem, not a setting you switch on.

```text
  Rough cost feel (illustrative price; on GitHub Models you pay $0):
    100,000 input tokens at $0.15/1M  ≈  $0.0150
```

That price is made up for intuition (and on GitHub Models you pay nothing) — but
the *shape* is what matters: cheap per call, yet an agent can send a big prompt on
**every step of every request**, so it multiplies fast. **Tokens are the one
number you watch** to keep both cost and speed under control. Every optimization
later in the path — trimming history, summarizing, prompt caching, retrieving only
what's relevant — is, at heart, *"send fewer tokens without losing what matters."*

---

## Run it, then break it (do these)

1. **Feel a language's cost (§2/§3).** In `demo_ratio`, replace the English
   paragraph with the same idea in another language, or paste a block of JSON or
   code. Re-run and watch the characters-per-token ratio drop — the same *meaning*
   now costs more tokens.
2. **Watch the marker tax grow (§4).** In `demo_local_vs_api`, split the one
   system message into three shorter system+user messages with the same total
   words. Re-run: the `Extra tokens` gap grows, because every message pays its own
   marker overhead.
3. **Change the cap (§5).** Set `max_tokens=100` in `demo_max_tokens`. Now the
   answer finishes and `finish_reason` flips to `'stop'`. Set it to `1` and you
   get a single token. You're steering the length directly.
4. **Prove digits are chunks (§2).** Add `"128"`, `"1280"`, `"12800"` to the
   samples. Watch how the *same digits* regroup into different token chunks — a
   peek at why models miscount.
5. **See a real byte-fragment (§2).** Add another flag like `"🇮🇳"` or a rare
   script like `"ℵ∇∂"`. More `�` fragments — the raw-bytes fallback, live.

---

## What you now know

- The model reads and writes **tokens** (integers), never raw text. A
  **tokenizer** converts both ways with a fixed dictionary.
- A token is a **common chunk**, not a word or a letter. Common words = 1 token;
  rare words, accents, digits, emoji, and other languages cost more.
- Tokens come from **byte-pair encoding**: start from 256 bytes, merge the most
  frequent pairs ~200k times. Common = merged into big cheap tokens; rare = left
  as small/byte tokens (that's why `🇯🇵` printed as `�` fragments).
- English averages **~4 characters per token** — a planning guess; count when it
  matters.
- The API bills **content tokens + per-message marker tokens** (the p0001 role
  structure, now with a price tag).
- Output is **autoregressive** (one token at a time); `finish_reason` tells you if
  it **`stop`**ped naturally or was cut off by **`length`**; `max_tokens` caps
  cost and enables streaming.
- A chat's token count **grows every turn** because history is re-sent. That drives
  **cost** and the **context-window wall** — the root of every later memory lesson.

*(Kotlin footnote, only if it helps: think of the tokenizer as a fixed
`Map<String, Int>` and its reverse `Map<Int, String>`, built once at model
creation. `enc.encode(text)` is the forward lookup, `enc.decode(ids)` the reverse.
There's no JVM equivalent you already use — tokenization is specific to LLMs — but
the mental shape is just two lookup tables plus the BPE merge rules that built
them.)*

**Next lesson — `p0003`: the system prompt.** You now know a prompt is a list of
role-tagged messages (p0001) counted in tokens (p0002). p0003 zooms into the most
powerful item in that list: the **`system`** message. We'll send the *same* user
question under different system prompts and watch the answer transform — your main
control surface, proven live.
