"""
p0002 — Tokens: the unit the model reads, and the unit you pay for.

Run me:
    uv run p0002_tokens.py

Read me with the doc open next to you:
    docs/p0002_tokens.md

In p0001 you saw "prompt=14, reply=3" flash by. This lesson slows that down.
The model does NOT read letters or words. It reads TOKENS — integers. A tool
called a "tokenizer" chops your text into tokens before the model ever sees it.
Everything about cost, speed, and the context-window wall is measured in tokens.
We make all of it visible:

    1. Text becomes TOKENS (integers), and back again.        (the core reveal)
    2. A token is not a word and not a character.             (the surprises)
    3. The rule of thumb: ~4 characters per token.            (planning number)
    4. Your local token count vs the API's own count.        (proves p0001)
    5. Output is built one token at a time; max_tokens caps it. (the cutoff)
    6. Why tokens bite: a chat's cost climbs every single turn. (the payoff)

The one sentence to hold onto:
    The model reads and writes TOKENS, not text. Tokens are the ruler for cost,
    latency, and the context window. When an LLM feels slow or expensive, the
    answer is almost always "too many tokens."
"""

import os
from pathlib import Path

import tiktoken
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(Path(__file__).with_name(".env"))

MODEL = "openai/gpt-4o-mini"

# gpt-4o and gpt-4o-mini read text using the "o200k_base" token vocabulary.
# We load that exact vocabulary so our local counts match what the model uses.
ENC = tiktoken.get_encoding("o200k_base")


def section(title: str) -> None:
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def build_client() -> OpenAI:
    token = os.environ.get("AGENTIC_AI_LEARNING_GH_TOKEN")
    if not token:
        raise SystemExit(
            "AGENTIC_AI_LEARNING_GH_TOKEN is not set.\n"
            "Put it in the .env file next to this script (see the .env template)."
        )
    return OpenAI(base_url="https://models.github.ai/inference", api_key=token)


# ===========================================================================
# 1. TEXT BECOMES TOKENS (integers), AND BACK AGAIN.
#    A tokenizer is a two-way dictionary: text <-> a list of integer IDs.
#    The neural network only ever sees the integers.
# ===========================================================================
def demo_text_to_tokens() -> None:
    section("1. The model reads TOKENS (integers), not letters")

    text = "Prompt engineering is fun!"
    ids = ENC.encode(text)                      # text  -> list of integer IDs

    print(f"Your text:     {text!r}")
    print(f"As token IDs:  {ids}")
    print(f"That is {len(ids)} tokens. The neural network ONLY ever sees these integers.")

    print("\nEach integer maps back to a piece of text. Split apart:")
    for i in ids:
        print(f"    {i:>7}  ->  {ENC.decode([i])!r}")

    back = ENC.decode(ids)                       # list of IDs -> text
    print(f"\nDecode the integers back:  {back!r}")
    print("  Round trip: text -> integers -> text. The tokenizer is a fixed 2-way")
    print("  dictionary, learned once when the model was built. It never changes.")


# ===========================================================================
# 2. A TOKEN IS NOT A WORD, AND NOT A CHARACTER.
#    Common words are one token. Rare/long words split into pieces. A leading
#    space is part of the token. Digits and emoji cost several tokens.
# ===========================================================================
def demo_token_boundaries() -> None:
    section("2. A token is not a word, and not a character")

    samples = [
        "cat",
        "cats",
        " cat",                              # note the leading space
        "tokenization",
        "Reinforcement",
        "naïve",                             # a non-English letter (ï)
        "1234567890",
        "🙂",                                # a common emoji
        "🇯🇵",                                # a flag (compound) emoji
    ]
    for s in samples:
        ids = ENC.encode(s)
        pieces = [ENC.decode([i]) for i in ids]
        print(f"  {s!r:>16}  ->  {len(ids)} token(s): {pieces}")

    print("\n  Read the surprises:")
    print("   - 'cat' and 'cats' are BOTH single tokens — but different ones. Common")
    print("     words, even plurals, each earn their own token.")
    print("   - ' cat' (leading space) differs from 'cat': a space rides WITH the")
    print("     token after it. This is why gluing words together changes the count.")
    print("   - longer/rarer words ('tokenization', 'Reinforcement') break into")
    print("     word-pieces; 'naïve' splits because 'ï' is not a plain ASCII letter.")
    print("   - digits chunk (often 3 at a time).")
    print("   - '🙂' is common enough to be ONE clean token, but '🇯🇵' becomes 4 tokens")
    print("     that print as '�' — proof a token can be a fragment of raw BYTES, not")
    print("     a letter. (More on why in the doc.)")


# ===========================================================================
# 3. THE RULE OF THUMB: ~4 CHARACTERS PER TOKEN (for English).
# ===========================================================================
def demo_ratio() -> None:
    section("3. The planning rule of thumb: ~4 characters per token")

    paragraph = (
        "Large language models read text as tokens. A token is a chunk of "
        "characters. On average an English token is about four characters, but "
        "it depends heavily on the exact words you use."
    )
    ids = ENC.encode(paragraph)
    chars = len(paragraph)

    print(f"Characters: {chars}")
    print(f"Tokens:     {len(ids)}")
    print(f"Ratio:      {chars / len(ids):.2f} characters per token")
    print("\n  ~4 chars/token is a PLANNING guess, not a law. Code, JSON, other")
    print("  languages, and rare words push it around. To estimate cost or whether")
    print("  something fits the context window, estimate the token count.")


# ===========================================================================
# 4. LOCAL COUNT vs THE API'S OWN COUNT — proves the role markers from p0001.
# ===========================================================================
def demo_local_vs_api(client: OpenAI) -> None:
    section("4. Your local count vs the API's own count")

    messages = [
        {"role": "system", "content": "You are a terse assistant. One short sentence."},
        {"role": "user", "content": "What is the capital of Japan?"},
    ]

    content_tokens = sum(len(ENC.encode(m["content"])) for m in messages)
    print(f"Tokens in just the CONTENT text of the 2 messages: {content_tokens}")

    resp = client.chat.completions.create(
        model=MODEL, messages=messages, temperature=0, max_tokens=20
    )
    api_prompt_tokens = resp.usage.prompt_tokens
    print(f"Tokens the API says the PROMPT cost:               {api_prompt_tokens}")
    print(f"Extra tokens the API counted:                      {api_prompt_tokens - content_tokens}")

    print("\n  The API always counts a bit MORE than the raw content. Remember p0001:")
    print("  before the model sees your list, the server wraps each message in role")
    print("  markers (<|system|>, <|user|>, ...). Those markers are real tokens.")
    print("  The extra count you see IS that structure. Your true prompt size =")
    print("  the content tokens PLUS the per-message formatting overhead.")


# ===========================================================================
# 5. OUTPUT IS BUILT ONE TOKEN AT A TIME — and max_tokens caps it.
# ===========================================================================
def demo_max_tokens(client: OpenAI) -> None:
    section("5. Output is built one token at a time — max_tokens caps it")

    messages = [{"role": "user",
                 "content": "List three fruits and describe each in a full sentence."}]

    resp = client.chat.completions.create(
        model=MODEL, messages=messages, temperature=0, max_tokens=6
    )
    choice = resp.choices[0]
    print("We asked for a long answer but set max_tokens=6:")
    print(f"    reply:         {choice.message.content!r}")
    print(f"    finish_reason: {choice.finish_reason!r}")
    print(f"    output tokens: {resp.usage.completion_tokens}")

    print("\n  The reply is chopped mid-thought, and finish_reason is 'length' — the")
    print("  model was CUT OFF at the cap, not finished ('stop' would mean finished).")
    print("  Why can it stop cleanly at 6? Because it builds the answer one token at")
    print("  a time: make a token, feed it back in, make the next. max_tokens just")
    print("  says 'stop after this many'. That same one-at-a-time process is what")
    print("  lets an answer be STREAMED to you token by token as it is made.")


# ===========================================================================
# 6. WHY TOKENS BITE: a chat's cost climbs every single turn.
#    Callback to p0001 §5 — memory is re-sending the list, and the list grows.
# ===========================================================================
def demo_why_it_bites() -> None:
    section("6. Why tokens bite: a chat's cost climbs every turn")

    turns = [
        "Hi, I'm planning a trip to Japan.",
        "What should I see in Tokyo?",
        "How many days do I need there?",
        "What food must I try?",
        "And the best time of year to go?",
    ]
    # A fixed-size stand-in for each assistant reply, so we can watch growth.
    fake_reply = "Here are some suggestions based on what you asked about. " * 2

    convo: list[dict] = []
    print("Every turn RESENDS the whole history (p0001 §5). Count the tokens you")
    print("send at each turn — the list only grows:")
    for n, user_text in enumerate(turns, start=1):
        convo.append({"role": "user", "content": user_text})
        total = sum(len(ENC.encode(m["content"])) for m in convo)
        print(f"    turn {n}: the list you send is now ~{total} tokens")
        convo.append({"role": "assistant", "content": fake_reply})

    print("\n  It never shrinks on its own. So each turn costs MORE than the last —")
    print("  you pay to re-read the entire past every single call. Two hard limits:")
    print("   - COST: price is per token, so a long chat gets pricier turn by turn.")
    print("   - CONTEXT WINDOW: every model has a max tokens it can read at once")
    print("     (tens to hundreds of thousands). Past that, old turns must be")
    print("     dropped or summarized — they stop existing for the model.")

    # Illustrative cost feel. GitHub Models is free; these are made-up unit prices
    # only to build intuition about the shape of the math.
    price_per_million_in = 0.15    # illustrative $ per 1,000,000 input tokens
    tokens = 100_000
    cost = tokens / 1_000_000 * price_per_million_in
    print("\n  Rough cost feel (illustrative price; on GitHub Models you pay $0):")
    print(f"    {tokens:,} input tokens at ${price_per_million_in}/1M  ≈  ${cost:.4f}")
    print("    Cheap once — but an agent can send that on EVERY step of EVERY")
    print("    request. Tokens are the one number you watch to keep cost and speed sane.")


def main() -> None:
    # Sections 1–3 and 6 are pure local tokenizer work — no network.
    demo_text_to_tokens()
    demo_token_boundaries()
    demo_ratio()

    # Sections 4–5 make real calls to read the API's token counts.
    client = build_client()
    demo_local_vs_api(client)
    demo_max_tokens(client)

    demo_why_it_bites()

    print("\n" + "=" * 70)
    print("Done. Open docs/p0002_tokens.md — it explains each step from zero.")
    print("=" * 70)


if __name__ == "__main__":
    main()
