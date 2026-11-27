"""The only path for messages the engine starts (reminders, digests).

Destinations are checked against the admin/ops allow-list before any network
call, so no code path can message a buyer by mistake. Replies inside the bot
process go back to the chat the admin wrote from, which the handlers have
already checked.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from contextlib import ExitStack
from pathlib import Path
from typing import Any

import httpx

from baby_arb.marketing.bot.auth import Access

API_BASE = "https://api.telegram.org"
MAX_ALBUM = 10
MEDIA_TIMEOUT = 120.0
JPEG_QUALITY = 88


def telegram_copy(path: Path) -> Path:
    """A JPEG copy of a rendered PNG for Telegram (made once, kept beside it).

    A preview round is several 1-2 MB PNGs; uploading them as one album timed out.
    Telegram recompresses photos anyway, and the PNG stays the file to post.
    """
    if path.suffix.lower() in {".jpg", ".jpeg"}:
        return path
    out = path.with_name(path.stem + ".tg.jpg")
    if not out.exists() or out.stat().st_mtime < path.stat().st_mtime:
        from PIL import Image

        with Image.open(path) as im:
            im.convert("RGB").save(out, "JPEG", quality=JPEG_QUALITY, optimize=True)
    return out


class DestinationNotAllowedError(RuntimeError):
    """Raised when a send targets a chat outside the allow-list."""


class OpsSender:
    """Send Telegram messages to admins and the ops group only."""

    def __init__(self, token: str, access: Access, client: httpx.Client | None = None) -> None:
        self._token = token
        self._access = access
        self._client = client or httpx.Client(timeout=30.0)

    def _check(self, chat_id: int) -> None:
        if chat_id not in self._access.chat_ids:
            raise DestinationNotAllowedError(f"chat {chat_id} is not an admin or ops chat")

    def send_message(
        self, chat_id: int, text: str, reply_markup: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Send a text message; returns Telegram's `result` object.

        Raises:
            DestinationNotAllowedError: chat_id is not allow-listed.
            httpx.HTTPStatusError: Telegram rejected the call.
        """
        self._check(chat_id)
        payload: dict[str, Any] = {"chat_id": chat_id, "text": text}
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        resp = self._client.post(f"{API_BASE}/bot{self._token}/sendMessage", json=payload)
        resp.raise_for_status()
        result: dict[str, Any] = resp.json()["result"]
        return result

    def send_media_group(
        self, chat_id: int, paths: Sequence[Path], caption: str | None = None
    ) -> list[dict[str, Any]]:
        """Send up to 10 local images as one album; returns the sent messages.

        Raises:
            DestinationNotAllowedError: chat_id is not allow-listed.
            ValueError: no images or more than 10.
            httpx.HTTPStatusError: Telegram rejected the call.
        """
        self._check(chat_id)
        if not 1 <= len(paths) <= MAX_ALBUM:
            raise ValueError(f"an album holds 1 to {MAX_ALBUM} images, got {len(paths)}")
        media: list[dict[str, Any]] = []
        with ExitStack() as stack:
            files: dict[str, Any] = {}
            for i, original in enumerate(paths):
                path = telegram_copy(original)
                key = f"f{i}"
                files[key] = (path.name, stack.enter_context(path.open("rb")), "image/jpeg")
                item: dict[str, Any] = {"type": "photo", "media": f"attach://{key}"}
                if i == 0 and caption:
                    item["caption"] = caption[:1024]
                media.append(item)
            resp = self._client.post(
                f"{API_BASE}/bot{self._token}/sendMediaGroup",
                data={"chat_id": str(chat_id), "media": json.dumps(media)},
                files=files,
                timeout=MEDIA_TIMEOUT,
            )
        resp.raise_for_status()
        result: list[dict[str, Any]] = resp.json()["result"]
        return result
