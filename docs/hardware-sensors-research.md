# Hardware sensors research — Phase 1/2

Survey of sensors that could help with `docs/joyoung-cj-a9u-notes.md`'s open
questions and with eventual monitoring/control, organized by how invasive
each is. Nothing here has been bought or tested yet — this is desk research
to shape what to actually acquire.

## Three tiers, by invasiveness

1. **Non-invasive, zero disassembly** — sensors placed near/on the sealed
   unit, or RF sniffing of any signal it emits. Safe to do immediately,
   answers several Phase 1 questions before ever opening the case.
2. **Board-level, case open** — taps the actual control signals once
   disassembly is decided on. Bigger step (warranty/safety), do after
   tier 1 is exhausted.
3. **Companion sensors, not CJ-A9U-specific** — feed the eventual "AI
   cooking companion" (Phase 3) rather than reverse-engineering the
   machine itself.

## Tier 0 — do this first: check for an existing wireless interface

Directly answers open question #1 ("is there already a Wi-Fi/BLE/serial
interface before resorting to board-level work?"). Cheapest, fastest,
zero risk — should happen before any of the below.

- **nRF52840 USB dongle + nRF Sniffer + Wireshark** — ~$10, the standard
  cheap way to capture BLE traffic. Flash the sniffer firmware, run the
  machine's companion app (if one exists) or just power-cycle the unit
  near the dongle, watch for advertisement packets. [novelbits.io guide](https://novelbits.io/nordic-ble-sniffer-guide-using-nrf52840-wireshark/), [Adafruit Wireshark walkthrough](https://learn.adafruit.com/ble-sniffer-with-nrf52840/working-with-wireshark).
- **ESP32 in promiscuous mode** — captures Wi-Fi frames to a pcap
  Wireshark can open; useful if the unit has a Wi-Fi-based companion app
  instead of/in addition to BLE. [hackmag.com writeup](https://hackmag.com/security/esp32-sniffer), [esp32sniffer on GitHub](https://github.com/yannpom/esp32sniffer).

## Tier 1 — non-invasive instrumentation

Placed near or on the sealed unit during normal cooking cycles. Enough to
characterize modes/power levels/stir behavior/audio cues without opening
anything.

| Sensor | Part(s) | Interface | Ballpark cost | What it answers |
|---|---|---|---|---|
| Current/power sensing | **SCT-013 CT clamp** (clips around the power cord, no rewiring) or **ACS712**/**INA219** if inline access is acceptable | Analog (SCT-013 needs a burden resistor) / I2C (INA219) | $10–20 | Logging power draw over a full cook cycle reveals how many discrete power/heat steps exist per mode, without opening the case. [CT clamp guide](https://componentindex.net/components/ct-clamp/), [INA219 vs ACS712](https://zbotic.in/current-voltage-sensor-modules-acs712-ina219/) |
| Thermal imaging | **MLX90640** (32×24 IR array, 55° or 110° FOV, -40 to 300°C, ~1°C accuracy) | I2C | ~$50–60 | Aimed at any viewing window/vent, maps the pot's surface heat pattern over a cycle — addresses whether mode programs are temperature-sensor-based or purely time-based. [Maker Portal build](https://makersportal.com/blog/2020/6/8/high-resolution-thermal-camera-with-raspberry-pi-and-mlx90640), [Pimoroni breakout](https://shop.pimoroni.com/en-us/products/mlx90640-thermal-camera-breakout) |
| Vibration/IMU | **MPU6050** (accel + gyro) preferred over **ADXL345** — more uniform response under mechanical vibration per a direct comparison study | I2C | ~$5–10 | Stuck to the case exterior, picks up the stir motor's vibration/rotation signature — helps map discrete stir speeds without any electrical tap. [ADXL345 vs MPU6050 study](https://rsdjournal.org/rsd/article/view/23082) |
| Audio | **INMP441** I2S MEMS mic | I2S | ~$5–10 | The unit likely beeps at phase transitions/ingredient-add cues; a mic + simple tone/FFT detection (or an Edge Impulse keyword-spotting model, 95–99% accuracy achievable on simple two-tone cases) timestamps those cues — directly answers "what triggers the add-ingredient cue." [INMP441 + Pi guide](https://makersportal.com/shop/p/i2s-mems-microphone-for-raspberry-pi-inmp441) |
| Gas/smoke/VOC | **BME680** (4-in-1: pressure/temp/humidity/VOC) or **MQ-2**/**MQ-135** (cheaper, less precise, need warm-up time and are humidity-sensitive) | I2C (BME680) / analog (MQ-series) | $5–25 | The CJ-A9U is marketed as "virtually smoke-free" — a VOC/smoke sensor near the vent can actually quantify that claim and flag oil-smoke-point crossings. [MQ-2/MQ-135 guide](https://zbotic.in/gas-sensor-guide-mq2-mq3-mq135-for-air-quality/), [BME680 product](https://www.amazon.com/Environmental-Temperature-Barometric-Detection-Raspberry/dp/B0BZ4W6J49) |
| Lid state | Reed switch / magnetic contact | Digital GPIO | ~$2–5 | Cheap binary sensor for lid-open/closed state, relevant since the chamber is described as fully enclosed during operation. [Hall/reed sensor tutorial](https://diyi0t.com/hall-sensor-tutorial-for-arduino-and-esp8266/) |

## Tier 2 — board-level (only after opening the case)

- **Bus Pirate** (v3 or v4/5) — probes UART/I2C/SPI/1-Wire without writing
  code first; also works as a basic logic analyzer. The open-hardware
  original from 2008, still actively used/updated. [Hackaday hands-on, Bus Pirate 5](https://hackaday.com/2024/02/12/hands-on-bus-pirate-5/), [official docs](https://docs.buspirate.com/docs/overview/hardware/)
- **ESP32-based logic analyzer** (e.g. via PulseView/sigrok) — cheaper
  DIY alternative, samples multiple GPIO lines as digital channels with
  protocol decoders for UART/SPI/I2C/PWM. [Hackster.io ESP32-S3 writeup](https://www.hackster.io/550277/turn-an-esp32-s3-into-a-usb-uart-spi-prog-logic-analyzer-b1b6ee)
- Directly answers open question #5 (same MCU driving front panel + motor/
  induction driver, or separate boards?) once physically tapped.

## Tier 3 — companion sensors (Phase 3 territory, not CJ-A9U reverse engineering)

- **HX711 + load cell** — weighs the whole unit or a prep surface;
  useful for a future "ingredient portioning / did the recipe actually
  go in as written" companion feature, not for characterizing the
  machine itself. [HX711 + Pi/Arduino guide](https://sensorsandgauges.com/pages/load-sensor-hx711-complete-guide-for-arduino-esp32-raspberry-pi)
- **TCS34725** color sensor or a camera (ESP32-CAM / Pi Camera) — visual
  doneness/browning signal, complements the thermal camera above for a
  future "is this actually done" companion feature. [TCS34725 + ESP32](https://www.makerguides.com/interfacing-esp32-and-tcs34725-rgb-color-sensor/)

## Platform choice: Raspberry Pi vs. ESP32

Since `service/` is already a Python/FastAPI backend, a **Raspberry Pi** is
the simplest integration path for Tier 0/1 prototyping — full CPython, easy
I2C/camera-frame handling, no serial bridge needed to get sensor data into
the existing backend. **ESP32** nodes make more sense later for anything
battery-powered or physically inside/on the unit relaying data wirelessly —
deterministic GPIO timing, µA-range deep sleep, ~$5–10 per node vs.
Pi pricing, at the cost of running MicroPython/CircuitPython instead of
full CPython. Reasonable read: prototype on a Pi now, push specific nodes
to ESP32 later only if battery/placement constraints demand it. [ESP32 vs Pi comparison](https://jlcpcb.com/blog/esp32-vs-raspberry-pi), [xda-developers: use both](https://www.xda-developers.com/your-smart-home-needs-an-esp32-and-raspberry-pi/)

## Suggested acquisition order

1. nRF52840 sniffer + confirm/rule out existing wireless (~$10–15) — do
   this before buying anything else, it might make some of tier 1 moot.
2. SCT-013 current clamp + MPU6050 + INMP441 mic, all on a Raspberry Pi
   (~$30–40 combined) — cheapest tier-1 set, covers power/vibration/audio.
3. MLX90640 thermal camera (~$50–60) — priciest single item, add once the
   cheaper tier-1 sensors have been tried.
4. BME680 or MQ-2/MQ-135 (~$10–25) — lower priority, mostly validates a
   marketing claim rather than answering a hardware-reverse-engineering
   question.
5. Bus Pirate (~$30, if going this route) — only once tier 0/1 are
   exhausted and opening the case is actually decided on.
