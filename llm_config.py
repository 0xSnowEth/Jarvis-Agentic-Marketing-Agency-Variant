import os
from openai import OpenAI, AsyncOpenAI

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
NVIDIA_NIM_BASE_URL = os.getenv("NVIDIA_NIM_BASE_URL", "https://integrate.api.nvidia.com/v1").strip()

def build_sync_client(provider: str, timeout: float = 30, max_retries: int = 0) -> OpenAI:
    if provider == "openrouter":
        return OpenAI(
            base_url=OPENROUTER_BASE_URL,
            api_key=os.getenv("OPENROUTER_API_KEY"),
            timeout=timeout,
            max_retries=max_retries,
        )
    if provider == "groq":
        return OpenAI(
            base_url=GROQ_BASE_URL,
            api_key=os.getenv("GROQ_API_KEY"),
            timeout=timeout,
            max_retries=max_retries,
        )
    if provider == "openai":
        return OpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            timeout=timeout,
            max_retries=max_retries,
        )
    if provider == "nvidia":
        return OpenAI(
            base_url=NVIDIA_NIM_BASE_URL,
            api_key=os.getenv("NVIDIA_API_KEY"),
            timeout=timeout,
            max_retries=max_retries,
        )
    raise RuntimeError(f"Unsupported provider: {provider}")

def build_async_client(provider: str, timeout: float = 30, max_retries: int = 0) -> AsyncOpenAI:
    if provider == "openrouter":
        return AsyncOpenAI(
            base_url=OPENROUTER_BASE_URL,
            api_key=os.getenv("OPENROUTER_API_KEY"),
            timeout=timeout,
            max_retries=max_retries,
        )
    if provider == "openai":
        return AsyncOpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            timeout=timeout,
            max_retries=max_retries,
        )
    if provider == "nvidia":
        return AsyncOpenAI(
            base_url=NVIDIA_NIM_BASE_URL,
            api_key=os.getenv("NVIDIA_API_KEY"),
            timeout=timeout,
            max_retries=max_retries,
        )
    raise RuntimeError(f"Unsupported async provider: {provider}")
