# Ingestion Workflow App — Spec

Turns the manual capture → normalize → draft → review → promote pipeline
(`docs/ingestion.md`) into an actual app, so working the inbox queue,
reviewing drafts, and promoting recipes doesn't mean hand-editing YAML and
running scripts from a terminal every time.

## Stack

- **Backend: Python (FastAPI).** Chosen over any alternative specifically
  because Python has the deepest ecosystem for the hardware-control work
  this project eventually leads to (Phase 1/2 in `docs/roadmap.md` —
  reverse-engineering and driving the CJ-A9U). Building the curation
  backend in the same language now means it's a natural place to add
  machine-control endpoints later, rather than a second stack to bridge.
- **Frontend: Flutter.** Matches the stack you already know from
  `voice-agent-input-hub`, `landfall`, `meals`, etc. Talks to the FastAPI
  backend over a plain REST API — same client/server split you already use
  in landfall.
- **No database.** The git repo *is* the database: `inbox/`,
  `recipes/_drafts/`, `recipes/`, `schema/` as they exist today. The
  backend reads/writes those files directly; nothing new to sync or
  migrate.
- **Local only, single user.** No auth, no multi-tenancy. It's a household
  curation tool, not a hosted service.

## Non-goals (v1)

- **No automated normalization.** The backend does not call any LLM API to
  turn a raw capture into a draft. Normalization stays exactly as it is
  today — a human (with Claude's help, in a session like this one) writes
  `recipes/_drafts/<slug>.yaml` by hand or with assistance. The app's job
  starts once a draft file exists (or once a raw capture exists, for the
  inbox-browsing screen) — it does not generate one.
- **No hardware control.** That's Phase 1/2 of the overall roadmap and a
  separate effort. Python-as-backend is chosen partly to keep that door
  open, but nothing here talks to the CJ-A9U.
- **No cooking/consumption UI.** Browsing the trusted collection here is
  for curation sanity-checks (dedup, "does this already exist"), not for
  cooking from — that's the eventual Phase 3 companion app.

## Data model

Nothing new — this app operates on what already exists:

- `schema/recipe-v1.schema.json` — recipe/draft shape, including the
  `provenance` block for ingested recipes.
- `inbox/<slug>/` — raw captures, one folder per candidate recipe.
- `recipes/_drafts/<slug>.yaml` — normalized but unreviewed.
- `recipes/<slug>.yaml` — reviewed, trusted, promoted.

## API surface (FastAPI, v1)

### Inbox

| Method & path | Purpose |
|---|---|
| `GET /inbox` | List capture folders — slug, inferred source type (from which files are present), capture date (file mtime), whether a draft already exists for this slug. |
| `GET /inbox/{slug}` | Raw file listing + contents, for reading what was captured (caption text, transcript, screenshot, jsonld, etc.). |
| `POST /inbox/{slug}/youtube` | Given a URL, run the same capture `tools/fetch_youtube.py` already does, via the backend instead of the CLI. |
| `POST /inbox/{slug}/files` | Write pasted text / uploaded files into `inbox/{slug}/` — the mechanism for Instagram/TikTok/document/pasted-text captures, which stay manual-paste by design (no scraping). |

### Drafts

| Method & path | Purpose |
|---|---|
| `GET /drafts` | List `recipes/_drafts/*.yaml` with summary metadata: title, mode, servings, schema-valid?, has extraction_notes?. |
| `GET /drafts/{slug}` | Full parsed draft content. |
| `PUT /drafts/{slug}` | Save edits. Re-validates on save but does **not** block saving an invalid/in-progress draft — you need to be able to save partial work. |
| `POST /drafts/{slug}/validate` | Explicit validate-now, returns the schema error list (this is `tools/validate_recipes.py --drafts`, callable per-file instead of batch). |
| `POST /drafts/{slug}/promote` | Runs the full review-readiness check (schema valid, id matches filename, dedup scan against `recipes/`). If a similar existing recipe is found, returns the candidate match(es) instead of promoting — the UI surfaces a merge-or-keep-both decision rather than silently proceeding. Only on a clean pass does it move the file from `_drafts/` to `recipes/`. |
| `DELETE /drafts/{slug}` | Discard a draft. Does not touch `inbox/{slug}/` — the raw capture stays as an audit trail either way. |

### Recipes (the trusted collection)

| Method & path | Purpose |
|---|---|
| `GET /recipes` | List all `recipes/*.yaml` with metadata (title, mode, cuisine, tags, servings). |
| `GET /recipes/{slug}` | Full recipe content. |
| `GET /recipes/tags` | Distinct tag list across the collection — backs the "reuse tags, don't reinvent" review step. |

### Schema

| Method & path | Purpose |
|---|---|
| `GET /schema` | Serves `schema/recipe-v1.schema.json` as-is, so the frontend can drive client-side validation/form generation from the same source of truth instead of a hand-maintained copy. |

## Frontend (Flutter) — screens

1. **Inbox queue** — folders in `inbox/` not yet normalized into a draft
   (and ones that already have a draft, shown distinctly). Opening one shows
   the raw capture — caption, transcript, screenshot, whatever's there — so
   you can read it side by side while doing the normalize step in a Claude
   session.
2. **Draft review** — the core screen. Surfaces `provenance.extraction_notes`
   and any live schema validation errors in prominent panels above the
   editor. **v1 implementation note:** editing is a single JSON text editor
   over the whole draft, not per-field/per-ingredient form widgets — this is
   where an ambiguous-egg-count-style gap gets fixed, just as parsed JSON
   rather than structured inputs. Chosen over per-field forms to avoid
   building bespoke UI for arbitrary nested ingredient/phase arrays before
   there's real usage to learn from; still means never touching a terminal
   or hand-editing YAML. Revisit if this proves clunky in practice. Surfaces
   dedup candidates from the promote check (blocking dialog, "promote
   anyway" re-submits with `force=true`). "Promote" and "Discard" actions.
3. **Collection browser** — list/grid of `recipes/*.yaml`, filterable by
   tag/cuisine/mode, read-only detail view. Not a cooking mode — just a way
   to sanity-check what's already in the trusted collection.
4. **Raw-paste capture** (stretch, not v1) — a form (slug, source type,
   caption/transcript textarea, screenshot upload, handle, date) that posts
   to `/inbox/{slug}/files`, so Instagram/TikTok/document/pasted-text
   captures don't require manually creating folders and files by hand.

## Build phases

- **Phase A — backend only.** Wrap the existing `tools/validate_recipes.py`
  and `tools/fetch_youtube.py` logic into the FastAPI endpoints above,
  reading/writing the filesystem directly. Verify via HTTP client before any
  UI exists — this alone removes needing to hand-run scripts from a
  terminal.
- **Phase B — Flutter shell.** Screens 1–3 above, talking to the Phase A
  backend on `localhost`.
- **Phase C — raw-paste capture screen.** Closes the loop on
  Instagram/TikTok/document/pasted-text capture without touching the
  filesystem by hand.
- **Explicitly not in this app's scope, ever:** automated normalization
  (deferred by design, see Non-goals) and hardware control (separate
  roadmap phase).

## Open questions to resolve during/before Phase A

- **Dedup algorithm at promote time** — `docs/ingestion.md` names the
  concept (title + ingredient-set similarity) but not an implementation.
  Reasonable starting point: fuzzy string match on title plus Jaccard
  similarity on ingredient-name sets, some threshold flagged for manual
  judgment rather than auto-merge either way. Worth prototyping against the
  couple of recipes that exist today before trusting it on a larger corpus.
- **Where this app lives** — recommend a new top-level directory inside
  `kitchen-hand` (e.g. `service/` for the FastAPI backend,
  `app/` for the Flutter frontend) rather than a separate repo, since the
  entire point is operating directly on this repo's files.
- **Remote access** — out of scope for v1 (local-only), but if this is ever
  run from a different machine than where the files live, the file-access
  model (mount vs. upload) needs revisiting. Not a blocker now.
