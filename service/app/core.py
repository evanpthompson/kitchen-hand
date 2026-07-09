"""Shared filesystem/schema helpers. The git repo is the database — every
function here reads/writes recipes/, recipes/_drafts/, inbox/, and
schema/recipe-v1.schema.json directly. No separate storage layer.
"""
import difflib
import json
import re
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
INBOX_DIR = REPO_ROOT / "inbox"
DRAFTS_DIR = REPO_ROOT / "recipes" / "_drafts"
RECIPES_DIR = REPO_ROOT / "recipes"
SCHEMA_PATH = REPO_ROOT / "schema" / "recipe-v1.schema.json"

_SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text())


def get_validator() -> Draft202012Validator:
    return Draft202012Validator(load_schema())


def is_valid_slug(slug: str) -> bool:
    return bool(_SLUG_RE.match(slug))


def load_recipe_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text()) or {}


def dump_recipe_yaml(data: dict, path: Path) -> None:
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True))


def validate_recipe_dict(data: dict, expected_slug: str | None = None) -> list[str]:
    """Returns a list of human-readable error strings; empty means valid."""
    validator = get_validator()
    errors = []
    for e in sorted(validator.iter_errors(data), key=lambda e: list(e.path)):
        loc = "/".join(str(p) for p in e.path) or "(root)"
        errors.append(f"{loc}: {e.message}")
    if expected_slug is not None and data.get("id") != expected_slug:
        errors.append(f"id: '{data.get('id')}' does not match slug '{expected_slug}'")
    return errors


def _recipe_summary(path: Path) -> dict:
    """Best-effort summary for a recipe/draft file; never raises on bad YAML."""
    slug = path.stem
    try:
        data = load_recipe_yaml(path)
    except yaml.YAMLError as e:
        return {"slug": slug, "parse_error": str(e)}

    errors = validate_recipe_dict(data, expected_slug=slug)
    notes = ""
    if isinstance(data.get("provenance"), dict):
        notes = data["provenance"].get("extraction_notes", "") or ""

    return {
        "slug": slug,
        "title": data.get("title"),
        "mode": data.get("mode"),
        "cuisine": data.get("cuisine"),
        "servings": data.get("servings"),
        "tags": data.get("tags", []),
        "valid": not errors,
        "errors": errors,
        "has_extraction_notes": bool(notes.strip()),
    }


def list_recipe_summaries(directory: Path) -> list[dict]:
    return [
        _recipe_summary(p)
        for p in sorted(directory.glob("*.yaml"))
    ]


def infer_inbox_source_type(files: list[str]) -> str:
    """Best-effort guess at capture source, from which files are present.
    Purely informational for the inbox listing — the real source_type of
    record lives in provenance.input_type once a draft exists.
    """
    names = set(files)
    if "youtube.md" in names:
        return "youtube"
    if "jsonld.json" in names or "url.txt" in names:
        return "url"
    if any(n.startswith("source.") for n in names):
        return "document"
    if "transcript.txt" in names or "caption.txt" in names:
        return "social"
    if "raw.txt" in names:
        return "pasted-text"
    return "unknown"


def title_similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def ingredient_name_set(data: dict) -> set[str]:
    return {
        str(i.get("name", "")).lower().strip()
        for i in data.get("ingredients", [])
        if i.get("name")
    }


def jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 0.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def find_dedup_candidates(
    draft: dict,
    title_threshold: float = 0.6,
    ingredient_threshold: float = 0.4,
) -> list[dict]:
    """Scan recipes/ for anything that looks like the same dish as `draft`.
    Flags candidates for a human decision (merge vs. keep-both) — never
    auto-resolves.
    """
    draft_title = draft.get("title", "")
    draft_ingredients = ingredient_name_set(draft)

    candidates = []
    for path in sorted(RECIPES_DIR.glob("*.yaml")):
        try:
            existing = load_recipe_yaml(path)
        except yaml.YAMLError:
            continue

        t_sim = title_similarity(draft_title, existing.get("title", ""))
        i_sim = jaccard(draft_ingredients, ingredient_name_set(existing))

        if t_sim >= title_threshold or i_sim >= ingredient_threshold:
            candidates.append(
                {
                    "slug": path.stem,
                    "title": existing.get("title"),
                    "title_similarity": round(t_sim, 3),
                    "ingredient_similarity": round(i_sim, 3),
                }
            )

    return sorted(
        candidates,
        key=lambda c: max(c["title_similarity"], c["ingredient_similarity"]),
        reverse=True,
    )


def collect_tags() -> list[str]:
    tags: set[str] = set()
    for path in RECIPES_DIR.glob("*.yaml"):
        try:
            data = load_recipe_yaml(path)
        except yaml.YAMLError:
            continue
        tags.update(data.get("tags", []) or [])
    return sorted(tags)
