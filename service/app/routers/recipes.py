from fastapi import APIRouter, HTTPException

from .. import core

router = APIRouter(prefix="/recipes", tags=["recipes"])


@router.get("")
def list_recipes():
    return core.list_recipe_summaries(core.RECIPES_DIR)


@router.get("/tags")
def list_tags():
    return core.collect_tags()


@router.get("/{slug}")
def get_recipe(slug: str):
    if not core.is_valid_slug(slug):
        raise HTTPException(400, f"invalid slug: {slug}")
    path = core.RECIPES_DIR / f"{slug}.yaml"
    if not path.is_file():
        raise HTTPException(404, f"no recipe for slug: {slug}")
    return core.load_recipe_yaml(path)
