# Perception sensors — computer input for Track A cook monitoring

Consolidates what the open rig (Track A) needs to *sense* during a cook, as
distinct from `docs/hardware-sensors-research.md` (which is about
externally instrumenting/reverse-engineering the sealed CJ-A9U, Track B).
This doc covers vision, thermal, weight, and dispensing-feedback sensors
for the rig's own cook loop, driven by the two MVP recipes so far
(`docs/mvp-bechamel.md`, `docs/mvp-fried-rice.md`).

Nothing here has been bought or tested yet — desk research to shape what
to acquire, same status as `docs/hardware-sensors-research.md`.

## Baseline set — needed for béchamel (MVP #1)

| Sensor | Part | Interface | Ballpark cost | What it's for |
|---|---|---|---|---|
| Food-contact thermometer | `DS18B20` waterproof probe | 1-Wire | ~$5 | Verifying low/medium heat hold during the roux and simmer stages — scorch avoidance is a heat-*ceiling* problem here. |
| Thermal camera | `MLX90640` (32×24 IR array) | I2C | ~$50–60 | Surface heat-pattern mapping, aimed down at the pot; catches localized hot spots (where scorching starts) that a single-point probe would miss. |
| Weight | `HX711` + load cell | Digital (HX711 breakout) | ~$10–15 | Mass tracking as a consistency/reduction proxy (water loss during simmer), and verifying a dispensed ingredient's mass landed correctly. |
| Vision camera | Pi Camera Module 3 or ESP32-CAM | CSI / Wi-Fi | ~$25–35 | General visual monitoring; optionally paired with `TCS34725` color sensor for calibrated browning detection, though camera-only is sufficient to start. |

These four cover béchamel's acceptance criteria (no lumps, no scorching,
correct nappe consistency, repeatability) — see `docs/mvp-bechamel.md`.

## Additions/changes needed for chicken fried rice (MVP #2)

Fried rice stresses the *opposite* end of the heat range and a different
food texture (chunky solids vs. a liquid sauce), which changes what the
baseline set above needs to do:

| Sensor | Part | Interface | Ballpark cost | Why béchamel's choice isn't enough here |
|---|---|---|---|---|
| Wider-range thermometer | `MAX31855` + K-type thermocouple | SPI | ~$15 | `DS18B20` tops out around 125°C — fine for a roux/simmer, but stir-fry frying temps can exceed that. The thermocouple combo already scoped for the SSR-bypass path in `docs/open-rig-hardware.md` handles the higher range and faster response this recipe's high-heat phases need. |
| Non-contact IR spot sensor | `MLX90614` | I2C | ~$15–20 | Dry rice gives no liquid-consistency cue that the pan is hot enough before it goes in, unlike a sauce. A fast single-point "is the pan actually at frying temp yet" check before adding rice catches a failure mode béchamel doesn't have. |
| Toss/redistribution verification | Load cell (reused from baseline) reading rhythmic weight-shift, or a top-down camera check for redistribution | (reuses HX711 or vision camera above) | $0 incremental | The `MPU6050` on the StirMATE housing (see `docs/hardware-sensors-research.md`) measures *stirrer arm motion*, not whether solid rice actually moved. "Stirrer is moving but rice just sits in a pile" is a failure mode chunky solids can produce that a liquid sauce can't — need a signal that reflects the food moving, not just the mechanism. |
| Smoke/VOC sensor | `BME680` or `MQ-2`/`MQ-135` | I2C (BME680) / analog (MQ-series) | $5–25 | Low priority for béchamel (a simmering sauce produces near-zero smoke), but sustained high heat + oil in a stir-fry is a real scorch/burning-oil signal — this moves from "validates a marketing claim" (its role in `docs/hardware-sensors-research.md`, written for the CJ-A9U) to "early scorch-detection cue" here, complementing the thermal camera. |

## Carries over unchanged

- Load cell (mass tracking) and vision camera (general monitoring) from
  the baseline set apply to both recipes without modification — neither is
  heat-range- or texture-specific.

## Explicitly out of scope for now

- A food-safety-grade internal-temperature probe for verifying raw chicken
  is cooked through — not needed for fried rice MVP #2, since that recipe
  deliberately uses pre-cooked chicken (`docs/mvp-fried-rice.md`). Becomes
  necessary whenever a "cook raw chicken safely" MVP is attempted.
- Any camera/CV doneness model (browning, wilting) beyond raw color/motion
  signals above — Phase 3 territory per `docs/roadmap.md`, not required by
  either MVP so far.

## Suggested acquisition order

1. `DS18B20` (~$5) — already needed for béchamel, cheapest, do first.
2. `HX711` + load cell (~$10–15) — mass tracking, serves both recipes.
3. Pi Camera or ESP32-CAM (~$25–35) — general vision, serves both recipes.
4. `MLX90640` thermal camera (~$50–60) — pricier, add once the above are
   in hand and proven on béchamel.
5. `MAX31855` + K-type thermocouple (~$15) and `MLX90614` (~$15–20) — pull
   forward only when starting fried-rice testing specifically; not needed
   for béchamel.
6. `BME680` or `MQ-2`/`MQ-135` (~$5–25) — lowest priority, add if scorch
   detection from the thermal camera alone proves insufficient during
   fried-rice testing.
