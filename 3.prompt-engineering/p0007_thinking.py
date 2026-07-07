"""
p0007 — see the <think> block, and the show_thinking switch in _llm.ask().

Run me:
    uv run p0007_thinking.py
"""

from _llm import PROVIDER, MODEL, build_client, ask, _THINK_RE

client = build_client()
print(f"(provider={PROVIDER}, model={MODEL})\n")

# 1) The switch on the REAL model. This qwen3-30b endpoint answers directly
#    (no <think> tags), so both lines look the same here.
q = [{"role": "user", "content": "What is the capital of France? One short sentence."}]
print("show_thinking=False:", repr(ask(client, q)))
print("show_thinking=True :", repr(ask(client, q, show_thinking=True)))

# 2) What a THINKING model's raw reply looks like, and what the switch does to it.
sample = ("<think>User asks for a capital. France's capital is Paris. "
          "Keep it to one sentence.</think>The capital of France is Paris.")
print("\nraw reply from a thinking model:")
print("   ", repr(sample))
print("show_thinking=True  (kept)   :", repr(sample.strip()))
print("show_thinking=False (stripped):", repr(_THINK_RE.sub("", sample).strip()))
