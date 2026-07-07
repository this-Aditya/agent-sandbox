# p0005 — Reliable answers: chain-of-thought + temperature

> **Run the code first, then read this.** `uv run p0005_reliable_answers.py`
> Each part matches a numbered block in `p0005_reliable_answers.py`.
> Builds on p0002 (tokens) especially. Output captured from GitHub Models
> `gpt-4o-mini`; wording varies by model, the mechanism does not.

*(This lesson merges two originally-separate topics — chain-of-thought and
temperature — because both answer one question: how do I make the answer correct
and repeatable? It makes only ~7 model calls; no loops.)*

---

## The one idea

Two dials control answer quality:

> **Chain-of-thought:** give the model room to *reason in the tokens it writes*
> before it commits to an answer. It computes as it writes, so reasoning first
> makes hard answers correct.
>
> **Temperature:** a number that sets how random the model's word choice is. `0` =
> always the most likely word (repeatable); higher = sometimes a less likely word
> (varied).

Four proofs:

1. A rushed answer is wrong; "think step by step" fixes it.
2. Reason for accuracy, but parse only the final answer with a marker.
3. Same prompt: temperature 0 repeats, high temperature varies.
4. The rule for when to use each temperature.

---

## 1. A rushed answer is wrong; "think step by step" fixes it

We ask the model to count the letter `r` in `"strawberry raspberry"` (real answer:
**6**). Two ways.

**[A] Rushed** — "reply with only the number":

```text
[A] RUSHED ('reply with only the number'):
      4
```

Wrong. Now **[B] reasoned** — "think step by step, spell it out, then count":

```text
[B] REASONED ('think step by step'):
      1. **strawberry**:
         - s
         - t
         - r (mark)
         ... r (mark) ... r (mark) ...
         In "strawberry", the letter 'r' appears **3 times**.
      2. **raspberry**:
         - r (mark) ... r (mark) ... r (mark) ...
         In "raspberry", the letter 'r' appears **3 times**.
      Total count of 'r': 3 + 3 = **6**.
```

Correct. Same model, same question, seconds apart. The only difference is that we
let it **write out its reasoning** before answering.

### Why does writing the reasoning make it correct? (the real mechanism)

This is the important part, and it has two layers.

**Layer 1 — general: the model computes *in* the tokens it writes.** Recall p0001:
the model produces its answer one token at a time, and each token it writes gets
fed back in to help produce the next one. So the tokens it writes are not just the
answer — they are also its **scratch paper**. When you force an answer in a single
token ("reply with only the number"), the model has to do all the work in one
forward pass, with no scratch space. Hard problems need several steps; there is no
room. When you let it write the steps, each step becomes input for the next step —
it literally has more compute to reach the answer. **Reasoning tokens are a
compute budget.** More room to think → better answers on anything multi-step.

**Layer 2 — this specific case: counting letters is extra hard (p0002).** The
model reads **tokens**, not letters. `"strawberry"` might be one or two tokens —
the individual `r`'s are *hidden inside* a token the model can't split apart just
by looking. That is why the rushed answer (`4`) was wrong: it was guessing at
something it can't directly see. Forcing it to **spell the word out** creates a
new token for each letter (`s`, `t`, `r`, …), and *now* the `r`'s are visible
tokens it can actually count. This is a perfect example of p0002 biting, and CoT
fixing it.

> Rule: whenever a task needs more than one step — math, logic, counting, careful
> comparison — ask for the reasoning first. Do **not** ask for a bare answer on a
> hard question.

---

## 2. Reason for accuracy, but parse only the final answer

Reasoning makes the model accurate — but now the reply is a paragraph, and your
code just wants the number. The fix: make it reason, then end with a **fixed
marker line** you can parse.

```text
Problem: 3 notebooks at £2.75, 2 pens at £1.40, pay with £20. How much change?

Full reply (reasoning + a marked final line):
      1. cost of notebooks = 3 × £2.75 = £8.25.
      2. cost of pens = 2 × £1.40 = £2.80.
      3. total = £8.25 + £2.80 = £11.05.
      4. change = £20.00 - £11.05 = £8.95.
      ANSWER: £8.95

  Code extracted just the final answer: '£8.95'
```

The prompt said: *"Reason step by step. Then on the very last line write exactly:
ANSWER: <amount>."* The model reasoned (and got £8.95 right), and ended with
`ANSWER: £8.95`. Then plain Python pulled out just that value:

```python
match = re.search(r"ANSWER:\s*(.+)", reply)
final = match.group(1).strip()      # -> '£8.95'
```

> **The pattern:** let the model think (for accuracy), but pin the *final* answer
> behind a marker so your code can grab it cleanly. You get both the accuracy of
> reasoning and a usable value.

This is a stepping stone. In p0006 we go further and force the *whole* reply to be
JSON that fits a schema — so you don't parse text with a regex, you get a typed
object directly. The marker here is the simple version of that idea.

---

## 3. Same prompt: temperature 0 repeats, high temperature varies

Same prompt both times: *"Write a six-word story about the sea."*

```text
temperature = 0:
  run 1:  Waves whispered secrets; the shore listened.
  run 2:  Waves whispered secrets; the shore listened.

temperature = 1.3:
  run 1:  Whispers of the deep, secrets untold.
  run 2:  Waves crashed; secrets whispered, hearts intertwined.
```

At **temp 0** the two runs are **identical**. At **temp 1.3** they are **two
different stories**. One number changed the behaviour completely.

### What temperature actually does (the mechanism)

At every step, the model does not pick one word — it produces a **score for every
possible next token** (how likely each one is). Temperature decides how you turn
those scores into an actual choice:

- **temperature = 0:** always take the **single highest-scoring token**. Same
  input → same top token → same output, every time. This is why both temp-0 runs
  matched exactly. Deterministic. (Provider note: "0" means *as repeatable as
  possible*; tiny hardware/rounding differences can still cause a rare change —
  we saw one back in p0003 — but usually it repeats, as here.)
- **higher temperature:** turn the scores into a **weighted dice roll** and sample.
  Low temp = a dice heavily loaded toward the top token (mostly repeats, small
  wobble). High temp (like 1.3) = a flatter dice, so **less-likely tokens get
  picked sometimes**. One surprising token early ("Whispers" instead of "Waves")
  sends the whole story down a different path — that's the variety you see.

So temperature is literally a **randomness knob** on the word-by-word dice. `0`
turns the dice off (pick the favourite); higher makes the dice fairer (more
surprises).

---

## 4. When to use temperature 0 vs higher (the rule)

No model calls here — just the rule that falls out of section 3.

- **Use temperature = 0** when there is a **right answer** and you want it the
  same every time:
  - **extraction** (pull fields out of text)
  - **classification** (pick a label)
  - **math / code / following a strict format**
  This is exactly why the phase build (p0006) uses temp 0 for `--classify` and
  `--extract`: you want the same, correct answer on the same input.

- **Use a higher temperature (~0.7–1.0)** when you want **variety or creativity**
  and there is no single right answer: brainstorming names, creative writing,
  offering several different options.

- **Default for backend/agent work: keep it low (0–0.3).** When code depends on
  the output, predictable beats surprising.

---

## Run it, then break it (mind your call budget — each is 1–2 calls)

1. **Make the rushed answer fail harder (§1).** Change the word to something
   longer like `"raspberry strawberry blueberry"`. The rushed count is usually
   even more wrong; the reasoned one stays right.
2. **Remove the reasoning room (§1).** In `[B]`, add `Reply with only the number.`
   to the reasoned prompt. Watch accuracy drop again — you took away its scratch
   paper.
3. **Move the marker (§2).** Change `ANSWER:` to `RESULT =` in both the prompt and
   the regex. It still works — the marker is your contract, pick any clear one.
4. **Turn the dice down (§3).** Change `temperature=1.3` to `temperature=0.3`.
   The two runs get much more similar — a lightly loaded dice. Then try `2.0` and
   watch it get strange or messy.
5. **Prove temp-0 determinism on something factual (§3).** Swap the prompt for
   `"Name one primary colour. One word."` at temp 0 twice — identical.

---

## What you now know

- The model **computes in the tokens it writes**, so **chain-of-thought** (reason
  before answering) gives it the room to get multi-step answers right (§1).
- Counting letters is a classic failure because the model sees **tokens, not
  letters** (p0002) — spelling it out fixes it (§1).
- To use CoT in code, make the model **reason then end with a marker line**
  (`ANSWER: …`) and parse just that (§2). p0006 upgrades this to typed JSON.
- **Temperature** is a randomness knob on the next-token dice: **0 = always the
  top token (repeatable)**, higher = sometimes a less-likely token (varied) (§3).
- **Rule:** temp **0** for right-answer tasks (extraction, classification, math);
  **higher** for creativity; **low by default** for backend work (§4).

*(Kotlin/Spring footnote, only if it helps: temperature is like a seed/randomness
setting on a generator. `temperature=0` is a pure function — same input, same
output — which is what you want for anything you unit-test or parse. Higher
temperature is a randomised strategy, fine for "give me options" but not for a
value your code branches on.)*

**Next lesson — `p0006`: typed output → Pydantic + the prompt-lab CLI.** This is
the payoff. We stop parsing text with regexes (the §2 marker) and instead force
the model to return **JSON that fits a schema**, parsed straight into a **Pydantic**
object (your Phase 2 skill returns). Then we ship the phase's build: a CLI with
`--classify`, `--extract`, and `--reason`, using everything from p0001–p0005 —
system prompts, structure, few-shot, chain-of-thought, and temp 0.
