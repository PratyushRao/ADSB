import asyncio
import json
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from flight_tracker import tracker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("adsb-backend")

app = FastAPI(
    title="ADS-B DSP Backend Server",
    description="Backend API and WebSocket streaming server for ADS-B radar flight tracking",
    version="0.1.0",
)

# Enable CORS for the Svelte frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    """Health check endpoint"""
    return {
        "status": "online",
        "service": "ADS-B DSP Backend",
        "active_flights": len(tracker.get_active_aircraft()),
    }


@app.get("/api/aircraft")
@app.get("/data.json")
def get_aircraft():
    """
    HTTP GET endpoint for polling frontend.
    Returns the list of currently tracked active aircraft.
    """
    return tracker.get_active_aircraft()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time streaming updates.
    Streams updated flight positions to connected Svelte frontend clients.
    """
    await websocket.accept()
    logger.info("WebSocket client connected from %s", websocket.client)

    try:
        while True:
            # Fetch active aircraft from tracker
            data = tracker.get_active_aircraft()
            # Push JSON payload to frontend
            await websocket.send_text(json.dumps(data))
            # Stream rate: 1 update per second (adjust as needed for DSP throughput)
            await asyncio.sleep(1.0)
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error("WebSocket error: %s", e)


# =====================================================================
# --- DSP / SDR Pipeline Hook (Future Implementation Placeholder) ---
# =====================================================================
# When you build your SDR demodulation pipeline (RTL-SDR, HackRF, etc.):
#
# 1. Capture IQ samples at 1090 MHz.
# 2. Demodulate PPM pulses & slice Mode-S 112-bit messages.
# 3. Decode CPR lat/lon, speed, heading, and callsign.
# 4. Feed decoded attributes to tracker:
#
#    tracker.update_aircraft(
#        hex_code="8008F1",
#        telemetry={
#            "callsign": "AIC101",
#            "lat": 28.6214,
#            "lon": 77.2541,
#            "altitude": 18500,
#            "speed": 410,
#            "heading": 240,
#            "verticalRate": -1200,
#            "squawk": "3412"
#        }
#    )
# =====================================================================


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
