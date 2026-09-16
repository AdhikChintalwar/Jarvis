from __future__ import annotations

import hashlib
import json
import os
import time

from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[2]
)

ENV_PATH = (
    PROJECT_ROOT
    / ".env"
)

load_dotenv(
    dotenv_path=ENV_PATH,
    override=False,
)


class NemotronClient:

    DEFAULT_MODEL = (
        "nvidia/nemotron-3-ultra-550b-a55b"
    )

    DEFAULT_BASE_URL = (
        "https://integrate.api.nvidia.com/v1"
    )

    def __init__(
        self,
        model: str | None = None,
        use_cache: bool = True,
        timeout_seconds: float = 300.0,
    ):

        api_key = os.getenv(
            "NVIDIA_API_KEY"
        )

        if not api_key:

            raise RuntimeError(
                "NVIDIA_API_KEY is not set. "
                f"Checked environment and {ENV_PATH}"
            )

        self.model = (
            model
            or os.getenv(
                "NVIDIA_NEMOTRON_MODEL",
                self.DEFAULT_MODEL,
            )
        )

        self.client = OpenAI(
            base_url=os.getenv(
                "NVIDIA_BASE_URL",
                self.DEFAULT_BASE_URL,
            ),
            api_key=api_key,
            timeout=timeout_seconds,
            max_retries=0,
        )

        self.use_cache = use_cache

        self.cache_dir = (
            PROJECT_ROOT
            / "data"
            / "nemotron_cache"
        )

        self.cache_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

    @staticmethod
    def is_transient_provider_error(error: Exception) -> bool:
        status = getattr(error, "status_code", None)
        if status is None:
            response = getattr(error, "response", None)
            status = getattr(response, "status_code", None)
        if status in {429, 500, 502, 503, 504}:
            return True
        text = str(error).lower()
        return any(x in text for x in (
            "error code: 429","error code: 500","error code: 502",
            "error code: 503","error code: 504",
            "service temporarily overloaded","service unavailable",
            "temporarily unavailable","rate limit","timeout","timed out",
            "connection reset","connection aborted",
        ))

    @staticmethod
    def _cached_result_shape_valid(task_name: str, data) -> bool:
        if not isinstance(data, dict):
            return False
        if (
            task_name.startswith("investment_deliberation_deep_v4_5")
            or task_name.startswith("investment_deliberation_recovery_v4_5_8")
        ):
            rows = data.get("deliberations")
            if not (isinstance(rows, list) and bool(rows)):
                return False
            for row in rows:
                if not isinstance(row, dict) or not str(row.get("symbol","")).strip():
                    return False
                for key in ("bull_claims", "bear_claims", "contradictions"):
                    section = row.get(key, [])
                    if not isinstance(section, list):
                        return False
                    if not all(isinstance(claim, dict) for claim in section):
                        return False
            return True
        if (
            task_name.startswith("investment_committee_deep_v4_5")
            or task_name.startswith("investment_committee_schema_repair_v4_5_5")
        ):
            rows = data.get("rankings")
            return isinstance(rows, list) and bool(rows) and all(
                isinstance(x, dict) and str(x.get("symbol","")).strip()
                for x in rows
            )
        return True

    def reason_json(
        self,
        system_prompt: str,
        payload: dict,
        task_name: str,
        temperature: float = 0.15,
        max_tokens: int = 5000,
        retries: int = 3,
        enable_thinking: bool = True,
    ) -> dict:

        cache_key = self._cache_key(
            system_prompt=system_prompt,
            payload=payload,
            task_name=task_name,
            enable_thinking=enable_thinking,
        )

        cache_path = (
            self.cache_dir
            / f"{cache_key}.json"
        )

        if (
            self.use_cache
            and cache_path.exists()
        ):

            try:

                cached = json.loads(cache_path.read_text())
                if self._cached_result_shape_valid(task_name, cached):
                    print(f"[Nemotron cache] {task_name}")
                    return cached
                print(
                    f"[Nemotron cache invalid] {task_name} | "
                    "stale/schema-mismatched entry ignored"
                )
            except Exception as cache_error:
                print(
                    f"[Nemotron cache invalid] {task_name} | "
                    f"{type(cache_error).__name__}"
                )

        request_text = json.dumps(
            payload,
            indent=2,
            default=str,
        )

        user_prompt = (
            "Analyze the following evidence package.\n\n"
            "Return ONLY valid JSON matching the requested "
            "schema. Do not include markdown fences.\n\n"
            f"{request_text}"
        )

        last_error = None

        transport_attempts = max(retries, 4)

        for attempt in range(
            1,
            transport_attempts + 1,
        ):

            try:

                print(
                    f"[Nemotron] "
                    f"{task_name} "
                    f"| attempt {attempt}/{transport_attempts} "
                    f"| thinking="
                    f"{'ON' if enable_thinking else 'OFF'}"
                )

                extra_body = {}

                if enable_thinking is not None:

                    extra_body = {
                        "chat_template_kwargs": {
                            "enable_thinking":
                                enable_thinking
                        }
                    }

                response = (
                    self.client
                    .chat
                    .completions
                    .create(
                        model=self.model,

                        messages=[
                            {
                                "role":
                                    "system",

                                "content":
                                    system_prompt,
                            },
                            {
                                "role":
                                    "user",

                                "content":
                                    user_prompt,
                            },
                        ],

                        temperature=temperature,

                        top_p=0.95,

                        max_tokens=max_tokens,

                        extra_body=extra_body,
                    )
                )

                message = (
                    response
                    .choices[0]
                    .message
                )

                text = (
                    message.content
                    or ""
                )

                if not text.strip():

                    reasoning_content = getattr(
                        message,
                        "reasoning_content",
                        None,
                    )

                    raise ValueError(
                        "Nemotron returned no final "
                        "response content. "
                        f"Reasoning content present: "
                        f"{bool(reasoning_content)}"
                    )

                parsed = self._parse_json(
                    text
                )

                cache_shape_valid = self._cached_result_shape_valid(
                    task_name,
                    parsed,
                )

                if self.use_cache and cache_shape_valid:
                    cache_path.write_text(
                        json.dumps(
                            parsed,
                            indent=2,
                            default=str,
                        )
                    )
                elif self.use_cache and not cache_shape_valid:
                    print(
                        f"[Nemotron cache skip] {task_name} | "
                        "response failed task-specific schema validation"
                    )

                return parsed

            except Exception as error:

                last_error = error

                print(
                    f"[Nemotron ERROR] "
                    f"{task_name}: "
                    f"{type(error).__name__}: "
                    f"{error}"
                )

                transient = self.is_transient_provider_error(error)

                if transient and attempt < transport_attempts:
                    delay = (5, 15, 30)[min(attempt - 1, 2)]
                    print(
                        f"[Nemotron retry] transient provider error; "
                        f"waiting {delay}s"
                    )
                    time.sleep(delay)
                    continue

                if not transient and attempt < retries:
                    time.sleep(attempt * 3)
                    continue

                break

        raise RuntimeError(
            f"Nemotron request failed: "
            f"{last_error}"
        )

    def _parse_json(
        self,
        text: str,
    ) -> dict:

        cleaned = text.strip()

        #
        # Remove visible reasoning blocks.
        #

        while (
            "<think>" in cleaned
            and "</think>" in cleaned
        ):

            start = cleaned.find("<think>")
            end = cleaned.find("</think>")

            if start >= 0 and end > start:

                cleaned = (
                    cleaned[:start]
                    + cleaned[
                        end + len("</think>"):
                    ]
                ).strip()

            else:
                break

        #
        # Remove markdown fences.
        #

        if cleaned.startswith("```"):

            cleaned = cleaned.replace(
                "```json",
                "",
                1,
            )

            cleaned = cleaned.replace(
                "```JSON",
                "",
                1,
            )

            cleaned = cleaned.replace(
                "```",
                "",
            ).strip()

        #
        # Perfect response.
        #

        try:

            value = json.loads(cleaned)

            if isinstance(value, dict):
                return value

        except Exception:
            pass

        #
        # Try normal object extraction.
        #

        start = cleaned.find("{")
        end = cleaned.rfind("}")

        if start >= 0 and end > start:

            candidate = cleaned[
                start:
                end + 1
            ]

            try:

                value = json.loads(candidate)

                if isinstance(value, dict):
                    return value

            except Exception:
                pass

        #
        # Batch-response recovery.
        #
        # Nemotron occasionally finishes several
        # candidate objects and then truncates or
        # corrupts the final one.
        #
        # Recover every fully balanced JSON object
        # inside the candidates array.
        #

        for array_key in ("deliberations", "rankings", "candidates"):
            recovered = self._recover_array_objects(
                cleaned,
                array_key,
            )
            if recovered:
                print(
                    f"[Nemotron recovery] Recovered {len(recovered)} "
                    f"complete {array_key} object(s) from partial JSON"
                )
                return {
                    array_key: recovered,
                    "_partial_response": True,
                    "_recovery_reason": "truncated_or_malformed_json",
                }

        raise ValueError(
            "Nemotron did not return usable JSON. "
            f"Response begins: "
            f"{cleaned[:500]!r}"
        )


    def _recover_array_objects(
        self,
        text: str,
        array_key: str,
    ) -> list[dict]:

        marker = f'"{array_key}"'

        marker_index = text.find(marker)

        if marker_index < 0:
            return []

        array_start = text.find(
            "[",
            marker_index,
        )

        if array_start < 0:
            return []

        recovered = []

        depth = 0
        object_start = None

        in_string = False
        escape = False

        for index in range(
            array_start + 1,
            len(text),
        ):

            char = text[index]

            if in_string:

                if escape:
                    escape = False
                    continue

                if char == "\\":
                    escape = True
                    continue

                if char == '"':
                    in_string = False

                continue

            if char == '"':
                in_string = True
                continue

            if char == "{":

                if depth == 0:
                    object_start = index

                depth += 1

            elif char == "}":

                if depth <= 0:
                    continue

                depth -= 1

                if (
                    depth == 0
                    and object_start is not None
                ):

                    object_text = text[
                        object_start:
                        index + 1
                    ]

                    try:

                        obj = json.loads(
                            object_text
                        )

                        if isinstance(
                            obj,
                            dict,
                        ):

                            recovered.append(
                                obj
                            )

                    except Exception:
                        pass

                    object_start = None

        return recovered

    def _cache_key(
        self,
        system_prompt,
        payload,
        task_name,
        enable_thinking,
    ):

        content = json.dumps(
            {
                "model":
                    self.model,

                "task":
                    task_name,

                "system":
                    system_prompt,

                "payload":
                    payload,

                "enable_thinking":
                    enable_thinking,
            },

            sort_keys=True,
            default=str,
        )

        digest = hashlib.sha256(
            content.encode(
                "utf-8"
            )
        ).hexdigest()

        return (
            f"{task_name}_"
            f"{digest}"
        )