# MVP target: flawless, automated béchamel sauce

Track A's (`docs/roadmap.md`, `docs/open-rig-hardware.md`) concrete MVP: the
open rig (induction burner + StirMATE + pans) makes a béchamel sauce
unattended, and it comes out right every time. Recipe itself is
`recipes/bechamel-sauce.yaml`.

## Why béchamel specifically

It's the smallest recipe that actually exercises both core capabilities the
rig needs, without needing the ingredient-dispensing gap solved first:

- **Precise low/medium heat hold, no scorching.** The roux stage (butter +
  flour, 2-3 min) is unforgiving — too hot and it browns/scorches before
  the flour actually cooks; too cool and the raw-flour taste never cooks
  out. The simmer stage (15-20 min) has the same failure mode at the pot's
  bottom/corners. This is a real, continuous test of whatever heat-control
  approach Step 1 lands on (button actuation vs. SSR+temp-probe bypass) —
  a sauce that scorches is an immediate, obvious "the heat control isn't
  good enough yet" signal.
- **Continuous stirring, not periodic.** Béchamel needs whisking through
  almost the entire cook, not occasional stirs — a real test of whether
  the StirMATE-under-external-control approach (servo-on-dial or
  motor-driver injection) can actually run unattended for ~20 minutes
  without stalling, losing contact with the pot, or needing a human to
  notice a lump forming.
- **At most one dispensed ingredient.** Milk is added gradually during
  cooking, but it's a single liquid — a single peristaltic pump would
  cover it, rather than needing Posha/Nosh's full multi-hopper spice
  carousel (Track A Step 2, the largest unsolved gap). Béchamel is a
  natural wedge into that problem: it justifies building *one* liquid
  doser before committing to the harder dry-ingredient dispensing
  mechanism.
- **Failure is legible.** Lumps, scorching, and wrong consistency are all
  things a person (or eventually a camera, per the CV stretch goal in
  `docs/roadmap.md` Phase 3) can immediately see. Good for validating
  "did the automation actually work" without needing taste-testing or
  ambiguous judgment calls.

## What "flawless" means (acceptance criteria)

A run counts as flawless if, unattended from butter-melt to seasoning:

1. **No lumps** — milk incorporation didn't outpace the whisking.
2. **No scorching** — nothing browned in the roux stage; nothing stuck/
   caramelized on the pot bottom or corners during the simmer.
3. **Correct consistency** — coats the back of a spoon (nappe): thick
   enough to hold a line drawn through it, not runny, not gluey/paste-like.
4. **Repeatable** — not a one-off lucky run; the same result across
   multiple attempts with the same recipe/hardware config.

## What this requires from Track A Step 1, concretely

- Heat control good enough to hold "medium-low" and "medium" reliably for
  extended periods without a human watching — this is really what decides
  whether button-actuation is good enough or the SSR+temp-probe bypass
  (`docs/open-rig-hardware.md`) is necessary. Button-actuation is worth
  trying first; béchamel's roux stage will likely be the thing that proves
  or disproves it.
- Stirring that survives ~20 continuous minutes without stalling or losing
  contact with the pot bottom/corners (where scorching starts).
- A milk-incorporation step that's either done by a human at a cued phase
  transition (fine for a first working version — the recipe's phase
  boundaries already mark exactly when to add it) or, once Step 1 heat/stir
  control is solid, handed to a single peristaltic pump as the first real
  piece of Step 2's dispensing work.

## Definition of done for this MVP

Not "the schema supports it" (already true) — the bar is an actual run on
actual hardware, unattended past the initial setup, that meets all four
acceptance criteria above, repeated at least twice.
