"""
Mode-S / ADS-B frame decoder: raw hex frames -> FlightTracker updates.

Uses pyModeS v3's stateful PipeDecoder, which:
  - pairs even/odd CPR frames per aircraft for global position decoding,
  - only releases positions after several mutually consistent fixes
    (rejects phantom positions from bit errors),
  - then decodes later frames locally against the last good position.
"""
from __future__ import annotations

import logging
import time
from typing import Any

import pyModeS

from flight_tracker import FlightTracker

logger = logging.getLogger("adsb-backend.decoder")

# pyModeS result key -> frontend/tracker key
_FIELD_MAP = {
    "altitude": "altitude",
    "groundspeed": "speed",
    "track": "heading",
    "vertical_rate": "verticalRate",
    "squawk": "squawk",
    "category": "category",
}


class AdsbDecoder:
    def __init__(self, tracker: FlightTracker):
        self.tracker = tracker
        self.pipe = pyModeS.PipeDecoder()
        self.frames = 0
        self.updates = 0
        self.positions = 0
        self.started = time.time()

    def handle_frame(self, hexmsg: str, timestamp: float, rssi_db: float | None = None) -> None:
        """Decode one validated frame from the demodulator and update the tracker."""
        self.frames += 1
        try:
            r = self.pipe.decode(hexmsg, timestamp=timestamp)
        except Exception as e:  # never let one odd frame kill the feed
            logger.debug("decode error for %s: %s", hexmsg, e)
            return

        icao = r.get("icao")
        if not icao or r.get("error") or r.get("crc_valid") is False:
            return

        update: dict[str, Any] = {}
        for src, dst in _FIELD_MAP.items():
            val = r.get(src)
            if val is not None:
                update[dst] = val

        callsign = r.get("callsign")
        if callsign:
            callsign = callsign.replace("_", "").replace("#", "").strip()
            if callsign:
                update["callsign"] = callsign

        lat, lon = r.get("latitude"), r.get("longitude")
        if lat is not None and lon is not None:
            update["lat"] = round(lat, 5)
            update["lon"] = round(lon, 5)
            self.positions += 1

        if "heading" in update:
            update["heading"] = round(update["heading"], 1)
        if rssi_db is not None:
            update["rssi"] = round(rssi_db, 1)

        self.tracker.update_aircraft(icao, update)
        self.updates += 1

    def stats(self) -> dict[str, Any]:
        elapsed = max(time.time() - self.started, 1e-6)
        return {
            "frames": self.frames,
            "frames_per_sec": round(self.frames / elapsed, 1),
            "positions": self.positions,
        }
