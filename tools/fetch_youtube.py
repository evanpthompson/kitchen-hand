#!/usr/bin/env python3
"""Capture a YouTube video's title/description/transcript into inbox/<slug>/youtube.md.

Uses markitdown, which pulls the transcript via YouTube's own transcript API
(no video download, no scraping the page by hand). This is the 'capture'
step only — see docs/ingestion.md for normalize/review/promote.

Usage: tools/fetch_youtube.py <slug> <youtube-url>
"""
import sys
from pathlib import Path

from markitdown import MarkItDown

ROOT = Path(__file__).resolve().parent.parent


def main():
    if len(sys.argv) != 3:
        print("Usage: fetch_youtube.py <slug> <youtube-url>", file=sys.stderr)
        sys.exit(1)

    slug, url = sys.argv[1], sys.argv[2]
    inbox_dir = ROOT / "inbox" / slug
    inbox_dir.mkdir(parents=True, exist_ok=True)

    result = MarkItDown().convert(url)

    (inbox_dir / "youtube.md").write_text(result.markdown)
    (inbox_dir / "url.txt").write_text(url + "\n")

    print(f"Captured to {inbox_dir / 'youtube.md'}")
    print(
        "Reminder: auto-generated transcripts mis-hear numbers/units more often "
        "than any other content. Cross-check every quantity/time/temp against "
        "the description and, if needed, the video itself before normalizing."
    )


if __name__ == "__main__":
    main()
