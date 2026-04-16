"""
Low-level LLM provider functions.

Each function wraps a single SDK call. Nodes never import SDKs directly —
they use orchestrator/llm/roles.py instead. This isolates SDK specifics here
so that swapping a provider only requires changing this file.
"""
import os


def gemini_generate(prompt: str, model: str) -> str:
    """Call Google Gemini with a text prompt. Returns the response text."""
    from google import genai  # deferred: not loaded unless Gemini is used

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY is not set. Add it to your environment or .env file."
        )
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(model=model, contents=prompt)
    return response.text


def openai_generate(prompt: str, model: str) -> str:
    """Call OpenAI chat completions with a text prompt. Returns the response text."""
    from openai import OpenAI  # deferred: not loaded unless OpenAI is used

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY is not set. Add it to your environment or .env file."
        )
    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content or ""
