"""
Role-based LLM invocation.

Each function represents a named role in the multi-agent pipeline.
Nodes import from here — never from providers.py or SDKs directly.

Role → Provider → Model mapping:
  architect  → Gemini  → GEMINI_ARCHITECT_MODEL  (default: gemini-2.5-pro)
  critic     → OpenAI  → OPENAI_CRITIC_MODEL     (default: gpt-5.4-mini)
  reviewer   → Gemini  → GEMINI_REVIEW_MODEL     (default: gemini-2.5-pro)

To swap a provider for a role, change the provider call here.
To change a model, set the corresponding env var.
"""
import os
from orchestrator.llm.providers import gemini_generate, openai_generate


def invoke_architect(prompt: str) -> str:
    """
    Lead Architect role — generates architecture and task plans.
    Provider: Google Gemini Pro
    """
    model = os.environ.get("GEMINI_ARCHITECT_MODEL", "gemini-2.5-pro")
    return gemini_generate(prompt, model)


def invoke_critic(prompt: str) -> str:
    """
    Critic role — reviews architecture plans for gaps and risks before build.
    Provider: OpenAI (default: gpt-5.4-mini; override via OPENAI_CRITIC_MODEL)
    """
    model = os.environ.get("OPENAI_CRITIC_MODEL", "gpt-5.4-mini")
    return openai_generate(prompt, model)


def invoke_reviewer(prompt: str) -> str:
    """
    Code Reviewer role — evaluates builder output against task requirements.
    Provider: Google Gemini Pro
    """
    model = os.environ.get("GEMINI_REVIEW_MODEL", "gemini-2.5-pro")
    return gemini_generate(prompt, model)
