"""Model setup, shared by every chapter. The only file that knows the provider is DeepSeek."""

import os
from datetime import datetime

from agent_framework import ChatContext, chat_middleware
from agent_framework.openai import OpenAIChatCompletionClient
from dotenv import load_dotenv
from openai import AsyncOpenAI, OpenAI

from agentlab.usage import record

load_dotenv()

BASE_URL = "https://api.deepseek.com"
BETA_URL = "https://api.deepseek.com/beta"  # beta features, such as strict tool definitions (Chapter 10)
MODEL = "deepseek-flash"

# US dollars per million tokens, as (peak, off-peak), from DeepSeek's pricing page on 2026-10-31.
# deepseek-v4-pro, checked on 2026-11-02, is Chapter 13's second judge.
PRICES = {
    "deepseek-flash": {"input": (0.30, 0.15), "cached_input": (0.006, 0.003), "output": (1.20, 0.60)},
    "deepseek-v4-pro": {"input": (1.32, 0.66), "cached_input": (0.044, 0.022), "output": (3.96, 1.98)},
}
PEAK_HOURS_UTC = {1, 2, 3, 6, 7, 8, 9}  # weekdays only: 01:00-04:00 and 06:00-10:00

client = OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"], base_url=BASE_URL)
beta_client = OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"], base_url=BETA_URL)


def chat(messages: list, beta: bool = False, **options):
    """One call to the model. Options such as tools or temperature are passed through unchanged."""
    # DeepSeek reasons before answering by default and ignores temperature while it does.
    # Turning that off makes temperature take effect.
    response = (beta_client if beta else client).chat.completions.create(
        model=MODEL, messages=messages, extra_body={"thinking": {"type": "disabled"}}, **options
    )
    usage = response.usage
    record(MODEL, usage.prompt_tokens, getattr(usage, "prompt_cache_hit_tokens", 0) or 0, usage.completion_tokens)
    return response


def describe_tool(name: str, description: str, **params: str) -> dict:
    """A tool description in the format the model receives, for a tool whose parameters are all strings."""
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": {p: {"type": "string", "description": d} for p, d in params.items()},
                "required": list(params),
            },
        },
    }


@chat_middleware
async def _each_call(context: ChatContext, call_next) -> None:
    """Gives framework calls the same thinking setting as chat(), and records each call's token usage."""
    context.options["extra_body"] = {"thinking": {"type": "disabled"}}
    await call_next()
    usage = context.result.usage_details or {}
    record(
        getattr(context.client, "model", None) or MODEL,
        usage.get("input_token_count", 0),
        usage.get("cache_read_input_token_count", 0),
        usage.get("output_token_count", 0),
    )


def make_client(
    timeout: float | None = None, max_retries: int | None = None, model: str = MODEL
) -> OpenAIChatCompletionClient:
    """Microsoft Agent Framework's chat client for the same model (Chapter 4 onwards), or another of the
    provider's models (Chapter 13's second judge).

    A timeout or retry count is set on the OpenAI library's client underneath, which MAF's client then uses (Chapter 5).
    """
    if timeout is None and max_retries is None:
        return OpenAIChatCompletionClient(
            model=model,
            api_key=os.environ["DEEPSEEK_API_KEY"],
            base_url=BASE_URL,
            middleware=[_each_call],
        )
    limits = {"timeout": timeout, "max_retries": max_retries}
    openai_client = AsyncOpenAI(
        api_key=os.environ["DEEPSEEK_API_KEY"], base_url=BASE_URL, **{k: v for k, v in limits.items() if v is not None}
    )
    return OpenAIChatCompletionClient(model=model, async_client=openai_client, middleware=[_each_call])


def cost(entry: dict) -> float:
    """What one call in the usage log cost, in US dollars."""
    time = datetime.fromisoformat(entry["time"])
    rate = 0 if time.weekday() < 5 and time.hour in PEAK_HOURS_UTC else 1
    prices = PRICES[entry["model"]]
    return (
        (entry["input"] - entry["cached"]) * prices["input"][rate]
        + entry["cached"] * prices["cached_input"][rate]
        + entry["output"] * prices["output"][rate]
    ) / 1_000_000
