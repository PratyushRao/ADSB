# How the ADS-B tracker works

This document follows one aircraft broadcast from the antenna to the dot on the map. It covers what each component does and exactly where demodulation and decoding happen.

> **Short answer: no dump1090, readsb or any other external decoder is used.**
> The RTL-SDR is driven by **GNU Radio** (through gr-soapy), and the 1090 MHz signal is demodulated into bits by our own **GNU Radio block** ([`backend/dsp_demod.py`](../backend/dsp_demod.py)). That block also runs the CRC check.
> **pyModeS** is used only *after* that, as a library that interprets an already-validated 112-bit message: callsign characters, altitude encoding, CPR position maths.
> dump1090 is mentioned in the code only as the name of a file format (`cu8` recordings) and as a reference for comparison.

---

## 1. The big picture

```
                 ┌────────────────────────── GNU Radio flowgraph (AdsbReceiver) ─────────────────────────┐
  ✈ 1090 MHz     │                                                                                       │
  ─────────► 📡 ─┼─► soapy.source ──► complex_to_mag ──► AdsbPpmDemod (our block) ──► hex frame + time    │
   antenna  RTL- │   RTL-SDR @ 2 Msps    |I+jQ| → pulse     preamble detect,           + signal level     │
            SDR  │   complex samples     amplitude          bit slicing, CRC-24                           │
                 └───────────────────────────────────────────────────────────────────────┬───────────────┘
                                                                                         │ "8D4840D6202CC371C32CE0576098"
                                                                                         ▼
     ┌──────────────────────────── FastAPI backend (main.py, asyncio event loop) ─────────────────────────┐
     │  AdsbDecoder (adsb_decoder.py) ──► FlightTracker (flight_tracker.py) ──► RouteLookup (route_lookup.py)
     │  pyModeS PipeDecoder:              merges messages per aircraft,         callsign → origin/destination,
     │  callsign, altitude, CPR position,  drops aircraft silent for 60 s        cross-checked vs live position
     │  speed, track, vertical rate                                                       │
     └────────────────────────────────────────────────────────────────────────────────────┼───────────────┘
                                                                                          │ JSON every 1 s
                                                                                          ▼ WebSocket /ws
                                                   Svelte frontend (frontend/src): parser.ts → Leaflet map, list, detail panel
```

| Stage | Done by | File |
| :--- | :--- | :--- |
| Talk to the RTL-SDR, tune to 1090 MHz, set the gain, stream samples | **GNU Radio** `soapy.source` | `dsp_demod.py` → `AdsbReceiver` |
| Convert complex I/Q to pulse amplitude | **GNU Radio** `blocks.complex_to_mag` | same |
| Buffering, threading, scheduling of the DSP | **GNU Radio** runtime | same |
| Find Mode-S preambles, slice the bits, check CRC, fix 1-bit errors | **Our GNU Radio block** `AdsbPpmDemod` (Python + numpy) | `dsp_demod.py` |
| Interpret message fields (callsign, altitude, CPR → lat/lon, velocity) | **pyModeS** library | `adsb_decoder.py` |
| Keep one record per aircraft, expire old ones | Our code | `flight_tracker.py` |
| Origin/destination for a callsign | Online route database + our position cross-check | `route_lookup.py` |
| Serve to the browser | FastAPI + WebSocket | `main.py` |
| Draw it | Svelte + Leaflet | `frontend/src` |

GNU Radio itself does not ship an ADS-B demodulator, so the Mode-S demodulator is our own block. Because it runs inside the GNU Radio scheduler, it can also be used visually in GNU Radio Companion: [`backend/grc/adsb_rx.grc`](../backend/grc/adsb_rx.grc) wraps the same class.

---

## 2. What the aircraft actually transmits

Every aircraft with a Mode-S transponder sends short bursts on **1090 MHz**:

- **Modulation:** pulse-position modulation (PPM) at 1 Mbit/s. Each bit lasts 1 µs and is split into two 0.5 µs halves. A pulse in the *first* half means `1`; a pulse in the *second* half means `0`.
- **Preamble:** 8 µs long, with pulses at 0, 1, 3.5 and 4.5 µs. It marks the start of a message.
- **Message:** 56 bits (short) or 112 bits (long). ADS-B "extended squitter" messages are long, **DF17**.

```
 preamble (8 µs)                    data: 112 bits × 1 µs
 ┌┐ ┌┐    ┌┐ ┌┐                     ┌┐  ┌┐┌┐    ┌┐
 ││ ││    ││ ││                     ││  ││││    ││ ...
─┘└─┘└────┘└─┘└───────────────────  ─┘└──┘└┘└────┘└──
 0  1    3.5 4.5 µs                  1   0  1  0  (bit values)
```

A DF17 message has this layout:

| Bits | Field | Example (`8D4840D6202CC371C32CE0576098`) |
| :--- | :--- | :--- |
| 1–5 | DF, downlink format | `17` (ADS-B) |
| 6–8 | CA, capability | `5` |
| 9–32 | ICAO address, the aircraft's unique 24-bit ID | `4840D6` |
| 33–88 | ME, the 56-bit payload; the first 5 bits are the *type code* | TC 4 → identification → `KLM1023` |
| 89–112 | PI, CRC-24 parity | `576098` |

The type code says what the payload holds:

| Type code | Content | What we take from it |
| :--- | :--- | :--- |
| 1–4 | Identification | callsign, category |
| 9–18 | Airborne position | barometric altitude, CPR-encoded lat/lon |
| 19 | Airborne velocity | ground speed, track, vertical rate |
| 5–8 | Surface position | (aircraft on the ground) |

Each aircraft sends these message types separately, roughly twice a second for position and velocity and every ~5 s for identification. **No message contains origin or destination.** See §6 for how we get those.

---

## 3. GNU Radio: from radio to pulse amplitude

`AdsbReceiver` (in `dsp_demod.py`) is a `gr.top_block`. For live SDR use it builds this chain:

```
soapy.source("driver=rtlsdr", fc32)  ──►  blocks.complex_to_mag  ──►  AdsbPpmDemod
   sample_rate = 2 Msps                    m[n] = |I[n] + jQ[n]|        (sync block, 1 input, 0 outputs,
   frequency   = 1090 MHz                                                 "frames" PDU message port)
   gain        = 40 dB (manual, AGC off)
   ppm         = frequency correction
```

When replaying a recording (`--iq-file`), the SDR source is replaced by:

`file_source → uchar_to_float → add −127.5 → ×1/127.5 → deinterleave → float_to_complex`

This turns rtl_sdr's 8-bit unsigned I/Q into the same complex stream, with an optional `throttle` for real-time playback.

**Why only the magnitude?** The aircraft's carrier frequency and phase are never exactly known: there is Doppler, and the transponder's oscillator can be off by up to ±1 MHz. PPM carries information only in *when* there is energy, not in the phase. So `|I+jQ|` is all we need, and it removes the carrier entirely.

**Why 2 Msps?** Each Mode-S chip lasts 0.5 µs, so at 2 Msps there is exactly one sample per chip. That's the slowest rate that works, and it is easy on the CPU. The catch: a pulse often falls *between* two samples and smears across both. Most of the demodulator's work goes into handling that.

---

## 4. Our demodulator block: `AdsbPpmDemod`

This is a `gr.sync_block` written in Python with numpy. GNU Radio calls `work()` with chunks of magnitude samples. `set_history(241)` makes sure every chunk also contains the last 240 samples of the previous one, so a message split across two chunks is never missed.

### 4.1 Preamble detection (vectorised over the whole chunk)

For every sample position `i`, using pulse-pair sums `p[k] + p[k+1]`:

```
pairs   = (p0+p1, p2+p3, p7+p8, p9+p10)      # energy at 0, 1, 3.5, 4.5 µs
level   = mean(pairs)
weakest = min(pairs)
quiet   = mean(p4, p5, p12, p13, p14)          # where there must be NO pulse

candidate if   weakest > 0.5·level            (all four pulses present, similar height)
          and  3·quiet < weakest              (gaps really are quiet)
          and  level > noise_floor × min_snr  (default 8 dB above the running median)
```

Adding each sample to its neighbour makes the test **independent of where the pulse falls between samples**. Without this, half the aircraft would be missed. The noise floor is a running median of the signal, so it adapts to gain and interference.

### 4.2 Bit slicing

For each candidate we decide 112 bits by comparing, for every bit, the energy in the first half vs the second half.

1. **Estimate the sub-sample phase δ.** This is measured from how much each preamble pulse spills into the following sample.
2. **Fast path.** Try the two phase hypotheses nearest to δ (from 0, ¼, ½, ¾). Each one uses a matched filter weighted for that phase: `score = (1−δ)·a + (2δ−1)·b − δ·c` over the samples a, b, c around each bit.
3. **Slow path (Viterbi).** If both fail the CRC, the pulse is badly smeared and the signal is strong enough (12 dB or more), so we fit a 4-tap pulse shape to *this frame's own preamble* by least squares. Then a 4-state Viterbi search finds the most likely bit sequence through the smear.

### 4.3 Validation (what makes a frame "real")

The 24 parity bits are a CRC-24 (generator `0xFFF409`) computed over the rest of the message.

- **DF17/18 (ADS-B):** the remainder must be 0. If it isn't, a table lookup tries to **correct a single flipped bit**, and the frame is accepted if that fixes it.
- **DF11 (all-call reply):** the remainder may equal the interrogator code (II/SI), which is allowed.
- **DF0/4/5/16/20/21 (surveillance replies):** the parity is XORed with the aircraft address, so it can't be checked on its own. These are accepted only if the recovered address matches an aircraft we've **recently seen in a CRC-clean DF11/17/18**. This blocks phantom aircraft.
- Messages whose DF isn't a known Mode-S format are rejected before any CRC work.

Each valid frame leaves the block as:

- a callback `on_frame(hex, timestamp, rssi_db)` → the backend, and
- a PDU on the `frames` message port, so GRC flowgraphs can connect a Message Debug block or similar.

**Measured:** 336 valid frames from dump1090's sample recording (`modes1.bin`, used only as *test data*). On our synthetic recording it recovers about 68% of frames with **zero false frames**. It runs 2–6× faster than real time on replayed files.

---

## 5. pyModeS: from bits to meaning

[`backend/adsb_decoder.py`](../backend/adsb_decoder.py) receives the validated hex string and passes it to pyModeS's **`PipeDecoder`**, which keeps state per aircraft.

| pyModeS output | Becomes (tracker / UI field) |
| :--- | :--- |
| `icao` | `hex` (aircraft key) |
| `callsign` (6-bit charset → `KLM1023`) | `callsign` |
| `altitude` (feet, Q-bit / Gillham decoding) | `altitude` |
| `groundspeed`, `track`, `vertical_rate` | `speed`, `heading`, `verticalRate` |
| `latitude`, `longitude` | `lat`, `lon` |
| `squawk`, `category` | `squawk`, `category` |
| the demodulator's level | `rssi` |

### Why positions take a few seconds to appear

Positions are sent in **CPR** (Compact Position Reporting): only 17 bits each for lat and lon, alternating "even" and "odd" frames. One frame alone is ambiguous: it identifies a spot within a ~360 NM zone, but not which zone. pyModeS therefore:

1. waits for an **even + odd pair** from the same aircraft received a few seconds apart and solves for the global position. For example, frames `8D40621D58C382D690C8AC2863A7` + `8D40621D58C386435CC412692AD6` → 52.2572° N, 3.9194° E;
2. requires **several mutually consistent fixes** before releasing a position (this rejects garbage from rare undetected bit errors);
3. afterwards decodes each new frame **locally** against the last good position, which is fast and unambiguous.

That's why a plane appears in the list (callsign, altitude) a little before it appears on the map.

### Thread hand-off

GNU Radio runs `work()` on its own thread. The callback does not touch shared state there. It schedules `decoder.handle_frame(...)` on the asyncio event loop with `loop.call_soon_threadsafe`, so pyModeS, the tracker and the WebSocket all run on one thread, and no locks are needed.

---

## 6. Origin and destination: not in ADS-B, so we look them up

ADS-B carries the **callsign** (e.g. `IGO5203`) but never the route. [`backend/route_lookup.py`](../backend/route_lookup.py) gets it like this:

1. **Filter:** only airline-style callsigns (3-letter airline code + number) are looked up. Registrations like `VTABC` have no schedule entry.
2. **Look up** in free route databases, with no API key and no Flightradar24:
   - [adsbdb.com](https://www.adsbdb.com) `/v0/callsign/IGO5203` → `6E5203`, IndiGo, **PNQ → DEL**, with airport names and coordinates;
   - [hexdb.io](https://hexdb.io) `/api/v1/route/icao/…` as a fallback.
3. **Cache:** a found route is kept for 6 h and "unknown" for 2 h. After a network error it retries in 5 min. Four background workers do the lookups, so the 1 s WebSocket push is never delayed.
4. **Cross-check against what we decoded.** Route databases are crowd-sourced, and airlines reuse callsigns for different legs, so every route is checked against the aircraft's **live position and track**:

| Badge | Meaning |
| :--- | :--- |
| ✓ matches position | Aircraft is within the corridor around the great-circle origin → destination (± max(60 NM, 20% of route length)) and, en route, heading towards the destination |
| ⚠ off route | Aircraft is far from that path: the database entry is probably stale or wrong for today |
| ⚠ opposite direction | On the path but flying towards the origin: the database has the return leg |
| unverified | No position decoded yet |

The UI shows `PNQ → DEL` on the list card, the full route panel (flight number, airline, cities, badge and its explanation) in the detail view, and the route on the map label of the selected aircraft. Use `--no-routes` to turn lookups off (for example, offline use).

---

## 7. Backend → browser

- `FlightTracker` merges every update into one dict per ICAO address and deletes aircraft silent for 60 s.
- `main.py` pushes the full aircraft list as JSON over **`WS /ws` every second**. The same data is available at `GET /api/aircraft`. Health and statistics are at `GET /`: frames, frames/s, positions, route-lookup counts.
- The frontend connects automatically to `ws://127.0.0.1:8000/ws`. `parser.ts` normalises each entry, works out distance and bearing from the receiver, and keeps a short trail. Aircraft without a position yet are kept back from the map. The receiver location comes from `GET /api/receiver` (`--lat/--lon`).

---

## 8. Following one message end to end

```
t = 0 µs     Aircraft KLM1023 transmits DF17 identification on 1090 MHz
             ↓ antenna → RTL-SDR → USB → soapy.source (2 Msps complex)
             ↓ complex_to_mag
             AdsbPpmDemod.work(): pulse pairs at samples 0/2/7/9 exceed noise × 2.5, quiet zones empty
             ↓ δ ≈ 0.3 → slice with δ = 0.25 → 112 bits
             ↓ CRC-24 remainder = 0 → valid → "8D4840D6202CC371C32CE0576098", rssi −14 dB
             ↓ loop.call_soon_threadsafe
             AdsbDecoder: pyModeS → {icao: 4840D6, typecode: 4, callsign: KLM1023}
             ↓ tracker.update_aircraft("4840D6", {callsign: "KLM1023", rssi: −14})
             ↓ RouteLookup queues "KLM1023" → adsbdb → origin/destination (cached)
≤ 1 s later  WebSocket push → browser list shows KLM1023 with its route;
             the map dot appears once an even/odd position pair has been decoded
```

---

## 9. Notes for benchmarking against Flightradar24

When comparing a screen of this app with FR24 for the same area and time:

- **FR24 combines thousands of receivers plus MLAT and satellite data.** We only show what *our* antenna hears. Count aircraft within a fixed radius of the receiver (the list's distance column) rather than everything on screen.
- **Coverage depends on the antenna.** Height and line of sight matter far more than software. Indoors, expect tens of km; at a rooftop with a 1090 MHz antenna, 150–300 km.
- **Known software limits:**
  - At 2 Msps, weak frames that land half a sample out of phase can't be recovered. That's why readsb samples at 2.4 Msps.
  - The demodulator is pure Python. If the backend log prints `O` characters, the SDR is delivering samples faster than they're processed, so some samples are being dropped.
- **Route data source differs.** FR24 uses airline schedules; we use the community databases above plus a live-position cross-check. Where the badge says ⚠, our route is probably wrong, and comparing those cases with FR24 is a good measure of route-data quality.
- Useful counters for a benchmark run: `curl localhost:8000/` → `receiver.frames_per_sec`, `receiver.positions`, `active_flights`, `routes.found / routes.lookups`.

---

## 10. File map

| File | Role |
| :--- | :--- |
| [`backend/dsp_demod.py`](../backend/dsp_demod.py) | GNU Radio flowgraph (`AdsbReceiver`), our Mode-S demodulator block (`AdsbPpmDemod`), CRC-24; also a standalone CLI (`python dsp_demod.py --sdr --decode`) |
| [`backend/adsb_decoder.py`](../backend/adsb_decoder.py) | pyModeS `PipeDecoder` → tracker fields |
| [`backend/flight_tracker.py`](../backend/flight_tracker.py) | Per-aircraft state, 60 s expiry |
| [`backend/route_lookup.py`](../backend/route_lookup.py) | Callsign → origin/destination, with cache and live cross-check |
| [`backend/main.py`](../backend/main.py) | FastAPI app, WebSocket, CLI flags (`--sdr`, `--iq-file`, `--simulate`, `--lat/--lon`, `--no-routes`) |
| [`backend/grc/adsb_rx.grc`](../backend/grc/adsb_rx.grc) | The same receiver as a GNU Radio Companion flowgraph |
| [`backend/tools/gen_test_iq.py`](../backend/tools/gen_test_iq.py) | Synthetic IQ recording generator for testing without an SDR |
| [`backend/sim_feeder.py`](../backend/sim_feeder.py) | Fake aircraft for UI work (`--simulate`), with no DSP |
| [`frontend/src/utils/parser.ts`](../frontend/src/utils/parser.ts) | Normalises backend JSON for the UI |
| [`frontend/src/components/`](../frontend/src/components/) | Map, list cards, detail panel (route display) |
