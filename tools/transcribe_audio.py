#!/usr/bin/env python3
"""Transcribe an audio or video file you already have into inbox/<slug>/.

For the sources that stay manual by design - a TikTok, a Reel, a voice note -
where the recipe is spoken rather than written. You supply the file; this does
the speech-to-text and writes inbox/<slug>/transcript.txt.

    uv sync --extra transcribe
    tools/transcribe_audio.py <slug> <file> [--model small] [--language en]

**It does not download anything from anywhere.** Instagram and TikTok both
disallow automated access (instagram.com/robots.txt names ClaudeBot and then
blocks * outright), and docs/ingestion.md rules out scraping them. Getting the
audio onto disk is your step, not this tool's.

Whisper rather than markitdown's built-in audio support, for one reason. That
path is `speech_recognition.recognize_google`, which uploads the audio to
Google and is noticeably weaker on exactly the words that matter here -
"two teaspoons" and "two tablespoons" differ by one phoneme and by a factor of
three. Whisper runs locally, costs nothing, and is better on numbers.

It is still not good enough to trust blind, which is the whole design of the
output: every transcript is written with a header saying so, and any segment
the model was unsure about is listed separately with its timestamp so a human
knows where to look. docs/ingestion.md already warns that "auto-generated
transcripts mis-hear numbers/units more than anything else in the text" - this
tool's job is to make that checkable, not to pretend it solved it.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INBOX = ROOT / "inbox"

# Allow-list, not a filter. Anything not named here is refused rather than
# handed to a decoder to find out.
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".wma"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".webm", ".mkv", ".avi"}

# Whisper reports two per-segment numbers. Below/above these, a segment is
# worth a human's eyes. The thresholds are deliberately loose: a false flag
# costs ten seconds of reading, a missed one costs a wrong quantity.
MIN_AVG_LOGPROB = -0.6
MAX_NO_SPEECH_PROB = 0.5

MODELS = ("tiny", "base", "small", "medium", "large-v3", "large-v3-turbo")


def _slug_dir(slug: str) -> Path:
    import re

    if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", slug):
        sys.exit(f"invalid slug: {slug!r} - lowercase, digits and single hyphens")
    return INBOX / slug


def header(source: Path, model: str, language: str | None, flagged: int) -> str:
    return (
        f"# Transcript - MACHINE GENERATED, NOT VERIFIED\n"
        f"#\n"
        f"# source file : {source.name}\n"
        f"# model       : faster-whisper {model}\n"
        f"# language    : {language or 'auto-detected'}\n"
        f"# transcribed : {date.today().isoformat()}\n"
        f"#\n"
        f"# Every quantity, time and temperature below needs cross-checking\n"
        f"# against the video before it goes into a draft. Speech-to-text\n"
        f"# mis-hears numbers and units more than any other content, and a\n"
        f"# wrong quantity reads exactly like a right one.\n"
        f"#\n"
        f"# {flagged} segment(s) were flagged as low confidence - listed at the\n"
        f"# end of this file with timestamps.\n"
        f"#\n"
        f"# Set provenance.transcribed: true on any draft built from this.\n"
        f"\n"
    )


def timestamp(seconds: float) -> str:
    return f"{int(seconds) // 60:02d}:{int(seconds) % 60:02d}"


def low_confidence(segments) -> list:
    """Segments a human should re-listen to.

    Whisper reports avg_logprob (how sure it was of the words) and
    no_speech_prob (how sure it was there were words at all). Either one going
    the wrong way is enough to flag: the cost of a false flag is ten seconds
    of reading, and the cost of a missed one is a wrong quantity that reads
    exactly like a right one.
    """
    return [
        s
        for s in segments
        if s.avg_logprob < MIN_AVG_LOGPROB or s.no_speech_prob > MAX_NO_SPEECH_PROB
    ]


def render(segments, source: Path, model: str, language: str | None) -> str:
    """The whole transcript file, header and flagged segments included."""
    flagged = low_confidence(segments)
    parts = [header(source, model, language, len(flagged))]
    parts.append("\n".join(s.text.strip() for s in segments if s.text.strip()))
    parts.append("\n")
    if flagged:
        parts.append("\n\n# --- LOW CONFIDENCE SEGMENTS - CHECK THESE FIRST ---\n")
        for s in flagged:
            parts.append(
                f"# [{timestamp(s.start)}-{timestamp(s.end)}] "
                f"(logprob {s.avg_logprob:.2f}, no-speech {s.no_speech_prob:.2f})\n"
                f"#   {s.text.strip()}\n"
            )
    return "".join(parts)


def transcribe(path: Path, model_name: str, language: str | None):
    """Returns (segments, info). Import is local so --help works without the extra."""
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        sys.exit(
            "faster-whisper is not installed. It is an optional extra so a plain\n"
            "clone stays light:\n\n"
            "    uv sync --extra transcribe\n"
        )

    # int8 on CPU: this runs on a laptop while you do something else, and the
    # accuracy difference on speech this clean does not justify float32.
    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    segments, info = model.transcribe(
        str(path),
        language=language,
        vad_filter=True,  # drop silence, which otherwise hallucinates text
        beam_size=5,
    )
    return list(segments), info


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("slug", help="inbox folder to write into; created if absent")
    ap.add_argument("file", type=Path, help="audio or video file you already have")
    ap.add_argument(
        "--model",
        default="small",
        choices=MODELS,
        help=(
            "whisper model (default: small). Larger is better on numbers and "
            "slower; the model downloads once on first use."
        ),
    )
    ap.add_argument(
        "--language",
        help="ISO code, e.g. en. Omit to auto-detect, which costs a little time.",
    )
    ap.add_argument(
        "--force",
        action="store_true",
        help="overwrite an existing transcript.txt (refused by default)",
    )
    args = ap.parse_args(argv)

    source = args.file
    if not source.is_file():
        sys.exit(f"not a file: {source}")
    suffix = source.suffix.lower()
    if suffix not in AUDIO_EXTENSIONS | VIDEO_EXTENSIONS:
        sys.exit(
            f"unsupported file type: {suffix or '(none)'}\n"
            f"audio: {', '.join(sorted(AUDIO_EXTENSIONS))}\n"
            f"video: {', '.join(sorted(VIDEO_EXTENSIONS))}"
        )

    folder = _slug_dir(args.slug)
    out = folder / "transcript.txt"
    if out.exists() and not args.force:
        sys.exit(
            f"{out} already exists. Refusing to overwrite a transcript you may\n"
            f"have corrected by hand - pass --force if you really mean to."
        )

    print(f"transcribing {source.name} with faster-whisper {args.model} ...")
    try:
        segments, info = transcribe(source, args.model, args.language)
    except SystemExit:
        raise
    except Exception as e:
        # A file with the right extension and the wrong contents reaches the
        # decoder and raises from deep inside av/ctranslate2. A traceback is
        # not an answer, and "it printed something red" is not a refusal.
        sys.exit(
            f"could not read audio from {source.name}: {type(e).__name__}: {e}\n"
            f"The extension says {suffix} - check the file is really that, and "
            f"is not truncated or DRM-protected."
        )
    if not segments:
        sys.exit("no speech found in that file - nothing written")

    text = render(
        segments, source, args.model, getattr(info, "language", args.language)
    )
    flagged = low_confidence(segments)

    folder.mkdir(parents=True, exist_ok=True)
    out.write_text(text)

    duration = getattr(info, "duration", None)
    print(f"wrote {out}")
    print(f"  segments        : {len(segments)}")
    print(f"  low confidence  : {len(flagged)}")
    if duration:
        print(f"  audio duration  : {timestamp(duration)}")
    print(
        "\nCross-check every quantity, time and temperature against the video "
        "before using this in a draft, and set provenance.transcribed: true."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
