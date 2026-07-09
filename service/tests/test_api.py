"""Smoke tests against the real repo state (recipes/, recipes/_drafts/,
inbox/ as they exist on disk) -- not an isolated fixture, deliberately, so
these catch real schema/data drift, not just code paths.
"""
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


def test_list_drafts_includes_chengdu_noodles():
    r = client.get("/drafts")
    slugs = {item["slug"] for item in r.json()}
    assert "chengdu-tomato-egg-noodles" in slugs


def test_draft_summary_flags_extraction_notes():
    r = client.get("/drafts")
    by_slug = {item["slug"]: item for item in r.json()}
    assert by_slug["chengdu-tomato-egg-noodles"]["has_extraction_notes"] is True
    assert by_slug["chengdu-tomato-egg-noodles"]["valid"] is True


def test_get_draft_full():
    r = client.get("/drafts/chengdu-tomato-egg-noodles")
    assert r.status_code == 200
    body = r.json()
    assert body["errors"] == []
    assert body["data"]["mode"] == "manual"


def test_inbox_lists_youtube_capture():
    r = client.get("/inbox")
    by_slug = {item["slug"]: item for item in r.json()}
    assert "chengdu-tomato-egg-noodles" in by_slug
    entry = by_slug["chengdu-tomato-egg-noodles"]
    assert entry["source_type_guess"] == "youtube"
    assert entry["has_draft"] is True


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
