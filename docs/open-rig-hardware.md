# Open rig hardware — induction burner + StirMATE + pans

Track A of the project (see `docs/roadmap.md`): an open-source alternative
to all-in-one cooking robots like Posha and Nosh, built from separately
controllable off-the-shelf components instead of one sealed unit. This doc
covers what's actually owned so far, what control problem each piece poses,
and the gap vs. feature parity with the commercial products it's meant to
replace.

## What Posha/Nosh actually do (the target feature set)

Researched 2026-07-09 since "replace their functionality" needs a concrete
target, not a vague one:

- **Posha** — countertop unit (~microwave-sized), 1800W induction cooktop,
  robotic stirring arm with 3 swappable spatulas, up to 6 ingredient
  hoppers/spice carousel with motorized valves timed by the recipe, a
  top-mounted camera with computer vision watching for doneness cues
  (browning, wilting), 1000+ recipe library, iOS/Android app with
  scheduling. [posha.com](https://www.posha.com/), [Wikipedia](https://en.wikipedia.org/wiki/Posha_(company)), [TIME Best Inventions 2025](https://time.com/collections/best-inventions-2025/7318336/posha/)
- **Nosh** — similar shape: induction heat, a continuously-stirring mixing
  arm, calibrated spice (¼ tsp) and liquid (1 tsp) dispensing, computer
  vision doneness monitoring, 500+ recipe app library with remote
  start/scheduling. $1499–2000. [letsnosh.io](https://www.letsnosh.io/), [webpronews CES 2026 coverage](https://www.webpronews.com/nosh-ai-robot-chef-automates-500-recipes-for-easy-home-cooking-at-ces-2026/)

Feature parity checklist, and where each already has a home in this repo:

| Feature | Posha/Nosh | Status here |
|---|---|---|
| Recipe format (ingredients, timed phases, heat/stir targets) | proprietary, in-app | **Already built** — `schema/recipe-v1.schema.json` already has `phases[].heat_level`/`stir_speed`/`duration_sec`/`add_ingredients`. Designed for exactly this before any hardware existed. |
| Recipe browsing/curation/ingestion | in-app library | **Already built** — the whole ingestion pipeline (`docs/ingestion.md`), the `service/`+`app/` ingestion workflow app. |
| Heat control | built-in 1800W induction, app-driven | **Not built** — burner is a plain manual-dial unit, no digital interface. See below. |
| Automated stirring | integrated robotic arm | **Partially owned** — StirMATE stirrer owned, but it's manual-dial too, no digital interface. See below. |
| Ingredient/spice dispensing | motorized hoppers/carousel | **Not started, biggest gap.** No hardware owned yet; this is net-new mechanical design (hoppers, augers/valves, a carousel), not just wiring up an existing product. |
| Computer vision doneness monitoring | camera + CV model watching for browning/wilting | **Not started.** Maps to Tier 3 in `docs/hardware-sensors-research.md` (color sensor/camera) — stretch goal, lower priority than heat/stir/dispense working at all. |
| App: schedule, remote start, monitor | iOS/Android app | **Partially built** — the ingestion app (Phase A/B) is a curation tool, not a cook-time control app yet; that's Phase 3 (`docs/roadmap.md`). |

## StirMATE — confirmed no digital interface

StirMATE Gen 3: battery-powered (rechargeable Li-Ion, ~9–10 hours/charge),
variable speed up to 30 RPM via a physical dial, self-adjusting clamp arm
fits 6–10" diameter / 3–9" deep pots, BPA-free food-safe plastic rated to
360°F. Confirmed via product research: **no Bluetooth, no app, no existing
digital control** — it's a self-contained mechanical device. [stirmate.com](https://www.stirmate.com/product-page/stirmate-ii-smart-pot-stirrer), [Amazon listing](https://www.amazon.com/StirMATE-Automatic-Variable-Self-Adjusting-Powerful/dp/B076HH4WZM)

Two ways to get programmatic control, same tradeoff shape as the CJ-A9U's
tiers in `docs/hardware-sensors-research.md`:

1. **Mechanical actuation of the physical speed dial** (e.g. a small servo
   turning the dial to a calibrated position) — non-invasive, reversible,
   doesn't touch the device's internals or void anything. Lower precision
   (servo positioning error stacks with the dial's own detents), but safe
   to try first.
2. **Open the housing, tap the motor driver directly** — almost certainly a
   simple DC motor with a potentiometer-based speed control; replacing/
   injecting into that with a microcontroller-driven PWM signal gives more
   precise, more reliable speed control, at the cost of opening the unit
   (warranty, reversibility).

Start with (1) — it's cheap to try (one servo, ~$5–10) and doesn't foreclose
(2) later if precision turns out to matter.

## Induction burner — plain manual-dial, no digital interface

Confirmed (per your description): buttons/dial only, no app/BLE/Wi-Fi. Two
analogous paths:

1. **Physical button/dial actuation** — small servos or solenoids pressing
   the existing buttons, exactly as a person would. Works with *any* dumb
   appliance without opening it, but is the least precise for heat control
   (locked to whatever discrete power-level buttons the unit already has).
2. **Open the unit, find the control board** — likely a small MCU reading a
   button matrix and driving the induction coil's IGBT module. Two
   sub-options once open: (a) inject signals at the button-matrix level
   (safer, keeps the manufacturer's induction-driving/safety logic intact,
   just replaces "a human pressing buttons" with GPIO), or (b) bypass the
   internal control entirely with an external SSR (solid-state relay) + a
   food-safe temperature probe (from `docs/hardware-sensors-research.md`'s
   Tier 1 — DS18B20 or thermocouple+MAX31855) running your own PID loop.
   (b) gives the most precise/continuous heat control but is mains-AC work
   — treat as a real electrical-safety task, not a weekend solder job,
   given induction burners run at real power (typically 1200–1800W).

Given the burner is "just" a heat source (unlike the StirMATE, where the
mechanism itself is the product), option 2(b) — external SSR + temp probe,
ignoring the burner's own control board entirely — is probably the more
promising long-term path once basic on/off automation is proven with
option 1. It also directly reuses Tier 1 temperature sensors already
researched for the CJ-A9U work, so the same sensor purchases serve both
hardware tracks.

## Ingredient dispensing — the real gap

Neither the burner nor the StirMATE does this at all, and it's the single
biggest piece of Posha/Nosh's actual functionality that has no owned
hardware yet. Rough shape of the problem, not yet researched in depth:

- Dry/spice dispensing: small auger-driven or vibratory hoppers (common in
  pet-feeder and coffee-grinder projects — worth a dedicated research pass
  rather than folding into this doc).
- Liquid dispensing: peristaltic pumps (common, cheap, food-safe tubing
  available) are the standard maker-community answer for calibrated liquid
  dosing.
- This needs its own research doc once the burner/stirrer control problem
  is further along — flagging here so it isn't forgotten as "the hard part
  we haven't looked at yet."

## Suggested order of attack

Concrete MVP target for all of this: `docs/mvp-bechamel.md` — an unattended,
flawless béchamel (`recipes/bechamel-sauce.yaml`). It's the acceptance test
for steps 1–3 below, not just an abstract "get it working" goal.

1. Get basic programmatic control of the StirMATE via servo-on-the-dial
   (cheapest, fastest win, proves the "external actuator on a dumb device"
   pattern before committing to it for the burner too).
2. Get basic on/off + rough power-level control of the induction burner the
   same way (servo/solenoid on its buttons), before attempting the SSR+PID
   bypass.
3. Only then start the SSR + temp-probe closed-loop heat control — the
   highest-payoff but also highest-risk (mains AC) piece. Béchamel's roux
   stage is a good real-world test of whether this is actually necessary
   or whether button-actuation heat control is precise enough.
4. A single peristaltic pump for milk — the béchamel MVP's only dispensing
   need, and a much smaller wedge into Step 2 than the full multi-hopper
   dispensing problem below.
5. Ingredient dispensing research + prototyping beyond that single pump —
   biggest scope item, tackle once heat+stir (and the MVP) are proven.
