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
- `docs/backlog.md` — what is left and what it is worth, with the measured
  yield curve behind it. Six batches took the collection from 3 recipes to 43;
  this records where the corpus stops paying and why.
- `docs/telegram-ingest-spec.md` — spec for a one-tap phone capture path: a
  Telegram bot you share a Reel to, which becomes an `inbox/` capture. Not
  built. Chosen over WhatsApp because it needs no public webhook, and over an
  iCloud queue file because Telegram holds messages server-side until
  collected.
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
- `tools/poll_telegram.py` + `tools/telegram_transport.py` — share a Reel to
  your own Telegram bot and it becomes an `inbox/` capture in seconds, rather
  than waiting days for a DYI export. Long polling, so **no public webhook** —
  which is what ruled out WhatsApp. Downloads nobody else's media. The
  transport half is stdlib-only and imports nothing from this repo, so it can
  be extracted when a second project wants it; a test parses its imports to
  keep that true. See `docs/telegram-ingest-spec.md`.
- `tools/transcribe_audio.py` — speech-to-text for a recipe that is spoken
  rather than written. **You supply the file**; it downloads nothing, because
  Instagram and TikTok both disallow automated access. Runs `faster-whisper`
  locally (free, offline) rather than markitdown's built-in
  `recognize_google`, which uploads your audio and is weaker on exactly the
  words that matter. Writes `inbox/<slug>/transcript.txt` with a header saying
  the text is unverified, and lists every segment the model was unsure about
  with its timestamp. Optional extra: `uv sync --extra transcribe`.
- `tools/triage_inbox.py` — scores every capture on how much of a recipe its
  text holds and sorts them into `strong` / `weak` / `food-no-text` /
  `not-food`. What makes a bulk import workable. A **report, never a gate**:
  it reads `inbox/` and writes nothing to it. `--bucket NAME` prints bare
  slugs for piping; `--out DIR` writes one file per bucket; `--urls` adds
  each capture's post link, for when you need to go and look at one.
- `tools/import_instagram_saved.py` — turns an Instagram "Download Your
  Information" export into `inbox/<slug>/` captures: `url.txt`, `meta.txt`
  (handle, permalink, hashtags, dates) and `caption.txt`. No Meta API returns
  saved posts; the JSON export is the only route, and it carries the caption
  text, so an imported post needs no pasting. `--list-collections` and
  `--collection NAME` filter to a curated saved collection. Repairs the
  Latin-1 mojibake Instagram writes into captions, and refuses to report
  success on a partial import. Re-runnable: dedups on permalink, never
  overwrites a file.
- `service/` — the ingestion workflow app's FastAPI backend (Phase A of
  `docs/app-spec.md`). Own `pyproject.toml`/`uv.lock`, separate from the
  root tooling.
- `app/` — the ingestion workflow app's Flutter frontend (Phases B and C):
  capture, inbox queue, draft review, collection browser, talking to
  `service/` over REST. The capture screen is a queue worker for the captures
  that still need text by hand — carousel posts whose steps are in the images,
  TikToks, documents, pasted text.

## Development

Dependency management is `uv` (Python) — `pyproject.toml` + `uv.lock`,
no `requirements.txt`. Three separate projects:

- **Root** (`tools/`): `uv run tools/validate_recipes.py [--drafts]`,
  `uv run tools/fetch_youtube.py <slug> <url>`,
  `uv run tools/import_instagram_saved.py <export> [--dry-run]`,
  `uv run tools/triage_inbox.py [--bucket NAME]`,
  `uv run --extra transcribe tools/transcribe_audio.py <slug> <file>`,
  `uv run tools/poll_telegram.py [--whoami|--once]`.
  `uv run pytest` runs the root tool tests.
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
spec for the ingestion workflow app (`docs/app-spec.md`). Phases A (FastAPI
backend in `service/`), B (Flutter frontend in `app/` — inbox queue, draft
review, collection browser) and C (raw-paste capture screen) are built and
tested. Hardware work not started yet.

## License

Code (schema, `tools/`, `service/`, `app/`) is MIT-licensed — see `LICENSE`.
That covers the software, not the recipe content: recipes brought in through
the ingestion pipeline retain whatever attribution/rights apply to their
original source (see each recipe's `provenance`/`source` field and
`docs/data-sources.md`) — MIT on this repo doesn't relicense someone else's
recipe or transcript as your own.

## Attribution and licensing

40 of the 43 recipes here come from named creators, and every one records its
`source`, `source_url` and creator. `source` is a required schema field, so a
recipe without attribution fails validation.

The MIT `LICENSE` covers the code, schema and file structure — not the recipe
content. See `NOTICE.md`, which also explains how a creator can have their
recipe removed.
