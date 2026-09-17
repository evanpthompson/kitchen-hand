# Ingestion pipeline

Goal: bring recipes in from wherever they're actually found (a URL, a photo
of a recipe card, an Instagram caption, a TikTok, a pasted forward from a
group chat) without lowering the bar on quality. The pipeline is one shared
process with a source-specific first step:

```
capture (source-specific) -> normalize (shared) -> draft -> review (human) -> promote
```

Every recipe in `recipes/*.yaml` has been through a human review step.
Nothing is auto-merged. `recipes/_drafts/` is the holding area for anything
that hasn't cleared review yet — treat it as "unverified," never as a source
of truth for cooking.

## 1. Capture — one folder per candidate recipe

Create `inbox/<slug>/` and drop the raw material in, untouched:

- **URL** — `inbox/<slug>/url.txt` containing the link. If the page has
  `schema.org/Recipe` JSON-LD (most recipe blogs do), save it as
  `inbox/<slug>/jsonld.json` too — it's already structured and is the
  highest-trust capture type, since the site authored it as data, not prose.
- **Document** (photo of a recipe card, cookbook page, PDF) — save the
  image/PDF itself as `inbox/<slug>/source.<ext>`. Read directly (Claude can
  read images natively) rather than routing through a separate OCR step.
- **Instagram** — do not scrape. Paste the caption and any comments that
  contain recipe content into `inbox/<slug>/caption.txt`, and save a
  screenshot as `inbox/<slug>/screenshot.png` if the steps are in the image
  itself (common for carousel recipe posts). Note the `@handle` and post
  date in a one-line `inbox/<slug>/meta.txt`.

  For posts you **saved** rather than found one at a time, don't build an
  Instagram app: no Meta API returns saved posts. Every permission in the
  "Manage messaging and content on Instagram" use case
  (`instagram_business_basic`, `instagram_basic`, `instagram_content_publish`,
  `pages_*`) scopes to content you own or manage — saved posts and collections
  have never had an endpoint. The sanctioned route is the export: Instagram →
  Accounts Centre → Your information and permissions → **Download your
  information**, in **JSON** format (not HTML).

  **The JSON export carries the captions.** Per saved post it holds the
  permalink, the full caption text, the creator's handle and display name, the
  hashtags, and when you saved it — so the import is the whole capture, not
  just bookkeeping. Nothing needs pasting for a post whose recipe is in its
  caption. (Verified 2026-09-17 against a 548-post archive: 547 carried a
  caption.)

  ```bash
  # what collections exist, and how big each is
  uv run tools/import_instagram_saved.py ~/Downloads/your_instagram_activity --list-collections

  # import one collection
  uv run tools/import_instagram_saved.py ~/Downloads/your_instagram_activity \
      --collection "Tasty recipes" --dry-run
  ```

  Saved **collections** are the useful filter. A saved folder is mostly not
  recipes; a collection you curated is. Drop `--collection` to sweep
  everything, which is worth doing once to catch recipes you never filed.

  Each post becomes `inbox/ig-<handle>-<shortcode>/` holding `url.txt`,
  `meta.txt` (handle, permalink, hashtags, collection, dates) and
  `caption.txt`. Folder names are provisional — you don't know the dish at
  capture time — so rename to the real dish slug when you normalize into
  `_drafts/`.

  Three things the importer refuses to do quietly, each of which showed up in
  a real export:

  - **Mis-encoded captions.** Instagram writes UTF-8 back as Latin-1, so an
    apostrophe arrives as three junk characters and fractions are worse. 333
    of 548 captions were damaged. The repair is applied only when the round
    trip fully succeeds; anything that fails is written unchanged and flagged
    `encoding: SUSPECT` in its `meta.txt`, because a half-decoded caption
    corrupts exactly the quantities this pipeline exists to get right.
  - **Posts a collection names but the export omits.** One of the 45 posts in
    a real "Tasty recipes" collection was absent from `saved_posts.json`
    (deleted by the creator, most likely). The run fails and prints the URL
    rather than importing 44 and calling it done.
  - **Entries it cannot parse.** Meta has shipped at least two export shapes;
    both are supported, and anything matching neither fails the run. When the
    format changed under an earlier version of this tool, all 548 entries came
    back unparsed and nothing was written — which is the correct failure.

  `--allow-unparsed` downgrades those refusals to warnings once you have read
  them. The importer is safe to re-run after every new export: it dedups on the
  permalink rather than the folder name, so folders you have already renamed
  are recognised, and it never overwrites a file that exists.

  **Still pasted by hand:** posts whose steps are in the carousel images rather
  than the caption (add `screenshot.png`), and any caption you need to correct.
  The app's capture screen (`docs/app-spec.md`) is the place to do both without
  touching the filesystem.

  Captions for a post you did not author have no cheap API route either — the
  only sanctioned one is `business_discovery` on the Instagram API *with
  Facebook Login*, needing a Business account linked to a Page, Advanced Access
  for `instagram_basic` (App Review + Business Verification), and the creator
  to also be Business/Creator. The export makes it moot.

- **TikTok** — same rule, no scraping/auto-download. Paste the caption into
  `caption.txt`. If the recipe is spoken rather than written on-screen,
  provide a transcript as `inbox/<slug>/transcript.txt`. Note `@handle` and
  date in `meta.txt`.

  `tools/transcribe_audio.py` is that transcription step, for any source where
  the recipe is spoken — TikTok, a Reel, a voice note:

  ```bash
  uv sync --extra transcribe          # once; faster-whisper is optional
  uv run tools/transcribe_audio.py <slug> ~/Desktop/clip.mp4 --language en
  ```

  **It downloads nothing.** Getting the media onto disk is your step, and it
  has to be: Instagram names ClaudeBot in robots.txt and then disallows `*`
  outright, and TikTok is the same. The tool refuses any file type not on its
  allow-list, refuses to overwrite a transcript you have corrected, and
  refuses with a readable message rather than a traceback when a file will not
  decode.

  It runs `faster-whisper` locally rather than markitdown's built-in audio
  support. markitdown's path is `speech_recognition.recognize_google`, which
  uploads the audio to Google and is weaker on the words that matter most
  here — "two teaspoons" and "two tablespoons" are one phoneme apart and a
  factor of three apart. Whisper is free either way and runs offline.

  **A transcript is never trusted output.** Each one is written with a header
  saying it is machine-generated and unverified, and every segment the model
  was unsure about is listed at the end with its timestamp and confidence
  scores, so the cross-check has somewhere to start. Flagged segments stay in
  the body as well — marking a line for review never removes it. Set
  `provenance.transcribed: true` on any draft built from one.
- **YouTube** — `tools/fetch_youtube.py <slug> <url>` pulls title,
  description, and full transcript straight from YouTube's own transcript
  API (via `markitdown`) into `inbox/<slug>/youtube.md` — no video download,
  no page scraping. Unlike Instagram/TikTok this is a legitimate direct API
  call, not something we're avoiding. Two things to watch for:
  - Cooking channels frequently link a full written recipe (blog/Substack)
    in the description — if one's there, also capture it as a **URL**
    source (see above) and treat it as higher-trust than the transcript for
    exact quantities.
  - Auto-generated transcripts mis-hear numbers/units more than anything
    else in the text. Treat every quantity/time/temp pulled from a
    transcript as needing a cross-check (against the description, comments,
    or the video itself) before it's trusted enough to promote.
- **Pasted text** (group chat, email, memory) — `inbox/<slug>/raw.txt`, plus
  whatever attribution is known in `meta.txt` (even "from Mom, no source").

Keep the raw capture around after promotion — it's the audit trail behind
`provenance.raw_capture_path` and the only way to re-check an extraction
later without re-finding the original post.

## 1b. Triage — making a bulk import workable

A one-at-a-time capture goes straight to normalize. A **bulk** capture does
not: sweeping a whole Instagram export put 549 folders in `inbox/`, of which
444 were guitar tutorials, electronics and interior design. An inbox that is
80% noise is an inbox nobody works.

```bash
uv run tools/triage_inbox.py                  # summary + the top of the list
uv run tools/triage_inbox.py --urls           # ... with each post's link
uv run tools/triage_inbox.py --bucket strong  # bare slugs, one per line
uv run tools/triage_inbox.py --out /tmp/tri   # one file per bucket
```

Use `--urls` whenever the output is going to a person rather than to `xargs`.
Normalizing a capture nearly always raises a question only the original post
can answer — a missing yield, an ambiguous unit, a method the caption skips —
and a slug is not something you can open.

Four buckets, in descending readiness:

| Bucket | What it is | What to do |
|---|---|---|
| `strong` | caption holds quantities and method | normalize it |
| `weak` | food, partial recipe | read it, then decide |
| `food-no-text` | food post, recipe not in the caption | screenshot or transcript via the capture screen |
| `not-food` | no food signal | drop it |

`food-no-text` is mostly one Instagram pattern: *"comment RECIPE and I'll DM
you the full thing."* The recipe is in neither the caption nor the video, so
these need a real capture step rather than a re-import.

### Why it reports instead of filtering

**`triage_inbox.py` never writes to `inbox/` and never deletes.** That is a
deliberate split, and the same rule as everywhere else here: a keyword
heuristic is not allowed to decide what counts as a recipe.

It was tempting to put the scoring in `import_instagram_saved.py` as a
`--min-food-signal` flag. Had that existed, the first version of the pattern
— which matched `eat` inside *great* and *creating*, filing a GitHub post as
food — would have silently not-imported seven real captures, and nothing
would ever have pointed at the bug. Because the importer took everything and
the scoring ran afterwards over what was on disk, the same bug was a visible
mislabel that took one commit to fix.

So the importer captures everything, triage sorts it, and a human runs the
delete:

```bash
uv run tools/triage_inbox.py --bucket not-food > /tmp/drop.txt
# read /tmp/drop.txt first
(cd inbox && xargs rm -rf < /tmp/drop.txt)
```

## 2. Normalize — shared, regardless of source

One rule set, applied by whoever/whatever does the extraction (in practice:
ask Claude to do it in a session, pointed at the `inbox/<slug>/` folder):

- **Never invent a value.** If a quantity, time, or temperature isn't in the
  source, leave the field out (or `null` for machine fields) — don't guess a
  plausible number. Put what's uncertain in `provenance.extraction_notes`
  instead of silently resolving it.
- **Preserve attribution.** `provenance` is required for anything that came
  through this pipeline: `input_type`, `creator`, `captured_date` at minimum,
  plus `source_url` when one exists.
- **Re-sequence into `phases`**, same as any hand-written recipe — one phase
  per real step, human `instruction` always filled in, machine fields
  (`heat_level`/`temp_c`/`stir_speed`/`lid`) filled in only if the source
  actually specifies them (rare) and otherwise left null.
- **Flag contradictions rather than resolving them silently** — e.g. a
  caption says 2 tbsp soy sauce, a comment reply from the creator corrects it
  to 2 tsp — note both in `extraction_notes` and let the human reviewer
  decide, don't pick one quietly.
- Output goes to `recipes/_drafts/<slug>.yaml`, not `recipes/`.

## 3. Review (human) — the actual quality gate

Before promoting a draft, check:

1. **Dedup** — does a similar recipe already exist in `recipes/`? Compare
   title and ingredient set. If yes: decide merge (better version replaces
   old) vs. keep-both (genuine variant — tag it as a variant in `notes`).
2. **Completeness** — ingredients have quantities where the source gave them;
   steps are actually sequential and unambiguous; nothing critical is
   missing (a step that's obviously implied but never stated, e.g. "add oil"
   before "sear" is fine to leave out only if truly obvious).
3. **Attribution correct** — creator/handle and source URL are accurate and
   the raw capture is still in `inbox/`.
4. **Validates** — run `tools/validate_recipes.py` (point it at `_drafts/`
   too, or move the file into `recipes/` first and validate there).
5. **Tags reused, not reinvented** — check existing tags across `recipes/`
   before adding a new one, to keep the vocabulary from sprawling.

Only after all five: move the file from `recipes/_drafts/` to `recipes/`.
That move *is* the promotion — there's no separate "publish" step.

## Why review gates instead of auto-import

The whole point raised when starting this collection was quality over raw
count. An importer that auto-merges whatever it scrapes optimizes for
volume; a human-reviewed draft folder optimizes for "would I actually trust
this enough to cook it and to eventually let a machine run it unattended."
Given that Phase 2+ of the roadmap is literally handing some of these
recipes to an automated cooking machine, silently wrong quantities or
temperatures are a real-world failure mode, not just a data-quality nit.
