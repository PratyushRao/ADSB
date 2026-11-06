"""
Flight route (origin -> destination) lookup from the decoded callsign.

ADS-B itself never carries origin/destination: aircraft only broadcast their
ICAO address, callsign (e.g. "IGO5203"), position, altitude and velocity.
The route has to come from a schedule/route database keyed by callsign:

  1. adsbdb.com   (free, no key)  /v0/callsign/<cs>  -> airline, IATA flight no,
                                                       origin + destination airports
  2. hexdb.io     (free, no key)  /api/v1/route/icao/<cs> -> "VABB-VIDP", fallback

Route databases are crowd-sourced and can be stale (an airline reuses a
callsign for a different leg), so every route is checked against what WE
received from the aircraft: is its live position near the great-circle
origin -> destination, and is it flying towards the destination?
That verdict is sent to the UI as route["check"]:

  plausible       position is on the route corridor (and heading the right way)
  off-route       position is far from the origin->destination path
  reverse         on the corridor but flying towards the origin (DB has the other leg)
  unverified      no position decoded yet

Lookups run on a few background workers with a cache, so each callsign is
fetched once (re-checked every few hours), never from the WebSocket loop.
"""
from __future__ import annotations

import asyncio
import json
import logging
import math
import re
import time
import urllib.error
import urllib.request
from typing import Any

logger = logging.getLogger("adsb-backend.routes")

USER_AGENT = "adsb-gnuradio-tracker/0.1"
TIMEOUT_S = 8
HIT_TTL_S = 6 * 3600       # a found route is trusted for 6 h
MISS_TTL_S = 2 * 3600      # "unknown callsign" is re-asked after 2 h
ERROR_RETRY_S = 5 * 60     # network error -> retry after 5 min
MIN_INTERVAL_S = 0.3       # be polite to the free APIs (per worker)
WORKERS = 4                # parallel lookups (each takes ~0.5-3 s)

# Airline-style callsigns: 3-letter ICAO airline code + flight number (IGO5203, AIC101, FDX8).
# Registrations (VTABC) and empty callsigns have no schedule entry, so skip them.
_AIRLINE_CS = re.compile(r"^[A-Z]{3}[0-9][0-9A-Z]{0,4}$")

EARTH_NM = 3440.065


# ---------------------------------------------------------------------------
# Providers
# ---------------------------------------------------------------------------
def _get_json(url: str) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404:  # adsbdb answers 404 for unknown callsigns
            try:
                return json.loads(e.read().decode("utf-8"))
            except Exception:
                return None
        raise


def _airport_adsbdb(a: dict) -> dict:
    return {
        "iata": a.get("iata_code"),
        "icao": a.get("icao_code"),
        "name": a.get("name"),
        "city": a.get("municipality"),
        "country": a.get("country_iso_name"),
        "lat": a.get("latitude"),
        "lon": a.get("longitude"),
    }


def _from_adsbdb(cs: str) -> dict | None:
    data = _get_json(f"https://api.adsbdb.com/v0/callsign/{cs}")
    fr = (data or {}).get("response")
    if not isinstance(fr, dict) or "flightroute" not in fr:
        return None
    fr = fr["flightroute"]
    airline = fr.get("airline") or {}
    return {
        "flight": fr.get("callsign_iata") or cs,
        "airline": airline.get("name"),
        "origin": _airport_adsbdb(fr.get("origin") or {}),
        "destination": _airport_adsbdb(fr.get("destination") or {}),
        "source": "adsbdb.com",
    }


_hexdb_airports: dict[str, dict] = {}


def _hexdb_airport(icao: str) -> dict:
    if icao not in _hexdb_airports:
        a = _get_json(f"https://hexdb.io/api/v1/airport/icao/{icao}") or {}
        _hexdb_airports[icao] = {
            "iata": a.get("iata"),
            "icao": icao,
            "name": a.get("airport"),
            "city": a.get("region_name"),
            "country": a.get("country_code"),
            "lat": a.get("latitude"),
            "lon": a.get("longitude"),
        }
    return _hexdb_airports[icao]


def _from_hexdb(cs: str) -> dict | None:
    data = _get_json(f"https://hexdb.io/api/v1/route/icao/{cs}") or {}
    route = data.get("route")
    if not route or "-" not in route:
        return None
    stops = route.split("-")
    return {
        "flight": cs,
        "airline": None,
        "origin": _hexdb_airport(stops[0]),
        "destination": _hexdb_airport(stops[-1]),
        "source": "hexdb.io",
    }


PROVIDERS = (_from_adsbdb, _from_hexdb)


# ---------------------------------------------------------------------------
# Cross-check a route against the live decoded position
# ---------------------------------------------------------------------------
def _dist_brg(lat1, lon1, lat2, lon2) -> tuple[float, float]:
    """Great-circle distance (NM) and initial bearing (deg) from point 1 to 2."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    d = 2 * EARTH_NM * math.asin(min(1.0, math.sqrt(a)))
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return d, (math.degrees(math.atan2(y, x)) + 360) % 360


def _angle_diff(a: float, b: float) -> float:
    return abs((a - b + 180) % 360 - 180)


def check_route(route: dict, plane: dict) -> tuple[str, str]:
    """Return (verdict, human-readable detail) for a route vs the aircraft's live state."""
    o, d = route.get("origin") or {}, route.get("destination") or {}
    lat, lon = plane.get("lat"), plane.get("lon")
    if None in (o.get("lat"), o.get("lon"), d.get("lat"), d.get("lon")):
        return "unverified", "airport coordinates unknown"
    if lat is None or lon is None:
        return "unverified", "waiting for a decoded position"

    route_len, brg_od = _dist_brg(o["lat"], o["lon"], d["lat"], d["lon"])
    d_o, brg_op = _dist_brg(o["lat"], o["lon"], lat, lon)
    d_dest, brg_to_dest = _dist_brg(lat, lon, d["lat"], d["lon"])
    _, brg_to_orig = _dist_brg(lat, lon, o["lat"], o["lon"])

    # Cross-track (distance off the great circle) and along-track (progress) in NM
    xt = math.asin(math.sin(d_o / EARTH_NM) * math.sin(math.radians(brg_op - brg_od))) * EARTH_NM
    at = math.acos(max(-1.0, min(1.0, math.cos(d_o / EARTH_NM) / math.cos(xt / EARTH_NM)))) * EARTH_NM
    if math.cos(math.radians(brg_op - brg_od)) < 0:
        at = -at

    corridor = max(60.0, 0.2 * route_len)  # airways + vectoring aren't great circles
    if abs(xt) > corridor or at < -corridor or at > route_len + corridor:
        return "off-route", f"{abs(xt):.0f} NM off the {o.get('iata') or o.get('icao')}-{d.get('iata') or d.get('icao')} path"

    # Direction check, only en-route (near airports aircraft turn in every direction)
    track = plane.get("heading")
    if track is not None and plane.get("speed") and d_o > 40 and d_dest > 40:
        if _angle_diff(track, brg_to_orig) + 30 < _angle_diff(track, brg_to_dest):
            return "reverse", "on the route but flying towards the origin"

    pct = max(0, min(100, round(100 * at / route_len))) if route_len else 0
    return "plausible", f"{d_dest:.0f} NM to destination, {pct}% of route flown"


# ---------------------------------------------------------------------------
# Cached background lookup
# ---------------------------------------------------------------------------
class RouteLookup:
    def __init__(self) -> None:
        self._cache: dict[str, tuple[dict | None, float]] = {}  # cs -> (route|None, expires_at)
        self._pending: set[str] = set()
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self.lookups = 0
        self.hits = 0

    def _wanted(self, cs: str | None) -> str | None:
        if not cs:
            return None
        cs = cs.strip().upper()
        return cs if _AIRLINE_CS.match(cs) else None

    def get(self, callsign: str | None) -> dict | None:
        """Cached route for a callsign, queueing a lookup if unknown or expired."""
        cs = self._wanted(callsign)
        if not cs:
            return None
        route, expires = self._cache.get(cs, (None, 0.0))
        if time.time() >= expires and cs not in self._pending:
            self._pending.add(cs)
            self._queue.put_nowait(cs)
        return route

    def annotate(self, aircraft: list[dict]) -> list[dict]:
        """Copy of the aircraft list with 'route' (incl. live cross-check) attached."""
        out = []
        for plane in aircraft:
            route = self.get(plane.get("callsign"))
            if route:
                verdict, detail = check_route(route, plane)
                plane = {**plane, "route": {**route, "check": verdict, "checkDetail": detail}}
            out.append(plane)
        return out

    async def run(self) -> None:
        """Resolve queued callsigns with a few parallel workers."""
        await asyncio.gather(*(self._worker() for _ in range(WORKERS)))

    async def _worker(self) -> None:
        while True:
            cs = await self._queue.get()
            route, ttl = None, MISS_TTL_S
            try:
                for provider in PROVIDERS:
                    route = await asyncio.to_thread(provider, cs)
                    if route:
                        break
                ttl = HIT_TTL_S if route else MISS_TTL_S
            except Exception as e:  # network down, rate limited, bad JSON...
                logger.warning("route lookup for %s failed: %s", cs, e)
                route, ttl = self._cache.get(cs, (None, 0.0))[0], ERROR_RETRY_S
            self.lookups += 1
            self.hits += bool(route)
            if route:
                logger.info("route %s: %s -> %s (%s)", cs, route["origin"].get("iata") or route["origin"].get("icao"),
                            route["destination"].get("iata") or route["destination"].get("icao"), route["source"])
            self._cache[cs] = (route, time.time() + ttl)
            self._pending.discard(cs)
            await asyncio.sleep(MIN_INTERVAL_S)

    def stats(self) -> dict[str, int]:
        return {"lookups": self.lookups, "found": self.hits, "cached": len(self._cache)}


routes = RouteLookup()
