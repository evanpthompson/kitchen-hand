"""Tests for tools/telegram_transport.py and tools/poll_telegram.py.

No network and no token. getUpdates returns JSON, so fixtures are cheap and
the transport's one HTTP call is injected.

Two properties here are not about behaviour at all, and both are deliberate:
that the transport contains no kitchen-hand reference (which is what keeps it
cheap to extract), and that neither file fetches a creator's media (which is
what keeps this repo inside its own docs/ingestion.md).
"""

import ast
import importlib.util
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parent.parent / "tools"
TRANSPORT = TOOLS / "telegram_transport.py"
SINK = TOOLS / "poll_telegram.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


sys.path.insert(0, str(TOOLS))
tg = _load(TRANSPORT, "telegram_transport")
sink = _load(SINK, "poll_telegram")


# Obviously-synthetic ids. An earlier demo printed a plausible-looking one
# and it got copied straight into a real .env, where it silently discarded
# every message - so these are chosen to be unmistakable if they ever escape.
ME = 10000000001
STRANGER = 10000000002
PLACEHOLDER = 10000000003  # in the allow-list, never sends anything


def url_entity(text: str, url: str) -> dict:
    """A `url` entity with offset and length in UTF-16 units, as Telegram
    sends them. Computed rather than hand-counted, because hand-counting them
    is exactly the mistake the code under test exists to survive."""
    before = text[: text.index(url)]
    return {
        "type": "url",
        "offset": len(before.encode("utf-16-le")) // 2,
        "length": len(url.encode("utf-16-le")) // 2,
    }


def update(
    update_id: int = 1,
    text: str = "",
    sender: int = ME,
    entities: list | None = None,
    photo: bool = False,
    voice: bool = False,
    forward: str | None = None,
    reply_to: dict | None = None,
) -> dict:
    message = {
        "message_id": update_id * 10,
        "from": {"id": sender, "first_name": "Evan"},
        "date": 1_789_000_000,
        "text": text,
    }
    if entities is not None:
        message["entities"] = entities
    if photo:
        message["photo"] = [
            {"file_id": "small", "file_size": 100},
            {"file_id": "large", "file_size": 9000},
        ]
    if voice:
        message["voice"] = {"file_id": "voice-1", "duration": 12}
    if forward:
        message["forward_origin"] = {"type": "user", "sender_user_name": forward}
    if reply_to is not None:
        message["reply_to_message"] = reply_to["message"]
    return {"update_id": update_id, "message": message}


@pytest.fixture
def api(monkeypatch):
    """Replace the transport's one HTTP call with a scripted response."""

    def factory(updates):
        monkeypatch.setattr(tg.poll, "call", lambda *a, **k: updates)

    return factory


@pytest.fixture
def inbox(tmp_path, monkeypatch):
    d = tmp_path / "inbox"
    d.mkdir()
    monkeypatch.setattr(sink, "INBOX", d)
    monkeypatch.setattr(sink, "captured_urls", lambda: _urls_in(d))
    return d


def _urls_in(inbox_dir):
    seen = {}
    for folder in sorted(inbox_dir.iterdir()):
        url_file = folder / "url.txt"
        if folder.is_dir() and url_file.is_file():
            for line in url_file.read_text().splitlines():
                if line.strip():
                    seen.setdefault(line.strip(), folder.name)
    return seen


@pytest.fixture
def configured(monkeypatch, tmp_path):
    monkeypatch.setenv(sink.ENV_TOKEN, "test-token")
    monkeypatch.setenv(sink.ENV_ALLOWED, str(ME))
    monkeypatch.setenv(sink.ENV_STATE, str(tmp_path / "offset"))
    return tmp_path / "offset"


# --- the two structural guards -------------------------------------------


STDLIB_ONLY = {
    "__future__",
    "json",
    "re",
    "urllib",
    "dataclasses",
    "datetime",
    "pathlib",
}


def test_the_transport_imports_only_the_standard_library():
    """Not a behavioural test - a pin on the import direction.

    The transport is stdlib-only on purpose, so that moving it to its own repo
    when a second project needs it is a git mv rather than a rewrite. A
    convenience import from kitchen-hand would silently turn that into a
    rewrite, and nobody would notice until the day it mattered.

    Parsed rather than grepped. A grep over the source cannot tell an import
    from the docstring that says not to write one - the first version of this
    test failed on the module's own prose - and it would miss a renamed
    helper. The import table is the actual property.
    """
    tree = ast.parse(TRANSPORT.read_text())
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])

    assert imported <= STDLIB_ONLY, (
        f"transport imports {sorted(imported - STDLIB_ONLY)}; it must stay "
        f"stdlib-only so it can be extracted without a rewrite"
    )


def test_the_sink_is_the_half_that_knows_about_recipes():
    """The other side of the same rule: poll_telegram.py is allowed - and
    expected - to import from kitchen-hand. If it ever stops, the knowledge
    has leaked into the transport."""
    tree = ast.parse(SINK.read_text())
    modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert "import_instagram_saved" in modules
    assert "telegram_transport" in {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }


@pytest.mark.parametrize("path", [TRANSPORT, SINK])
def test_neither_file_fetches_anyone_elses_media(path):
    """docs/ingestion.md rules out scraping Instagram and TikTok, and both
    disallow automated access. getFile - files you sent to your own bot - is
    a different thing and arrives in Phase 2."""
    source = path.read_text()
    for forbidden in ("instagram.com/p/", "cdninstagram", "tiktokcdn", "yt_dlp"):
        assert forbidden not in source


# --- transport: parsing --------------------------------------------------


def test_urls_come_from_entities_not_a_regex():
    """Telegram marks up the links it recognised; entity offsets are exact
    where a regex has to guess where a URL stops."""
    text = "Look at this https://www.instagram.com/reel/ABC123/ so good"
    url = "https://www.instagram.com/reel/ABC123/"
    u = update(text=text, entities=[url_entity(text, url)])
    assert tg.parse_message(u["message"]).urls == (
        "https://www.instagram.com/reel/ABC123/",
    )


def test_entity_offsets_are_utf16_not_characters():
    """The bug this guards: Telegram counts UTF-16 code units, so one emoji
    before the link shifts a character-based slice by one and silently
    truncates the URL. Recipe captions are full of emoji."""
    text = "\U0001f35c yum https://www.instagram.com/reel/ABC123/"
    url = "https://www.instagram.com/reel/ABC123/"
    entity = url_entity(text, url)
    # The emoji is a surrogate pair: 2 UTF-16 units but 1 Python character, so
    # a character-based slice at this offset lands one short and silently
    # truncates the trailing slash.
    assert entity["offset"] == text.index(url) + 1
    u = update(text=text, entities=[entity])
    assert tg.parse_message(u["message"]).urls == (
        "https://www.instagram.com/reel/ABC123/",
    )


def test_a_text_link_entity_carries_a_url_not_in_the_text():
    u = update(
        text="this recipe",
        entities=[
            {"type": "text_link", "offset": 0, "length": 11, "url": "https://x.test/r"}
        ],
    )
    assert tg.parse_message(u["message"]).urls == ("https://x.test/r",)


def test_a_bare_url_with_no_entities_still_parses():
    u = update(text="https://www.instagram.com/reel/ABC123/")
    assert tg.parse_message(u["message"]).urls == (
        "https://www.instagram.com/reel/ABC123/",
    )


def test_trailing_punctuation_is_trimmed_from_a_regex_match():
    u = update(text="see https://x.test/recipe.")
    assert tg.parse_message(u["message"]).urls == ("https://x.test/recipe",)


def test_the_largest_photo_size_is_the_one_recorded():
    """Telegram sends every resolution; a screenshot of a recipe card is
    worthless at thumbnail size."""
    m = tg.parse_message(update(photo=True)["message"])
    assert [a.file_id for a in m.attachments] == ["large"]


def test_a_voice_note_is_identified_but_not_downloaded():
    m = tg.parse_message(update(voice=True)["message"])
    assert [(a.kind, a.file_id) for a in m.attachments] == [("voice", "voice-1")]


def test_a_forwarded_message_records_where_it_came_from():
    m = tg.parse_message(update(forward="chef.mike")["message"])
    assert m.forwarded_from == "chef.mike"


# --- transport: polling and the allow-list -------------------------------


def test_only_allowed_senders_become_messages(api):
    api([update(1, "mine", sender=ME), update(2, "theirs", sender=STRANGER)])
    result = tg.poll("t", {ME})
    assert [m.text for m in result.messages] == ["mine"]
    assert [m.sender_id for m in result.rejected] == [STRANGER]


def test_an_empty_allow_list_is_refused_outright():
    """Never "allow everyone". Anyone who finds the bot can message it."""
    with pytest.raises(ValueError, match="refusing to accept every sender"):
        tg.poll("t", set())


def test_an_update_that_is_not_a_message_is_reported_not_dropped(api):
    api([{"update_id": 5, "edited_message": {"text": "x"}}])
    result = tg.poll("t", {ME})
    assert result.messages == [] and len(result.unparsable) == 1
    assert result.next_offset == 6


def test_next_offset_is_one_past_the_last_update(api):
    api([update(7), update(8)])
    assert tg.poll("t", {ME}).next_offset == 9


def test_offset_round_trips_through_the_state_file(tmp_path):
    path = tmp_path / "nested" / "offset"
    assert tg.load_offset(path) is None
    tg.save_offset(path, 42)
    assert tg.load_offset(path) == 42


def test_a_corrupt_offset_file_reads_as_no_offset(tmp_path):
    path = tmp_path / "offset"
    path.write_text("not a number")
    assert tg.load_offset(path) is None


# --- sink: classification ------------------------------------------------


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://www.instagram.com/reel/C_aB3xy/", ("instagram", "ig-c-ab3xy")),
        ("https://instagram.com/p/ABC123/", ("instagram", "ig-abc123")),
        (
            "https://www.tiktok.com/@chef.mike/video/7123456789",
            ("tiktok", "tt-chef-mike-7123456789"),
        ),
        ("https://youtu.be/dQw4w9WgXcQ", ("youtube", "yt-dqw4w9wgxcq")),
    ],
)
def test_known_platforms_get_a_readable_slug(url, expected):
    assert sink.classify(url) == expected


def test_an_unknown_url_is_slugged_by_host_and_hash():
    kind, slug = sink.classify("https://smittenkitchen.com/2020/01/soup/")
    assert kind == "url"
    assert slug.startswith("url-smittenkitchen-com-")
    # Same URL, same slug - so a re-send does not make a second folder.
    assert sink.classify("https://smittenkitchen.com/2020/01/soup/")[1] == slug


def test_two_different_urls_on_the_same_host_get_different_slugs():
    a = sink.classify("https://x.test/one")[1]
    b = sink.classify("https://x.test/two")[1]
    assert a != b


# --- sink: writing -------------------------------------------------------


def test_a_shared_link_with_a_pasted_caption_becomes_a_full_capture(inbox, api):
    api(
        [
            update(
                1,
                "https://www.instagram.com/reel/ABC123/\n\n2 eggs\n1 tbsp soy sauce",
            )
        ]
    )
    sink.handle(tg.poll("t", {ME}), dry_run=False)

    folder = inbox / "ig-abc123"
    assert sorted(p.name for p in folder.iterdir()) == [
        "caption.txt",
        "meta.txt",
        "url.txt",
    ]
    assert "2 eggs" in (folder / "caption.txt").read_text()
    assert "input_type: instagram" in (folder / "meta.txt").read_text()


def test_a_link_with_no_other_text_writes_no_caption(inbox, api):
    """The link is already in url.txt; a caption.txt containing only the URL
    would make the capture look complete when it is not."""
    api([update(1, "https://www.instagram.com/reel/ABC123/")])
    sink.handle(tg.poll("t", {ME}), dry_run=False)

    folder = inbox / "ig-abc123"
    assert sorted(p.name for p in folder.iterdir()) == ["meta.txt", "url.txt"]


# --- reply threading ------------------------------------------------------


def test_a_reply_inherits_the_parent_messages_url(inbox, api):
    """The natural gesture: share the link, then reply to it with the caption
    you copied. The caption has no link of its own."""
    link = update(1, "https://www.instagram.com/reel/ABC123/")
    api([link])
    sink.handle(tg.poll("t", {ME}), dry_run=False)

    api([update(2, "2 eggs\n1 tbsp soy sauce", reply_to=link)])
    summary = sink.handle(tg.poll("t", {ME}), dry_run=False)

    assert [p.name for p in inbox.iterdir()] == ["ig-abc123"]
    assert "2 eggs" in (inbox / "ig-abc123" / "caption.txt").read_text()
    assert len(summary["backfilled"]) == 1
    assert not summary["orphans"]


def test_a_reply_is_classified_by_the_parents_platform(inbox, api):
    """caption.txt rather than raw.txt - the reply is an Instagram capture
    because the post it answers is."""
    link = update(1, "https://www.instagram.com/reel/ABC123/")
    api([link])
    sink.handle(tg.poll("t", {ME}), dry_run=False)

    api([update(2, "steps here", reply_to=link)])
    sink.handle(tg.poll("t", {ME}), dry_run=False)
    assert (inbox / "ig-abc123" / "caption.txt").is_file()
    assert not (inbox / "ig-abc123" / "raw.txt").exists()


def test_the_messages_own_url_wins_over_its_parents(inbox, api):
    """Replying to one post while pasting a different link is about the link
    you pasted, not the one you happened to reply to."""
    link = update(1, "https://www.instagram.com/reel/PARENT/")
    api([link])
    sink.handle(tg.poll("t", {ME}), dry_run=False)

    api([update(2, "https://www.instagram.com/reel/OWN1/ notes", reply_to=link)])
    sink.handle(tg.poll("t", {ME}), dry_run=False)
    assert (inbox / "ig-own1" / "url.txt").is_file()


def test_a_reply_to_a_message_with_no_url_is_still_an_orphan(inbox, api, capsys):
    plain = update(1, "hello")
    api([update(2, "2 eggs", reply_to=plain)])
    summary = sink.handle(tg.poll("t", {ME}), dry_run=False)
    assert len(summary["orphans"]) == 1


def test_an_unattached_caption_is_reported_not_filed_silently(inbox, api, capsys):
    """Filing a caption away from its recipe leaves two half-captures of one
    dish, and nothing says so."""
    api([update(1, "2 eggs\n1 tbsp soy sauce")])
    summary = sink.handle(tg.poll("t", {ME}), dry_run=False)
    sink.report(summary, dry_run=False)

    out = capsys.readouterr().out
    assert "had no link and did not reply to one" in out
    assert "reply to the message carrying its link" in out


def test_a_link_only_message_is_not_an_orphan(inbox, api):
    """The gate must not fire on the ordinary case, or it becomes noise."""
    api([update(1, "https://www.instagram.com/reel/ABC123/")])
    assert not sink.handle(tg.poll("t", {ME}), dry_run=False)["orphans"]


def test_a_message_with_no_url_is_still_a_capture(inbox, api):
    api([update(1, "Mum's shortbread: 2 parts flour, 1 sugar, 1 butter")])
    sink.handle(tg.poll("t", {ME}), dry_run=False)

    folders = list(inbox.iterdir())
    assert len(folders) == 1 and folders[0].name.startswith("note-")
    assert (folders[0] / "raw.txt").read_text().startswith("Mum's shortbread")
    assert "input_type: pasted-text" in (folders[0] / "meta.txt").read_text()


def test_resending_the_same_link_does_not_clobber_a_corrected_caption(inbox, api):
    api([update(1, "https://www.instagram.com/reel/ABC123/\ncaption")])
    sink.handle(tg.poll("t", {ME}), dry_run=False)
    (inbox / "ig-abc123" / "caption.txt").write_text("corrected: 2 tsp not 2 tbsp")

    api([update(2, "https://www.instagram.com/reel/ABC123/\ncaption")])
    sink.handle(tg.poll("t", {ME}), dry_run=False)
    assert (
        inbox / "ig-abc123" / "caption.txt"
    ).read_text() == "corrected: 2 tsp not 2 tbsp"


def test_a_later_message_backfills_a_url_only_capture(inbox, api):
    """The two-speed pipeline within Telegram itself: share the link now,
    paste the caption when you have read it."""
    api([update(1, "https://www.instagram.com/reel/ABC123/")])
    sink.handle(tg.poll("t", {ME}), dry_run=False)
    assert not (inbox / "ig-abc123" / "caption.txt").exists()

    api([update(2, "https://www.instagram.com/reel/ABC123/\n2 eggs")])
    summary = sink.handle(tg.poll("t", {ME}), dry_run=False)
    assert "2 eggs" in (inbox / "ig-abc123" / "caption.txt").read_text()
    assert len(summary["backfilled"]) == 1 and not summary["created"]


def test_a_link_already_captured_under_another_name_is_not_duplicated(inbox, api):
    """Dedup is on the permalink, so a folder already renamed to its dish
    slug is the one that gets added to."""
    folder = inbox / "chengdu-tomato-egg-noodles"
    folder.mkdir()
    (folder / "url.txt").write_text("https://www.instagram.com/reel/ABC123/\n")

    api([update(1, "https://www.instagram.com/reel/ABC123/\n2 eggs")])
    sink.handle(tg.poll("t", {ME}), dry_run=False)

    assert [p.name for p in inbox.iterdir()] == ["chengdu-tomato-egg-noodles"]
    assert (folder / "caption.txt").is_file()


def test_media_is_recorded_for_phase_two_not_downloaded(inbox, api):
    api(
        [
            update(
                1,
                "https://www.instagram.com/reel/ABC123/ steps in the images",
                photo=True,
            )
        ]
    )
    summary = sink.handle(tg.poll("t", {ME}), dry_run=False)

    meta = (inbox / "ig-abc123" / "meta.txt").read_text()
    assert "telegram_pending_media: photo:large" in meta
    assert not (inbox / "ig-abc123" / "screenshot.png").exists()
    assert summary["pending_media"] == 1


def test_dry_run_writes_nothing(inbox, api):
    api([update(1, "https://www.instagram.com/reel/ABC123/\n2 eggs")])
    sink.handle(tg.poll("t", {ME}), dry_run=True)
    assert list(inbox.iterdir()) == []


# --- sink: config and run ------------------------------------------------


def test_a_missing_token_refuses_to_start(monkeypatch):
    monkeypatch.delenv(sink.ENV_TOKEN, raising=False)
    monkeypatch.setenv(sink.ENV_ALLOWED, str(ME))
    with pytest.raises(SystemExit) as e:
        sink.load_config()
    assert sink.ENV_TOKEN in str(e.value)


def test_a_missing_allow_list_refuses_to_start(monkeypatch):
    """Missing config is never a permissive default."""
    monkeypatch.setenv(sink.ENV_TOKEN, "t")
    monkeypatch.delenv(sink.ENV_ALLOWED, raising=False)
    with pytest.raises(SystemExit) as e:
        sink.load_config()
    assert sink.ENV_ALLOWED in str(e.value)
    assert "no default" in str(e.value)


def test_a_non_numeric_allow_list_refuses_to_start(monkeypatch):
    monkeypatch.setenv(sink.ENV_TOKEN, "t")
    monkeypatch.setenv(sink.ENV_ALLOWED, "@evan")
    with pytest.raises(SystemExit) as e:
        sink.load_config()
    assert "numeric ids" in str(e.value)


# --- --whoami: the bootstrap path ----------------------------------------


def test_whoami_lists_senders_without_an_allow_list(monkeypatch, capsys, tmp_path):
    """Breaks a real loop: the allow-list is required to run, and the only way
    to learn your own id is to read it off a getUpdates response."""
    monkeypatch.setenv(sink.ENV_TOKEN, "t")
    monkeypatch.delenv(sink.ENV_ALLOWED, raising=False)
    monkeypatch.setattr(
        tg.poll, "call", lambda *a, **k: [update(1, "hello", sender=ME)]
    )

    assert sink.main(["--whoami"]) == 0
    out = capsys.readouterr().out
    assert str(ME) in out
    assert f"export {sink.ENV_ALLOWED}={ME}" in out


def test_whoami_flags_an_allow_list_that_does_not_match(monkeypatch, capsys):
    """The failure this prevents is close to undebuggable from its symptom:
    --once exits 0 and prints "created: 0" while discarding everything."""
    monkeypatch.setenv(sink.ENV_TOKEN, "t")
    monkeypatch.setenv(sink.ENV_ALLOWED, str(PLACEHOLDER))
    monkeypatch.setattr(tg.poll, "call", lambda *a, **k: [update(1, "hi", sender=ME)])

    assert sink.main(["--whoami"]) == 1
    captured = capsys.readouterr()
    assert "NOT on your allow-list" in captured.out
    assert "MISMATCH" in captured.err
    assert str(PLACEHOLDER) in captured.err and str(ME) in captured.err
    assert "still exit 0" in captured.err


def test_whoami_says_nothing_to_change_when_it_matches(monkeypatch, capsys):
    monkeypatch.setenv(sink.ENV_TOKEN, "t")
    monkeypatch.setenv(sink.ENV_ALLOWED, str(ME))
    monkeypatch.setattr(tg.poll, "call", lambda *a, **k: [update(1, "hi", sender=ME)])

    assert sink.main(["--whoami"]) == 0
    captured = capsys.readouterr()
    assert "on your allow-list" in captured.out
    assert "set correctly" in captured.out
    assert captured.err == ""


def test_whoami_names_a_stale_id_that_sent_nothing(monkeypatch, capsys):
    """A placeholder left in the allow-list is the specific thing that bit
    here, so it gets named rather than merely implied."""
    monkeypatch.setenv(sink.ENV_TOKEN, "t")
    monkeypatch.setenv(sink.ENV_ALLOWED, str(PLACEHOLDER))
    monkeypatch.setattr(tg.poll, "call", lambda *a, **k: [update(1, "hi", sender=ME)])

    assert sink.main(["--whoami"]) == 1
    assert "sent nothing here" in capsys.readouterr().err


def test_whoami_reports_the_configured_ids_even_with_an_empty_queue(
    monkeypatch, capsys
):
    monkeypatch.setenv(sink.ENV_TOKEN, "t")
    monkeypatch.setenv(sink.ENV_ALLOWED, str(ME))
    monkeypatch.setattr(tg.poll, "call", lambda *a, **k: [])

    assert sink.main(["--whoami"]) == 1
    assert str(ME) in capsys.readouterr().out


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("123", {123}),
        ("123,456", {123, 456}),
        (" 123 , 456 ", {123, 456}),
        ("", set()),
        ("@evan", set()),
        ("123,@evan", {123}),
    ],
)
def test_configured_ids_is_forgiving_where_load_config_is_strict(
    monkeypatch, raw, expected
):
    """load_config() exits on a malformed allow-list. This one parses what it
    can, because a malformed value is itself worth reporting rather than
    exiting over - the whole point is to explain a misconfiguration."""
    monkeypatch.setenv(sink.ENV_ALLOWED, raw)
    assert sink.configured_ids() == expected


def test_whoami_writes_nothing(inbox, monkeypatch, tmp_path):
    monkeypatch.setenv(sink.ENV_TOKEN, "t")
    monkeypatch.setenv(sink.ENV_STATE, str(tmp_path / "offset"))
    monkeypatch.setattr(
        tg.poll,
        "call",
        lambda *a, **k: [update(1, "https://www.instagram.com/reel/ABC123/")],
    )

    assert sink.main(["--whoami"]) == 0
    assert list(inbox.iterdir()) == []
    assert not (tmp_path / "offset").exists()


def test_whoami_with_an_empty_queue_says_what_to_do(monkeypatch, capsys):
    monkeypatch.setenv(sink.ENV_TOKEN, "t")
    monkeypatch.setattr(tg.poll, "call", lambda *a, **k: [])
    assert sink.main(["--whoami"]) == 1
    assert "Send your bot any message" in capsys.readouterr().out


def test_whoami_still_needs_a_token(monkeypatch):
    monkeypatch.delenv(sink.ENV_TOKEN, raising=False)
    with pytest.raises(SystemExit) as e:
        sink.main(["--whoami"])
    assert sink.ENV_TOKEN in str(e.value)


def test_the_offset_advances_only_after_the_captures_are_written(
    inbox, api, configured
):
    api([update(7, "https://www.instagram.com/reel/ABC123/")])
    assert sink.main(["--once"]) == 0
    assert configured.read_text().strip() == "8"
    assert (inbox / "ig-abc123").is_dir()


def test_a_crash_mid_write_leaves_the_offset_alone(inbox, api, configured, monkeypatch):
    """The ordering, which the test above cannot see.

    Both files existing after a clean run is true whichever order they happen
    in. The property is that a failure between them re-delivers the message,
    and that is only visible when the write fails. Re-delivery is free because
    write_message never clobbers.
    """

    def boom(*a, **k):
        raise RuntimeError("disk full")

    api([update(7, "https://www.instagram.com/reel/ABC123/")])
    monkeypatch.setattr(sink, "handle", boom)

    with pytest.raises(RuntimeError):
        sink.main(["--once"])
    assert not configured.exists(), "offset advanced past a message never written"


def test_a_dry_run_does_not_advance_the_offset(inbox, api, configured):
    api([update(7, "https://www.instagram.com/reel/ABC123/")])
    assert sink.main(["--once", "--dry-run"]) == 0
    assert not configured.exists()


def test_an_unparsable_update_fails_the_run(inbox, api, configured):
    api([update(1, "https://x.test/a"), {"update_id": 2, "poll_answer": {}}])
    assert sink.main(["--once"]) == 1
    assert sink.main(["--once", "--allow-unparsed"]) == 0


def test_a_rejected_sender_writes_nothing_and_is_reported(
    inbox, api, configured, capsys
):
    api([update(1, "https://x.test/a", sender=STRANGER)])
    assert sink.main(["--once"]) == 0
    assert list(inbox.iterdir()) == []
    assert str(STRANGER) in capsys.readouterr().err


def test_an_api_failure_exits_nonzero_rather_than_raising(
    inbox, configured, monkeypatch
):
    def boom(*a, **k):
        raise tg.TelegramError("getUpdates refused: 'Unauthorized'")

    monkeypatch.setattr(tg.poll, "call", boom)
    assert sink.main(["--once"]) == 1
