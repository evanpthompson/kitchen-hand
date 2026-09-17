"""Tests for tools/triage_inbox.py.

Two things are worth pinning here. First, that the tool never writes to
inbox/ - it is a report, and the moment it starts acting on its own guesses
a keyword heuristic is deciding what counts as a recipe. Second, the word
boundaries in FOOD: the first version matched "eat" inside "great", which
filed unrelated posts as food and inflated seven captures into the strong
bucket. That bug is invisible without a test that names it.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().parent.parent / "tools" / "triage_inbox.py"

spec = importlib.util.spec_from_file_location("triage_inbox", TOOL)
mod = importlib.util.module_from_spec(spec)
sys.modules["triage_inbox"] = mod
spec.loader.exec_module(mod)


RECIPE_CAPTION = """Italian Sausage and Bacon Potato Soup

Ingredients
- 4 slices of bacon, chopped
- 2 cups of chicken broth
- 1 tbsp olive oil

Saute the onion, then simmer for 20 minutes and serve.
"""


def make_capture(
    tmp_path: Path,
    slug: str,
    caption: str = "",
    handle: str = "@someone",
    hashtags: str = "",
    collection: str = "",
) -> Path:
    folder = tmp_path / slug
    folder.mkdir(parents=True)
    (folder / "url.txt").write_text("https://www.instagram.com/p/AAA1/\n")
    meta = [f"creator: {handle}", "input_type: instagram"]
    if hashtags:
        meta.append(f"hashtags: {hashtags}")
    if collection:
        meta.append(f"collection: {collection}")
    meta += ["", "# a trailing comment block, as the importer writes"]
    (folder / "meta.txt").write_text("\n".join(meta) + "\n")
    if caption:
        (folder / "caption.txt").write_text(caption)
    return folder


@pytest.fixture
def inbox(tmp_path):
    d = tmp_path / "inbox"
    d.mkdir()
    return d


# --- the word-boundary regression ----------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "Build Your Own X is a great way to learn the real mechanics",
        "Claude has a feature for creating executive function support",
        "Beginner Drop D tutorial for metalheads",
        "Explore our range of unique DIY electronic components and kits",
        "I've finally finished mounting and framing the artwork",
    ],
)
def test_non_food_text_is_not_matched_as_food(text):
    """'eat' inside 'great' and 'creating' is the bug this guards.

    Every string here is a real caption from a saved export that the
    unbounded pattern classified as food.
    """
    assert not mod.FOOD.search(text), text


@pytest.mark.parametrize(
    "text",
    [
        "Creamy Pan Fried Chicken is the ultimate comfort food",
        "Easy weeknight dinner",
        "best bbq brisket",
        "what I eat in a day",
        "#mealprep #highprotein",
    ],
)
def test_real_food_text_is_still_matched(text):
    """The boundaries must not be so tight that real food text slips past."""
    assert mod.FOOD.search(text), text


def test_a_non_food_post_lands_in_not_food(inbox):
    make_capture(
        inbox,
        "ig-github-unpacked-x1",
        caption="Build Your Own X is a great way to learn the real mechanics",
        handle="@github_unpacked",
    )
    ((score, bucket, _),) = mod.triage(inbox)
    assert bucket == "not-food"
    assert score < mod.WEAK_SCORE


# --- quantities ----------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "grab a cup and go",
        "a dash of style",
        "sticks and stones",
        "measured in grams, roughly",
        "the g in gif is soft",
    ],
)
def test_measure_requires_a_leading_number(text):
    """A quantity is a number plus a unit. Bare unit words turn up in prose
    constantly, and counting them would promote any chatty caption."""
    assert not mod.MEASURE.search(text), text


@pytest.mark.parametrize(
    "text",
    [
        "2 cups of chicken broth",
        "1 tbsp olive oil",
        "500 g flour",
        "1/2 cup milk",
        "3 cloves garlic",
        "4 oz cream cheese",
    ],
)
def test_measure_matches_a_real_quantity(text):
    assert mod.MEASURE.search(text), text


def test_bare_unit_words_do_not_push_a_post_into_strong(inbox):
    make_capture(
        inbox,
        "ig-nobody-aaa1",
        caption="Grab a cup, a dash of style, sticks and stones. Dinner vibes.",
        handle="@nobody",
    )
    ((score, bucket, _),) = mod.triage(inbox)
    assert bucket != "strong", score


# --- bucketing -----------------------------------------------------------


def test_a_full_recipe_caption_is_strong(inbox):
    make_capture(
        inbox,
        "ig-janays-cookin-aaa1",
        caption=RECIPE_CAPTION,
        handle="@janays_cookin",
        hashtags="#soup #dinner",
    )
    ((score, bucket, capture),) = mod.triage(inbox)
    assert bucket == "strong"
    assert score >= mod.STRONG_SCORE
    assert capture.title == "Italian Sausage and Bacon Potato Soup"


def test_food_post_without_a_recipe_is_food_no_text(inbox):
    """The "comment RECIPE and I'll DM you" pattern - 16 of these in a real
    export. Food, but the recipe is in neither the caption nor the video."""
    make_capture(
        inbox,
        "ig-thejoshelkin-aaa1",
        caption="Chili Cheese Stuffed Baked Potatoes. Comment recipe and I'll send it",
        handle="@thejoshelkin",
    )
    ((_, bucket, _),) = mod.triage(inbox)
    assert bucket == "food-no-text"


def test_a_capture_with_no_caption_at_all_is_bucketed_not_dropped(inbox):
    make_capture(inbox, "ig-someone-aaa1", handle="@someone")
    rows = mod.triage(inbox)
    assert len(rows) == 1
    assert rows[0][1] == "not-food"
    assert rows[0][2].title == "(no caption)"


def test_collection_membership_outranks_weak_text(inbox):
    """A post the user filed under a recipe collection is their own judgement
    and should not be demoted by a terse caption."""
    make_capture(
        inbox,
        "ig-chef-mike-aaa1",
        caption="worth making",
        handle="@chef.mike",
        collection="Tasty recipes",
    )
    ((_, bucket, _),) = mod.triage(inbox)
    assert bucket == "strong"


def test_rows_come_back_best_first(inbox):
    make_capture(inbox, "ig-b-weak", caption="dinner", handle="@nobody")
    make_capture(inbox, "ig-a-strong", caption=RECIPE_CAPTION, handle="@chef.mike")
    rows = mod.triage(inbox)
    assert [r[2].slug for r in rows] == ["ig-a-strong", "ig-b-weak"]


def test_transcript_and_raw_are_read_when_there_is_no_caption(inbox):
    folder = make_capture(inbox, "ig-x-aaa1", handle="@nobody")
    (folder / "raw.txt").write_text(RECIPE_CAPTION)
    ((score, bucket, _),) = mod.triage(inbox)
    assert bucket == "strong"


# --- what must never land in the drop bucket -----------------------------


def test_a_youtube_capture_is_read_not_scored_as_empty(inbox):
    """youtube.md was missing from the content-file list, so a real YouTube
    capture scored 0 and landed one command away from deletion. Unlike an
    Instagram import it cannot be re-created from an export."""
    folder = make_capture(inbox, "chengdu-tomato-egg-noodles", handle="@nobody")
    (folder / "caption.txt").unlink(missing_ok=True)
    (folder / "youtube.md").write_text(RECIPE_CAPTION)

    ((_, bucket, capture),) = mod.triage(inbox)
    assert bucket == "strong"
    assert "4 slices of bacon" in capture.caption


def test_a_jsonld_capture_is_read_too(inbox):
    folder = make_capture(inbox, "ig-x-aaa1", handle="@nobody")
    (folder / "jsonld.json").write_text(RECIPE_CAPTION)
    ((_, bucket, _),) = mod.triage(inbox)
    assert bucket == "strong"


def test_content_file_list_matches_the_rest_of_the_repo():
    """The service and the Flutter app each keep their own list of files that
    mean 'this capture has its text'. They must agree, or a capture is
    'done' in one place and empty in another."""
    service_core = (
        Path(__file__).resolve().parent.parent / "service" / "app" / "core.py"
    ).read_text()
    for name in mod.CONTENT_FILES:
        assert f'"{name}"' in service_core, f"{name} unknown to the service"


def test_a_capture_with_a_draft_is_never_droppable(tmp_path):
    """Its folder is the audit trail behind that draft's provenance."""
    repo = tmp_path / "repo"
    inbox = repo / "inbox"
    inbox.mkdir(parents=True)
    (repo / "recipes" / "_drafts").mkdir(parents=True)

    make_capture(inbox, "chengdu-tomato-egg-noodles", caption="", handle="@nobody")
    ((_, bucket_before, _),) = mod.triage(inbox)
    assert bucket_before == "not-food", "precondition: text alone scores nothing"

    (repo / "recipes" / "_drafts" / "chengdu-tomato-egg-noodles.yaml").write_text(
        "id: chengdu-tomato-egg-noodles\n"
    )
    ((_, bucket_after, _),) = mod.triage(inbox)
    assert bucket_after == "strong"


def test_a_capture_with_a_promoted_recipe_is_never_droppable(tmp_path):
    repo = tmp_path / "repo"
    inbox = repo / "inbox"
    inbox.mkdir(parents=True)
    (repo / "recipes").mkdir(parents=True)

    make_capture(inbox, "kung-pao-chicken", caption="", handle="@nobody")
    (repo / "recipes" / "kung-pao-chicken.yaml").write_text("id: kung-pao-chicken\n")
    ((_, bucket, _),) = mod.triage(inbox)
    assert bucket == "strong"


# --- it is a report, never a gate ----------------------------------------


def test_triage_never_modifies_the_inbox(inbox):
    make_capture(inbox, "ig-a-aaa1", caption=RECIPE_CAPTION, handle="@chef.mike")
    make_capture(inbox, "ig-b-bbb2", caption="unrelated", handle="@nobody")
    before = {
        p.relative_to(inbox): p.read_bytes() for p in inbox.rglob("*") if p.is_file()
    }

    assert mod.main(["--inbox", str(inbox)]) == 0
    assert mod.main(["--inbox", str(inbox), "--bucket", "not-food"]) == 0

    after = {
        p.relative_to(inbox): p.read_bytes() for p in inbox.rglob("*") if p.is_file()
    }
    assert after == before


def test_bucket_output_is_bare_slugs_for_piping(inbox, capsys):
    make_capture(inbox, "ig-a-aaa1", caption=RECIPE_CAPTION, handle="@chef.mike")
    make_capture(inbox, "ig-b-bbb2", caption="unrelated tech post", handle="@nobody")

    assert mod.main(["--inbox", str(inbox), "--bucket", "strong"]) == 0
    assert capsys.readouterr().out.split() == ["ig-a-aaa1"]

    assert mod.main(["--inbox", str(inbox), "--bucket", "not-food"]) == 0
    assert capsys.readouterr().out.split() == ["ig-b-bbb2"]


def test_out_writes_one_file_per_bucket(inbox, tmp_path):
    make_capture(inbox, "ig-a-aaa1", caption=RECIPE_CAPTION, handle="@chef.mike")
    out = tmp_path / "triage"
    assert mod.main(["--inbox", str(inbox), "--out", str(out)]) == 0

    assert {p.name for p in out.iterdir()} == {f"{b}.txt" for b in mod.BUCKETS}
    assert "ig-a-aaa1" in (out / "strong.txt").read_text()
    assert (out / "not-food.txt").read_text() == ""


def test_an_empty_inbox_is_reported_not_crashed(tmp_path, capsys):
    empty = tmp_path / "inbox"
    empty.mkdir()
    assert mod.main(["--inbox", str(empty)]) == 1
    assert "no captures" in capsys.readouterr().err


# --- meta.txt parsing ----------------------------------------------------


def test_meta_field_reads_the_importers_fields():
    meta = (
        "input_type: instagram\n"
        "creator: @chef.mike\n"
        "source_url: https://www.instagram.com/p/C_aB3xy/\n"
        "collection: Tasty recipes\n"
    )
    assert mod.meta_field(meta, "creator") == "@chef.mike"
    assert mod.meta_field(meta, "collection") == "Tasty recipes"
    # A URL value keeps its own colons.
    assert mod.meta_field(meta, "source_url").endswith("/p/C_aB3xy/")
    assert mod.meta_field(meta, "nope") == ""


def test_meta_field_ignores_a_commented_out_key():
    """The importer's meta.txt ends in a comment block. The '#' parses as part
    of the key, so no explicit skip is needed - pinned so it stays that way."""
    assert mod.meta_field("# creator: @wrong\ncreator: @right", "creator") == "@right"
    assert mod.meta_field("# creator: @wrong", "creator") == ""
