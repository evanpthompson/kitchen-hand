"""Tests for tools/transcribe_audio.py.

No model and no faster-whisper needed: the parts worth testing are the
refusals, the file layout and the low-confidence flagging, and segments are
cheap to fake. Whisper's own accuracy is not this suite's business.

The properties here are the same shape as everywhere else in this repo. A
transcript is machine output that reads exactly like verified text, so the
file has to say it is not, and the segments the model was unsure about have to
be visible rather than blended into the body.
"""

import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().parent.parent / "tools" / "transcribe_audio.py"

spec = importlib.util.spec_from_file_location("transcribe_audio", TOOL)
mod = importlib.util.module_from_spec(spec)
sys.modules["transcribe_audio"] = mod
spec.loader.exec_module(mod)


@dataclass
class FakeSegment:
    """Matches the attributes faster-whisper's Segment exposes."""

    text: str
    start: float = 0.0
    end: float = 5.0
    avg_logprob: float = -0.2
    no_speech_prob: float = 0.01


@dataclass
class _FakeInfo:
    language: str
    duration: float


CONFIDENT = [
    FakeSegment("Start with two tablespoons of butter.", 0, 4),
    FakeSegment("Add three quarters of a cup of heavy cream.", 4, 8),
]


@pytest.fixture
def inbox(tmp_path, monkeypatch):
    d = tmp_path / "inbox"
    d.mkdir()
    monkeypatch.setattr(mod, "INBOX", d)
    return d


@pytest.fixture
def audio(tmp_path):
    f = tmp_path / "reel.wav"
    f.write_bytes(b"RIFF....WAVEfake")
    return f


# --- the transcript file itself ------------------------------------------


def test_transcript_says_it_is_unverified():
    """A transcript reads exactly like text somebody checked. It has to
    announce that it is not, in the file, not just in the terminal."""
    text = mod.render(CONFIDENT, Path("reel.wav"), "small", "en")
    assert "MACHINE GENERATED, NOT VERIFIED" in text
    assert "needs cross-checking" in text
    assert "mis-hears numbers and units" in text
    assert "provenance.transcribed: true" in text


def test_header_records_what_produced_it():
    text = mod.render(CONFIDENT, Path("reel.wav"), "large-v3", "en")
    assert "source file : reel.wav" in text
    assert "model       : faster-whisper large-v3" in text
    assert "language    : en" in text


def test_body_is_the_spoken_text_without_the_hash_prefix():
    text = mod.render(CONFIDENT, Path("reel.wav"), "small", "en")
    body = [ln for ln in text.splitlines() if ln and not ln.startswith("#")]
    assert body == [
        "Start with two tablespoons of butter.",
        "Add three quarters of a cup of heavy cream.",
    ]


def test_empty_segments_are_skipped_not_rendered_as_blank_lines():
    segments = [FakeSegment("Real text."), FakeSegment("   "), FakeSegment("More.")]
    body = [
        ln
        for ln in mod.render(segments, Path("a.wav"), "small", "en").splitlines()
        if ln and not ln.startswith("#")
    ]
    assert body == ["Real text.", "More."]


# --- low confidence ------------------------------------------------------


def test_a_confident_transcript_flags_nothing():
    """The gate must not fire on clean speech, or it becomes noise people
    learn to skip."""
    assert mod.low_confidence(CONFIDENT) == []
    text = mod.render(CONFIDENT, Path("a.wav"), "small", "en")
    assert "0 segment(s) were flagged" in text
    assert "LOW CONFIDENCE SEGMENTS" not in text


def test_a_low_logprob_segment_is_flagged():
    mumbled = FakeSegment("two tablespoons of salt", 12, 15, avg_logprob=-1.1)
    assert mod.low_confidence([*CONFIDENT, mumbled]) == [mumbled]


def test_a_high_no_speech_segment_is_flagged():
    """Whisper hallucinates confident text over near-silence, which is the
    worst case: fluent, plausible, and invented."""
    noise = FakeSegment("Thanks for watching!", 30, 33, no_speech_prob=0.9)
    assert mod.low_confidence([noise]) == [noise]


def test_flagged_segments_are_listed_with_timestamps_and_scores():
    mumbled = FakeSegment("two tablespoons of salt", 75, 92, avg_logprob=-1.1)
    text = mod.render([*CONFIDENT, mumbled], Path("a.wav"), "small", "en")

    assert "1 segment(s) were flagged" in text
    assert "LOW CONFIDENCE SEGMENTS - CHECK THESE FIRST" in text
    assert "[01:15-01:32]" in text
    assert "logprob -1.10" in text
    assert "two tablespoons of salt" in text


def test_a_flagged_segment_still_appears_in_the_body():
    """Flagging marks a segment for review; it never removes it. Dropping
    uncertain text would silently lose a step."""
    mumbled = FakeSegment("two tablespoons of salt", 12, 15, avg_logprob=-1.1)
    text = mod.render([mumbled], Path("a.wav"), "small", "en")
    body = [ln for ln in text.splitlines() if ln and not ln.startswith("#")]
    assert body == ["two tablespoons of salt"]


@pytest.mark.parametrize(
    "seconds, expected", [(0, "00:00"), (9, "00:09"), (75, "01:15"), (3599, "59:59")]
)
def test_timestamp_formatting(seconds, expected):
    assert mod.timestamp(seconds) == expected


# --- refusals ------------------------------------------------------------


def test_an_existing_transcript_is_not_overwritten(inbox, audio):
    folder = inbox / "chengdu-noodles"
    folder.mkdir()
    (folder / "transcript.txt").write_text("corrected by hand: 2 tsp, not 2 tbsp")

    with pytest.raises(SystemExit) as e:
        mod.main(["chengdu-noodles", str(audio)])
    assert "Refusing to overwrite" in str(e.value)
    assert (folder / "transcript.txt").read_text().startswith("corrected by hand")


@pytest.mark.parametrize(
    "name", ["notes.txt", "recipe.pdf", "archive.zip", "video.exe", "noextension"]
)
def test_file_types_off_the_allow_list_are_refused(inbox, tmp_path, name):
    f = tmp_path / name
    f.write_bytes(b"x")
    with pytest.raises(SystemExit) as e:
        mod.main(["some-slug", str(f)])
    assert "unsupported file type" in str(e.value)


@pytest.mark.parametrize("name", ["clip.mp3", "clip.m4a", "clip.mp4", "clip.mov"])
def test_audio_and_video_types_are_transcribed(inbox, tmp_path, monkeypatch, name):
    """Whisper itself is stubbed - this is about the allow-list letting the
    real media types through, and the file landing where it should."""
    f = tmp_path / name
    f.write_bytes(b"x")
    monkeypatch.setattr(
        mod, "transcribe", lambda *a, **k: (CONFIDENT, _FakeInfo("en", 8.0))
    )
    assert mod.main(["some-slug", str(f)]) == 0
    assert (
        "two tablespoons of butter"
        in (inbox / "some-slug" / "transcript.txt").read_text()
    )


def test_an_unreadable_file_refuses_instead_of_raising(inbox, tmp_path, monkeypatch):
    """A .mov that is not really a .mov reaches the decoder and raises from
    inside av. A traceback is not a refusal."""
    f = tmp_path / "clip.mov"
    f.write_bytes(b"not actually a movie")

    def boom(*a, **k):
        raise ValueError("Invalid data found when processing input")

    monkeypatch.setattr(mod, "transcribe", boom)
    with pytest.raises(SystemExit) as e:
        mod.main(["some-slug", str(f)])
    assert "could not read audio from clip.mov" in str(e.value)
    assert "truncated or DRM-protected" in str(e.value)
    assert not (inbox / "some-slug").exists()


def test_a_file_with_no_speech_writes_nothing(inbox, tmp_path, monkeypatch):
    f = tmp_path / "silence.wav"
    f.write_bytes(b"x")
    monkeypatch.setattr(mod, "transcribe", lambda *a, **k: ([], _FakeInfo("en", 3.0)))
    with pytest.raises(SystemExit) as e:
        mod.main(["some-slug", str(f)])
    assert "no speech found" in str(e.value)
    assert not (inbox / "some-slug").exists()


def test_a_missing_file_is_refused(inbox, tmp_path):
    with pytest.raises(SystemExit) as e:
        mod.main(["some-slug", str(tmp_path / "nope.wav")])
    assert "not a file" in str(e.value)


@pytest.mark.parametrize("slug", ["Not_A_Slug", "under_score", "../escape", ""])
def test_an_invalid_slug_is_refused_before_anything_is_written(inbox, audio, slug):
    with pytest.raises(SystemExit) as e:
        mod.main([slug, str(audio)])
    assert "invalid slug" in str(e.value)
    assert list(inbox.iterdir()) == []


def test_the_tool_never_downloads_anything():
    """Not a behavioural test - a pin on the stated contract. Instagram and
    TikTok disallow automated access, and a future edit adding a fetch would
    put this repo in breach of its own docs/ingestion.md."""
    source = TOOL.read_text()
    for forbidden in ("yt_dlp", "youtube_dl", "requests.get", "urllib.request"):
        assert forbidden not in source, f"{forbidden} would make this a downloader"
    assert "does not download anything" in source
