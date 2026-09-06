"""Thin, retrying wrapper around the Anthropic SDK.

Two call shapes are used by the rest of the application:

``structured()``  - forces Claude to answer through a tool with a JSON Schema,
                    so callers get validated data rather than prose to parse.
``vision()``      - the same, with images attached.

The model name is never hard-coded here; it comes from settings.
"""

from __future__ import annotations

import base64
import json
import random
import time
from pathlib import Path
from typing import Any

from ..config import Settings, get_settings
from ..errors import AIError
from ..logging_setup import get_logger

log = get_logger(__name__)

MEDIA_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
}

# Anthropic's image request limit is generous, but large photos waste tokens.
MAX_IMAGE_BYTES = 3_500_000


class ClaudeClient:
    def __init__(self, settings: Settings | None = None, client: Any | None = None) -> None:
        """``client`` injects a pre-built SDK client. Used by tests."""
        self.settings = settings or get_settings()
        self._client: Any = client

    # ------------------------------------------------------------------ setup

    @property
    def client(self) -> Any:
        if self._client is None:
            api_key = self.settings.require_claude()
            try:
                from anthropic import Anthropic
            except ImportError as exc:  # pragma: no cover
                raise AIError(
                    "The 'anthropic' package is not installed. Run: pip install -e '.[dev]'"
                ) from exc
            # We drive our own retry loop so we can log each attempt.
            self._client = Anthropic(api_key=api_key, max_retries=0)
        return self._client

    @property
    def enabled(self) -> bool:
        return self.settings.claude_enabled

    # ------------------------------------------------------------------- core

    def structured(
        self,
        *,
        system: str,
        prompt: str,
        tool_name: str,
        tool_description: str,
        schema: dict,
        images: list[Path] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> dict:
        """Force a tool call and return its validated input dict."""
        content: list[dict] = []
        for image_path in images or []:
            content.append(self._image_block(image_path))
        content.append({"type": "text", "text": prompt})

        tool = {
            "name": tool_name,
            "description": tool_description,
            "input_schema": schema,
        }

        response = self._call(
            model=model or self.settings.anthropic_model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=[{"role": "user", "content": content}],
            tools=[tool],
            tool_choice={"type": "tool", "name": tool_name},
        )

        for block in response.content:
            if getattr(block, "type", None) == "tool_use" and block.name == tool_name:
                return dict(block.input)

        raise AIError(
            f"Claude did not call the required tool {tool_name!r}. "
            f"stop_reason={getattr(response, 'stop_reason', 'unknown')}"
        )

    def vision(self, *, images: list[Path], **kwargs: Any) -> dict:
        """``structured()`` with images and the (cheaper) vision model default."""
        kwargs.setdefault("model", self.settings.anthropic_vision_model)
        kwargs.setdefault("temperature", 0.2)
        return self.structured(images=images, **kwargs)

    # -------------------------------------------------------------- internals

    def _image_block(self, path: Path) -> dict:
        if not path.exists():
            raise AIError(f"Image for Claude not found: {path}")
        media_type = MEDIA_TYPES.get(path.suffix.lower())
        if media_type is None:
            raise AIError(f"Unsupported image type for Claude: {path.suffix}")
        data = path.read_bytes()
        if len(data) > MAX_IMAGE_BYTES:
            data = self._downscale(path)
            media_type = "image/jpeg"
        return {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": media_type,
                "data": base64.standard_b64encode(data).decode("ascii"),
            },
        }

    @staticmethod
    def _downscale(path: Path) -> bytes:
        """Shrink oversized references so a vision call stays cheap."""
        import io

        from PIL import Image

        with Image.open(path) as handle:
            image = handle.convert("RGB")
        image.thumbnail((1568, 1568), Image.Resampling.LANCZOS)
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=85, optimize=True)
        return buffer.getvalue()

    def _call(self, **kwargs: Any) -> Any:
        """Retry with exponential backoff + jitter on transient failures."""
        attempts = max(self.settings.anthropic_max_retries, 1)
        last_error: Exception | None = None

        for attempt in range(1, attempts + 1):
            try:
                started = time.monotonic()
                response = self.client.messages.create(**kwargs)
                usage = getattr(response, "usage", None)
                log.info(
                    "Claude %s ok in %.1fs (in=%s out=%s)",
                    kwargs.get("model"),
                    time.monotonic() - started,
                    getattr(usage, "input_tokens", "?"),
                    getattr(usage, "output_tokens", "?"),
                )
                return response
            except Exception as exc:
                last_error = exc
                if not self._is_retryable(exc) or attempt == attempts:
                    break
                delay = min(2**attempt, 30) + random.uniform(0, 1.5)
                log.warning(
                    "Claude call failed (attempt %d/%d): %s - retrying in %.1fs",
                    attempt,
                    attempts,
                    type(exc).__name__,
                    delay,
                )
                time.sleep(delay)

        raise AIError(
            f"Claude request failed after {attempts} attempt(s): {last_error}"
        ) from last_error

    @staticmethod
    def _is_retryable(exc: Exception) -> bool:
        name = type(exc).__name__
        if name in {
            "RateLimitError",
            "APIConnectionError",
            "APITimeoutError",
            "InternalServerError",
            "APIStatusError",
        }:
            status = getattr(exc, "status_code", None)
            if status is None:
                return True
            return status == 429 or status >= 500
        return False


_singleton: ClaudeClient | None = None


def get_claude(settings: Settings | None = None) -> ClaudeClient:
    global _singleton
    if _singleton is None or settings is not None:
        _singleton = ClaudeClient(settings)
    return _singleton


def compact_json(value: Any, limit: int = 12000) -> str:
    """Serialise context for a prompt, truncating defensively."""
    text = json.dumps(value, indent=2, default=str)
    if len(text) > limit:
        text = text[:limit] + "\n... [truncated]"
    return text
