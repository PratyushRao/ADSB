#!/usr/bin/env python3
"""
Generate a synthetic 1090 MHz ADS-B IQ recording for testing the GNU Radio
demodulator without an SDR.

Encodes real DF17 frames (identification, airborne CPR position, airborne
velocity) for a handful of aircraft flying around a receiver, PPM-modulates
them at 2 Msps, and adds impairments: thermal noise, a random carrier
offset/phase per frame, a wide range of signal levels, pulse smearing
(finite receiver bandwidth) and half-sample timing offsets.

Output is interleaved unsigned 8-bit I/Q (the same format rtl_sdr writes),
plus an optional truth file listing every transmitted frame.

    python tools/gen_test_iq.py -o test.bin --seconds 30 --truth truth.txt
    python main.py --iq-file test.bin
"""
from __future__ import annotations

import argparse
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dsp_demod import crc_remainder  # noqa: E402

FS = 2_000_000
CHARSET = "#ABCDEFGHIJKLMNOPQRSTUVWXYZ##### ###############0123456789######"


# ---------------------------------------------------------------------------
# DF17 encoding
# ---------------------------------------------------------------------------
def _nl(lat: float) -> int:
    if abs(lat) >= 87.0:
        return 1
    a = 1 - math.cos(math.pi / 30)
    b = math.cos(math.pi / 180 * abs(lat)) ** 2
    return int(math.floor(2 * math.pi / math.acos(1 - a / b)))


def _cpr_encode(lat: float, lon: float, odd: int) -> tuple[int, int]:
    dlat = 360.0 / (60 - odd)
    yz = math.floor(2**17 * ((lat % dlat) / dlat) + 0.5)
    rlat = dlat * (yz / 2**17 + math.floor(lat / dlat))
    dlon = 360.0 / max(_nl(rlat) - odd, 1)
    xz = math.floor(2**17 * ((lon % dlon) / dlon) + 0.5)
    return yz & 0x1FFFF, xz & 0x1FFFF


def _alt_field(alt_ft: float) -> int:
    n = int(round((alt_ft + 1000) / 25))
    return ((n >> 4) << 5) | (1 << 4) | (n & 0xF)  # Q-bit = 1 (25 ft steps)


def _frame(icao: int, me: int) -> bytes:
    body = bytes([0x8D]) + icao.to_bytes(3, "big") + me.to_bytes(7, "big")
    parity = crc_remainder(body + b"\x00\x00\x00")
    return body + parity.to_bytes(3, "big")


def ident_frame(icao: int, callsign: str) -> bytes:
    chars = 0
    for ch in callsign.ljust(8)[:8]:
        chars = (chars << 6) | CHARSET.index(ch)
    return _frame(icao, (4 << 51) | chars)


def position_frame(icao: int, lat: float, lon: float, alt: float, odd: int) -> bytes:
    yz, xz = _cpr_encode(lat, lon, odd)
    me = (11 << 51) | (_alt_field(alt) << 36) | (odd << 34) | (yz << 17) | xz
    return _frame(icao, me)


def velocity_frame(icao: int, speed: float, track: float, vrate: float) -> bytes:
    vx = speed * math.sin(math.radians(track))
    vy = speed * math.cos(math.radians(track))
    s_ew, v_ew = int(vx < 0), min(int(round(abs(vx))) + 1, 1023)
    s_ns, v_ns = int(vy < 0), min(int(round(abs(vy))) + 1, 1023)
    s_vr, v_vr = int(vrate < 0), min(int(round(abs(vrate) / 64)) + 1, 511)
    me = (19 << 51) | (1 << 48)
    me |= (s_ew << 42) | (v_ew << 32) | (s_ns << 31) | (v_ns << 21)
    me |= (1 << 20) | (s_vr << 19) | (v_vr << 10)
    return _frame(icao, me)


# ---------------------------------------------------------------------------
# PPM modulation
# ---------------------------------------------------------------------------
_PREAMBLE = np.array([1, 0, 1, 0, 0, 0, 0, 1, 0, 1, 0, 0, 0, 0, 0, 0], dtype=np.float32)


def modulate(frame: bytes) -> np.ndarray:
    bits = np.unpackbits(np.frombuffer(frame, dtype=np.uint8)).astype(np.float32)
    chips = np.empty(2 * len(bits), dtype=np.float32)
    chips[0::2] = bits
    chips[1::2] = 1 - bits
    return np.concatenate([_PREAMBLE, chips])


# ---------------------------------------------------------------------------
# Scenario
# ---------------------------------------------------------------------------
class Plane:
    def __init__(self, rng, rx_lat, rx_lon, idx):
        self.icao = 0x800000 + int(rng.integers(0, 0x3FFFF))
        self.callsign = f"{['AIC', 'IGO', 'VTI', 'SEJ', 'AKJ', 'UAE', 'BAW', 'SIA'][idx % 8]}{rng.integers(10, 9999)}"
        brg = rng.uniform(0, 360)
        dist = rng.uniform(5, 50) / 60.0
        self.lat = rx_lat + dist * math.cos(math.radians(brg))
        self.lon = rx_lon + dist * math.sin(math.radians(brg)) / math.cos(math.radians(rx_lat))
        self.alt = float(rng.choice([4000, 9000, 18000, 31000, 36000, 39000]))
        self.speed = rng.uniform(200, 480)
        self.track = rng.uniform(0, 360)
        self.vrate = float(rng.choice([0, 0, -1216, 1472]))
        self.amp = rng.uniform(0.04, 0.6)  # signal level (strong .. weak)
        self.next_pos, self.next_vel, self.next_id = rng.uniform(0, 0.5, 3)
        self.odd = 0

    def step(self, dt):
        nm = self.speed * dt / 3600
        self.lat += nm / 60 * math.cos(math.radians(self.track))
        self.lon += nm / 60 * math.sin(math.radians(self.track)) / math.cos(math.radians(self.lat))
        self.alt = max(1000.0, self.alt + self.vrate * dt / 60)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-o", "--output", required=True)
    ap.add_argument("--seconds", type=float, default=30.0)
    ap.add_argument("--aircraft", type=int, default=8)
    ap.add_argument("--rx-lat", type=float, default=28.5562)
    ap.add_argument("--rx-lon", type=float, default=77.1000)
    ap.add_argument("--noise", type=float, default=0.02, help="noise std-dev (full scale = 1.0)")
    ap.add_argument("--truth", help="write transmitted frames (time, hex) to this file")
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()

    rng = np.random.default_rng(args.seed)
    planes = [Plane(rng, args.rx_lat, args.rx_lon, i) for i in range(args.aircraft)]
    truth = []
    smear = np.array([0.15, 0.7, 0.15], dtype=np.float32)

    with open(args.output, "wb") as out:
        for sec in range(int(math.ceil(args.seconds))):
            n = FS
            buf = (rng.normal(0, args.noise, n) + 1j * rng.normal(0, args.noise, n)).astype(np.complex64)
            t_start = float(sec)
            busy_until = 0
            events = []
            for p in planes:
                for t in np.arange(0, 1.0, 0.05):
                    tt = t_start + t
                    if tt >= p.next_pos:
                        events.append((tt, p, "pos"))
                        p.next_pos = tt + 0.5
                    if tt >= p.next_vel:
                        events.append((tt + 0.02, p, "vel"))
                        p.next_vel = tt + 0.5
                    if tt >= p.next_id:
                        events.append((tt + 0.03, p, "id"))
                        p.next_id = tt + 5.0
            events.sort(key=lambda e: e[0])
            last_t = {id(p): t_start for p in planes}

            for tt, p, kind in events:
                p.step(tt - last_t[id(p)])
                last_t[id(p)] = tt
                if kind == "pos":
                    frame = position_frame(p.icao, p.lat, p.lon, p.alt, p.odd)
                    p.odd ^= 1
                elif kind == "vel":
                    frame = velocity_frame(p.icao, p.speed, p.track, p.vrate)
                else:
                    frame = ident_frame(p.icao, p.callsign)

                start = int((tt - t_start) * FS) + int(rng.integers(0, 2000))
                env = np.convolve(modulate(frame), smear, mode="same")
                if rng.random() < 0.5:  # half-sample timing offset
                    env = 0.5 * (env + np.concatenate([[0], env[:-1]]))
                if start < busy_until or start + len(env) >= n:
                    continue  # avoid overlapping frames (no garbling in this test)
                busy_until = start + len(env) + 20
                phase = np.exp(1j * (rng.uniform(0, 2 * np.pi) + 2 * np.pi * rng.uniform(-50e3, 50e3)
                                     * np.arange(len(env)) / FS))
                buf[start:start + len(env)] += (p.amp * env * phase).astype(np.complex64)
                truth.append((t_start + start / FS, frame.hex().upper()))

            iq = np.empty(2 * n, dtype=np.float32)
            iq[0::2], iq[1::2] = buf.real, buf.imag
            out.write(np.clip(iq * 127.5 + 127.5, 0, 255).astype(np.uint8).tobytes())

    if args.truth:
        with open(args.truth, "w") as f:
            for t, h in truth:
                f.write(f"{t:.6f} {h}\n")
    print(f"wrote {args.output}: {args.seconds:.0f}s, {len(truth)} frames, "
          f"{len(planes)} aircraft: {', '.join(p.callsign for p in planes)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
