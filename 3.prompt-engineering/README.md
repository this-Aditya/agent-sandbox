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
| 4 | Structure & examples (delimiters + few-shot) | [`p0004_structure_examples.py`](p0004_structure_examples.py) | [`docs/p0004_structure_examples.md`](docs/p0004_structure_examples.md) | Mark your **data** so the model can't mistake it for **instructions** (XML tags / markdown), then **show** the task with examples. Few-shot = pattern-completion. |
| 5 | Reliable answers (chain-of-thought + temperature) | [`p0005_reliable_answers.py`](p0005_reliable_answers.py) | [`docs/p0005_reliable_answers.md`](docs/p0005_reliable_answers.md) | Ask it to **reason before answering** for hard questions (it computes in the tokens it writes), and control randomness with **temperature** (0 for extraction, higher for creativity). |
| 6 | Typed output → Pydantic (+ the build) | [`p0006_typed_output.py`](p0006_typed_output.py) | [`docs/p0006_typed_output.md`](docs/p0006_typed_output.md) | Force JSON that fits a schema (`json_object` / `json_schema`), parse into typed Pydantic objects, validate. Constrained decoding. |

> Lessons 4–6 each merge two originally-planned topics — denser, not padded.

**The build:** [`prompt_lab.py`](prompt_lab.py) — the Phase 3 deliverable CLI.
```bash
uv run prompt_lab.py --classify "I love the design, but the battery dies fast."
uv run prompt_lab.py --extract  "Tim Cook met UN officials in Paris on 3 May 2024."
uv run prompt_lab.py --reason   "A bat and ball cost £1.10; the bat is £1.00 more. Ball?"
```
It ties together every lesson: system prompt (p0003), few-shot + structure (p0004),
temperature 0 + chain-of-thought (p0005), and JSON → Pydantic with a validation
retry (p0006).

**✅ Phase 3 (Prompt Engineering) complete.** Next on the roadmap: **Phase 4 —
Tool Calling (raw)** — give the model tools it can ask your code to run. Every
agent framework is built on that loop.

## Provider

Lessons call an LLM through the shared [`_llm.py`](_llm.py) helper, which speaks the
OpenAI SDK to any of four backends and auto-picks the best available:
**RADAR `qwen3-30b`** (default — unlimited, no VPN) → KCL ARC-AI → Google Gemini →
GitHub Models. Force one with `LLM_PROVIDER=radar|arc|gemini|github` in `.env`.
Keys live in the gitignored `.env`. (p0001–p0005 output was captured on GitHub
Models `gpt-4o-mini`; p0006 on RADAR — concepts are identical.)

## Environment

- Python **3.14** (see `.python-version`), managed by [`uv`](https://docs.astral.sh/uv/).
- Deps: `openai` (the client), `pydantic` (typed parsing), `python-dotenv` (load
  the token), `tiktoken` (see tokenization offline, from p0002). Added with `uv add`.
- `uv run <file>` runs a file inside this project's `.venv` automatically.
