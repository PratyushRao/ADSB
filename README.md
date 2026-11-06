# ✈️ ADS-B Flight Radar & Visualizer

A real-time flight tracking radar and visualization system built with **Svelte 5**, **TypeScript**, **Tailwind CSS v4**, and **Leaflet** on the frontend, paired with an asynchronous **FastAPI** backend for live telemetry ingestion. Designed for SDR and DSP demodulators to track and display aircraft in real time over the air.

---

## 📁 Project & Folder Structure

```
ADSB/
├── frontend/                          # Svelte 5 + Vite + Leaflet Web Application
│   ├── public/                        # Static public assets & icons
│   ├── src/
│   │   ├── components/
│   │   │   ├── Map.svelte             # Leaflet tactical radar canvas, rotated ✈️ markers, range rings
│   │   │   ├── Sidebar.svelte         # Callsign/hex search, telemetry statistics, filters, layer selectors
│   │   │   ├── AircraftCard.svelte    # Flight summary list card with dynamic altitude badges
│   │   │   ├── AircraftDetailModal.svelte # Telemetry inspector HUD with origin → destination route panel
│   │   │   └── ConnectionModal.svelte # Feed settings (WebSocket / HTTP URL, JSON upload, receiver coords)
│   │   ├── types/
│   │   │   └── aircraft.ts            # TypeScript interfaces for Aircraft, FeedStatus & ReceiverLocation
│   │   ├── utils/
│   │   │   ├── geo.ts                 # Haversine distance (NM), bearing calculation & altitude formatters
│   │   │   ├── mockData.ts            # Realistic flight simulation generator with vector kinematics
│   │   │   └── parser.ts              # Universal multi-format ADS-B JSON parser & normalizer
│   │   ├── App.svelte                 # Main application coordinator (handles feed connection & state)
│   │   ├── app.css                    # Tailwind CSS v4 & Leaflet radar styles
│   │   └── main.ts                    # Svelte application mounting point
│   ├── index.html                     # HTML root template with aviation favicon
│   ├── package.json                   # Frontend dependencies and npm scripts
│   ├── tsconfig.json                  # TypeScript project references
│   ├── tsconfig.app.json              # TypeScript compiler configuration (DOM, ES2023)
│   └── vite.config.ts                 # Vite bundler configuration with Tailwind CSS plugin
│
├── backend/                           # FastAPI ADS-B Backend Server
│   ├── main.py                        # FastAPI server: data source selection, WebSocket, HTTP endpoints
│   ├── dsp_demod.py                   # GNU Radio receiver + our Mode-S PPM demodulator block (CRC-24)
│   ├── adsb_decoder.py                # pyModeS PipeDecoder: hex frames -> callsign/altitude/position/velocity
│   ├── flight_tracker.py              # In-memory aircraft state store with automatic stale aircraft purging
│   ├── route_lookup.py                # Callsign -> origin/destination (adsbdb/hexdb), cross-checked vs position
│   ├── sim_feeder.py                  # Simulated aircraft (--simulate), no DSP
│   ├── grc/adsb_rx.grc                # Same receiver as a GNU Radio Companion flowgraph
│   ├── tools/gen_test_iq.py           # Synthetic 1090 MHz IQ recording generator (testing without an SDR)
│   ├── requirements.txt               # Python dependencies (GNU Radio itself comes from OS packages)
│   └── README.md                      # Backend-specific documentation
│
├── docs/
│   └── HOW_IT_WORKS.md                # End-to-end walkthrough: RF -> GNU Radio -> pyModeS -> map
│
├── LICENSE                            # Project license
└── README.md                          # Main project documentation (this file)
```

---

## ⚡ Startup Commands

### 1. Start the Backend Server (FastAPI)

Open a terminal in the root directory:

```bash
# Navigate to the backend directory
cd backend

# Create virtual environment (system site packages = access to the OS-installed GNU Radio)
python3 -m venv --system-site-packages .venv
source .venv/bin/activate

# Install dependencies (FastAPI, pyModeS, ...)
pip install -r requirements.txt

# Start the server with ONE data source:
python main.py --sdr                                     # live RTL-SDR via GNU Radio
python main.py --sdr --lat 19.0222 --lon 72.8561 --rx-name "VJTI"   # optional: centre map on your antenna
python main.py --iq-file grc/test_adsb.bin               # replay an IQ recording (no SDR)
python main.py --simulate                                # simulated aircraft, no DSP
```

> See [backend/README.md](backend/README.md) for SDR setup, generating test recordings, the GNU Radio
> Companion flowgraph ([backend/grc/adsb_rx.grc](backend/grc/adsb_rx.grc)), and how the demodulator works.
> The frontend connects to the backend automatically and centres the map on `--lat/--lon` (optional;
> aircraft positions come from the aircraft themselves). Origin/destination are looked up online per
> callsign; use `--no-routes` to work offline. Full pipeline walkthrough: [docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md).
>
> **RTL-SDR on Linux:** if opening the dongle fails with `usb_claim_interface error -6`, the kernel TV driver
> has claimed it: `echo -e 'blacklist dvb_usb_rtl28xxu\nblacklist rtl2832_sdr\nblacklist rtl2832' | sudo tee /etc/modprobe.d/blacklist-rtlsdr.conf`
> then replug. Only one program can use the dongle at a time (stop `dsp_demod.py` before `main.py`).

> **Backend Network Addresses:**
> - **WebSocket Feed (Default)**: `ws://127.0.0.1:8000/ws`
> - **HTTP REST Feed**: [http://127.0.0.1:8000/api/aircraft](http://127.0.0.1:8000/api/aircraft) (or `/data.json`)
> - **Interactive Swagger Docs**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
> - **Health Check**: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)

---

### 2. Start the Frontend Application (Svelte 5)

Open a second terminal in the root directory:

```powershell
# Navigate to the frontend directory
cd frontend

# Install Node.js dependencies (first time only)
npm install

# Start the Vite development server
npm run dev
```

Open your browser and navigate to:
**[http://localhost:5173](http://localhost:5173)**

> **Production Build Commands:**
> ```powershell
> cd frontend
> npm run check    # Type-checks Svelte and TypeScript files
> npm run build    # Compiles production-ready static assets to dist/
> npm run preview  # Previews the production build locally
> ```

---

## 📡 Backend Data JSON Structure Format

The frontend receives flight updates either through a continuous **WebSocket push** (`ws://127.0.0.1:8000/ws`) or via periodic **HTTP GET polling** (`http://127.0.0.1:8000/api/aircraft`).

The parser automatically detects and normalizes any of the following structures:

### Schema 1: Simple JSON Array *(Recommended for Custom Python/DSP Backends)*

The cleanest format to emit from your DSP demodulator:

```json
[
  {
    "hex": "8008F1",
    "callsign": "AIC101",
    "lat": 28.6214,
    "lon": 77.2541,
    "altitude": 18500,
    "speed": 410,
    "heading": 240,
    "verticalRate": -1200,
    "squawk": "3412"
  },
  {
    "hex": "80054A",
    "callsign": "IGO5203",
    "lat": 28.4812,
    "lon": 76.9532,
    "altitude": 3200,
    "speed": 175,
    "heading": 95,
    "verticalRate": 700,
    "squawk": "1200"
  }
]
```

---

### Schema 2: Standard `dump1090` / `readsb` Format

Standard format produced by SDR demodulators:

```json
{
  "now": 1712700000.0,
  "aircraft": [
    {
      "hex": "8008f1",
      "flight": "AIC101  ",
      "lat": 28.6214,
      "lon": 77.2541,
      "alt_baro": 18500,
      "speed": 410.0,
      "track": 240.0,
      "vert_rate": -1200,
      "squawk": "3412",
      "seen": 0.5
    }
  ]
}
```

---

### Schema 3: OpenSky Network Format

The frontend also decodes state vectors from OpenSky:

```json
{
  "time": 1712700000,
  "states": [
    [
      "8008f1",
      "AIC101",
      "India",
      1712699995,
      1712700000,
      77.2541,
      28.6214,
      5638.8,
      false,
      210.9,
      240.0,
      -6.1
    ]
  ]
}
```

---

### 📋 Field Specification Table

| Field Key | Aliases Accepted | Type | Required? | Description & Frontend Behavior |
| :--- | :--- | :--- | :--- | :--- |
| `lat` | `latitude`, `latitude_deg`, `pos[0]` | `number` | **Yes** | Latitude coordinate in decimal degrees (e.g. `28.6214`). Required to plot marker. |
| `lon` | `lng`, `longitude`, `longitude_deg`, `pos[1]` | `number` | **Yes** | Longitude coordinate in decimal degrees (e.g. `77.2541`). Required to plot marker. |
| `hex` | `icao`, `icao24`, `id` | `string` | Optional | Unique 24-bit Mode-S ICAO hex address (e.g. `"8008F1"`). Used as plane identifier. |
| `callsign` | `flight`, `ident` | `string` | Optional | Flight number (e.g. `"AIC101"`). Defaults to `hex` if omitted. |
| `heading` | `track`, `true_track`, `course`, `bearing` | `number` | Optional | Magnetic ground track in degrees (`0°` to `360°`). **Rotates the ✈️ airplane emoji**. |
| `altitude` | `alt_baro`, `alt_geom`, `alt`, `baro_altitude` | `number` | Optional | Barometric altitude in feet. Values $\ge$ 18,000 ft are formatted as Flight Levels (e.g. `FL360`). |
| `speed` | `gs`, `velocity`, `ground_speed` | `number` | Optional | Ground speed in knots. Displays knots and converts to km/h in the inspector HUD. |
| `verticalRate` | `vert_rate`, `vertical_rate`, `climb` | `number` | Optional | Climb/descent rate in feet per minute (fpm). Displays `▲` (climbing) or `▼` (descending). |
| `squawk` | `squawk` | `string` | Optional | 4-digit transponder squawk code (e.g. `"3412"`, `"7700"` emergency). |
| `seen` | `seen` | `number` | Optional | Seconds elapsed since the last transmission was received. |
| `route` | — | `object` | Optional | Added by our backend: `flight`, `airline`, `origin`/`destination` airports, `source`, and `check` (`plausible` / `off-route` / `reverse` / `unverified`) from comparing the route with the live position. |

---

## 🛠️ How Data Flows into the System

```
[ RTL-SDR / HackRF / USRP Dongle ] 
                 │ (1090 MHz I/Q RF Samples)
                 ▼
[ GNU Radio flowgraph (dsp_demod.py) ] ── Preamble detect, PPM slicing, CRC-24 check/fix
                 │ (112-bit binary packets)
                 ▼
[ Mode-S Decoder (adsb_decoder.py) ] ── pyModeS: callsign, CPR position, velocity
                 │ (Decoded flight attributes)
                 ▼
[ State Store (flight_tracker.py) ] ── Merges packets by ICAO hex & purges stale planes
                 │
                 ▼
[ Route Lookup (route_lookup.py) ] ── Callsign -> origin/destination, cross-checked vs live position
                 │ (JSON payload)
                 ▼
[ FastAPI Server (main.py) ] ── Emits over WebSocket (ws://127.0.0.1:8000/ws)
                 │ (Low-latency push stream)
                 ▼
[ Svelte 5 Frontend (App.svelte) ] ── Renders rotated ✈️ emojis on Leaflet radar map
```

---

## 🗺️ Status & Roadmap

**Done**
- Live reception from an RTL-SDR through GNU Radio (gr-soapy), with our own Mode-S demodulator block: phase-invariant preamble detection, sub-sample phase slicing, Viterbi fallback, CRC-24 with 1-bit correction, address/parity checks. No dump1090/readsb.
- pyModeS decoding (callsign, altitude, CPR position, velocity, squawk) into the tracker; WebSocket push to the map.
- IQ-file replay, synthetic test-signal generator, simulated feed, GNU Radio Companion flowgraph.
- Origin/destination per callsign from free route databases, with a live-position plausibility check (no Flightradar24 dependency).
- Receiver location (`--lat/--lon`) sent to the map.

**To do**
- **UI revamp** of the frontend.
- **Heading-aware aircraft icons:** replace the fixed ✈️ emoji with an SVG plane icon drawn to point at the decoded track (the emoji is drawn pointing ~45° north-east, so rotating it by the heading is visually off by 45°). Possibly vary the icon by aircraft category.
- Demodulator throughput: the Python block can fall behind live 2 Msps (`O` overflow markers in the log); vectorise further or move the hot loop to C++/numba, and consider 2.4 Msps.
- Benchmarking against Flightradar24: aircraft count within radius, position latency, route-match rate.

