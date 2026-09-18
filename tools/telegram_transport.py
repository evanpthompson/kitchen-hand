#!/usr/bin/env python3
"""Telegram Bot API transport. Knows nothing about recipes.

Polls `getUpdates`, filters to an allow-list of senders, and yields normalized
message dicts. Everything that knows what a message *means* lives in the
caller - see tools/poll_telegram.py.

**This module must not import anything from kitchen-hand.** Not
`write_capture`, not `INBOX`, not the slug rules, not the service's `app`
package. That is enforced by a test, not by discipline, because it is what
keeps this file cheap to extract to its own repo when a second project needs
it. See docs/telegram-ingest-spec.md, "Why not its own repo, yet".

Long polling, never webhooks. A webhook needs a public HTTPS endpoint, which
is what ruled out WhatsApp for this job in the first place; `getUpdates` lets
a script behind NAT pull with nothing exposed.

Stdlib only, deliberately - urllib rather than requests - so extraction has
no dependency story to carry either.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

API_ROOT = "https://api.telegram.org/bot"

# Long-poll seconds held open by Telegram. Well under any sane socket timeout.
POLL_TIMEOUT = 25
HTTP_TIMEOUT = POLL_TIMEOUT + 10

_URL_RE = re.compile(r"https?://[^\s<>\"]+")


class TelegramError(RuntimeError):
    """The API answered, and the answer was no."""


@dataclass(frozen=True)
class Attachment:
    """A file on a message, identified but not yet downloaded.

    file_id is stable for the life of the bot, so recording it is enough to
    fetch the file later. That is what lets text be captured now and media
    backfilled afterwards without re-sending the message.
    """

    file_id: str
    kind: str  # photo | voice | audio | video | video_note | document
    original_name: str | None = None


@dataclass(frozen=True)
class Message:
    """One inbound message, flattened into what a sink actually needs."""

    message_id: int
    sender_id: int
    date: str  # ISO 8601, UTC
    text: str = ""
    urls: tuple[str, ...] = ()
    attachments: tuple[Attachment, ...] = ()
    forwarded_from: str | None = None
    # URLs from the message this one replies to. A caption sent as a reply to
    # a shared link has nothing joinable of its own, and the parent is where
    # the link is - so the reply carries it forward rather than the caller
    # having to keep its own history.
    reply_urls: tuple[str, ...] = ()
    raw: dict = field(default_factory=dict, repr=False, compare=False)


# --- HTTP ----------------------------------------------------------------


def call(token: str, method: str, params: dict | None = None) -> dict:
    """One Bot API call. Raises TelegramError on anything but ok:true."""
    url = f"{API_ROOT}{token}/{method}"
    data = urllib.parse.urlencode(params or {}).encode()
    request = urllib.request.Request(url, data=data)
    try:
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as response:
            payload = json.loads(response.read())
    except urllib.error.HTTPError as e:
        # Telegram puts a usable reason in the body even on a 4xx, and the
        # status alone ("400") is not something anyone can act on.
        body = e.read().decode(errors="replace")[:300]
        raise TelegramError(f"{method} failed: HTTP {e.code}: {body}") from e
    except urllib.error.URLError as e:
        raise TelegramError(f"{method} failed: {e.reason}") from e

    if not payload.get("ok"):
        raise TelegramError(
            f"{method} refused: {payload.get('description', payload)!r}"
        )
    return payload.get("result")


# --- parsing -------------------------------------------------------------


def extract_urls(message: dict) -> tuple[str, ...]:
    """URLs from the message, entities first.

    Telegram marks up links it recognised in `entities`, which is more
    reliable than a regex over the text - it gets the boundaries right, and
    `text_link` entities carry a URL that is not in the text at all. The
    regex is a fallback for a message whose entities are absent.
    """
    text = message.get("text") or message.get("caption") or ""
    found: list[str] = []

    entities = message.get("entities") or message.get("caption_entities") or []
    for entity in entities:
        if entity.get("type") == "text_link" and entity.get("url"):
            found.append(entity["url"])
        elif entity.get("type") == "url":
            offset, length = entity.get("offset", 0), entity.get("length", 0)
            # Telegram offsets are in UTF-16 code units, not characters. For
            # anything outside the BMP - emoji, which captions are full of -
            # slicing the str directly lands in the wrong place.
            encoded = text.encode("utf-16-le")
            found.append(
                encoded[offset * 2 : (offset + length) * 2].decode(
                    "utf-16-le", errors="replace"
                )
            )

    if not found:
        found = _URL_RE.findall(text)

    seen: list[str] = []
    for url in found:
        cleaned = url.rstrip(".,);]")
        if cleaned and cleaned not in seen:
            seen.append(cleaned)
    return tuple(seen)


def extract_attachments(message: dict) -> tuple[Attachment, ...]:
    """Files on the message, identified only. Nothing is downloaded here."""
    out: list[Attachment] = []

    photos = message.get("photo") or []
    if photos:
        # Telegram sends every resolution; the last is the largest.
        largest = max(photos, key=lambda p: p.get("file_size", 0))
        out.append(Attachment(largest["file_id"], "photo"))

    for kind in ("voice", "audio", "video", "video_note", "document"):
        item = message.get(kind)
        if isinstance(item, dict) and item.get("file_id"):
            out.append(Attachment(item["file_id"], kind, item.get("file_name")))
    return tuple(out)


def forwarded_from(message: dict) -> str | None:
    origin = message.get("forward_origin") or {}
    if origin:
        chat = origin.get("chat") or origin.get("sender_chat") or {}
        user = origin.get("sender_user") or {}
        return (
            origin.get("sender_user_name")
            or chat.get("title")
            or chat.get("username")
            or user.get("username")
            or user.get("first_name")
        )
    # Pre-2023 field, still sent by some clients.
    legacy = message.get("forward_from") or message.get("forward_from_chat")
    if isinstance(legacy, dict):
        return legacy.get("username") or legacy.get("title") or legacy.get("first_name")
    return None


def parse_message(message: dict) -> Message:
    sender = message.get("from") or {}
    epoch = message.get("date")
    when = (
        datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()
        if isinstance(epoch, int)
        else datetime.now(tz=timezone.utc).isoformat()
    )
    parent = message.get("reply_to_message")
    return Message(
        message_id=message.get("message_id", 0),
        sender_id=sender.get("id", 0),
        date=when,
        text=(message.get("text") or message.get("caption") or "").strip(),
        urls=extract_urls(message),
        attachments=extract_attachments(message),
        forwarded_from=forwarded_from(message),
        reply_urls=extract_urls(parent) if isinstance(parent, dict) else (),
        raw=message,
    )


# --- polling -------------------------------------------------------------


@dataclass
class Poll:
    """What one getUpdates round produced."""

    messages: list[Message] = field(default_factory=list)
    rejected: list[Message] = field(default_factory=list)  # sender not allowed
    unparsable: list[dict] = field(default_factory=list)
    next_offset: int | None = None


def poll(
    token: str,
    allowed_ids: set[int],
    offset: int | None = None,
    timeout: int = POLL_TIMEOUT,
) -> Poll:
    """One getUpdates round.

    An empty allow-list is a programming error here rather than a permissive
    default - the caller is responsible for refusing to start without one, and
    this refuses to be handed one anyway.
    """
    if not allowed_ids:
        raise ValueError("allowed_ids is empty; refusing to accept every sender")

    params: dict = {"timeout": timeout}
    if offset is not None:
        params["offset"] = offset

    result = poll.call(token, "getUpdates", params)  # type: ignore[attr-defined]
    out = Poll()
    for update in result or []:
        update_id = update.get("update_id")
        if isinstance(update_id, int):
            out.next_offset = update_id + 1

        message = update.get("message") or update.get("channel_post")
        if not isinstance(message, dict) or not message.get("from"):
            # An update shape this does not understand - an edit, a reaction,
            # a callback. Reported, never silently dropped.
            out.unparsable.append(update)
            continue

        parsed = parse_message(message)
        (out.messages if parsed.sender_id in allowed_ids else out.rejected).append(
            parsed
        )
    return out


# Indirection so tests can supply responses without a network or a token.
poll.call = call  # type: ignore[attr-defined]


# --- offset persistence --------------------------------------------------
#
# Mechanism only. *When* to save is a policy the caller owns, because only the
# caller knows whether the work the message caused actually succeeded.


def load_offset(path: Path) -> int | None:
    try:
        return int(path.read_text().strip())
    except (FileNotFoundError, ValueError):
        return None


def save_offset(path: Path, offset: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{offset}\n")
