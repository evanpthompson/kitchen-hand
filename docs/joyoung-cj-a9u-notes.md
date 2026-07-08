# Joyoung CJ-A9U — known specs (pre-reverse-engineering)

Gathered from public product listings and spec sheets, 2026-07-07. None of
this comes from opening the unit — treat it as "manufacturer claims," not
verified control parameters. Update this file as hands-on findings replace
guesses.

## Hardware

- Rated voltage/frequency: 120V, 60Hz (US model)
- Rated power: 1200W
- Capacity: 3.5L, inner pot diameter 260mm
- Weight: 7kg; size 428 x 247 x 393mm
- Heating: induction (IH), described as "3D"/"360°" heating
- Stirring: automatic double-wing spatula, fixed to the pot assembly
- Pot: non-stick "iron axe" inner pot, detachable for cleaning
- Enclosed cooking chamber (lid closes during operation — safety/anti-splash)

## Modes (5 presets)

- Stir-fry
- Braise
- Soup
- Hotpot
- Fry

Each mode reportedly runs its own fixed temperature + stir-speed program
("maintains the right temperature and stirring speed for each selected mode
without manual intervention"). No public source lists the actual temperature
ranges, discrete stir speed steps, or phase timings inside a mode — this is
exactly what Phase 1 (reverse engineering) needs to determine.

## Control interface

- "One-key control interface" — suggests mode selection is simple (few
  buttons/a dial), not a full programmable touchscreen. Worth confirming
  whether there's a display, and whether any timer/customization exists
  beyond mode + go.
- Unconfirmed: whether this model has a companion app, Wi-Fi/BLE, or any
  external control surface. Some Joyoung cooking-robot models do; check the
  physical unit and its manual for pairing instructions before assuming
  it's fully offline/closed.

## Open questions for Phase 1

1. Is there any existing digital interface (Wi-Fi/BLE/serial) before
   resorting to board-level reverse engineering?
2. How many discrete heat levels and stir speeds does the firmware actually
   support, independent of the 5 named modes?
3. Are mode programs time-based, temperature-sensor-based, or both?
4. What triggers the "add ingredients now" cues in real use, if any (timer
   beep vs. fixed schedule)?
5. Is the motor/induction driver controlled by the same MCU as the front
   panel, or is there a separate board worth tapping into directly?

## Sources

- [Joyoung CJ-A9U Smart Cooking Robot — YOURISHOP](https://www.yourishop.com/products/joyoung-cj-a9u)
- [Amazon listing](https://www.amazon.com/Joyoung-CJ-A9U-Intelligent-Automatic-Cooking/dp/B0BB5L5CDP)
- [eBay listing](https://www.ebay.com/itm/186906950210)
- [Joyoung CJ-A9U — zhlshop](https://www.zhlshop.com/products/cj-a9u)
- [Joyoung CJ-A9U — Cooking Gizmos](https://www.cookinggizmos.com/joyoung-cj-a9u/)
- [Original manual (Chinese), device.report](https://device.report/m/7da1e462401f56d3eda806f1576212c463f45cd62e7ac19dc9e7a221d86c0baf) — not yet successfully fetched/parsed; try again or find a mirror.
- [Joyoung CJ-A9U — SHEIN listing](https://us.shein.com/Joyoung-CJ-A9U-Intelligent-Fully-Automatic-Stir-Fry-Machine-Robot,-Intelligent-Temperature-Control,-Automatic-Stir-Frying,-Smoke-Free,-Oil-Free,-3.5L-p-19470152.html)
