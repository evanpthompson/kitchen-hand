# Kitchen Hand

An open-source alternative to all-in-one cooking robots like Posha and Nosh:
a recipe collection/ingestion pipeline plus two parallel hardware tracks —
(A) an open rig built from separately-controlled off-the-shelf components
(induction burner, pans, a StirMATE stirrer, eventually an ingredient
dispenser), and (B) a reverse-engineered **Joyoung CJ-A9U** ("Intelligent
Fully Automatic Stir-Fry Machine Robot") as a second, harder target and a
reference for how a sealed commercial unit solves the same problems. See
`docs/roadmap.md` for the full plan and `docs/open-rig-hardware.md` for the
feature-parity checklist against Posha/Nosh. Track A's concrete MVP: an
unattended, flawless béchamel sauce — see `docs/mvp-bechamel.md`.

## Why this shape

Both hardware tracks cook via discrete phases (heat, stir, hold,
add-ingredient cues) rather than free-form stovetop technique. Recipes here
are written as an ordered list of **phases** from day one — each phase has a
human-readable instruction *and* the parameters (temperature/heat level,
stir speed, duration, lid state) a machine program would need for that same
step. Nothing forces you to fill in the machine fields now; a recipe with
only `instruction` text is still valid. But as either hardware track comes
online, existing recipes slot into a machine program without being
rewritten from scratch.

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
- `docs/hardware-sensors-research.md` — sensor survey for the CJ-A9U track
  (current/thermal/vibration/audio/RF), tiered by how invasive each is.
- `docs/open-rig-hardware.md` — the open-rig track: StirMATE/induction
  burner control options, the Posha/Nosh feature-parity checklist, and the
  ingredient-dispensing gap.
- `docs/mvp-bechamel.md` — Track A's concrete MVP definition and acceptance
  criteria; `recipes/bechamel-sauce.yaml` is the reference recipe.
- `tools/validate_recipes.py` — schema validator; `--drafts` checks
  `recipes/_drafts/` instead of the main collection.
- `tools/fetch_youtube.py` — captures a YouTube video's title/description/
  transcript into `inbox/` via `markitdown` (transcript API, no scraping).
- `service/` — the ingestion workflow app's FastAPI backend (Phase A of
  `docs/app-spec.md`). Own `pyproject.toml`/`uv.lock`, separate from the
  root tooling.
- `app/` — the ingestion workflow app's Flutter frontend (Phase B):
  inbox queue, draft review, collection browser, talking to `service/`
  over REST.

## Development

Dependency management is `uv` (Python) — `pyproject.toml` + `uv.lock`,
no `requirements.txt`. Three separate projects:

- **Root** (`tools/`): `uv run tools/validate_recipes.py [--drafts]`,
  `uv run tools/fetch_youtube.py <slug> <url>`.
- **`service/`** (the API backend): from `service/`, `uv run uvicorn
  app.main:app --reload` to serve it, `uv run pytest` to test, `uv run
  ruff check .` to lint.
- **`app/`** (the Flutter frontend): from `app/`, `flutter run -d macos`
  (or your platform), `flutter test`, `flutter analyze`.

See `CONTRIBUTING.md` for the full contribution workflow, including how
recipe contributions go through the ingestion pipeline rather than a
direct PR into `recipes/`.

## Status

Phase 0: schema, ingestion pipeline, and a first example recipe, plus a
spec for the ingestion workflow app (`docs/app-spec.md`). Phase A (FastAPI
backend in `service/`) and Phase B (Flutter frontend in `app/` — inbox
queue, draft review, collection browser) are both built and tested. Phase C
(raw-paste capture screen) and hardware work not started yet.

## License

Code (schema, `tools/`, `service/`, `app/`) is MIT-licensed — see `LICENSE`.
That covers the software, not the recipe content: recipes brought in through
the ingestion pipeline retain whatever attribution/rights apply to their
original source (see each recipe's `provenance`/`source` field and
`docs/data-sources.md`) — MIT on this repo doesn't relicense someone else's
recipe or transcript as your own.
