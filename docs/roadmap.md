# Roadmap

## Phase 0 — Recipe collection (current)
- Define the recipe schema (`schema/recipe-v1.schema.json`).
- Write recipes as ordered phases with human instructions; fill in machine
  parameters (temp/stir/duration) opportunistically, not required.
- No app yet — recipes are just YAML files, readable and cookable by a human
  with no machine at all.

## Phase 1 — Reverse engineer the CJ-A9U
- Open the unit / inspect the control board, or capture the signals between
  the front-panel MCU and the induction/motor driver, whichever is less
  invasive to try first.
- Determine: how many discrete heat levels and stir speeds actually exist,
  how "modes" (stir-fry/braise/soup/hotpot/fry) map to those, whether there's
  any serial/BLE/Wi-Fi interface already present (some Joyoung models have an
  app + cloud pairing — check before assuming it's fully closed).
- Record findings in `docs/joyoung-cj-a9u-notes.md` as they're confirmed,
  separating "official spec" from "measured/inferred."

## Phase 2 — Map recipes to machine programs
- Once real control parameters are known, translate the `machine_program`
  fields already in the recipe schema into whatever protocol/format the
  machine (or a replacement controller) actually accepts.
- Validate a handful of existing recipes end-to-end on hardware.

## Phase 3 — Companion app
- Build the "AI-powered cooking companion" on top of the validated recipe
  format: recipe browsing/search, guided cook mode for recipes without full
  machine params, one-tap send-to-machine for recipes that have them.
- This is the point where a Flutter app (or reuse of an existing scaffold)
  makes sense — not before the format and hardware control are proven out.
