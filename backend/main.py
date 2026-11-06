import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from flight_tracker import tracker
from route_lookup import routes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("adsb-backend")

# Data source, configured via env vars so it also works with `uvicorn main:app`
# (python main.py --sdr / --iq-file / --simulate sets these for you):
#   ADSB_SOURCE   = none | simulate | sdr | file
#   ADSB_DEVICE   = SoapySDR device string (default "driver=rtlsdr")
#   ADSB_GAIN     = tuner gain dB (default 40)     ADSB_PPM = freq correction
#   ADSB_IQ_FILE  = path to a 2 Msps IQ recording  ADSB_IQ_FORMAT = cu8 | cf32
#   ADSB_RX_LAT / ADSB_RX_LON / ADSB_RX_NAME = your antenna location (sent to the map)
#   ADSB_ROUTES   = 1 (default) look up origin/destination per callsign online, 0 = off
SOURCE = os.environ.get("ADSB_SOURCE", "none").lower()
ROUTES_ON = os.environ.get("ADSB_ROUTES", "1") != "0"


def aircraft_payload() -> list:
    """Tracked aircraft, with origin/destination attached when known."""
    planes = tracker.get_active_aircraft()
    return routes.annotate(planes) if ROUTES_ON else planes

# Set while an SDR/file receiver is running; exposed on the health endpoint
decoder = None


def _start_receiver(loop: asyncio.AbstractEventLoop):
    """Build and start the GNU Radio flowgraph; frames are decoded on the event loop."""
    global decoder
    from adsb_decoder import AdsbDecoder
    from dsp_demod import AdsbReceiver

    decoder = AdsbDecoder(tracker)

    def on_frame(hexmsg: str, ts: float, rssi: float) -> None:
        # Called from a GNU Radio thread: hop onto the event loop so tracker
        # state is only ever touched from one thread.
        loop.call_soon_threadsafe(decoder.handle_frame, hexmsg, ts, rssi)

    is_file = SOURCE == "file"
    rx = AdsbReceiver(
        on_frame=on_frame,
        device=os.environ.get("ADSB_DEVICE", "driver=rtlsdr"),
        gain=float(os.environ.get("ADSB_GAIN", "40")),
        ppm=float(os.environ.get("ADSB_PPM", "0")),
        iq_file=os.environ.get("ADSB_IQ_FILE") if is_file else None,
        iq_format=os.environ.get("ADSB_IQ_FORMAT", "cu8"),
        realtime=is_file,  # play recordings back at real speed, like a live feed
        repeat=is_file,
    )
    rx.start()
    if is_file:
        logger.info("Replaying IQ file %s", os.environ.get("ADSB_IQ_FILE"))
    else:
        logger.info("SDR receiver started (%s, gain %s dB) at 1090 MHz",
                    os.environ.get("ADSB_DEVICE", "driver=rtlsdr"), os.environ.get("ADSB_GAIN", "40"))
    return rx


@asynccontextmanager
async def lifespan(app: FastAPI):
    feed_task = None
    rx = None
    route_task = asyncio.create_task(routes.run()) if ROUTES_ON else None
    if SOURCE == "simulate":
        from sim_feeder import run_simulated_feed
        feed_task = asyncio.create_task(run_simulated_feed(tracker))
    elif SOURCE in ("sdr", "file"):
        rx = _start_receiver(asyncio.get_running_loop())
    else:
        logger.info("No data source configured (use --sdr, --iq-file or --simulate)")
    yield
    if feed_task:
        feed_task.cancel()
    if route_task:
        route_task.cancel()
    if rx:
        rx.stop()
        await asyncio.to_thread(rx.wait)


app = FastAPI(
    lifespan=lifespan,
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
        "source": SOURCE,
        "active_flights": len(tracker.get_active_aircraft()),
        "receiver": decoder.stats() if decoder else None,
        "routes": routes.stats() if ROUTES_ON else None,
    }


@app.get("/api/receiver")
def get_receiver():
    """Receiver (antenna) location, so the map centres on it. null if not configured."""
    lat, lon = os.environ.get("ADSB_RX_LAT"), os.environ.get("ADSB_RX_LON")
    if lat is None or lon is None:
        return None
    return {
        "name": os.environ.get("ADSB_RX_NAME", "My Receiver"),
        "lat": float(lat),
        "lon": float(lon),
        "altitudeMeters": 0,
    }


@app.get("/api/aircraft")
@app.get("/data.json")
def get_aircraft():
    """
    HTTP GET endpoint for polling frontend.
    Returns the list of currently tracked active aircraft.
    """
    return aircraft_payload()


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
            data = aircraft_payload()
            # Push JSON payload to frontend
            await websocket.send_text(json.dumps(data))
            # Stream rate: 1 update per second (adjust as needed for DSP throughput)
            await asyncio.sleep(1.0)
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error("WebSocket error: %s", e)


if __name__ == "__main__":
    import argparse
    import uvicorn

    ap = argparse.ArgumentParser(description="ADS-B backend server")
    src = ap.add_mutually_exclusive_group()
    src.add_argument("--sdr", action="store_true", help="receive live from an SDR (GNU Radio + SoapySDR)")
    src.add_argument("--iq-file", help="replay a 2 Msps IQ recording through the demodulator")
    src.add_argument("--simulate", action="store_true", help="feed simulated aircraft (no hardware)")
    ap.add_argument("--device", help='SoapySDR device string, e.g. "driver=rtlsdr" or "driver=hackrf"')
    ap.add_argument("--gain", type=float, help="tuner gain in dB (default 40)")
    ap.add_argument("--ppm", type=float, help="frequency correction in ppm")
    ap.add_argument("--format", choices=["cu8", "cf32"], help="IQ file format (default cu8)")
    ap.add_argument("--lat", type=float, help="receiver (antenna) latitude, e.g. 12.9716")
    ap.add_argument("--lon", type=float, help="receiver (antenna) longitude, e.g. 77.5946")
    ap.add_argument("--rx-name", help='receiver name shown on the map, e.g. "Home"')
    ap.add_argument("--no-routes", action="store_true", help="don't look up origin/destination online")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()

    # Env vars (not globals) so settings survive uvicorn's reload subprocess
    if args.sdr:
        os.environ["ADSB_SOURCE"] = "sdr"
    elif args.iq_file:
        os.environ["ADSB_SOURCE"] = "file"
        os.environ["ADSB_IQ_FILE"] = os.path.abspath(args.iq_file)
    elif args.simulate:
        os.environ["ADSB_SOURCE"] = "simulate"
    for name, val in (("ADSB_DEVICE", args.device), ("ADSB_GAIN", args.gain),
                      ("ADSB_PPM", args.ppm), ("ADSB_IQ_FORMAT", args.format),
                      ("ADSB_RX_LAT", args.lat), ("ADSB_RX_LON", args.lon), ("ADSB_RX_NAME", args.rx_name)):
        if val is not None:
            os.environ[name] = str(val)

    if args.no_routes:
        os.environ["ADSB_ROUTES"] = "0"

    # Auto-reload would restart (and re-open) the SDR on every code edit
    hardware = os.environ.get("ADSB_SOURCE") in ("sdr", "file")
    uvicorn.run("main:app", host=args.host, port=args.port, reload=not hardware)
