# Backlog

What is left, and what it is worth. Written 2026-09-18, after six batches of
normalization took the collection from 3 recipes to 43.

Destined for Plane once the ticketing skill is working — this file is the
source, not the record.

---

## Where the corpus stands

All 106 captures in `inbox/`, accounted for:

| | count |
|---|---|
| Normalized into `recipes/` | 40 |
| Read and found to carry no recipe | 16 |
| **Untouched** | **50** |

Plus 3 recipes that predate the Instagram import and have no capture, for 43
in the collection.

## The yield curve

Six batches, and the fall-off is sharp and monotonic:

| batch | triage score | attempted | drafted | no recipe |
|---|---|---|---|---|
| 1 | 12–14 | 5 | 5 | 0 |
| 2 | 10–14 | 10 | 7 | 3 |
| 3 | 9–11 | 10 | 9 | 1 |
| 4 | 8–9 | 10 | 8 | 2 |
| 5 | 7–8 | 10 | 8 | 2 |
| 6 | **6–7** | 10 | **2** | **8** |

**Below a triage score of about 7 the captures stop being recipes.**
Everything scoring 8 or above is now either in the collection or recorded
here as having no method.

## What the 50 untouched actually are

| bucket | left | scores | expected yield |
|---|---|---|---|
| strong | 13 | 2 at 6, **11 at 5** | 2–3 recipes |
| weak | 21 | 8 at 4, 13 at 2 | 1 at most |
| food-no-text | 16 | 3 at 1, **13 at 0** | **0 from reading** |

The `food-no-text` bucket is not low-yield, it is *no*-yield by reading: 13 of
its 16 score zero because there is no recipe text at all. Those need
capturing, not extracting.

---

## Items

### B1 — Chase the two known link-outs
**Effort:** ~20 min · **Yield:** up to 4 complete recipes · **Best value left**

Two captures name a creator's own recipe site, and creator-authored pages have
consistently arrived complete — yield, prep and cook times, gram weights, no
questions asked. Both `mini-loaf-pan-focaccia` and
`roasted-garlic-butter-chicken` came in that way and needed nothing.

1. `jam-buttered-toast-cookies` — the creator states the caption is an
   abridgement and the full version is on her Substack. Named, not linked; the
   Substack needs finding. This is the only capture in the collection where
   the source says outright that what you are reading is incomplete.
2. `thepracticalkitchen.com` — a promo post
   (`ig-the-practical-kitchen-cxbu2oevyxq`) names four small-batch bread
   recipes on the site: mini focaccia (already in the collection), mini
   ciabatta, small batch crusty bread, small batch baguette. Three to fetch.

Check `robots.txt` before fetching either domain, as with every other URL
capture here.

### B2 — One final batch of the 13 strong
**Effort:** one batch · **Yield:** ~3 recipes

Exhausts the readable pile. Front-loaded: the 2 at score 6 first, then 11 at
score 5 where yield approaches zero.

After this, nothing readable is left behind.

### B3 — Decide what to do with `food-no-text`
**Effort:** a decision, then per-item capture · **Yield:** 16 recipes at most

Sixteen captures that are food but carry no recipe text. Mostly one Instagram
pattern: *"comment RECIPE and I'll DM you the full thing"*, plus carousel
posts whose steps are in the images.

The tools for these all exist as of today and none has been used in anger:

- **Telegram bot** — reply to the link message with the comment text pasted
- **Capture screen** (`app/`, Phase C) — screenshot upload for carousels
- **`transcribe_audio.py`** — Whisper, for recipes that are only spoken

The work is going back to Instagram per item and deciding whether each is
worth the trip. That is a different kind of task from batching, and it is the
user's call rather than a queue to work through.

### B4 — Telegram ingest, Phases 2 and 3
**Effort:** medium · See `docs/telegram-ingest-spec.md`

- **Phase 2 — media.** Photos to `screenshot.png`, voice notes through
  `transcribe_audio.py`. Phase 1 already records the Telegram `file_id` in
  `meta.txt` as `telegram_pending_media`, and a `file_id` is stable for the
  life of the bot, so nothing needs re-sending.
- **Phase 3 — acknowledgement.** Reply to each message with the slug it
  became, so the phone confirms without opening a laptop.

B3 is easier once Phase 2 lands, since screenshots then arrive from the phone
rather than through the desktop app.

### B5 — Recipes carried in with known gaps
**Effort:** a cook or a video each · **Yield:** quality, not count

Promoted deliberately, each flagged in its own file. None blocks cooking by
someone who knows the technique; all would block handing the recipe to
someone who does not.

| recipe | gap |
|---|---|
| `garlic-butter-chicken-creamy-potatoes` | air fryer temperature and time |
| `honey-butter-garlic-chicken` | air fryer temperature and time; **the whole sauce method is a proposal, not the source's** |
| `sweet-potato-breakfast-bowls` | turkey sausage and egg methods both absent |
| `arroz-con-pollo-meal-prep` | Spanish rice method points at an uncaptured video; "4 cups water plus 1½ later" implies a two-stage cook never described |
| `bbq-beef-sliders` | pepper jack listed twice in one assembly line — deliberate double layer, or a copy-paste error |
| `shredded-beef-cheese-sliders` | garlic paste in the method, absent from the ingredient list |
| `meatball-stroganoff` | credits "By: Luke Brown" but posted by @carnivorefamilykitchen — which account originated it |
| `poor-mans-burnt-ends` | rub, brown sugar and BBQ sauce still unquantified |

Two air-fryer recipes with no temperature or time is a pattern, not bad luck:
Instagram air-fryer recipes routinely omit both, presumably because the video
shows the dial.

### B6 — `triage_inbox.py --undone`
**Effort:** ~15 min

Every batch has needed the same ad-hoc query: which captures have neither a
recipe nor a draft. Reimplementing it inline got it wrong once — the
one-liner excluded `recipes/` but not `recipes/_drafts/`, and offered nine
in-progress drafts as fresh work. `pipeline_slugs()` already knows the answer.

One flag, one correct implementation.

### B7 — An ingredients-only filter for triage
**Effort:** ~20 min · **Value:** stops re-reading known rejects

Three of ten top-scoring captures in batch 2 had no procedure at all;
`ig-gymratrecipes` scored 11 on ingredient density with zero instructions.
`MEASURE` counts quantities and `METHOD` counts verbs, and neither can tell a
recipe from a shopping list — a shopping list for a recipe contains the same
words.

The fix is structural rather than lexical: **does any line begin with an
imperative or a step marker?** A step list starts lines with "Heat", "Add",
"Bake", or with `1.` / `-`. An ingredient list starts them with a number and a
unit. That check would have caught all three.

Related: rejected captures have no recorded state, so they resurface at the
top of every batch. Three of the first four candidates in batch 4 were already
rejected in batch 3. Either this filter or a marker file solves it.

---

## Not on this list

**The hardware tracks.** `docs/roadmap.md` Phases 1 and 2 are a separate
effort and unaffected by any of the above.

One thing the corpus did produce for them, though: **five recipes now share a
single roux-then-liquid machine program** — `bechamel-sauce`,
`white-country-gravy`, `creamy-pan-fried-chicken`, `meatball-stroganoff` and
`garlic-butter-chicken-mac-and-cheese`. Fat plus flour cooked out, liquid
added gradually with a continuous stir, thickened to a target. One program,
five parameter sets.

`white-country-gravy` is the plainest of the five — no protein to cook first,
nothing folded in afterwards — which makes it the natural second test after
the béchamel MVP in `docs/mvp-bechamel.md`.

`crispy-potato-omelet` is the other hardware candidate worth noting: a flat
pan held at medium-low for a timed stage, one flip, a second timed stage. No
stirring, no liquid, no judgement call except the flip.
