"""
p0006 — Typed output: JSON -> Pydantic. (The finale + the phase build.)

Run me:
    uv run p0006_typed_output.py

Read me with the doc open next to you:
    docs/p0006_typed_output.md

The whole phase has led here. An LLM returns TEXT, but your code wants typed
data. This lesson closes that gap: force the model to return JSON, and turn that
JSON into a typed Pydantic object (your Phase 2 skill returns). Then the phase
build (prompt_lab.py) uses it for real.

    1. Text -> JSON -> a typed Pydantic object.        (the bridge)
    2. Strict schema mode: the shape is guaranteed.    (the strongest way)
    3. Validation catches bad output.                  (your safety net)
    4. The build: prompt_lab.py (classify/extract/reason).

The one sentence to hold onto:
    Make the model reply in JSON, then let Pydantic turn that JSON into a typed,
    validated object. Now the LLM's answer is real Python data your code can
    trust — not a string you have to pick apart.
"""

import json
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from _llm import PROVIDER, MODEL, build_client


def section(title: str) -> None:
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


# A Pydantic model is the SHAPE we want back. label must be one of three values;
# confidence must be a number between 0 and 1. (Phase 2's Pydantic, put to work.)
class Sentiment(BaseModel):
    label: Literal["positive", "negative", "neutral"]
    confidence: float = Field(ge=0, le=1)


# ===========================================================================
# 1. TEXT -> JSON -> A TYPED PYDANTIC OBJECT.
# ===========================================================================
def demo_text_to_typed(client) -> None:
    section("1. Text -> JSON -> a typed Pydantic object")

    system = ("Classify the sentiment of the user's message. Return a JSON object "
              "with keys: label (one of positive, negative, neutral) and confidence "
              "(a number from 0 to 1).")
    user = "Honestly, this is the best product I have ever bought!"

    # response_format={"type":"json_object"} tells the endpoint: your reply MUST
    # be valid JSON (no prose, no ```json fences). Cleaner than hoping.
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}],
        temperature=0,
        max_tokens=200,
        response_format={"type": "json_object"},
    )
    raw = resp.choices[0].message.content
    print("The model returned this TEXT (which happens to be JSON):")
    print("   ", repr(raw))

    # ONE line turns that text into a typed object.
    s = Sentiment.model_validate_json(raw)
    print("\nParsed into a Sentiment object — a real typed Python value:")
    print(f"    type(s)      = {type(s).__name__}")
    print(f"    s.label      = {s.label!r}   (a str, one of the 3 allowed)")
    print(f"    s.confidence = {s.confidence}   (a float, not a piece of a string)")

    print("\n  This is the whole phase in one move. p0005 pulled ONE value out of text")
    print("  with a fragile regex. Here the WHOLE reply is JSON, and model_validate_json")
    print("  turns it into a typed object your code can trust — s.confidence * 100 just")
    print("  works, because it is a real float.")


# ===========================================================================
# 2. STRICT SCHEMA MODE: THE SHAPE IS GUARANTEED.
# ===========================================================================
def demo_strict_schema(client) -> None:
    section("2. Strict schema mode: the shape is guaranteed")

    schema = Sentiment.model_json_schema()
    print("Pydantic can hand its schema straight to the model:")
    print("   ", json.dumps(schema))

    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "system", "content": "Classify the sentiment."},
                  {"role": "user", "content": "It's fine, nothing special."}],
        temperature=0,
        max_tokens=200,
        response_format={"type": "json_schema",
                         "json_schema": {"name": "Sentiment", "schema": schema}},
    )
    raw = resp.choices[0].message.content
    print("\nWith response_format=json_schema, the reply is forced to fit that shape:")
    print("   ", repr(raw))
    s = Sentiment.model_validate_json(raw)
    print(f"    parsed: label={s.label!r}, confidence={s.confidence}")

    print("\n  Two levels of 'give me JSON':")
    print("    json_object  -> guarantees the reply is VALID json (any shape).")
    print("    json_schema  -> guarantees json that fits YOUR exact shape.")
    print("  qwen3-30b supports both. json_schema is strongest: the wrong shape is")
    print("  not just discouraged, it is impossible to generate.")


# ===========================================================================
# 3. VALIDATION CATCHES BAD OUTPUT (no model call — pure Pydantic).
# ===========================================================================
def demo_validation_safety() -> None:
    section("3. Pydantic validation catches bad output (your safety net)")

    good = '{"label": "positive", "confidence": 0.9}'
    print("Good JSON parses into a clean object:")
    print("   ", Sentiment.model_validate_json(good))

    bad_cases = [
        ("confidence is text", '{"label": "positive", "confidence": "very high"}'),
        ("confidence out of 0..1", '{"label": "positive", "confidence": 5}'),
        ("label not allowed", '{"label": "amazing", "confidence": 0.9}'),
    ]
    print("\nBad JSON is REFUSED, with a clear reason:")
    for name, bad in bad_cases:
        try:
            Sentiment.model_validate_json(bad)
            print(f"  {name}: (unexpectedly accepted!)")
        except ValidationError as e:
            print(f"  REJECTED — {name}: {e.errors()[0]['msg']}")

    print("\n  No model call here — pure Pydantic. The point: even if the model")
    print("  returns something wrong, your schema refuses it instead of letting bad")
    print("  data into your program. In production you catch this error and retry.")
    print("  The Literal labels and the 0..1 range ARE your guardrail.")


# ===========================================================================
# 4. THE PHASE BUILD.
# ===========================================================================
def demo_the_build() -> None:
    section("4. The phase build: prompt_lab.py")

    print("  Everything above ships in prompt_lab.py — a CLI with three commands:")
    print()
    print('    uv run prompt_lab.py --classify "I love the design, but the battery dies fast."')
    print('    uv run prompt_lab.py --extract  "Tim Cook met UN officials in Paris on 3 May 2024."')
    print('    uv run prompt_lab.py --reason   "A bat and ball cost £1.10; the bat is £1.00 more. Ball?"')
    print()
    print("    --classify -> Sentiment(label, confidence)   [temp 0, JSON]")
    print("    --extract  -> Entities(people, orgs, dates)   [temp 0, JSON]")
    print("    --reason   -> Reasoning(reasoning, answer)     [chain-of-thought, JSON]")
    print()
    print("  Each forces JSON and parses it into a typed Pydantic object, using every")
    print("  technique from p0001-p0005. See docs/p0006_typed_output.md for real runs.")


def main() -> None:
    print(f"(backend: provider={PROVIDER}, model={MODEL})")
    client = build_client()
    demo_text_to_typed(client)
    demo_strict_schema(client)
    demo_validation_safety()
    demo_the_build()

    print("\n" + "=" * 70)
    print("Done. Open docs/p0006_typed_output.md — it explains each step from zero.")
    print("=" * 70)


if __name__ == "__main__":
    main()
