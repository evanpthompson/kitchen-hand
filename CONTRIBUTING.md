# Contributing

Kitchen Hand is a personal project that's open source because it might be
useful to others, not a project actively seeking outside contributors —
that said, issues, PRs, and recipe contributions are welcome.

## Project layout

See `README.md` for the full layout. In short: `schema/` (recipe format),
`recipes/` (the trusted collection) and `recipes/_drafts/` (unreviewed),
`inbox/` (raw captures), `tools/` (root Python CLI scripts), `service/`
(FastAPI backend, its own `pyproject.toml`), `app/` (Flutter frontend).

## Dev setup

Dependency management is `uv` (Python) — no `requirements.txt` anywhere,
`pyproject.toml` + `uv.lock` is the source of truth. Two independent Python
projects plus one Flutter project:

```sh
# root tools/
uv run tools/validate_recipes.py [--drafts]
uv run tools/fetch_youtube.py <slug> <url>
uv run ruff check tools/

# service/ (API backend)
cd service
uv run uvicorn app.main:app --reload   # serve
uv run pytest                          # test
uv run ruff check .                    # lint

# app/ (Flutter frontend)
cd app
flutter pub get
flutter analyze
flutter test
flutter run -d macos   # or your platform of choice
```

Run `ruff check` / `flutter analyze` clean before opening a PR. The
`service/` test suite runs against the real repo state (actual
`recipes/`/`_drafts/`/`inbox/` contents, not a fixture) — if you add
recipes as part of a PR, expect the test count/assertions to still pass,
but don't be surprised the tests know about real recipe content.

## Contributing a recipe

Recipes don't get merged directly into `recipes/` — they go through the
pipeline in `docs/ingestion.md`: capture the source into `inbox/<slug>/`,
normalize into `recipes/_drafts/<slug>.yaml` against
`schema/recipe-v1.schema.json`, and open a PR with the draft. Review
before merging into `recipes/` checks:

- Schema-valid (`uv run tools/validate_recipes.py --drafts`, or the
  `service/` API's `/drafts/{slug}/validate`).
- Real attribution — `provenance` filled in for anything ingested from an
  external source (URL/document/social/YouTube), or a `source` note at
  minimum. Don't submit a recipe you don't have the right to share; see
  `docs/data-sources.md` for which upstream APIs/datasets are actually
  redistributable.
- No invented values — a gap in the source (missing quantity, ambiguous
  timing) should show up in `provenance.extraction_notes`, not a guessed
  number. See the Chengdu noodles example already in `recipes/_drafts/`
  for what a properly-flagged draft looks like.
- No near-duplicate of an existing recipe without a reason (the `service/`
  backend's promote step checks this automatically).

## Contributing code

- Keep changes scoped — this repo deliberately keeps normalization manual
  (see `docs/app-spec.md` Non-goals) and hardware control out of the app
  entirely (that's the separate, much earlier-stage Phase 1/2 work in
  `docs/roadmap.md`). PRs that quietly expand either of those should
  explain why in the PR description.
- Match existing patterns rather than introducing a new one — e.g. the
  ingestion API's dedup check and draft lifecycle in `service/app/core.py`
  and `service/app/routers/` are the reference for how new endpoints
  should be shaped.
- Add a test. The `service/` suite is small on purpose; a PR that adds
  behavior without a test covering it will likely get asked for one.

## Reporting issues

Open a GitHub issue. For anything related to the Joyoung CJ-A9U hardware
work specifically, note that Phase 1 (reverse engineering) hasn't started
yet — see `docs/joyoung-cj-a9u-notes.md` for what's confirmed vs. still
just manufacturer claims.
