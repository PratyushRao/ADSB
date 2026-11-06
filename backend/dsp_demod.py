#!/usr/bin/env python3
"""
GNU Radio ADS-B (Mode-S 1090 MHz) receiver / demodulator.

Flowgraph
---------
    [SDR via gr-soapy | IQ file] --complex--> |IQ| --float--> AdsbPpmDemod --> frames

`AdsbPpmDemod` is a custom gr.sync_block that, on the magnitude stream at
2 Msps (2 samples per 1 us Mode-S chip):

  1. Detects the 8 us Mode-S preamble (pulses at 0, 1, 3.5, 4.5 us). At
     2 Msps a 0.5 us pulse usually straddles two samples, so detection uses
     pulse-pair sums p[k]+p[k+1], which don't depend on the sub-sample phase.
  2. Estimates that phase (delta) from how much each preamble pulse spills
     into the following sample, then slices 56/112 PPM bits with a
     delta-weighted matched filter. If the CRC fails it retries nearby
     phases; the CRC picks the right one.
  3. Validates the CRC-24 parity:
       - DF17/18 (ADS-B / TIS-B): remainder must be 0; single-bit errors are
         corrected via a syndrome table.
       - DF11 (all-call reply): remainder holds only the 7-bit II/SI code.
       - DF0/4/5/16/20/21: parity is XORed with the ICAO address, so the
         remainder *is* the address; accepted only if that ICAO was recently
         seen in a CRC-clean DF11/17/18 (same approach as dump1090).
  4. Emits valid frames as hex strings (via a Python callback and a PDU
     message port named "frames", so the block also works inside GRC).

Run standalone to test the RF side without the web backend:

    python dsp_demod.py --sdr                      # live, prints *HEX; frames
    python dsp_demod.py --sdr --decode             # live, decoded with pyModeS
    python dsp_demod.py --iq-file capture.bin      # replay an rtl_sdr capture
"""
from __future__ import annotations

import argparse
import math
import sys
import time
from typing import Callable, Optional

import numpy as np
import pmt
from gnuradio import blocks, gr

# ---------------------------------------------------------------------------
# Mode-S CRC-24 (generator polynomial 0x1FFF409)
# ---------------------------------------------------------------------------
_CRC_POLY = 0xFFF409


def _make_crc_table() -> list[int]:
    table = []
    for i in range(256):
        c = i << 16
        for _ in range(8):
            c = ((c << 1) ^ _CRC_POLY) if c & 0x800000 else (c << 1)
        table.append(c & 0xFFFFFF)
    return table


_CRC_TABLE = _make_crc_table()


def crc_remainder(msg: bytes) -> int:
    """CRC of the data bits XORed with the transmitted parity (0 == clean)."""
    crc = 0
    for b in msg[:-3]:
        crc = ((crc << 8) & 0xFFFFFF) ^ _CRC_TABLE[((crc >> 16) ^ b) & 0xFF]
    return crc ^ int.from_bytes(msg[-3:], "big")


def _make_syndrome_table(nbits: int) -> dict[int, int]:
    """Map CRC syndrome -> bit index for every single-bit error (DF field excluded)."""
    table = {}
    nbytes = nbits // 8
    for j in range(5, nbits):
        err = bytearray(nbytes)
        err[j // 8] |= 0x80 >> (j % 8)
        table[crc_remainder(bytes(err))] = j
    return table


_SYNDROME_112 = _make_syndrome_table(112)

# ---------------------------------------------------------------------------
# PPM demodulator block
# ---------------------------------------------------------------------------
PREAMBLE_SAMPLES = 16          # 8 us at 2 Msps
LONG_BITS = 112
SPAN = PREAMBLE_SAMPLES + 2 * LONG_BITS + 1  # samples for one long frame (+1 for phase spill)
PHASES = (0.0, 0.25, 0.5, 0.75)
_VALID_DF = frozenset((0, 4, 5, 11, 16, 17, 18, 20, 21))
VITERBI_SNR_DB = 12.0  # weaker frames at bad phases aren't recoverable at 2 Msps anyway  # sub-sample timing hypotheses (fraction of a sample)
ICAO_TTL_SEC = 60.0            # how long an ICAO stays "known" for AP checks

FrameCallback = Callable[[str, float, float], None]


class AdsbPpmDemod(gr.sync_block):
    """Mode-S preamble detector + PPM bit slicer + CRC validator.

    Input : float magnitude |IQ| at 2 Msps.
    Output: PDUs on message port "frames" and/or `on_frame(hex, ts, rssi_db)`.
    """

    def __init__(
        self,
        sample_rate: float = 2e6,
        min_snr_db: float = 8.0,
        on_frame: Optional[FrameCallback] = None,
        t0: Optional[float] = None,
    ):
        gr.sync_block.__init__(self, name="ADS-B PPM Demod", in_sig=[np.float32], out_sig=None)
        if int(sample_rate) != 2_000_000:
            raise ValueError("AdsbPpmDemod expects a 2 Msps magnitude stream")
        self.sample_rate = sample_rate
        self.min_snr = 10 ** (min_snr_db / 20.0)  # amplitude ratio
        self._viterbi_snr = 10 ** (VITERBI_SNR_DB / 20.0)
        self.on_frame = on_frame
        self.t0 = time.time() if t0 is None else t0

        # Keep SPAN-1 samples from the previous call so frames that straddle
        # a work() boundary are still fully visible.
        self.set_history(SPAN)
        self.message_port_register_out(pmt.intern("frames"))

        self._noise: Optional[float] = None
        self._skip_until = -1  # absolute sample index; avoids re-detecting a frame
        self._known_icaos: dict[int, float] = {}
        self._last_prune = 0.0
        self.stats = {
            "preambles": 0, "frames": 0, "df17": 0, "corrected": 0, "phase_retry": 0, "viterbi": 0,
            "df11": 0, "ap_matched": 0, "crc_fail": 0,
        }

    # -- helpers -----------------------------------------------------------
    def _remember_icao(self, icao: int, ts: float) -> None:
        self._known_icaos[icao] = ts

    def _icao_known(self, icao: int, ts: float) -> bool:
        seen = self._known_icaos.get(icao)
        return seen is not None and ts - seen < ICAO_TTL_SEC

    def _prune_icaos(self, ts: float) -> None:
        if ts - self._last_prune > 10.0:
            self._known_icaos = {k: v for k, v in self._known_icaos.items() if ts - v < ICAO_TTL_SEC}
            self._last_prune = ts

    def _validate(self, bits: np.ndarray, ts: float) -> Optional[bytes]:
        """Return the (possibly corrected) frame bytes if valid, else None."""
        df = int(np.packbits(bits[:5])[0] >> 3)
        if df not in _VALID_DF:
            return None
        nbits = LONG_BITS if df >= 16 else 56
        raw = bytearray(np.packbits(bits[:nbits]).tobytes())
        rem = crc_remainder(raw)

        if df in (17, 18):
            if rem != 0:
                j = _SYNDROME_112.get(rem)
                if j is None:
                    self.stats["crc_fail"] += 1
                    return None
                raw[j // 8] ^= 0x80 >> (j % 8)
                self.stats["corrected"] += 1
            self.stats["df17"] += 1
            self._remember_icao(int.from_bytes(raw[1:4], "big"), ts)
            return bytes(raw)

        if df == 11:
            if rem & ~0x7F:  # anything beyond the II/SI code => corrupted
                self.stats["crc_fail"] += 1
                return None
            icao = int.from_bytes(raw[1:4], "big")
            if rem == 0:
                self._remember_icao(icao, ts)
            elif not self._icao_known(icao, ts):
                return None
            self.stats["df11"] += 1
            return bytes(raw)

        if df in (0, 4, 5, 16, 20, 21):
            # Address/Parity: remainder == ICAO address of the transmitter
            if self._icao_known(rem, ts):
                self.stats["ap_matched"] += 1
                return bytes(raw)
            return None

        return None

    def _demod_at(self, m: np.ndarray, i: int, ts: float) -> Optional[bytes]:
        """Slice bits for the preamble at m[i], trying sub-sample phases."""
        # Spill of each preamble pulse into the following sample ~= delta
        spill = (m[i + 1] / (m[i] + m[i + 1] + 1e-9) + m[i + 3] / (m[i + 2] + m[i + 3] + 1e-9)
                 + m[i + 8] / (m[i + 7] + m[i + 8] + 1e-9) + m[i + 10] / (m[i + 9] + m[i + 10] + 1e-9)) * 0.25
        x = m[i + PREAMBLE_SAMPLES:i + SPAN]
        a, b, c = x[0:-1:2], x[1::2], x[2::2]   # chip-0, chip-1, next chip-0 samples
        for attempt, delta in enumerate(sorted(PHASES, key=lambda d: abs(d - spill))[:2]):
            # Matched filter: chip energy is (1-delta) in its own sample and
            # delta in the next one. delta=0 reduces to a > b.
            score = (1 - delta) * a + (2 * delta - 1) * b - delta * c
            frame = self._validate(score > 0, ts)
            if frame is not None:
                if attempt:
                    self.stats["phase_retry"] += 1
                return frame

        # Fallback: learn the actual pulse shape from this frame's preamble and
        # run a Viterbi search over the bits. Handles any timing phase and the
        # receiver's pulse smearing, at a higher CPU cost.
        if i >= 2 and 0.15 < spill < 0.85 and self._pulse_level(m, i) > self._noise * self._viterbi_snr:
            h = self._estimate_channel(m, i)
            if h is not None:
                frame = self._validate(self._slice_viterbi(x, h), ts)
                if frame is not None:
                    self.stats["viterbi"] += 1
                    return frame
        return None

    @staticmethod
    def _pulse_level(m: np.ndarray, i: int) -> float:
        return float(m[i] + m[i + 1] + m[i + 2] + m[i + 3] + m[i + 7] + m[i + 8] + m[i + 9] + m[i + 10]) * 0.25

    # Preamble chip pattern (1 = pulse) at 2 samples per us
    _PRE_CHIPS = (1, 0, 1, 0, 0, 0, 0, 1, 0, 1, 0, 0, 0, 0, 0, 0)

    @classmethod
    def _estimate_channel(cls, m: np.ndarray, i: int) -> Optional[np.ndarray]:
        """Least-squares fit of a 4-tap pulse response + DC from the known preamble.

        Model: m[j] = h0*chip[j+1] + h1*chip[j] + h2*chip[j-1] + h3*chip[j-2] + dc
        """
        def chip(j):
            return cls._PRE_CHIPS[j] if 0 <= j < 16 else 0
        rows, ys = [], []
        for j in range(-2, 15):  # sample j only depends on known chips (<= j+1 <= 15)
            rows.append((chip(j + 1), chip(j), chip(j - 1), chip(j - 2), 1.0))
            ys.append(m[i + j])
        h, *_ = np.linalg.lstsq(np.array(rows, dtype=np.float64), np.array(ys, dtype=np.float64), rcond=None)
        if h[1] + h[2] <= 0:
            return None
        return h

    @staticmethod
    def _slice_viterbi(x: np.ndarray, h: np.ndarray) -> np.ndarray:
        """Maximum-likelihood bit sequence for samples x given pulse response h.

        Each bit b occupies chips (b, 1-b). Sample 2k depends on chips
        2k+1..2k-2 (this bit and the previous one); sample 2k+1 also on the
        next bit's first chip. State = (previous bit, current bit).
        """
        h0, h1, h2, h3, dc = (float(v) for v in h)
        xs = x.tolist()
        n = LONG_BITS

        def chips(b):
            return (1.0, 0.0) if b else (0.0, 1.0)

        # state key: (prev_bit, cur_bit); prev_bit None = preamble tail (chips 0,0)
        INF = float("inf")
        cost = {(None, 0): 0.0, (None, 1): 0.0}
        back: list[dict] = []
        for k in range(n):
            new_cost: dict = {}
            new_back: dict = {}
            s0, s1 = xs[2 * k], xs[2 * k + 1]
            for (pb, b), c_prev in cost.items():
                pa, pz = (0.0, 0.0) if pb is None else chips(pb)
                ca, cz = chips(b)
                e0 = s0 - (h0 * cz + h1 * ca + h2 * pz + h3 * pa + dc)
                for nb in ((0, 1) if k + 1 < n else (0,)):
                    na = 1.0 if nb else 0.0
                    e1 = s1 - (h0 * na + h1 * cz + h2 * ca + h3 * pz + dc)
                    c = c_prev + e0 * e0 + e1 * e1
                    key = (b, nb)
                    if c < new_cost.get(key, INF):
                        new_cost[key] = c
                        new_back[key] = (pb, b)
            back.append(new_back)
            cost = new_cost
        # trace back: final states are (bit_{n-1}, 0-dummy)
        state = min(cost, key=cost.get)
        bits = np.zeros(n, dtype=bool)
        for k in range(n - 1, -1, -1):
            prev = back[k][state]
            bits[k] = bool(prev[1])
            state = prev
        return bits

    # -- GNU Radio work ----------------------------------------------------
    def work(self, input_items, output_items):
        m = input_items[0]
        n = len(m) - (SPAN - 1)          # candidate start positions this call
        if n <= 0:
            return 0
        base = self.nitems_read(0) - (SPAN - 1)  # absolute index of m[0]

        # Running noise-floor estimate (median is robust to the pulses themselves)
        nf = float(np.median(m[:n])) + 1e-9
        self._noise = nf if self._noise is None else 0.9 * self._noise + 0.1 * nf

        def s(k):
            return m[k:k + n]

        p = [s(k) for k in range(15)]
        # Pulse energy at 0, 1, 3.5, 4.5 us. Summing each sample with the next
        # makes this independent of where the pulse falls between samples.
        pairs = (p[0] + p[1], p[2] + p[3], p[7] + p[8], p[9] + p[10])
        level = (pairs[0] + pairs[1] + pairs[2] + pairs[3]) * 0.25
        weakest = np.minimum(np.minimum(pairs[0], pairs[1]), np.minimum(pairs[2], pairs[3]))
        # Quiet-zone samples furthest from any pulse (immune to smear/spill)
        quiet = (p[4] + p[5] + p[12] + p[13] + p[14]) * 0.2
        cand = (
            (weakest > 0.5 * level)              # all four pulses present
            & (quiet * 3.0 < weakest)            # quiet zones clearly quiet
            & (level > self._noise * self.min_snr)
        )

        for i in np.flatnonzero(cand):
            abs_i = base + int(i)
            if abs_i < self._skip_until:
                continue
            self.stats["preambles"] += 1
            ts = self.t0 + abs_i / self.sample_rate
            frame = self._demod_at(m, int(i), ts)
            if frame is None:
                continue

            self._skip_until = abs_i + PREAMBLE_SAMPLES + 16 * len(frame)
            self.stats["frames"] += 1
            rssi_db = 20 * math.log10(max(float(level[i]), 1e-9))
            hexmsg = frame.hex().upper()

            if self.on_frame is not None:
                self.on_frame(hexmsg, ts, rssi_db)
            meta = pmt.make_dict()
            meta = pmt.dict_add(meta, pmt.intern("timestamp"), pmt.from_double(ts))
            meta = pmt.dict_add(meta, pmt.intern("rssi_db"), pmt.from_double(rssi_db))
            meta = pmt.dict_add(meta, pmt.intern("hex"), pmt.intern(hexmsg))
            self.message_port_pub(
                pmt.intern("frames"),
                pmt.cons(meta, pmt.init_u8vector(len(frame), list(frame))),
            )

        self._prune_icaos(self.t0 + (base + n) / self.sample_rate)
        return n


# ---------------------------------------------------------------------------
# Flowgraph
# ---------------------------------------------------------------------------
class AdsbReceiver(gr.top_block):
    """SDR (gr-soapy) or IQ-file source -> |IQ| -> AdsbPpmDemod."""

    def __init__(
        self,
        on_frame: Optional[FrameCallback] = None,
        device: str = "driver=rtlsdr",
        gain: float = 40.0,
        freq: float = 1090e6,
        ppm: float = 0.0,
        iq_file: Optional[str] = None,
        iq_format: str = "cu8",
        realtime: bool = False,
        repeat: bool = False,
        min_snr_db: float = 8.0,
    ):
        gr.top_block.__init__(self, "ADS-B Receiver", catch_exceptions=True)
        self.sample_rate = 2e6

        if iq_file:
            src = self._file_source(iq_file, iq_format, repeat)
            if realtime:
                thr = blocks.throttle(gr.sizeof_gr_complex, self.sample_rate, True)
                self.connect(src, thr)
                src = thr
            # File timestamps start at 0 unless played back in real time
            t0 = time.time() if realtime else 0.0
        else:
            from gnuradio import soapy
            self.sdr = soapy.source(device, "fc32", 1, "", "", [""], [""])
            self.sdr.set_sample_rate(0, self.sample_rate)
            self.sdr.set_frequency(0, freq)
            if ppm:
                self.sdr.set_frequency_correction(0, ppm)
            self.sdr.set_gain_mode(0, False)   # manual gain; AGC hurts pulse detection
            self.sdr.set_gain(0, gain)
            src = self.sdr
            t0 = time.time()

        self.mag = blocks.complex_to_mag(1)
        self.demod = AdsbPpmDemod(self.sample_rate, min_snr_db=min_snr_db, on_frame=on_frame, t0=t0)
        self.connect(src, self.mag, self.demod)

    def _file_source(self, path: str, fmt: str, repeat: bool):
        if fmt == "cf32":  # GNU Radio file sink / complex64
            src = blocks.file_source(gr.sizeof_gr_complex, path, repeat)
            self._keep = [src]
            return src
        if fmt == "cu8":   # rtl_sdr / dump1090 capture: interleaved unsigned 8-bit I/Q
            src = blocks.file_source(gr.sizeof_char, path, repeat)
            to_f = blocks.uchar_to_float()
            center = blocks.add_const_ff(-127.5)
            scale = blocks.multiply_const_ff(1 / 127.5)
            deint = blocks.deinterleave(gr.sizeof_float, 1)
            to_c = blocks.float_to_complex(1)
            self.connect(src, to_f, center, scale, deint)
            self.connect((deint, 0), (to_c, 0))
            self.connect((deint, 1), (to_c, 1))
            self._keep = [src, to_f, center, scale, deint, to_c]
            return to_c
        raise ValueError(f"unknown IQ format {fmt!r} (use cu8 or cf32)")


# ---------------------------------------------------------------------------
# Standalone CLI
# ---------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description="GNU Radio ADS-B demodulator")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--sdr", action="store_true", help="receive live from an SDR via SoapySDR")
    src.add_argument("--iq-file", help="replay a 2 Msps IQ recording")
    ap.add_argument("--format", default="cu8", choices=["cu8", "cf32"],
                    help="IQ file format: cu8 = rtl_sdr/dump1090 (default), cf32 = GNU Radio complex")
    ap.add_argument("--device", default="driver=rtlsdr", help="SoapySDR device string")
    ap.add_argument("--gain", type=float, default=40.0, help="tuner gain in dB (default 40)")
    ap.add_argument("--ppm", type=float, default=0.0, help="frequency correction in ppm")
    ap.add_argument("--min-snr", type=float, default=8.0, help="preamble SNR threshold in dB (default 8)")
    ap.add_argument("--decode", action="store_true", help="print pyModeS-decoded fields")
    args = ap.parse_args()

    pipe = None
    if args.decode:
        import pyModeS
        pipe = pyModeS.PipeDecoder()

    def on_frame(hexmsg: str, ts: float, rssi: float) -> None:
        if pipe is None:
            print(f"*{hexmsg};", flush=True)
            return
        r = dict(pipe.decode(hexmsg, timestamp=ts))
        keep = {k: r[k] for k in ("df", "icao", "callsign", "altitude", "latitude", "longitude",
                                  "groundspeed", "track", "vertical_rate", "squawk") if r.get(k) is not None}
        print(f"{ts:14.6f} {rssi:6.1f}dB {hexmsg:28} {keep}", flush=True)

    tb = AdsbReceiver(
        on_frame=on_frame, device=args.device, gain=args.gain, ppm=args.ppm,
        iq_file=args.iq_file, iq_format=args.format, min_snr_db=args.min_snr,
    )
    tb.start()
    try:
        tb.wait()
    except KeyboardInterrupt:
        tb.stop()
        tb.wait()
    print(f"# stats: {tb.demod.stats}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
