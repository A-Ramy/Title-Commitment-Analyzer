"""Calls to Claude. One shape for every step: the cached system prompt, the documents (cached), then the step's
task, answered as JSON that matches a Pydantic model (structured outputs).

Streaming keeps long reviews clear of HTTP timeouts; the server-side fallback re-runs a declined request on
Anthropic's recommended model instead of returning nothing.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from typing import Protocol, TypeVar

from pydantic import BaseModel

from titleagent.config import EFFORT, MODEL

T = TypeVar("T", bound=BaseModel)

# $ per million tokens for the default model (Claude Opus 5.5)
PRICE = {"input": 4.00, "output": 20.00, "cache_read": 0.20, "cache_write": 5.00}


class AgentError(RuntimeError):
    """The AI could not give a usable answer (declined, cut off, or not valid JSON). The message is for people."""


@dataclass(frozen=True)
class Doc:
    data: bytes
    title: str  # "Title commitment", "Purchase contract"


@dataclass
class Usage:
    input: int = 0
    output: int = 0
    cache_read: int = 0
    cache_write: int = 0
    calls: int = 0
    steps: list[str] = field(default_factory=list)

    def add(self, step: str, u) -> None:
        self.calls += 1
        self.steps.append(step)
        self.input += getattr(u, "input_tokens", 0) or 0
        self.output += getattr(u, "output_tokens", 0) or 0
        self.cache_read += getattr(u, "cache_read_input_tokens", 0) or 0
        self.cache_write += getattr(u, "cache_creation_input_tokens", 0) or 0

    @property
    def cost(self) -> float:
        return (self.input * PRICE["input"] + self.output * PRICE["output"] + self.cache_read * PRICE["cache_read"]
                + self.cache_write * PRICE["cache_write"]) / 1_000_000

    def as_dict(self) -> dict:
        return {"input": self.input, "output": self.output, "cache_read": self.cache_read,
                "cache_write": self.cache_write, "calls": self.calls, "steps": self.steps,
                "cost_usd": round(self.cost, 4)}


class LLM(Protocol):
    def ask(self, *, step: str, system: str, docs: list[Doc], task: str, schema: type[T], usage: Usage) -> T: ...


def _content(docs: list[Doc], task: str) -> list[dict]:
    blocks: list[dict] = []
    for i, d in enumerate(docs):
        block = {
            "type": "document",
            "source": {"type": "base64", "media_type": "application/pdf",
                       "data": base64.standard_b64encode(d.data).decode("ascii")},
            "title": d.title,
        }
        if i == len(docs) - 1:  # everything up to the last document is the same on every step: cache it
            block["cache_control"] = {"type": "ephemeral"}
        blocks.append(block)
    blocks.append({"type": "text", "text": task})
    return blocks


class ClaudeLLM:
    def __init__(self, api_key: str, model: str = MODEL, effort: str = EFFORT):
        import anthropic

        self._anthropic = anthropic
        self.client = anthropic.Anthropic(api_key=api_key, max_retries=3)
        self.model = model
        self.effort = effort

    def ask(self, *, step: str, system: str, docs: list[Doc], task: str, schema: type[T], usage: Usage) -> T:
        a = self._anthropic
        try:
            with self.client.beta.messages.stream(
                model=self.model,
                max_tokens=64000,
                system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": _content(docs, task)}],
                output_config={"effort": self.effort},
                output_format=schema,
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            ) as stream:
                msg = stream.get_final_message()
        except a.AuthenticationError as exc:
            raise AgentError("The Anthropic API key was rejected. Check ANTHROPIC_API_KEY in the app's "
                             "secrets.") from exc
        except a.RateLimitError as exc:
            raise AgentError("The AI service is busy (rate limit). Wait a minute and run it again.") from exc
        except a.BadRequestError as exc:
            raise AgentError(f"The AI service rejected the request: {exc.message}") from exc
        except a.APIStatusError as exc:
            raise AgentError(f"The AI service had an error ({exc.status_code}). Run it again in a minute.") from exc
        except a.APIConnectionError as exc:
            raise AgentError("Could not reach the AI service. Check the connection and run it again.") from exc

        usage.add(step, msg.usage)
        if msg.stop_reason == "refusal":
            raise AgentError("The AI declined to review this document. Try again, or review it by hand.")
        if msg.stop_reason == "max_tokens":
            raise AgentError("The answer was too long and got cut off. Try again; split very large files.")
        text = next((b.text for b in msg.content if getattr(b, "type", "") == "text"), "")
        try:
            return schema.model_validate_json(text)
        except Exception as exc:
            raise AgentError("The AI's answer was not in the expected format. Run it again.") from exc


class ScriptedLLM:
    """Answers from a dict of step -> model instance (or a callable). Used by tests and the demo."""

    def __init__(self, answers: dict):
        self.answers = answers
        self.calls: list[dict] = []

    def ask(self, *, step: str, system: str, docs: list[Doc], task: str, schema: type[T], usage: Usage) -> T:
        self.calls.append({"step": step, "task": task, "system": system, "docs": [d.title for d in docs]})
        answer = self.answers[step]
        if callable(answer):
            answer = answer(len([c for c in self.calls if c["step"] == step]), task)
        usage.calls += 1
        usage.steps.append(step)
        return answer
