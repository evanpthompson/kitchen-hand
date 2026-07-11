# MVP target #2: chicken fried rice (pre-cooked rice)

Track A's second concrete milestone, after `docs/mvp-bechamel.md`: the open
rig makes chicken fried rice unattended, using pre-cooked rice and
pre-cooked chicken as inputs. Recipe is `recipes/chicken-fried-rice.yaml`.

## Why fried rice, and why pre-cooked rice this round

Béchamel proved sustained low/medium heat hold and continuous stirring.
Fried rice is a deliberately different stress test:

- **Sustained high heat, not low/medium.** Fried rice needs the pan hot
  enough to fry rather than steam the rice (wok hei) — the opposite end of
  the heat-control range from béchamel's scorch-avoidance problem. This
  exercises whatever heat-control approach Step 1 lands on at its other
  extreme: can it hold "high" reliably, not just "low/medium precisely"?
- **Intermittent, high-speed tossing, not continuous whisking.** The
  StirMATE-under-control problem shifts from "don't stall over 20 minutes"
  to "move solid, chunky, low-liquid content without it just spinning in
  place or piling up against the pot wall" — a real test of whether the
  stirring mechanism actually works on food that isn't a liquid/sauce.
- **Multiple discrete ingredient-add events, still zero dispensing gap.**
  Egg, chicken, rice, then a soy-sauce/sesame-oil/scallion finish — four
  distinct add points, more than béchamel's single milk addition, but
  every one of them is still assumed to be a human (or future dispenser)
  action at a cued phase boundary. This pushes on phase-timing/sequencing
  without yet requiring the dry-ingredient dispensing mechanism (Step 2's
  biggest unsolved gap) to exist.
- **Pre-cooked rice and pre-cooked chicken, deliberately, for now.** Two
  harder problems are explicitly deferred rather than solved here:
  - Cooking raw rice needs a water-ratio + timing + doneness problem this
    rig doesn't have a solution for yet (no water dispensing, no way to
    judge rice doneness short of a camera/CV check).
  - Cooking raw chicken safely needs verified internal temperature, which
    means either a probe thermometer inserted into the food itself (not
    yet part of the rig) or a much more conservative time/temp margin than
    this MVP is trying to prove out.
  Using both pre-cooked keeps this milestone scoped to "can the rig sear/
  fry/toss at high heat," not "can the rig cook rice or verify food safety"
  — those become their own later MVPs once this one is proven.

## What "flawless" means (acceptance criteria)

A run counts as flawless if, unattended from the egg-scramble step through
plating:

1. **Rice isn't clumped or mushy** — clumps from the cold rice got broken
   up and separated during frying, not left as intact cold lumps.
2. **No scorching** — nothing stuck/blackened on the pot bottom despite
   sustained high heat.
3. **Even distribution** — soy sauce, egg, and vegetables are mixed
   through the rice, not pooled/settled in one spot from insufficient
   tossing.
4. **Everything reheated through** — the pre-cooked chicken and rice are
   hot throughout, not just on the surface that touched the pan.
5. **Repeatable** — same result across multiple attempts with the same
   recipe/hardware config.

## What this requires from Track A Step 1, concretely

- Heat control that holds "high" reliably for several minutes straight —
  the opposite calibration target from béchamel's "hold low/medium without
  scorching." If button-actuation heat control was borderline on béchamel,
  this phase is the one likely to expose whether the discrete power-level
  buttons even go high enough, or whether the SSR bypass
  (`docs/open-rig-hardware.md`) is needed for this end of the range too.
- Stirring/tossing that actually displaces solid rice grains around the
  pot, not just spins against pooled liquid — may reveal that the
  servo-on-StirMATE-dial approach that worked for béchamel's sauce isn't
  sufficient for a drier, chunkier food, in which case the board-level
  motor-driver injection option becomes worth trying sooner than planned.
- Correct phase-timed ingredient adds at four points instead of one — a
  test of sequencing/timing precision, not of any new hardware capability.

## Definition of done for this MVP

An actual run on actual hardware, unattended from the first phase through
plating, meeting all five acceptance criteria above, repeated at least
twice — same bar as `docs/mvp-bechamel.md`.

## Explicitly out of scope for this version

- Cooking rice from raw (water dispensing, doneness judgment) — future MVP.
- Cooking chicken from raw (temp-verified food safety) — future MVP, likely
  needs a food-contact probe thermometer per `docs/perception-sensors.md`
  discussion (not yet written up as its own doc).
- Any camera/CV doneness check — Phase 3 territory, not needed here since
  pre-cooked inputs make "doneness" a non-issue for this version.
