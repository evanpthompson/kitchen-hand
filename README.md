# Stirfry Companion

A recipe collection and cooking-instruction format that starts as a plain human
cookbook and is structured so it can later drive an automatic cooking machine —
specifically a reverse-engineered **Joyoung CJ-A9U** ("Intelligent Fully
Automatic Stir-Fry Machine Robot").

## Why this shape

The CJ-A9U cooks via discrete phases (heat, stir, hold, add-ingredient cues)
rather than free-form stovetop technique. Recipes here are written as an
ordered list of **phases** from day one — each phase has a human-readable
instruction *and* the parameters (temperature/heat level, stir speed, duration,
lid state) a machine program would need for that same step. Nothing forces you
to fill in the machine fields now; a recipe with only `instruction` text is
still valid. But when the reverse-engineering work is further along, existing
recipes slot into a machine program without being rewritten from scratch.

## Layout

- `schema/recipe-v1.schema.json` — JSON Schema for a recipe file.
- `recipes/*.yaml` — one recipe per file, validated against the schema. Only
  reviewed, trustworthy recipes live here.
- `recipes/_drafts/` — normalized-but-unreviewed recipes, awaiting the review
  checklist in `docs/ingestion.md`. Not part of the collection yet.
- `inbox/` — raw captures (URLs, photos, social captions/transcripts, pasted
  text) feeding the ingestion pipeline, one folder per candidate recipe.
- `docs/roadmap.md` — phased plan from "cookbook" to "companion app driving the
  machine."
- `docs/ingestion.md` — how recipes get in: capture → normalize → draft →
  review → promote, across every input type (URL, document, Instagram,
  TikTok, pasted text), with the quality bar for promotion.
- `docs/data-sources.md` — verified licensing terms for recipe APIs/datasets
  considered as bulk sources (what's safe to store vs. live-lookup-only).
- `docs/app-spec.md` — spec for the ingestion workflow app (Python/FastAPI
  backend, Flutter frontend) that turns the manual pipeline into a real
  inbox/review/promote UI.
- `docs/joyoung-cj-a9u-notes.md` — what's publicly known about the CJ-A9U's
  modes/hardware, gathered before any hands-on reverse engineering starts.
- `tools/validate_recipes.py` — schema validator; `--drafts` checks
  `recipes/_drafts/` instead of the main collection.
- `tools/fetch_youtube.py` — captures a YouTube video's title/description/
  transcript into `inbox/` via `markitdown` (transcript API, no scraping).

## Status

Phase 0: schema, ingestion pipeline, and a first example recipe, plus a
spec for the ingestion workflow app (`docs/app-spec.md`). App not built yet;
no hardware work yet.
