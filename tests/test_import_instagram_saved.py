"""Tests for tools/import_instagram_saved.py.

The properties worth testing here are the fail-closed ones: a partial import
must not report success, and a re-run must not cost you a hand correction.
Each is asserted in both directions - that it fires, and that it does not fire
on the healthy case - so a gate that has quietly stopped working is visible.

Fixture data mirrors the shape of a real export (checked 2026-09-17 against a
548-post archive), including the mojibake Instagram writes into captions.
"""

import importlib.util
import json
import sys
import zipfile
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().parent.parent / "tools" / "import_instagram_saved.py"

spec = importlib.util.spec_from_file_location("import_instagram_saved", TOOL)
mod = importlib.util.module_from_spec(spec)
sys.modules["import_instagram_saved"] = mod
spec.loader.exec_module(mod)


# --- fixture builders ----------------------------------------------------


def post_entry(
    handle: str,
    shortcode: str,
    caption: str = "Tomato egg noodles. 2 eggs, 1 tbsp soy sauce.",
    *,
    kind: str = "p",
    title: str = "",
    hashtags: tuple[str, ...] = ("noodles",),
    display_name: str = "Chef Mike",
    timestamp: int = 1_700_000_000,
) -> dict:
    """One entry in the current export shape."""
    return {
        "timestamp": timestamp,
        "media": [],
        "fbid": "17985690738100702",
        "label_values": [
            {
                "label": "URL",
                "value": f"https://www.instagram.com/{kind}/{shortcode}/",
                "href": f"https://www.instagram.com/{kind}/{shortcode}/",
            },
            {"label": "Caption", "value": caption},
            {"label": "Title", "value": title},
            {
                "title": "Hashtags",
                "dict": [
                    {"dict": [{"label": "Name", "value": h}], "title": ""}
                    for h in hashtags
                ],
            },
            {
                "title": "Owner",
                "dict": [
                    {
                        "dict": [
                            {"label": "URL", "value": "http://chefmike.test"},
                            {"label": "Name", "value": display_name},
                            {"label": "Username", "value": handle},
                        ],
                        "title": "",
                    }
                ],
            },
        ],
    }


def legacy_entry(handle: str, shortcode: str, timestamp: int = 1_700_000_000) -> dict:
    """An entry in the older string_map_data encoding."""
    return {
        "title": handle,
        "string_map_data": {
            "Saved on": {
                "href": f"https://www.instagram.com/p/{shortcode}/",
                "timestamp": timestamp,
            }
        },
    }


def collection_entry(name: str, urls: list[str]) -> dict:
    return {
        "timestamp": 1_682_251_035,
        "media": [],
        "label_values": [
            {"label": "Name", "value": name},
            {"label": "Type", "value": "Default"},
            {
                "title": "Posts",
                "dict": [
                    {
                        "dict": [
                            {"label": "URL", "value": u, "href": u},
                            {"label": "Caption", "value": "x"},
                        ],
                        "title": "",
                    }
                    for u in urls
                ],
            },
        ],
    }


def write_export(
    tmp_path: Path,
    entries: list[dict],
    collections: list[dict] | None = None,
    as_zip: bool = False,
    legacy: bool = False,
) -> Path:
    posts = {"saved_saved_media": entries} if legacy else entries
    files = {"your_instagram_activity/saved/saved_posts.json": json.dumps(posts)}
    if collections is not None:
        files["your_instagram_activity/saved/saved_collections.json"] = json.dumps(
            collections
        )

    if as_zip:
        archive = tmp_path / "instagram-export.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            for name, body in files.items():
                zf.writestr(name, body)
        return archive

    directory = tmp_path / "export"
    for name, body in files.items():
        path = directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body)
    return directory


@pytest.fixture
def inbox(tmp_path, monkeypatch):
    d = tmp_path / "inbox"
    d.mkdir()
    monkeypatch.setattr(mod, "INBOX", d)
    return d


# --- the current export shape --------------------------------------------


def test_imports_caption_handle_and_hashtags(tmp_path, inbox):
    """The export carries the whole capture, so nothing needs pasting."""
    archive = write_export(tmp_path, [post_entry("chef.mike", "C_aB3xy")])
    assert mod.main([str(archive)]) == 0

    folder = inbox / "ig-chef-mike-c-ab3xy"
    assert sorted(p.name for p in folder.iterdir()) == [
        "caption.txt",
        "meta.txt",
        "url.txt",
    ]
    assert "2 eggs" in (folder / "caption.txt").read_text()

    meta = (folder / "meta.txt").read_text()
    assert "creator: @chef.mike" in meta
    assert "creator_name: Chef Mike" in meta
    assert "hashtags: #noodles" in meta
    assert "saved_on: 2023-11-14" in meta
    # Fail closed on dates we were not given: the export has no post date.
    assert "post_date: unknown" in meta


def test_title_is_prepended_to_the_caption_when_present(tmp_path, inbox):
    archive = write_export(
        tmp_path, [post_entry("chef.mike", "C_aB3xy", title="Chengdu Noodles")]
    )
    assert mod.main([str(archive)]) == 0
    text = (inbox / "ig-chef-mike-c-ab3xy" / "caption.txt").read_text()
    assert text.startswith("Chengdu Noodles\n\n")


def test_a_post_with_no_caption_still_imports_and_is_flagged(tmp_path, inbox, capsys):
    archive = write_export(tmp_path, [post_entry("chef.mike", "C_aB3xy", caption="")])
    assert mod.main([str(archive)]) == 0

    folder = inbox / "ig-chef-mike-c-ab3xy"
    assert not (folder / "caption.txt").exists()
    assert (folder / "url.txt").is_file()
    assert "no caption" in capsys.readouterr().out


@pytest.mark.parametrize("kind", ["p", "reel", "tv"])
def test_accepts_every_permalink_shape(tmp_path, inbox, kind):
    archive = write_export(tmp_path, [post_entry("chef.mike", "Abc1", kind=kind)])
    assert mod.main([str(archive)]) == 0
    assert (inbox / "ig-chef-mike-abc1" / "url.txt").is_file()


def test_missing_owner_block_degrades_to_unknown_rather_than_failing(tmp_path, inbox):
    entry = post_entry("chef.mike", "C_aB3xy")
    entry["label_values"] = [
        lv for lv in entry["label_values"] if lv.get("title") != "Owner"
    ]
    archive = write_export(tmp_path, [entry])
    assert mod.main([str(archive)]) == 0
    assert (inbox / "ig-unknown-c-ab3xy" / "url.txt").is_file()


# --- encoding ------------------------------------------------------------


def test_mojibake_in_a_caption_is_repaired():
    """Instagram stores UTF-8 read back as Latin-1. 333 of 548 captions in a
    real export were damaged this way, apostrophes and fractions included.

    The broken fixture is built by applying that exact damage to good text,
    rather than hand-typing the byte escapes - which is how the first version
    of this test ended up asserting against an impossible string.
    """
    good = "It isn\u2019t \u00bc cup \u2014 it is \u00bd."
    broken = good.encode("utf-8").decode("latin-1")
    assert broken != good and "\u00e2" in broken  # the fixture really is damaged

    fixed, repaired, suspect = mod.repair_mojibake(broken)
    assert repaired and not suspect
    assert fixed == good


def test_correctly_stored_text_is_left_alone():
    """A caption with real emoji encodes cleanly and must not be touched -
    round-tripping it through Latin-1 would destroy it."""
    good = "Tomato egg noodles \U0001f35c ready in 10"
    out, repaired, suspect = mod.repair_mojibake(good)
    assert out == good
    assert not repaired and not suspect


def test_undecodable_text_is_returned_unchanged_and_flagged():
    """Half-decoding a caption would corrupt the quantities, so a failed
    repair keeps the original and says so."""
    broken = "2 tbsp â soy ÿþ"
    out, repaired, suspect = mod.repair_mojibake(broken)
    assert out == broken
    assert not repaired and suspect


def test_suspect_encoding_is_recorded_in_meta(tmp_path, inbox):
    archive = write_export(
        tmp_path,
        [post_entry("chef.mike", "C_aB3xy", caption="2 tbsp â soy ÿþ")],
    )
    assert mod.main([str(archive), "--allow-unparsed"]) == 0
    meta = (inbox / "ig-chef-mike-c-ab3xy" / "meta.txt").read_text()
    assert "encoding: SUSPECT" in meta


# --- collections ---------------------------------------------------------


def test_collection_filter_imports_only_that_collection(tmp_path, inbox):
    recipes = "https://www.instagram.com/p/AAA1/"
    tech = "https://www.instagram.com/p/BBB2/"
    archive = write_export(
        tmp_path,
        [post_entry("chef.mike", "AAA1"), post_entry("some.dev", "BBB2")],
        collections=[
            collection_entry("Tasty recipes ", [recipes]),
            collection_entry("Tech", [tech]),
        ],
    )
    assert mod.main([str(archive), "--collection", "Tasty recipes"]) == 0
    assert [p.name for p in inbox.iterdir()] == ["ig-chef-mike-aaa1"]
    assert (
        "collection: Tasty recipes"
        in (inbox / "ig-chef-mike-aaa1" / "meta.txt").read_text()
    )


def test_collection_membership_ignores_creator_website_urls(tmp_path, inbox):
    """A collection entry also carries each creator's own site under the same
    "URL" label. Counting those overstated a real collection as 77 posts when
    it held 45."""
    coll = collection_entry("Tasty recipes", ["https://www.instagram.com/p/AAA1/"])
    coll["label_values"][2]["dict"].append(
        {"dict": [{"label": "URL", "value": "http://someblog.test"}], "title": ""}
    )
    archive = write_export(
        tmp_path, [post_entry("chef.mike", "AAA1")], collections=[coll]
    )

    members = mod._read_members(archive)
    mapping = mod.parse_collections(members["saved_collections.json"])
    assert list(mapping) == ["https://www.instagram.com/p/AAA1/"]


def test_a_collection_post_missing_from_the_export_fails_the_run(tmp_path, inbox):
    """A real export named 45 posts in a collection and carried 44 of them.
    Importing 44 without saying so is the silent-partial this tool refuses."""
    archive = write_export(
        tmp_path,
        [post_entry("chef.mike", "AAA1")],
        collections=[
            collection_entry(
                "Tasty recipes",
                [
                    "https://www.instagram.com/p/AAA1/",
                    "https://www.instagram.com/reel/GONE9/",
                ],
            )
        ],
    )
    assert mod.main([str(archive), "--collection", "Tasty recipes"]) == 1
    # The one it could read is still written - refusing the run does not mean
    # discarding work, only refusing to call it complete.
    assert (inbox / "ig-chef-mike-aaa1").is_dir()
    assert (
        mod.main([str(archive), "--collection", "Tasty recipes", "--allow-unparsed"])
        == 0
    )


def test_unknown_collection_name_is_refused(tmp_path, inbox):
    archive = write_export(
        tmp_path,
        [post_entry("chef.mike", "AAA1")],
        collections=[collection_entry("Tasty recipes", [])],
    )
    assert mod.main([str(archive), "--collection", "Nope"]) == 1
    assert list(inbox.iterdir()) == []


# --- the older export shape ----------------------------------------------


def test_legacy_string_map_data_export_still_parses(tmp_path, inbox):
    archive = write_export(
        tmp_path, [legacy_entry("chef.mike", "C_aB3xy")], legacy=True
    )
    assert mod.main([str(archive)]) == 0
    folder = inbox / "ig-chef-mike-c-ab3xy"
    assert (folder / "url.txt").is_file()
    # That shape carries no caption, which is why the paste screen exists.
    assert not (folder / "caption.txt").exists()


def test_legacy_entry_list_key_rename_still_parses():
    """Meta has renamed the wrapper key across export versions; shape-matching
    on 'the one value that is a list' survives that."""
    raw = json.dumps({"some_future_key_name": [legacy_entry("chef.mike", "C_aB3xy")]})
    result = mod.parse_saved_posts(raw.encode())
    assert len(result.posts) == 1 and not result.unparsed
    assert result.posts[0].handle == "chef.mike"


# --- safety properties ---------------------------------------------------


def test_reads_the_zip_without_unpacking_it(tmp_path, inbox):
    archive = write_export(tmp_path, [post_entry("chef.mike", "C_aB3xy")], as_zip=True)
    assert mod.main([str(archive)]) == 0
    assert (inbox / "ig-chef-mike-c-ab3xy" / "caption.txt").is_file()


def test_rerun_never_clobbers_a_hand_correction(tmp_path, inbox):
    archive = write_export(tmp_path, [post_entry("chef.mike", "C_aB3xy")])
    assert mod.main([str(archive)]) == 0

    folder = inbox / "ig-chef-mike-c-ab3xy"
    (folder / "caption.txt").write_text("corrected: 2 tsp, not 2 tbsp")
    (folder / "meta.txt").write_text("hand-corrected handle")

    assert mod.main([str(archive)]) == 0
    assert (folder / "caption.txt").read_text() == "corrected: 2 tsp, not 2 tbsp"
    assert (folder / "meta.txt").read_text() == "hand-corrected handle"


def test_never_overwrites_an_existing_file_in_the_folder(tmp_path, inbox):
    """The no-clobber guard inside write_capture, exercised directly.

    The re-run test above does not reach it - URL dedup short-circuits first -
    so without this the guard is dead code nobody has watched work. The live
    path to it: a folder that exists at the provisional slug but whose url.txt
    is missing or points elsewhere.
    """
    folder = inbox / "ig-chef-mike-c-ab3xy"
    folder.mkdir()
    (folder / "meta.txt").write_text("hand-written, do not touch")

    post = mod.SavedPost(
        url="https://www.instagram.com/p/C_aB3xy/",
        shortcode="C_aB3xy",
        handle="chef.mike",
        caption="x",
    )
    written = mod.write_capture(post, "ig-chef-mike-c-ab3xy", dry_run=False)

    assert "meta.txt" not in written
    assert (folder / "meta.txt").read_text() == "hand-written, do not touch"
    assert (folder / "url.txt").is_file()


def test_folder_with_a_stale_url_keeps_its_hand_edits(tmp_path, inbox):
    folder = inbox / "ig-chef-mike-c-ab3xy"
    folder.mkdir()
    (folder / "url.txt").write_text("https://www.instagram.com/p/DIFFERENT/\n")
    (folder / "meta.txt").write_text("hand-written, do not touch")

    archive = write_export(tmp_path, [post_entry("chef.mike", "C_aB3xy")])
    assert mod.main([str(archive)]) == 0
    assert (folder / "meta.txt").read_text() == "hand-written, do not touch"


def test_dedups_on_url_so_a_renamed_folder_is_not_recreated(tmp_path, inbox):
    archive = write_export(tmp_path, [post_entry("chef.mike", "C_aB3xy")])
    assert mod.main([str(archive)]) == 0

    # Renaming to the real dish slug is the documented next step.
    (inbox / "ig-chef-mike-c-ab3xy").rename(inbox / "chengdu-tomato-egg-noodles")

    assert mod.main([str(archive)]) == 0
    assert [p.name for p in inbox.iterdir()] == ["chengdu-tomato-egg-noodles"]


def test_dry_run_writes_nothing(tmp_path, inbox):
    archive = write_export(tmp_path, [post_entry("chef.mike", "C_aB3xy")])
    assert mod.main([str(archive), "--dry-run"]) == 0
    assert list(inbox.iterdir()) == []


def test_unparsable_entry_fails_the_run(tmp_path, inbox):
    """The gate: 1 of 2 imported must not exit 0."""
    archive = write_export(
        tmp_path,
        [
            post_entry("chef.mike", "C_aB3xy"),
            {"timestamp": 1, "label_values": [{"label": "URL", "value": "nope"}]},
        ],
    )
    assert mod.main([str(archive)]) == 1
    assert (inbox / "ig-chef-mike-c-ab3xy").is_dir()


def test_allow_unparsed_downgrades_the_refusal(tmp_path, inbox):
    archive = write_export(
        tmp_path,
        [post_entry("chef.mike", "C_aB3xy"), {"timestamp": 1, "label_values": []}],
    )
    assert mod.main([str(archive), "--allow-unparsed"]) == 0


def test_missing_saved_posts_file_is_refused(tmp_path, inbox):
    empty = tmp_path / "export"
    empty.mkdir()
    assert mod.main([str(empty)]) == 1
