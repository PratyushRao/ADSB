"""
Simulated ADS-B feeder.

Stands in for the future SDR/DSP pipeline so the full backend -> WebSocket ->
frontend path can be tested without radio hardware.

It mimics how real ADS-B arrives: each aircraft emits *separate* message
types (identification, airborne position, airborne velocity) at different
rates, and the FlightTracker has to merge them by ICAO hex. Aircraft also
enter and leave coverage, so stale purging gets exercised too.
"""
import asyncio
import logging
import math
import random
from dataclasses import dataclass, field

from flight_tracker import FlightTracker

logger = logging.getLogger("adsb-backend.sim")

# Default receiver: Delhi (VIDP), matches the frontend's DEFAULT_RECEIVER
RX_LAT = 28.5562
RX_LON = 77.1000
COVERAGE_NM = 60.0

AIRLINES = ["AIC", "IGO", "VTI", "SEJ", "AKJ", "UAE", "BAW", "SIA", "QTR", "DLH"]


@dataclass
class SimPlane:
    hex: str
    callsign: str
    lat: float
    lon: float
    altitude: float
    speed: float
    heading: float
    vertical_rate: float
    squawk: str
    target_alt: float
    # Real transponders don't send everything at once; stagger message timers.
    next_ident: float = field(default_factory=lambda: random.uniform(0, 5))
    next_pos: float = field(default_factory=lambda: random.uniform(0, 1))
    next_vel: float = field(default_factory=lambda: random.uniform(0, 1))


def _random_hex() -> str:
    # 0x800000-0x83FFFF is India's ICAO allocation block
    return f"{random.randint(0x800000, 0x83FFFF):06X}"


def _spawn_plane() -> SimPlane:
    # Enter at the coverage edge, pointing roughly through the receiver area
    bearing = random.uniform(0, 360)
    dist_deg = (COVERAGE_NM * random.uniform(0.6, 0.95)) / 60.0
    lat = RX_LAT + dist_deg * math.cos(math.radians(bearing))
    lon = RX_LON + dist_deg * math.sin(math.radians(bearing)) / math.cos(math.radians(RX_LAT))
    heading = (bearing + 180 + random.uniform(-40, 40)) % 360

    cruise = random.random() < 0.6
    altitude = random.choice([31000, 33000, 35000, 37000, 39000]) if cruise else random.uniform(3000, 15000)
    target_alt = altitude if cruise else random.choice([2000, 24000, 30000])
    speed = random.uniform(440, 510) if cruise else random.uniform(180, 320)

    return SimPlane(
        hex=_random_hex(),
        callsign=f"{random.choice(AIRLINES)}{random.randint(1, 9999)}",
        lat=lat,
        lon=lon,
        altitude=altitude,
        speed=speed,
        heading=heading,
        vertical_rate=0.0,
        squawk=f"{random.randint(0, 7)}{random.randint(0, 7)}{random.randint(0, 7)}{random.randint(0, 7)}",
        target_alt=target_alt,
    )


def _distance_nm(lat: float, lon: float) -> float:
    dlat = (lat - RX_LAT) * 60.0
    dlon = (lon - RX_LON) * 60.0 * math.cos(math.radians(RX_LAT))
    return math.hypot(dlat, dlon)


def _step(p: SimPlane, dt: float) -> None:
    """Advance kinematics by dt seconds."""
    nm = p.speed * dt / 3600.0
    p.lat += (nm / 60.0) * math.cos(math.radians(p.heading))
    p.lon += (nm / 60.0) * math.sin(math.radians(p.heading)) / math.cos(math.radians(p.lat))

    # Climb/descend toward target altitude
    diff = p.target_alt - p.altitude
    if abs(diff) > 100:
        p.vertical_rate = math.copysign(min(2000.0, abs(diff) * 2), diff)
        p.altitude += p.vertical_rate * dt / 60.0
    else:
        p.vertical_rate = 0.0

    # Occasional gentle heading drift
    if random.random() < 0.02:
        p.heading = (p.heading + random.uniform(-15, 15)) % 360


async def run_simulated_feed(
    tracker: FlightTracker,
    num_aircraft: int = 10,
    tick_sec: float = 0.5,
) -> None:
    """Background task: keep `num_aircraft` simulated planes feeding the tracker."""
    planes = [_spawn_plane() for _ in range(num_aircraft)]
    t = 0.0
    logger.info("Simulated ADS-B feed started (%d aircraft)", num_aircraft)

    while True:
        t += tick_sec
        for i, p in enumerate(planes):
            _step(p, tick_sec)

            # Left coverage: stop transmitting (tracker purges it after timeout)
            # and bring in a fresh plane.
            if _distance_nm(p.lat, p.lon) > COVERAGE_NM:
                logger.info("%s (%s) left coverage", p.callsign, p.hex)
                planes[i] = _spawn_plane()
                continue

            # Identification message (DF17 TC 1-4) roughly every 5 s
            if t >= p.next_ident:
                tracker.update_aircraft(p.hex, {"callsign": p.callsign, "squawk": p.squawk})
                p.next_ident = t + 5.0

            # Airborne position (TC 9-18) roughly twice a second, with ~10% packet loss
            if t >= p.next_pos:
                if random.random() > 0.1:
                    tracker.update_aircraft(p.hex, {
                        "lat": round(p.lat, 5),
                        "lon": round(p.lon, 5),
                        "altitude": int(round(p.altitude / 25) * 25),
                    })
                p.next_pos = t + 0.5

            # Airborne velocity (TC 19) roughly twice a second
            if t >= p.next_vel:
                if random.random() > 0.1:
                    tracker.update_aircraft(p.hex, {
                        "speed": int(p.speed),
                        "heading": int(p.heading),
                        "verticalRate": int(round(p.vertical_rate / 64) * 64),
                    })
                p.next_vel = t + 0.5

        await asyncio.sleep(tick_sec)
