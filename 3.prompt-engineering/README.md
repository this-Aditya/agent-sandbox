# Phase 3 — Prompt Engineering

A hands-on, run-it-yourself course. Each lesson is **a runnable program that
proves its own claims** plus a deep written explanation. Prompt engineering is
the highest-leverage skill on the whole path — so we go slow and from the root.

Everything here is **self-contained**: every idea is proven by code you can edit
and re-run, and explained in its doc. No jumping between outside tutorials.

## How to use this

For each lesson `pNNNN`:

1. **Run the code** and read the output:
   ```bash
   uv run pNNNN_topic.py
   ```
2. **Read the doc** in `docs/pNNNN_topic.md` — it explains *why* each block
   behaves the way it does, section-for-section with the code.
3. **Break it.** Every doc ends with experiments. Edit a line, re-run, watch the
   model's behavior change. That loop is where prompt engineering is learned.

## Setup (one time)

The lessons call a real model (GitHub Models, OpenAI-compatible). Put your token
in a gitignored `.env` file next to the lessons:

```
AGENTIC_AI_LEARNING_GH_TOKEN=your_token_here
```

`uv run` picks up the project's `.venv` automatically; the code loads `.env`
itself. You never activate or export anything by hand.

## Lessons

Built root → leaf: first *what a prompt is*, then each technique that shapes it,
then the payoff build.

| # | Topic | Code | Doc | The one idea |
|---|-------|------|-----|--------------|
| 1 | What a prompt really is | [`p0001_prompt.py`](p0001_prompt.py) | [`docs/p0001_prompt.md`](docs/p0001_prompt.md) | A prompt is a **list of role-tagged messages** serialized to JSON — not a string. The model is stateless; "memory" is you re-sending the list. |
| 2 | Tokens | [`p0002_tokens.py`](p0002_tokens.py) | [`docs/p0002_tokens.md`](docs/p0002_tokens.md) | The model reads **tokens** (integers), not letters — and you pay per token. Byte-pair encoding, the ~4-chars rule, and why a chat's cost climbs every turn. |
| 3 | Role & instructions (system prompt) | [`p0003_system_prompt.py`](p0003_system_prompt.py) | [`docs/p0003_system_prompt.md`](docs/p0003_system_prompt.md) | Same question + different `system` message → different answer. The honest truth about system-vs-user, guardrails, persistence, and weak-vs-strong prompts. |
| 4 | Delimiters & structure | _next_ | | Separate **instructions** from **data**. Why XML tags suit Claude, markdown suits GPT. |
| 5 | Few-shot examples | _planned_ | | Show, don't tell — 2–3 examples lock the output format. |
| 6 | Chain-of-thought | _planned_ | | Ask it to reason **before** answering → it gets hard questions right. |
| 7 | Temperature | _planned_ | | Same prompt ×5: temp 0 = identical, temp 1 = varied. When to use which. |
| 8 | Structured output → Pydantic | _planned_ | | Force JSON that fits a schema; parse straight into typed Python objects. |
| 9 | Build: the prompt-lab CLI | _planned_ | | Assemble it all: `--classify`, `--extract`, `--reason`. The phase deliverable. |

## Environment

- Python **3.14** (see `.python-version`), managed by [`uv`](https://docs.astral.sh/uv/).
- Deps: `openai` (the client), `pydantic` (typed parsing), `python-dotenv` (load
  the token), `tiktoken` (see tokenization offline, from p0002). Added with `uv add`.
- `uv run <file>` runs a file inside this project's `.venv` automatically.
