"""
prompt_lab.py — the Phase 3 build.

A small CLI that turns text into TYPED data using an LLM. Three commands:

    uv run prompt_lab.py --classify "I love the design, but the battery dies fast."
    uv run prompt_lab.py --extract  "Tim Cook met UN officials in Paris on 3 May 2024."
    uv run prompt_lab.py --reason   "A bat and ball cost £1.10; the bat is £1.00 more. Ball?"

It uses everything from Phase 3:
  - a clear system prompt (p0003)
  - a stated JSON shape / structure (p0004)
  - temperature 0 for classify/extract, so the answer is stable (p0005)
  - chain-of-thought for --reason (p0005)
  - JSON forced by the API and parsed into a typed Pydantic object (p0006)

Every command validates the model's JSON against a Pydantic model, and retries
once if the model returns something off-shape.
"""

import argparse
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from _llm import MODEL, PROVIDER, build_client


# --- the shapes we want back (Pydantic models) ------------------------------
class Sentiment(BaseModel):
    label: Literal["positive", "negative", "neutral"]
    confidence: float = Field(ge=0, le=1)


class Entities(BaseModel):
    people: list[str] = []
    organizations: list[str] = []
    dates: list[str] = []


class Reasoning(BaseModel):
    reasoning: str          # the step-by-step thinking
    answer: str             # the final answer, on its own


client = build_client()


def ask_typed(model_cls: type[BaseModel], system: str, user: str,
              temperature: float = 0.0) -> BaseModel:
    """Call the model, force JSON, and parse it into model_cls. Retry once."""
    messages = [{"role": "system", "content": system},
                {"role": "user", "content": user}]
    last_error = None
    for _ in range(2):
        resp = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            temperature=temperature,
            max_tokens=800,
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content or ""
        try:
            return model_cls.model_validate_json(raw)
        except ValidationError as e:
            # Feed the error back and ask the model to fix its JSON.
            last_error = e
            messages.append({"role": "assistant", "content": raw})
            messages.append({"role": "user",
                             "content": f"That JSON was invalid: {e.errors()[0]['msg']}. "
                                        f"Return corrected JSON only."})
    raise SystemExit(f"Model kept returning invalid JSON:\n{last_error}")


def classify(text: str) -> None:
    system = ("You classify the sentiment of the user's message. Return a JSON object "
              "with keys: label (one of positive, negative, neutral) and confidence "
              "(a number from 0 to 1). Examples:\n"
              'Message: "This is wonderful!" -> {"label":"positive","confidence":0.98}\n'
              'Message: "It broke on day one." -> {"label":"negative","confidence":0.95}')
    s: Sentiment = ask_typed(Sentiment, system, text)
    print(f"label      : {s.label}")
    print(f"confidence : {s.confidence}")


def extract(text: str) -> None:
    system = ("Extract named entities from the user's text. Return a JSON object with "
              "keys: people (list of person names), organizations (list of org names), "
              "dates (list of dates as written). Use an empty list if a category has none.")
    e: Entities = ask_typed(Entities, system, text)
    print(f"people        : {e.people}")
    print(f"organizations : {e.organizations}")
    print(f"dates         : {e.dates}")


def reason(question: str) -> None:
    system = ("Answer the user's question. First think step by step, then give the "
              "final answer. Return a JSON object with keys: reasoning (your full "
              "step-by-step thinking, as one string) and answer (the final answer only).")
    r: Reasoning = ask_typed(Reasoning, system, question)
    print("--- reasoning ---")
    print(r.reasoning)
    print("\n--- answer ---")
    print(r.answer)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prompt-lab: turn text into typed data with an LLM.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--classify", metavar="TEXT", help="sentiment + confidence")
    group.add_argument("--extract", metavar="TEXT", help="people / orgs / dates")
    group.add_argument("--reason", metavar="QUESTION", help="chain-of-thought answer")
    args = parser.parse_args()

    print(f"(backend: provider={PROVIDER}, model={MODEL})\n")
    if args.classify is not None:
        classify(args.classify)
    elif args.extract is not None:
        extract(args.extract)
    elif args.reason is not None:
        reason(args.reason)


if __name__ == "__main__":
    main()
