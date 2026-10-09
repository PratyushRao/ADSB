# 🛰️ ADS-B DSP Backend Server

A lightweight **FastAPI** server providing both **HTTP REST** and **WebSocket** real-time streaming feeds for the Svelte ADS-B radar frontend.

---

## ⚡ Quick Start

### 1. Setup Virtual Environment (Recommended)

In this `backend/` directory:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2. Install Dependencies

```powershell
pip install -r requirements.txt
```

### 3. Run the Server

```powershell
python main.py
```
Or directly with Uvicorn:
```powershell
uvicorn main:app --reload --port 8000
```

The server will start at:
- **Health check**: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- **HTTP REST Feed**: [http://127.0.0.1:8000/api/aircraft](http://127.0.0.1:8000/api/aircraft)
- **Interactive Swagger Docs**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Real-Time WebSocket**: `ws://127.0.0.1:8000/ws`

---

## 🔗 Connecting to the Svelte Frontend

In the running Svelte frontend ([http://localhost:5173](http://localhost:5173)):
1. Click the **📡 Settings** button in the sidebar.
2. In the **Backend Endpoint URL** field, enter:
   - For WebSocket streaming: `ws://127.0.0.1:8000/ws`
   - For HTTP polling: `http://127.0.0.1:8000/api/aircraft`
3. Click **Connect & Poll**.

---

## 🏗️ Future DSP / SDR Integration

When you implement your DSP demodulation pipeline:
1. Capture 1090 MHz I/Q samples from your SDR (RTL-SDR, HackRF, etc.).
2. Demodulate PPM pulses and decode Mode-S / ADS-B packets.
3. Call `tracker.update_aircraft(hex_code, telemetry)` from [`flight_tracker.py`](flight_tracker.py).
4. The server automatically aggregates the data and pushes it over the WebSocket to the Svelte frontend.
