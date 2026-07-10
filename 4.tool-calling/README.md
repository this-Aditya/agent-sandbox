# Phase 4 — Tool Calling (raw)

**The most important phase on the path.** Every framework you touch later —
LangChain's `@tool`, LangGraph's `ToolNode`, MCP servers — is built on this one
primitive. If you understand it raw, those abstractions are obvious. If you don't,
they will confuse you. So here we build it with **no frameworks**, from the root.

The root idea: an LLM is only a **text function** — it cannot know the time, read
your database, or call an API. *Tool calling* is a fixed 4-step protocol that lets
the model **ask your code** to do something, and your code does it:

1. **You describe tools** to the model (name, description, parameter schema).
2. **The model decides** and asks for one (`finish_reason == "tool_calls"`).
3. **You execute** the real function.
4. **You return the result**; call the model again. It continues, or answers.

## How to use this

For each lesson `pNNNN`:

1. **Run the code** and read the output:
   ```bash
   uv run pNNNN_topic.py
   ```
2. **Read the doc** in `docs/pNNNN_topic.md` — it explains *why* each block
   behaves the way it does, section-for-section with the code.
3. **Break it.** Every doc ends with experiments. Edit a line, re-run, watch the
   behavior change. That loop is where understanding actually happens.

## Lessons

Built root → leaf: first *build the dance by hand* (no API), then the real API,
then the full robust agent loop.

| # | Topic | Code | Doc | The one idea |
|---|-------|------|-----|--------------|
| 1 | Tool calling, by hand | [`p0001_tools_by_hand.py`](p0001_tools_by_hand.py) | [`docs/p0001_tools_by_hand.md`](docs/p0001_tools_by_hand.md) | There is no magic: a "tool call" is the model **writing a text request**; your code runs the function and feeds the result back. Built with just a prompt. |
| 2 | The real `tools=` API | [`p0002_tools_api.py`](p0002_tools_api.py) | [`docs/p0002_tools_api.md`](docs/p0002_tools_api.md) | The provider formalizes the same 4 steps: `finish_reason == "tool_calls"`, a structured `tool_calls` array (`id`, name, `arguments`-as-string), and a `role:"tool"` reply matched by `tool_call_id`. |
| 3 | The agent loop (capstone) | [`p0003_agent_loop.py`](p0003_agent_loop.py) | [`docs/p0003_agent_loop.md`](docs/p0003_agent_loop.md) | An agent = a bounded `while`-loop around the 4 steps: registry dispatcher that **contains errors**, **parallel** calls in one round, **multi-step** chains across rounds, a **max-iterations cap**. Doc also covers Anthropic's `tool_use` shape + client-vs-server tools. *(the build)* |

> Lesson 3 merges two originally-planned topics (the loop + making it robust) into
> one dense capstone — the loop *is* where error handling belongs.

**Side demos (not numbered lessons):**
- [`demo_mcp_broker.py`](demo_mcp_broker.py) — answers "is `tools=` the same as
  MCP?" by showing your app broker between a fake MCP server (`tools/list` +
  `tools/call`) and the LLM (`tools=`). `uv run demo_mcp_broker.py`.
- [`demo_parallel_tools.py`](demo_parallel_tools.py) — answers "should parallel
  tool_calls run concurrently?" Times a slow (I/O) tool run sequentially vs in a
  thread pool: **3.01s → 1.01s** (3×). Concurrency overlaps *waiting*, not work,
  and this is why `p0003`'s loop runs calls concurrently. `uv run demo_parallel_tools.py`.
- [`demo_async_agent.py`](demo_async_agent.py) — the **real-world async shape** of
  the p0003 loop: `AsyncOpenAI` + `async def` tools + `asyncio.gather` (no threads).
  Two 1s tools finish in ~1.0s. p0003 uses threads only because its stack is sync;
  production agents are async-native. `uv run demo_async_agent.py`.

**✅ Phase 4 (Tool Calling) complete.** Next on the roadmap: **Phase 5 —
LangChain** — rebuild this same agent in ~20 lines with `create_agent` + `@tool`,
pointed at GitHub Models. Because you built the loop by hand, the framework will
read as labeled convenience, not magic.

## Setup (one time)

Lessons call a real model through the shared [`_llm.py`](_llm.py) helper (OpenAI
SDK). Keys live in a gitignored `.env` next to the lessons.

**This phase forces `LLM_PROVIDER=github`.** Tool calling needs a backend whose
server actually parses tool calls. RADAR's `qwen3-30b` (the default in other
phases) runs on a vLLM started *without* `--enable-auto-tool-choice`, so any
request with `tools=` returns HTTP 400. GitHub Models `openai/gpt-4o-mini`
supports full tool calling — including **parallel** tool calls — so we use it
here. (Google Gemini also works if you set `AGENTIC_AI_LEARNING_GEMINI_KEY` and
`LLM_PROVIDER=gemini`.)

## Environment

- Python **3.14** (see `.python-version`), managed by [`uv`](https://docs.astral.sh/uv/).
- Deps: `openai` (the client), `pydantic` (typed args, later lessons),
  `python-dotenv` (load the key). Added with `uv add`.
- `uv run <file>` runs a file inside this project's `.venv` automatically — you
  never activate anything by hand.
