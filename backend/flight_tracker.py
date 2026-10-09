import time
from typing import Dict, Any, List

class FlightTracker:
    """
    In-memory state store for tracked aircraft.
    Aggregates separate ADS-B messages (identity, position, velocity)
    by their 24-bit ICAO transponder hex code.
    """
    def __init__(self, stale_timeout_sec: float = 60.0):
        self.flights: Dict[str, Dict[str, Any]] = {}
        self.stale_timeout_sec = stale_timeout_sec

    def update_aircraft(self, hex_code: str, telemetry: Dict[str, Any]) -> None:
        """
        Merge newly decoded telemetry into existing aircraft state.
        Called by your DSP/ADS-B demodulation pipeline.
        """
        hex_code = hex_code.strip().upper()
        now = time.time()

        if hex_code not in self.flights:
            self.flights[hex_code] = {
                "hex": hex_code,
                "callsign": hex_code,
                "lat": 0.0,
                "lon": 0.0,
                "altitude": 0,
                "speed": 0,
                "heading": 0,
                "verticalRate": 0,
                "squawk": None,
                "first_seen": now,
                "last_seen": now,
            }

        plane = self.flights[hex_code]
        plane.update(telemetry)
        plane["last_seen"] = now

    def purge_stale(self) -> None:
        """Remove aircraft that haven't transmitted within the timeout window."""
        now = time.time()
        stale_keys = [
            hex_code for hex_code, data in self.flights.items()
            if now - data.get("last_seen", now) > self.stale_timeout_sec
        ]
        for hex_code in stale_keys:
            del self.flights[hex_code]

    def get_active_aircraft(self) -> List[Dict[str, Any]]:
        """Return list of active aircraft formatted for the Svelte frontend."""
        self.purge_stale()
        return list(self.flights.values())


# Global singleton instance for the server
tracker = FlightTracker()
