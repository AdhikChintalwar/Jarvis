from __future__ import annotations

import os
import re
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()


class NvidiaNemotronClient:
    """
    NVIDIA Nemotron client.

    Important:
    - Receives only privacy-approved content.
    - Has no direct desktop/filesystem permissions.
    - Removes internal reasoning traces before returning content
      to Baby's other systems.
    """

    DEFAULT_BASE_URL = (
        "https://integrate.api.nvidia.com/v1"
    )

    DEFAULT_MODEL = (
        "nvidia/nemotron-3-ultra-550b-a55b"
    )

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        model: str = DEFAULT_MODEL,
    ) -> None:
        resolved_key = (
            api_key
            or os.getenv("NVIDIA_API_KEY")
        )

        if not resolved_key:
            raise RuntimeError(
                "NVIDIA_API_KEY is not configured."
            )

        self.model = model

        self.client = OpenAI(
            base_url=base_url,
            api_key=resolved_key,
        )

    def chat(
        self,
        *,
        messages: list[dict[str, str]],
        max_tokens: int = 4096,
        temperature: float = 0.7,
        top_p: float = 0.95,
        reasoning: bool = True,
        reasoning_budget: int = 4096,
    ) -> str:
        """
        Send a conversation to Nemotron and return only the
        user-facing answer.

        Internal reasoning traces are removed locally.
        """

        extra_body: dict[str, Any] = {
            "chat_template_kwargs": {
                "enable_thinking": reasoning,
                "force_nonempty_content": True,
            },
        }

        if reasoning:
            extra_body[
                "reasoning_budget"
            ] = reasoning_budget

        response = (
            self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                top_p=top_p,
                max_tokens=max_tokens,
                extra_body=extra_body,
                stream=False,
            )
        )

        if not response.choices:
            raise RuntimeError(
                "Nemotron returned no response choices."
            )

        message = response.choices[0].message

        content = message.content or ""

        cleaned = self._clean_response(
            content
        )

        if not cleaned:
            raise RuntimeError(
                "Nemotron returned an empty final response."
            )

        return cleaned

    @staticmethod
    def _clean_response(
        content: str,
    ) -> str:
        """
        Remove model reasoning/thinking markup.

        Handles:

            <think>
            internal reasoning
            </think>
            final answer

        and responses where only the closing </think>
        marker appears.
        """

        if not isinstance(content, str):
            return ""

        cleaned = content.strip()

        # Remove complete <think>...</think> blocks.
        cleaned = re.sub(
            r"<think>.*?</think>",
            "",
            cleaned,
            flags=(
                re.IGNORECASE
                | re.DOTALL
            ),
        ).strip()

        # Some model/API responses contain reasoning followed
        # only by a closing </think> marker.
        if "</think>" in cleaned.lower():
            parts = re.split(
                r"</think>",
                cleaned,
                flags=re.IGNORECASE,
            )

            if len(parts) > 1:
                cleaned = parts[-1].strip()

        # Remove leftover opening tags if one survives.
        cleaned = re.sub(
            r"</?think>",
            "",
            cleaned,
            flags=re.IGNORECASE,
        ).strip()

        return cleaned