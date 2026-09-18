"""Smoke tests against the real repo state (recipes/, recipes/_drafts/,
inbox/ as they exist on disk) -- not an isolated fixture, deliberately, so
these catch real schema/data drift, not just code paths.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_schema_served():
    r = client.get("/schema")
    assert r.status_code == 200
    assert r.json()["title"] == "Recipe v1"


def test_list_recipes_includes_kung_pao():
    r = client.get("/recipes")
    assert r.status_code == 200
    slugs = {item["slug"] for item in r.json()}
    assert "kung-pao-chicken" in slugs


def test_get_recipe():
    r = client.get("/recipes/kung-pao-chicken")
    assert r.status_code == 200
    assert r.json()["title"] == "Kung Pao Chicken"


def test_get_recipe_404():
    assert client.get("/recipes/does-not-exist").status_code == 404


def test_tags_include_chicken():
    r = client.get("/recipes/tags")
    assert "chicken" in r.json()


# These read-path tests used to name chengdu-tomato-egg-noodles, the only
# draft that existed when they were written. It has since been reviewed and
# promoted, which broke all four - correctly, since the module tests real repo
# state on purpose. The lesson is that curation state is not a fixture: any
# named draft is one review away from being a recipe. They now supply their
# own draft and assert the real state generically.


@pytest.fixture
def a_draft():
    """A draft that exists for the duration of one test, then does not."""
    from app import core

    slug = "test-fixture-draft"
    path = core.DRAFTS_DIR / f"{slug}.yaml"
    core.dump_recipe_yaml(
        {
            "id": slug,
            "title": "Fixture Dish",
            "servings": 2,
            "mode": "manual",
            "provenance": {
                "input_type": "pasted-text",
                "creator": "test",
                "captured_date": "2026-09-17",
                "extraction_notes": "something was ambiguous",
            },
            "ingredients": [{"id": "salt", "name": "Salt", "quantity": "1 tsp"}],
            "phases": [{"name": "Season", "instruction": "Add the salt."}],
        },
        path,
    )
    yield slug
    path.unlink(missing_ok=True)


def test_list_drafts_includes_a_draft_that_exists(a_draft):
    slugs = {item["slug"] for item in client.get("/drafts").json()}
    assert a_draft in slugs


def test_draft_summary_flags_extraction_notes(a_draft):
    by_slug = {item["slug"]: item for item in client.get("/drafts").json()}
    assert by_slug[a_draft]["has_extraction_notes"] is True
    assert by_slug[a_draft]["valid"] is True


def test_get_draft_full(a_draft):
    r = client.get(f"/drafts/{a_draft}")
    assert r.status_code == 200
    body = r.json()
    assert body["errors"] == []
    assert body["data"]["mode"] == "manual"


def test_every_draft_in_the_collection_is_listed_and_summarised():
    """The real-state half, without naming anything: whatever is in _drafts/
    is what /drafts reports."""
    from app import core

    on_disk = {p.stem for p in core.DRAFTS_DIR.glob("*.yaml")}
    listed = {item["slug"] for item in client.get("/drafts").json()}
    assert listed == on_disk


def test_inbox_lists_the_youtube_capture():
    r = client.get("/inbox")
    by_slug = {item["slug"]: item for item in r.json()}
    assert "chengdu-tomato-egg-noodles" in by_slug
    assert by_slug["chengdu-tomato-egg-noodles"]["source_type_guess"] == "youtube"


def test_has_draft_matches_what_is_actually_in_drafts():
    """has_draft is a claim about the filesystem, so check it against the
    filesystem rather than against a slug that was true once."""
    from app import core

    drafts = {p.stem for p in core.DRAFTS_DIR.glob("*.yaml")}
    for entry in client.get("/inbox").json():
        assert entry["has_draft"] is (entry["slug"] in drafts), entry["slug"]


def test_inbox_capture_contents():
    r = client.get("/inbox/chengdu-tomato-egg-noodles")
    names = {f["name"] for f in r.json()["files"]}
    assert "youtube.md" in names


def test_draft_lifecycle_create_validate_discard():
    slug = "test-lifecycle-recipe"
    minimal_recipe = {
        "id": slug,
        "title": "Test Lifecycle Recipe",
        "servings": 2,
        "ingredients": [{"id": "water", "name": "Water"}],
        "phases": [{"name": "Boil", "instruction": "Boil the water."}],
    }

    r = client.put(f"/drafts/{slug}", json=minimal_recipe)
    assert r.status_code == 200
    assert r.json()["errors"] == []

    r = client.post(f"/drafts/{slug}/validate")
    assert r.json() == {"slug": slug, "valid": True, "errors": []}

    r = client.get(f"/drafts/{slug}")
    assert r.json()["data"]["title"] == "Test Lifecycle Recipe"

    r = client.delete(f"/drafts/{slug}")
    assert r.json()["discarded"] is True

    assert client.get(f"/drafts/{slug}").status_code == 404


def test_promote_blocks_on_invalid_schema():
    slug = "test-invalid-promote"
    client.put(f"/drafts/{slug}", json={"id": slug, "title": "Broken"})

    r = client.post(f"/drafts/{slug}/promote")
    assert r.status_code == 422
    assert r.json()["detail"]["reason"] == "schema_invalid"

    client.delete(f"/drafts/{slug}")


def test_promote_flags_dedup_against_kung_pao():
    slug = "test-kung-pao-clone"
    clone = {
        "id": slug,
        "title": "Kung Pao Chicken",
        "servings": 3,
        "ingredients": [
            {"id": "chicken", "name": "Boneless chicken thigh"},
            {"id": "peanuts", "name": "Roasted peanuts"},
        ],
        "phases": [{"name": "Cook", "instruction": "Cook it."}],
    }
    client.put(f"/drafts/{slug}", json=clone)

    r = client.post(f"/drafts/{slug}/promote")
    assert r.status_code == 200
    body = r.json()
    assert body["promoted"] is False
    assert body["reason"] == "dedup_candidates_found"
    assert any(c["slug"] == "kung-pao-chicken" for c in body["candidates"])

    client.delete(f"/drafts/{slug}")


def test_promote_succeeds_for_novel_recipe_then_cleanup():
    slug = "test-novel-recipe-for-promotion"
    novel = {
        "id": slug,
        "title": "Completely Unrelated Test Dish",
        "servings": 1,
        "ingredients": [{"id": "salt", "name": "Salt"}],
        "phases": [{"name": "Season", "instruction": "Add salt."}],
    }
    client.put(f"/drafts/{slug}", json=novel)

    r = client.post(f"/drafts/{slug}/promote")
    assert r.status_code == 200
    assert r.json() == {"promoted": True, "slug": slug}

    # cleanup: this test promotes into the real recipes/ dir, remove it after
    from app import core

    (core.RECIPES_DIR / f"{slug}.yaml").unlink()


# --- Manual capture (POST /inbox/{slug}/files), the Phase C backend ---


@pytest.fixture
def capture_slug(request):
    """A capture folder that is removed however the test ends.

    These tests run against the real inbox/ (see module docstring), and the
    refusal paths are exactly the ones that must leave nothing behind — so
    cleanup cannot live at the end of the test body.
    """
    import re

    from app import core

    # Node names carry underscores and [param] brackets; core.is_valid_slug
    # accepts neither, and an invalid slug 400s before the endpoint under test
    # is reached -- which silently turns a refusal assertion green.
    stem = re.sub(r"[^a-z0-9]+", "-", request.node.name.lower()).strip("-")
    slug = f"test-capture-{stem[:60].strip('-')}"
    assert core.is_valid_slug(slug), slug
    yield slug
    d = core.INBOX_DIR / slug
    if d.is_dir():
        for f in d.iterdir():
            f.unlink()
        d.rmdir()


def test_capture_accepts_a_multi_paragraph_caption_as_a_form_field(capture_slug):
    """The reason these are Form() and not query params.

    A real Instagram recipe caption runs to several KB. As a query parameter
    it either blows the URL length limit or gets truncated by something in
    the middle, and truncation is the bad kind of failure: a caption missing
    its last three steps still looks like a successful capture.
    """
    caption = "Step one. " * 900  # ~9 KB, well past any sane URL limit
    r = client.post(f"/inbox/{capture_slug}/files", data={"caption": caption})
    assert r.status_code == 200
    assert r.json()["captured_files"] == ["caption.txt"]

    got = client.get(f"/inbox/{capture_slug}").json()
    stored = next(f for f in got["files"] if f["name"] == "caption.txt")
    assert stored["content"] == caption


def test_blank_caption_does_not_erase_the_importers_meta(capture_slug):
    """tools/import_instagram_saved.py writes meta.txt before the paste.

    A capture screen whose meta box failed to load would post an empty string
    over it and silently lose the handle and permalink. Blank means "not
    provided", never "clear the file".
    """
    client.post(f"/inbox/{capture_slug}/files", data={"meta": "creator: @chef.mike"})
    r = client.post(f"/inbox/{capture_slug}/files", data={"caption": "real", "meta": "   "})
    assert r.status_code == 200
    assert r.json()["captured_files"] == ["caption.txt"]

    got = client.get(f"/inbox/{capture_slug}").json()
    meta = next(f for f in got["files"] if f["name"] == "meta.txt")
    assert meta["content"] == "creator: @chef.mike"


def test_capture_with_no_content_is_refused(capture_slug):
    from app import core

    r = client.post(f"/inbox/{capture_slug}/files", data={"caption": "  "})
    assert r.status_code == 400
    assert not (core.INBOX_DIR / capture_slug).exists()


def test_screenshot_upload_is_accepted_and_kept_under_the_slug(capture_slug):
    from app import core

    r = client.post(
        f"/inbox/{capture_slug}/files",
        data={"caption": "carousel post"},
        files={"uploads": ("screenshot.png", b"\x89PNG\r\n\x1a\n", "image/png")},
    )
    assert r.status_code == 200
    assert set(r.json()["captured_files"]) == {"caption.txt", "screenshot.png"}
    assert (core.INBOX_DIR / capture_slug / "screenshot.png").is_file()


# The upload-name guard has three independent layers. Each is tested on its
# own, because a test that only asserts "some layer refused" stays green when
# the layer it was written for is deleted -- which is how the first version of
# this test passed with the basename reduction removed.


def test_upload_name_reduced_to_basename_cannot_reach_a_real_repo_file(capture_slug):
    """Isolates the basename layer.

    The payload clears the other two on purpose: it does not start with '.',
    and .json is on the extension allow-list. Joined unsanitised it resolves
    to <repo>/schema/recipe-v1.schema.json -- the file the whole validation
    chain depends on.
    """
    from app import core

    victim = core.SCHEMA_PATH
    before = victim.read_bytes()

    r = client.post(
        f"/inbox/{capture_slug}/files",
        files={
            "uploads": (
                "x/../../../schema/recipe-v1.schema.json",
                b'{"pwned": true}',
                "application/json",
            )
        },
    )
    assert r.status_code == 200, "allowed extension, so it should be stored"
    assert victim.read_bytes() == before, "schema was overwritten"
    assert (core.INBOX_DIR / capture_slug / "recipe-v1.schema.json").is_file()


@pytest.mark.parametrize(
    "filename, reason",
    [
        ("payload.yaml", "not allowed"),
        ("archive.zip", "not allowed"),
        ("payload", "not allowed"),
        (".hidden.png", "unusable"),
        # Basename-reduced to kung-pao-chicken.yaml first, so this lands on
        # the extension gate rather than the dotfile one.
        ("../../recipes/kung-pao-chicken.yaml", "not allowed"),
    ],
)
def test_upload_names_off_the_allow_list_are_refused(capture_slug, filename, reason):
    from app import core

    r = client.post(
        f"/inbox/{capture_slug}/files",
        files={"uploads": (filename, b"x", "application/octet-stream")},
    )
    assert r.status_code == 400
    assert reason in r.json()["detail"]
    assert not (core.INBOX_DIR / capture_slug).exists()
