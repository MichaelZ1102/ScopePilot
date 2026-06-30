"""AI Provider abstraction for ScopePilot analysis pipeline."""

import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

import httpx


class AIError(Exception):
    """Base exception for AI provider errors."""


class AIProvider(ABC):
    """Abstract base class for AI providers."""

    @abstractmethod
    def chat(self, system_prompt: str, user_prompt: str, response_format: Optional[dict] = None) -> str:
        """Send a chat completion request. Returns text content."""
        ...

    def chat_json(self, system_prompt: str, user_prompt: str) -> dict:
        """Send a chat completion request and parse JSON response.
        Falls back gracefully if provider does not support JSON mode."""
        # Try with JSON mode first (supported by OpenAI, Groq, etc.)
        for attempt in range(2):
            use_json_mode = (attempt == 0)
            rf = {"type": "json_object"} if use_json_mode else None
            try:
                response = self.chat(system_prompt, user_prompt, response_format=rf)
                if response and response.strip():
                    return self._parse_json(response)
            except Exception:
                if not use_json_mode:
                    raise  # Both attempts failed
                continue  # JSON mode failed, try plain text

        raise AIError("AI returned empty response")

    @staticmethod
    def _parse_json(text: str) -> dict:
        """Parse JSON from LLM response, handling markdown code fences and common LLM JSON issues."""
        if not text or not text.strip():
            raise json.JSONDecodeError("Empty response", "", 0)

        text = text.strip()

        # Remove markdown code fences if present
        if text.startswith("```"):
            lines = text.split("\n")
            first_line = lines[0].strip()
            if first_line.startswith("```"):
                end_fence = None
                for i, line in enumerate(lines[1:], 1):
                    if line.strip() == "```":
                        end_fence = i
                        break
                if end_fence:
                    text = "\n".join(lines[1:end_fence])
                else:
                    text = "\n".join(lines[1:])
                text = text.strip()

        # Try standard parse first
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try with strict=False (allows control characters)
        try:
            return json.loads(text, strict=False)
        except json.JSONDecodeError:
            pass

        # Try common fixes for LLM-generated JSON
        fixed = text
        # 1. Escape unescaped newlines inside strings (newlines not preceded by backslash)
        # 2. Try to find the last complete JSON object/array
        for attempt in range(3):
            try:
                return json.loads(fixed, strict=False)
            except json.JSONDecodeError as e:
                pos = e.pos if hasattr(e, 'pos') else 0
                if pos <= 0:
                    # Try wrapping in array or extracting partial JSON
                    break
                # Truncate at the error position and try again
                fixed = fixed[:pos].rstrip()
                # Remove trailing comma if present
                if fixed.rstrip().endswith(","):
                    fixed = fixed.rstrip()[:-1].rstrip()
                # Close unclosed braces/brackets
                opens = fixed.count("{") - fixed.count("}")
                if opens > 0:
                    fixed += "}" * opens
                opens_bracket = fixed.count("[") - fixed.count("]")
                if opens_bracket > 0:
                    fixed += "]" * opens_bracket

        # Final fallback: return error dict
        raise json.JSONDecodeError(
            f"Failed to parse AI response after fixes: {text[:200]}",
            text,
            0,
        )


class OpenAILikeProvider(AIProvider):
    """Provider for OpenAI-compatible APIs (OpenAI, Groq, OpenCode etc.)."""

    def __init__(
        self,
        api_key: str,
        model: str = "deepseek-v4-flash",
        base_url: str = "https://opencode.ai/zen/go/v1",
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")

    def chat(self, system_prompt: str, user_prompt: str, response_format: Optional[dict] = None) -> str:
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.3,
            "max_tokens": 4096,
        }
        if response_format:
            body["response_format"] = response_format

        try:
            with httpx.Client(timeout=120.0) as client:
                resp = client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=body,
                )
                if resp.status_code == 401:
                    raise AIError("AI provider authentication failed. Check your API key.")
                if resp.status_code == 429:
                    raise AIError("AI provider rate limited. Please wait and try again.")
                if resp.status_code >= 400:
                    raise AIError(f"AI provider error ({resp.status_code}): {resp.text[:500]}")

                data = resp.json()
                return data["choices"][0]["message"]["content"]
        except httpx.RequestError as e:
            raise AIError(f"AI provider connection error: {e}") from e


def create_provider() -> AIProvider:
    """Create an AI provider based on environment configuration.

    Priority:
    1. OPENCODE_API_KEY (OpenCode Go)
    2. GROQ_API_KEY (Groq)
    3. STEPFUN_API_KEY (StepFun)
    4. OPENAI_API_KEY (OpenAI)
    """
    # OpenCode Go (default for current user)
    api_key = os.getenv("OPENCODE_API_KEY")
    if api_key:
        return OpenAILikeProvider(
            api_key=api_key,
            model=os.getenv("OPENCODE_MODEL", "deepseek-v4-flash"),
            base_url=os.getenv("OPENCODE_BASE_URL", "https://opencode.ai/zen/go/v1"),
        )

    # Groq
    api_key = os.getenv("GROQ_API_KEY")
    if api_key:
        return OpenAILikeProvider(
            api_key=api_key,
            model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
            base_url="https://api.groq.com/openai/v1",
        )

    # StepFun
    api_key = os.getenv("STEPFUN_API_KEY")
    if api_key:
        return OpenAILikeProvider(
            api_key=api_key,
            model=os.getenv("STEPFUN_MODEL", "step-1-8k"),
            base_url=os.getenv("STEPFUN_BASE_URL", "https://api.stepfun.com/v1"),
        )

    # OpenAI
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        return OpenAILikeProvider(
            api_key=api_key,
            model=os.getenv("OPENAI_MODEL", "gpt-4o"),
            base_url=base_url,
        )

    raise AIError(
        "No AI provider configured. Set STEPFUN_API_KEY, OPENCODE_API_KEY, GROQ_API_KEY, or OPENAI_API_KEY in .env file."
    )
