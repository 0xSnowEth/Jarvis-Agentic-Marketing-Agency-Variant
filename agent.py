import os
import re
import time

from openai import APIStatusError, OpenAI, RateLimitError
from dotenv import load_dotenv

load_dotenv(override=True)

GROQ_BASE_URL = "https://api.groq.com/openai/v1"


def _rate_limit_retry_delay_seconds(exc: Exception) -> float:
    message = str(exc or "")
    match = re.search(r"Please try again in\s+([0-9.]+)\s*(ms|s)", message, re.IGNORECASE)
    if match:
        value = float(match.group(1))
        unit = match.group(2).lower()
        seconds = value / 1000.0 if unit == "ms" else value
        return max(seconds, 0.25)
    return 1.0


class Agent:
    def __init__(self, tools, model=None):
        openrouter_key = os.getenv("OPENROUTER_API_KEY")
        openai_key = os.getenv("OPENAI_API_KEY")
        groq_key = os.getenv("GROQ_API_KEY")
        self.fallback_client = None
        self.fallback_model = None
        self.provider = ""
        self.requested_model = str(model or os.getenv("MODEL") or "").strip()
        configured_model = str(model or os.getenv("MODEL") or "").strip()
        explicit_provider = ""
        if ":" in configured_model:
            maybe_provider, maybe_model = configured_model.split(":", 1)
            if maybe_provider in {"openrouter", "openai", "groq"} and maybe_model.strip():
                explicit_provider = maybe_provider
                configured_model = maybe_model.strip()

        if explicit_provider == "groq":
            if not groq_key:
                raise RuntimeError("Please add GROQ_API_KEY in .env for groq-prefixed models")
            self.provider = "groq"
            self.client = OpenAI(
                base_url=GROQ_BASE_URL,
                api_key=groq_key,
            )
        elif explicit_provider == "openrouter":
            if not openrouter_key:
                raise RuntimeError("Please add OPENROUTER_API_KEY in .env for openrouter-prefixed models")
            self.provider = "openrouter"
            self.client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=openrouter_key,
            )
            if openai_key:
                self.fallback_client = OpenAI(api_key=openai_key)
        elif explicit_provider == "openai":
            if not openai_key:
                raise RuntimeError("Please add OPENAI_API_KEY in .env for openai-prefixed models")
            self.provider = "openai"
            self.client = OpenAI(api_key=openai_key)
        elif openrouter_key:
            self.provider = "openrouter"
            self.client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=openrouter_key,
            )
            if openai_key:
                self.fallback_client = OpenAI(api_key=openai_key)
        elif groq_key:
            self.provider = "groq"
            self.client = OpenAI(
                base_url=GROQ_BASE_URL,
                api_key=groq_key,
            )
        elif openai_key:
            self.provider = "openai"
            self.client = OpenAI(api_key=openai_key)
        else:
            raise RuntimeError("Please add OPENROUTER_API_KEY, GROQ_API_KEY, or OPENAI_API_KEY in .env")

        provider_default_model = (
            "openai/gpt-oss-120b" if self.provider == "groq"
            else ("openai/gpt-4o-mini" if self.provider == "openrouter" else "gpt-4o-mini")
        )
        self.model = configured_model or provider_default_model
        if self.provider == "openrouter" and self.fallback_client:
            self.fallback_model = self.model.split("/", 1)[1] if "/" in self.model else self.model

        self.system_message = (
            "You are one of the most intelligent Assistant in human history, capable to break down even the most hardest and complicated tasks into very easy points"
        )
        self.tools = tools
        self.tool_map = {tool.get_schema()["function"]["name"]: tool for tool in tools}
        self.messages = []

    def _get_tool_schemas(self):
        return [tool.get_schema() for tool in self.tools]

    def chat(self, message):
        if message is not None and str(message).strip():
            self.messages.append({"role": "user", "content": message})

        payload = [{"role": "system", "content": self.system_message}] + self.messages
        request_kwargs = {
            "model": self.model,
            "max_tokens": 2048,
            "tools": self._get_tool_schemas() if self.tools else None,
            "messages": payload,
            "temperature": 0.1,
        }

        for attempt in range(3):
            try:
                return self.client.chat.completions.create(**request_kwargs)
            except RateLimitError as exc:
                if attempt >= 2:
                    raise RuntimeError(
                        f"LLM request failed for provider {self.provider or 'unknown'} model {self.model}: {type(exc).__name__}: {exc}"
                    ) from exc
                time.sleep(_rate_limit_retry_delay_seconds(exc))
                continue
            except APIStatusError as exc:
                if (
                    self.provider == "openrouter"
                    and getattr(exc, "status_code", None) == 402
                    and self.fallback_client is not None
                    and self.fallback_model
                ):
                    fallback_kwargs = dict(request_kwargs)
                    fallback_kwargs["model"] = self.fallback_model
                    return self.fallback_client.chat.completions.create(**fallback_kwargs)
                raise RuntimeError(
                    f"LLM request failed for provider {self.provider or 'unknown'} model {self.model}: {type(exc).__name__}: {exc}"
                ) from exc
            except Exception as exc:
                raise RuntimeError(
                    f"LLM request failed for provider {self.provider or 'unknown'} model {self.model}: {type(exc).__name__}: {exc}"
                ) from exc
