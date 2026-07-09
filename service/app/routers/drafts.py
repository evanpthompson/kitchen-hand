from fastapi import APIRouter, HTTPException

from .. import core

router = APIRouter(prefix="/drafts", tags=["drafts"])


def _draft_path(slug: str, must_exist: bool):
    if not core.is_valid_slug(slug):
        raise HTTPException(400, f"invalid slug: {slug}")
    path = core.DRAFTS_DIR / f"{slug}.yaml"
    if must_exist and not path.is_file():
        raise HTTPException(404, f"no draft for slug: {slug}")
    return path


@router.get("")
def list_drafts():
    return core.list_recipe_summaries(core.DRAFTS_DIR)


@router.get("/{slug}")
def get_draft(slug: str):
    path = _draft_path(slug, must_exist=True)
    data = core.load_recipe_yaml(path)
    return {
        "slug": slug,
        "data": data,
        "errors": core.validate_recipe_dict(data, expected_slug=slug),
    }


@router.put("/{slug}")
def save_draft(slug: str, data: dict):
    """Create-or-update. Does NOT block saving an invalid/in-progress
    draft — validation errors come back alongside the save confirmation
    so partial work is never lost.
    """
    if not core.is_valid_slug(slug):
        raise HTTPException(400, f"invalid slug: {slug}")
    path = core.DRAFTS_DIR / f"{slug}.yaml"
    core.DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
    core.dump_recipe_yaml(data, path)
    return {
        "slug": slug,
        "saved": True,
        "errors": core.validate_recipe_dict(data, expected_slug=slug),
    }


@router.post("/{slug}/validate")
def validate_draft(slug: str):
    path = _draft_path(slug, must_exist=True)
    data = core.load_recipe_yaml(path)
    errors = core.validate_recipe_dict(data, expected_slug=slug)
    return {"slug": slug, "valid": not errors, "errors": errors}


@router.post("/{slug}/promote")
def promote_draft(slug: str, force: bool = False):
    """Moves recipes/_drafts/{slug}.yaml -> recipes/{slug}.yaml, but only
    on a clean review-readiness check: schema valid, id matches filename,
    and no unresolved dedup candidates. Pass force=true to promote anyway
    once a human has looked at the dedup candidates and decided keep-both.
    """
    path = _draft_path(slug, must_exist=True)
    data = core.load_recipe_yaml(path)

    errors = core.validate_recipe_dict(data, expected_slug=slug)
    if errors:
        raise HTTPException(422, {"reason": "schema_invalid", "errors": errors})

    dest = core.RECIPES_DIR / f"{slug}.yaml"
    if dest.exists() and not force:
        raise HTTPException(
            409,
            {
                "reason": "slug_already_promoted",
                "detail": f"recipes/{slug}.yaml already exists",
            },
        )

    if not force:
        candidates = core.find_dedup_candidates(data)
        if candidates:
            return {
                "promoted": False,
                "reason": "dedup_candidates_found",
                "candidates": candidates,
            }

    core.RECIPES_DIR.mkdir(parents=True, exist_ok=True)
    path.rename(dest)
    return {"promoted": True, "slug": slug}


@router.delete("/{slug}")
def discard_draft(slug: str):
    path = _draft_path(slug, must_exist=True)
    path.unlink()
    return {"slug": slug, "discarded": True}
