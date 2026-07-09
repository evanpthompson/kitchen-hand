# Roadmap

## Vision

Build an open-source alternative to all-in-one cooking robots like Posha
and Nosh — automated heat control, automated stirring, ingredient
dispensing, and recipe-driven operation — using separately-controlled,
off-the-shelf/DIY hardware (induction burner, pans, a StirMATE stirrer, and
eventually an ingredient dispenser) instead of one closed proprietary unit.
See `docs/open-rig-hardware.md` for the feature-parity checklist and what's
owned so far.

The Joyoung CJ-A9U reverse-engineering effort runs in parallel as a second,
harder hardware target for the same recipe format and (eventually) the same
software stack — and as a reference for how a sealed commercial unit solves
the same heat/stir/ingredient-timing problems.

## Phase 0 — Recipe collection (current, shared by both tracks)
- Define the recipe schema (`schema/recipe-v1.schema.json`).
- Write recipes as ordered phases with human instructions; fill in machine
  parameters (temp/stir/duration) opportunistically, not required.
- No app yet — recipes are just YAML files, readable and cookable by a human
  with no machine at all.
- The ingestion pipeline and workflow app (`docs/ingestion.md`,
  `docs/app-spec.md`) — built, and shared by both hardware tracks below.

## Track A — Open rig (induction burner + StirMATE + pans + future dispenser)

See `docs/open-rig-hardware.md` for full detail. Summary:

- **Step 1 — instrument & control each component.** StirMATE and the
  induction burner are both plain manual-dial devices with no existing
  digital interface — each needs either external physical actuation
  (servo/solenoid on the existing dial/buttons, non-invasive) or
  board-level control (open the unit, tap the motor driver / bypass with
  an SSR + temp probe, more precise but invasive). Start non-invasive,
  escalate only if precision demands it.
- **Step 2 — ingredient dispensing.** The biggest gap vs. Posha/Nosh
  feature parity — no hardware owned yet, needs its own research pass
  (auger/vibratory hoppers for dry ingredients, peristaltic pumps for
  liquids are the standard maker-community answers, not yet investigated
  in depth here).
- **Step 3 — map recipes to the rig.** The recipe schema's
  `heat_level`/`stir_speed`/`duration_sec`/`add_ingredients` fields were
  designed for exactly this before any hardware existed — once steps 1–2
  establish real control primitives (servo angle → stir speed, button
  sequence → temp target, valve ID → ingredient ID), wire them up.

## Track B — Joyoung CJ-A9U (parallel/reference)

- **Step 1 — reverse engineer the CJ-A9U.** Open the unit / inspect the
  control board, or capture the signals between the front-panel MCU and
  the induction/motor driver, whichever is less invasive to try first.
  Determine: how many discrete heat levels and stir speeds actually exist,
  how "modes" (stir-fry/braise/soup/hotpot/fry) map to those, whether
  there's any serial/BLE/Wi-Fi interface already present. Record findings
  in `docs/joyoung-cj-a9u-notes.md` as they're confirmed, separating
  "official spec" from "measured/inferred." `docs/hardware-sensors-research.md`
  surveys sensors for this — starts with non-invasive RF sniffing (check
  for an existing wireless interface first — the Flipper Zero + Wi-Fi
  DevBoard already on hand covers the Wi-Fi half of that) before any
  board-level work.
- **Step 2 — map recipes to machine programs.** Once real control
  parameters are known, translate the recipe schema's machine fields into
  whatever protocol/format the machine (or a replacement controller)
  actually accepts. Validate a handful of existing recipes end-to-end on
  hardware.

## Phase 3 — Companion app (shared by both tracks)
- Build the "AI-powered cooking companion" on top of the validated recipe
  format: recipe browsing/search, guided cook mode for recipes without full
  machine params, one-tap send-to-machine for recipes that have them
  (whichever hardware track is ready first).
- Stretch goal, matching Posha/Nosh's camera: computer-vision doneness
  monitoring (browning/wilting cues), per Tier 3 in
  `docs/hardware-sensors-research.md` — lower priority than getting
  heat/stir/dispense working at all on either track.
- This is the point where a Flutter app (or reuse of the existing ingestion
  app scaffold) makes sense for cook-time control — not before the format
  and at least one hardware track are proven out.
