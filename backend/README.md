# 🛰️ ADS-B DSP Backend Server

A **FastAPI** server that receives 1090 MHz ADS-B with **GNU Radio**, decodes it with **pyModeS**, and streams aircraft to the Svelte radar frontend over **WebSocket** and **HTTP**.

```
SDR (gr-soapy) ─┐
                ├─► |IQ| ─► AdsbPpmDemod ─► hex frames ─► pyModeS PipeDecoder ─► FlightTracker ─► /ws, /api/aircraft
IQ file ────────┘        (dsp_demod.py)                    (adsb_decoder.py)    (flight_tracker.py)   (main.py)
```

---

## ⚡ Setup (Linux)

GNU Radio (with gr-soapy) and the SoapySDR driver for your radio come from the OS packages, **not pip**.
Create the venv with `--system-site-packages` so it can see them:

```bash
cd backend
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
pip install -r requirements.txt

# check: should print the GNU Radio version
python -c "from gnuradio import gr, soapy; print(gr.version())"
```

---

## ▶️ Running

Pick one data source:

```bash
# Live from an RTL-SDR (set YOUR antenna location so the map centres on it)
python main.py --sdr --lat 12.9716 --lon 77.5946 --rx-name "Home"

# Other radios / options
python main.py --sdr --device "driver=hackrf" --gain 30 --lat ... --lon ...

# Replay an IQ recording through the same GNU Radio demodulator (no SDR needed)
python main.py --iq-file grc/test_adsb.bin --lat 28.5562 --lon 77.1

# Simulated aircraft, no DSP at all
python main.py --simulate
```

Origin/destination are looked up online per callsign (adsbdb.com, hexdb.io) and cross-checked against the
decoded position; add `--no-routes` to disable. Full walkthrough of the pipeline: [`docs/HOW_IT_WORKS.md`](../docs/HOW_IT_WORKS.md).

Then start the frontend (`cd ../frontend && npm run dev`) and open http://localhost:5173.
It connects to `ws://127.0.0.1:8000/ws` automatically and centres the map on `--lat/--lon`.

| Endpoint | What |
| :--- | :--- |
| `GET /` | Health + receiver stats (`frames`, `frames_per_sec`, `positions`) |
| `GET /api/aircraft` (or `/data.json`) | Current aircraft list |
| `GET /api/receiver` | Antenna location from `--lat/--lon` (or `null`) |
| `WS /ws` | Aircraft list pushed every second |
| `GET /docs` | Swagger UI |

**Tips for real reception:** use a 1090 MHz antenna (even a 6.9 cm quarter-wave whip on a ground plane beats the stock one), place it high with sky view, and try gains between 30 and 49 dB. Check what the SDR sees with `SoapySDRUtil --find` or `rtl_test`.

---

## 🧪 Testing without an SDR

```bash
# Synthetic 30 s recording: 8 aircraft around a location, realistic impairments
python tools/gen_test_iq.py -o grc/test_adsb.bin --seconds 30 --rx-lat 28.5562 --rx-lon 77.1

# Raw demodulator only: print frames (*HEX;) or decoded fields
python dsp_demod.py --iq-file grc/test_adsb.bin
python dsp_demod.py --iq-file grc/test_adsb.bin --decode
python dsp_demod.py --sdr --decode            # once the SDR is plugged in

# Record your own capture for later replay (2 Msps, unsigned 8-bit IQ)
rtl_sdr -f 1090e6 -s 2e6 -g 40 -n 60000000 capture.bin   # 30 s
```

---

## 📻 GNU Radio Companion flowgraph

[`grc/adsb_rx.grc`](grc/adsb_rx.grc) is the same receiver as a visual flowgraph:

```bash
cd backend/grc
gnuradio-companion adsb_rx.grc
```

- By default the **file playback** chain is enabled (plays `grc/test_adsb.bin`; generate it first, see above).
- When your RTL-SDR is plugged in: select the **Soapy RTLSDR Source** and press **E** to enable it, then select the file chain blocks and press **D** to disable them.
- Valid frames print in the GRC console; the Qt scope shows the |IQ| pulses, triggered on each preamble.
- The **ADS-B PPM Demod** block wraps `AdsbPpmDemod` from `dsp_demod.py`, so GRC and the server run the same DSP. Edit it there.

---

## 🔬 How the demodulator works (`dsp_demod.py`)

At 2 Msps each 0.5 µs Mode-S chip is one sample, but in practice a pulse usually lands *between* two samples.

1. **Preamble detection.** Pulse-pair sums `p[k]+p[k+1]` at 0, 1, 3.5 and 4.5 µs (which don't depend on that sub-sample phase) are compared against the quiet zones and a running noise floor (`--min-snr`, default 8 dB).
2. **Bit slicing.** The phase is estimated from how much each preamble pulse spills into the next sample, and the two nearest phase hypotheses go through a weighted matched filter. If both fail the CRC, a **Viterbi** search runs over a pulse shape fitted by least squares to that frame's own preamble.
3. **Validation.** CRC-24 is checked: DF17/18 must be clean, with single-bit errors corrected; DF11 may carry an II/SI code; DF0/4/5/16/20/21 are accepted only when address/parity gives an ICAO recently seen in a clean frame.

Measured here: on dump1090's real `modes1.bin` capture it recovers 336 valid frames (DF17 186). On the synthetic test it gets about 68% of frames with **zero false frames**, and every frame from strong aircraft at any timing phase. It runs 2–6× faster than real time in Python. Weak frames that land half a sample out of phase can't be recovered at 2 Msps; that's why readsb samples at 2.4 Msps.
