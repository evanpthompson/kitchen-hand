#!/usr/bin/env python3
"""Turn messages sent to your own Telegram bot into inbox/ captures.

Phase 1 of docs/telegram-ingest-spec.md: text and URLs.

    export KITCHEN_HAND_TELEGRAM_TOKEN=...        # from @BotFather
    export KITCHEN_HAND_TELEGRAM_ALLOWED_IDS=...  # your numeric id
    tools/poll_telegram.py --once

The gap this closes is timing. The DYI export is the only thing that carries a
caption in bulk, but it takes days and cannot be automated; you see a Reel at
9pm on the sofa and everything that gets it into the collection happens at a
desk, later. Copy the caption, share the post to your bot, and the capture
exists in seconds.

**It downloads no one else's media.** Reels and TikToks are never fetched -
Instagram names ClaudeBot in robots.txt and then disallows * outright, and
docs/ingestion.md rules out scraping either platform. Files *you* send to
*your own* bot are a different thing entirely, the same shape as the DYI
export, and Phase 2 handles those.

Phase 1 does capture the text and URL of a message that has media attached,
and records the Telegram file_id in meta.txt so Phase 2 can fetch it later
without you re-sending anything. That is the same backfill shape
import_instagram_saved.py uses: take what is available now, complete it when
the slower path arrives.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

import telegram_transport as tg
from import_instagram_saved import captured_urls, slugify

ROOT = Path(__file__).resolve().parent.parent
INBOX = ROOT / "inbox"
DEFAULT_STATE = ROOT / ".telegram-offset"

ENV_TOKEN = "KITCHEN_HAND_TELEGRAM_TOKEN"
ENV_ALLOWED = "KITCHEN_HAND_TELEGRAM_ALLOWED_IDS"
ENV_STATE = "KITCHEN_HAND_TELEGRAM_STATE"

INSTAGRAM_RE = re.compile(
    r"^https?://(?:www\.)?instagram\.com/(?:p|reel|tv)/([A-Za-z0-9_-]+)"
)
TIKTOK_RE = re.compile(r"^https?://(?:www\.)?tiktok\.com/@([A-Za-z0-9_.]+)/video/(\d+)")
YOUTUBE_RE = re.compile(
    r"^https?://(?:www\.)?(?:youtube\.com/(?:watch\?v=|shorts/)|youtu\.be/)"
    r"([A-Za-z0-9_-]{6,})"
)


# --- config --------------------------------------------------------------


def load_config() -> tuple[str, set[int], Path]:
    """Refuse to start on missing config, naming the key that is missing.

    An unset allow-list is never "allow everyone": anyone who discovers the
    bot's username can message it, so an empty allow-list is the one setting
    that must not have a permissive default.
    """
    token = os.environ.get(ENV_TOKEN, "").strip()
    if not token:
        sys.exit(f"{ENV_TOKEN} is not set. Get a token from @BotFather.")

    raw = os.environ.get(ENV_ALLOWED, "").strip()
    if not raw:
        sys.exit(
            f"{ENV_ALLOWED} is not set. Anyone who finds your bot can message "
            f"it, so this has no default.\nMessage your bot once, then read "
            f"your numeric id from the first getUpdates response."
        )
    try:
        allowed = {int(part) for part in raw.split(",") if part.strip()}
    except ValueError:
        sys.exit(f"{ENV_ALLOWED} must be comma-separated numeric ids, got {raw!r}")
    if not allowed:
        sys.exit(f"{ENV_ALLOWED} parsed to no ids")

    state = Path(os.environ.get(ENV_STATE) or DEFAULT_STATE)
    return token, allowed, state


# --- classification ------------------------------------------------------


def classify(url: str) -> tuple[str, str]:
    """(input_type, slug) for a URL.

    Slugs are provisional, as everywhere else in this pipeline - the dish is
    not known at capture time. Note the asymmetry with the export importer,
    which produces ig-<handle>-<shortcode> because the export carries the
    owner: a bare Instagram URL does not, so this produces ig-<shortcode>.
    Harmless, because dedup is on the permalink rather than the name.
    """
    if m := INSTAGRAM_RE.match(url):
        return "instagram", f"ig-{slugify(m.group(1))}"
    if m := TIKTOK_RE.match(url):
        return "tiktok", f"tt-{slugify(m.group(1))}-{m.group(2)}"
    if m := YOUTUBE_RE.match(url):
        return "youtube", f"yt-{slugify(m.group(1))}"

    host = (urlparse(url).netloc or "unknown").removeprefix("www.")
    digest = hashlib.sha256(url.encode()).hexdigest()[:8]
    return "url", f"url-{slugify(host)}-{digest}"


def slug_for(message: tg.Message) -> tuple[str, str, str | None]:
    """(input_type, slug, url). A message with no URL is still a capture."""
    for url in message.urls:
        input_type, slug = classify(url)
        return input_type, slug, url
    stamp = message.date.replace("-", "").replace(":", "")[:13].replace("T", "-")
    return "pasted-text", f"note-{slugify(stamp)}", None


# --- writing -------------------------------------------------------------


def meta_text(message: tg.Message, input_type: str, url: str | None) -> str:
    lines = [f"input_type: {input_type}"]
    if url:
        lines.append(f"source_url: {url}")
    lines += [
        f"captured_date: {date.today().isoformat()}",
        "post_date: unknown",
        f"telegram_message_id: {message.message_id}",
        f"telegram_sent_at: {message.date}",
    ]
    if message.forwarded_from:
        lines.append(f"forwarded_from: {message.forwarded_from}")
    if message.attachments:
        # Recorded rather than downloaded. file_id is stable for the life of
        # the bot, so Phase 2 can fetch these later with nothing re-sent.
        lines.append(
            "telegram_pending_media: "
            + " ".join(f"{a.kind}:{a.file_id}" for a in message.attachments)
        )
    lines += [
        "",
        "# Captured from Telegram. creator is not recorded because a bare",
        "# post URL does not carry the handle - the DYI export backfills it.",
        "# This folder name is provisional - rename it to the dish slug when",
        "# you normalize into recipes/_drafts/.",
    ]
    return "\n".join(lines) + "\n"


def caption_filename(input_type: str) -> str:
    """Which file the message text becomes, matching docs/ingestion.md."""
    return {
        "instagram": "caption.txt",
        "tiktok": "caption.txt",
        "youtube": "caption.txt",
    }.get(input_type, "raw.txt")


def write_message(
    message: tg.Message,
    folder_name: str,
    url: str | None,
    input_type: str,
    dry_run: bool,
) -> list[str]:
    """Create the folder and any missing files. Never clobbers."""
    folder = INBOX / folder_name
    files: dict[str, str] = {"meta.txt": meta_text(message, input_type, url)}
    if url:
        files["url.txt"] = url + "\n"

    # The text minus the URL that is already in url.txt - a shared link whose
    # only text is the link itself is not a caption.
    body = message.text
    for found in message.urls:
        body = body.replace(found, "")
    body = body.strip()
    if body:
        files[caption_filename(input_type)] = body + "\n"

    written = []
    for name, content in files.items():
        path = folder / name
        if path.exists():
            continue  # never clobber
        written.append(name)
        if not dry_run:
            folder.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
    return sorted(written)


# --- run -----------------------------------------------------------------


def handle(poll_result: tg.Poll, dry_run: bool) -> dict:
    """Write every allowed message. Returns a summary."""
    already = captured_urls()
    summary = {
        "created": [],
        "backfilled": [],
        "unchanged": [],
        "pending_media": 0,
        "rejected": poll_result.rejected,
        "unparsable": poll_result.unparsable,
    }

    for message in poll_result.messages:
        input_type, slug, url = slug_for(message)
        folder_name = already.get(url, slug) if url else slug
        existed = (INBOX / folder_name).is_dir()

        written = write_message(message, folder_name, url, input_type, dry_run)
        if message.attachments:
            summary["pending_media"] += 1

        entry = (folder_name, message, written)
        if not written:
            summary["unchanged"].append(entry)
        elif existed:
            summary["backfilled"].append(entry)
        else:
            summary["created"].append(entry)
    return summary


def report(summary: dict, dry_run: bool) -> None:
    verb = "would create" if dry_run else "created"
    print(f"{verb}: {len(summary['created'])}")
    for slug, message, written in summary["created"]:
        print(f"  {slug}  (+{', '.join(written)})")
    if summary["backfilled"]:
        print(f"added to existing captures: {len(summary['backfilled'])}")
        for slug, _, written in summary["backfilled"]:
            print(f"  {slug}  (+{', '.join(written)})")
    if summary["unchanged"]:
        print(f"already complete: {len(summary['unchanged'])}")
    if summary["pending_media"]:
        print(
            f"\n{summary['pending_media']} message(s) carried media, which "
            "Phase 1 does not download. The file ids are recorded in meta.txt "
            "as telegram_pending_media - nothing needs re-sending."
        )

    sys.stdout.flush()
    if summary["rejected"]:
        ids = sorted({m.sender_id for m in summary["rejected"]})
        print(
            f"\n{len(summary['rejected'])} message(s) from senders not on the "
            f"allow-list were discarded. Sender ids: {ids}",
            file=sys.stderr,
        )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--once",
        action="store_true",
        help="drain what is queued and exit, for cron. Default is to loop.",
    )
    ap.add_argument("--dry-run", action="store_true", help="write nothing")
    ap.add_argument(
        "--allow-unparsed",
        action="store_true",
        help="exit 0 despite updates this does not understand",
    )
    args = ap.parse_args(argv)

    token, allowed, state_path = load_config()
    offset = tg.load_offset(state_path)
    status = 0

    while True:
        try:
            result = tg.poll(token, allowed, offset)
        except tg.TelegramError as e:
            print(f"\nerror: {e}", file=sys.stderr)
            return 1

        if result.messages or result.rejected or result.unparsable:
            summary = handle(result, args.dry_run)
            report(summary, args.dry_run)

            if result.unparsable:
                n = len(result.unparsable)
                print(
                    f"\n{n} update(s) were not messages this understands "
                    "(an edit, a reaction, a callback).",
                    file=sys.stderr,
                )
                if not args.allow_unparsed:
                    print(
                        "error: refusing to report success on a partial run. "
                        "Re-run with --allow-unparsed once you have seen what "
                        "these are.",
                        file=sys.stderr,
                    )
                    status = 1

        # The offset advances only after the captures are on disk. A crash
        # before this point re-delivers the messages, and re-delivery is free
        # because write_message never clobbers.
        if result.next_offset is not None:
            offset = result.next_offset
            if not args.dry_run:
                tg.save_offset(state_path, offset)

        if args.once:
            return status


if __name__ == "__main__":
    sys.exit(main())
