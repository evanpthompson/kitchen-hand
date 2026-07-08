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
- `recipes/*.yaml` — one recipe per file, validated against the schema.
- `docs/roadmap.md` — phased plan from "cookbook" to "companion app driving the
  machine."
- `docs/joyoung-cj-a9u-notes.md` — what's publicly known about the CJ-A9U's
  modes/hardware, gathered before any hands-on reverse engineering starts.
- `tools/` — validator/scripts (empty for now).

## Status

Phase 0: schema + a few example recipes. No app, no hardware work yet.
