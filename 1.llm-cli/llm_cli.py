"""
A tiny command-line chat tool that talks to an LLM via GitHub Models.

Two ways to use it once installed:

    llm                          -> interactive chat (type questions, it replies)
    llm --prompt "Summarize ..." -> ask one question, print the answer, exit

It needs an environment variable AGENTIC_AI_LEARNING_GH_TOKEN holding your
GitHub token, because that token proves to GitHub Models you're allowed to call it.
"""

import os
import argparse

from openai import OpenAI


def build_client() -> OpenAI:
    token = os.environ.get("AGENTIC_AI_LEARNING_GH_TOKEN")
    if not token:
        raise SystemExit(
            "AGENTIC_AI_LEARNING_GH_TOKEN is not set.\n"
            "Set it first, e.g.:  export AGENTIC_AI_LEARNING_GH_TOKEN=ghp_your_token_here"
        )
    # GitHub Models speaks the OpenAI API "shape", so we use the OpenAI SDK
    # but point it at GitHub's address and give it our token.
    return OpenAI(
        base_url="https://models.github.ai/inference",
        api_key=token,
    )


def ask(client: OpenAI, messages: list) -> str:
    """Send the whole conversation so far and return the model's reply text."""
    response = client.chat.completions.create(
        model="openai/gpt-4o-mini",
        messages=messages,            # the conversation: each item has a role + content
        temperature=0.2,              # low = focused/consistent; higher = more creative
    )
    return response.choices[0].message.content


def main() -> None:
    parser = argparse.ArgumentParser(description="Chat with an LLM from your terminal.")
    parser.add_argument(
        "--prompt",
        help="Ask a single question and exit. Omit this to start interactive chat.",
    )
    args = parser.parse_args()

    client = build_client()

    # ONE-SHOT MODE: --prompt was given, so answer once and quit.
    if args.prompt:
        print(ask(client, [{"role": "user", "content": args.prompt}]))
        return

    # INTERACTIVE MODE: no --prompt, so open a chat loop (like `claude`).
    # We keep `messages` growing so the model remembers the conversation.
    print("Chatting with gpt-4o-mini. Type 'exit' (or press Ctrl-D) to quit.")
    messages: list = []
    while True:
        try:
            user_text = input("\nYou: ")
        except EOFError:      # user pressed Ctrl-D
            print()
            break
        if user_text.strip().lower() in {"exit", "quit"}:
            break
        if not user_text.strip():
            continue          # ignore empty lines

        messages.append({"role": "user", "content": user_text})
        reply = ask(client, messages)
        messages.append({"role": "assistant", "content": reply})
        print(f"\nAI: {reply}")


if __name__ == "__main__":
    # This runs main() only when the file is executed directly,
    # e.g. `uv run llm_cli.py` during development.
    main()
