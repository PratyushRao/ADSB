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
│   │   │   ├── AircraftDetailModal.svelte # Telemetry inspector HUD & flight data lookup links
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
│   ├── main.py                        # FastAPI server with WebSocket streaming, HTTP endpoints & CORS
│   ├── flight_tracker.py              # In-memory aircraft state store with automatic stale aircraft purging
│   ├── requirements.txt               # Python package dependencies (fastapi, uvicorn, websockets)
│   └── README.md                      # Backend-specific documentation
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

# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
# On Linux / macOS:
source .venv/bin/activate
# On Windows (PowerShell):
# .\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Start the server
python main.py
```

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

---

## 🛠️ How Data Flows into the System

```
[ RTL-SDR / HackRF / USRP Dongle ] 
                 │ (1090 MHz I/Q RF Samples)
                 ▼
[ DSP Demodulator (dsp_demod.py) ] ── Detects 8 µs preamble & PPM bit-slicing
                 │ (112-bit binary packets)
                 ▼
[ Mode-S Decoder (adsb_decoder.py) ] ── CRC check, CPR position decoding
                 │ (Decoded flight attributes)
                 ▼
[ State Store (flight_tracker.py) ] ── Merges packets by ICAO hex & purges stale planes
                 │ (JSON payload)
                 ▼
[ FastAPI Server (main.py) ] ── Emits over WebSocket (ws://127.0.0.1:8000/ws)
                 │ (Low-latency push stream)
                 ▼
[ Svelte 5 Frontend (App.svelte) ] ── Renders rotated ✈️ emojis on Leaflet radar map
```
