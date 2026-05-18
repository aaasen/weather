"""
Binary forecast encoding — 157 printable GSM chars for all forecast types.

Uses 125 printable GSM 03.38 chars (all 128 minus LF, CR, ESC) as a base-125
alphabet. All messages encode to exactly 157 chars (covers 1092 bits, the
maximum needed by any type).

Common header (12 bits):
  3  type   — forecast type 0-4
  4  month  — 1-12
  5  day    — 1-31

Period type (50 bits) — all types and models:
  5  wc      WMO weather code; index into 28-value WMO_CODES table
  4  precip  precipitation probability 0–100 %, stored in 10 % steps
  8  freeze  freezing level 0–25,500 ft, stored in 100 ft steps
  5  snow    snowfall 0–31 inches (period accumulation)
  4  cloud   mid-level cloud cover 0–100 %, stored in 10 % steps
  8  w500    500 hPa (~18k ft) wind: 5 bits speed (0–155 mph, 5 mph steps) + 3 bits direction (8 cardinals)
  8  w600    600 hPa (~14k ft) wind: same encoding
  8  w700    700 hPa (~10k ft) wind: same encoding

Type layout (header + interleaved slots):
  0 (10d-daily-2m):  12 + 10×2×50 = 1012 bits
  1 (5d-daily-3m):   12 +  5×3×50 =  762 bits
  2 (1d-hourly-1m):  12 + 20×1×50 = 1012 bits  (20h to stay ≤ 1092)
  3 (5d-6h-1m):      12 + 20×1×50 = 1012 bits
  4 (5d-12h-2m):     12 + 10×2×50 = 1012 bits

Models per type (fixed, primary first):
  0: ECMWF, GFS
  1: ECMWF, GFS, ICON
  2: ECMWF
  3: ECMWF
  4: ECMWF, GFS
"""

import datetime
import math
from dataclasses import dataclass
from enum import IntEnum
from typing import Any, ClassVar

from bitarray import bitarray
from bitarray.util import ba2int, int2ba
from pydantic import BaseModel

# ── Alphabet ──────────────────────────────────────────────────────────────────

# GSM 03.38 default alphabet minus LF (10), CR (13), ESC (27) — 125 printable chars.
SAFE_GSM = (
    "@£$¥èéùìòÇ"  # GSM  0- 9
    "Øø"  # GSM 11-12
    "ÅåΔ_ΦΓΛΩΠΨΣΘΞ"  # GSM 14-26
    "ÆæßÉ "  # GSM 28-32
    "!\"#¤%&'()*+,-./"  # GSM 33-47
    "0123456789:;<=>?"  # GSM 48-63
    "¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§"  # GSM 64-95
    "¿abcdefghijklmnopqrstuvwxyzäöñüà"  # GSM 96-127
)
assert len(SAFE_GSM) == 125
assert len(set(SAFE_GSM)) == 125
_SG2I = {c: i for i, c in enumerate(SAFE_GSM)}

_MSG_BITS = 1092  # type 2: 12 + 24×45
_MSG_CHARS = math.ceil(_MSG_BITS * math.log(2) / math.log(125))  # = 157


def encode_gsm_safe(bits: bitarray) -> str:
    """Encode bits as 157 printable GSM chars using base-125. Pads with zeros."""
    if len(bits) < _MSG_BITS:
        bits = bits + bitarray(_MSG_BITS - len(bits))
    value = ba2int(bits[:_MSG_BITS])
    chars = []
    for _ in range(_MSG_CHARS):
        chars.append(SAFE_GSM[value % 125])
        value //= 125
    return "".join(reversed(chars))


def decode_gsm_safe(s: str) -> bitarray:
    """Decode 157 printable GSM chars back to a 1092-bit bitarray."""
    value = 0
    count = 0
    for c in s:
        if c in _SG2I:
            value = value * 125 + _SG2I[c]
            count += 1
            if count == _MSG_CHARS:
                break
    return int2ba(value, length=_MSG_BITS)


# ── Type / model registry ─────────────────────────────────────────────────────


class ForecastType(IntEnum):
    DAY10_DAILY_2M = 0
    DAY5_DAILY_3M = 1
    DAY1_HOURLY_1M = 2
    DAY5_6H_1M = 3
    DAY5_12H_2M = 4


OPENMETEO_MODELS: dict[str, str] = {
    "ECMWF": "ecmwf_ifs025",
    "GFS": "gfs_seamless",
    "ICON": "icon_seamless",
}

TYPE_MODELS: dict[ForecastType, list[str]] = {
    ForecastType.DAY10_DAILY_2M: ["ECMWF", "GFS"],
    ForecastType.DAY5_DAILY_3M: ["ECMWF", "GFS", "ICON"],
    ForecastType.DAY1_HOURLY_1M: ["ECMWF"],
    ForecastType.DAY5_6H_1M: ["ECMWF"],
    ForecastType.DAY5_12H_2M: ["ECMWF", "GFS"],
}

TYPE_LABEL: dict[ForecastType, str] = {
    ForecastType.DAY10_DAILY_2M: "10-day daily · ECMWF + GFS",
    ForecastType.DAY5_DAILY_3M: "5-day daily · ECMWF + GFS + ICON",
    ForecastType.DAY1_HOURLY_1M: "Today hourly · ECMWF",
    ForecastType.DAY5_6H_1M: "5-day 6-hourly · ECMWF",
    ForecastType.DAY5_12H_2M: "5-day 12-hourly · ECMWF + GFS",
}

# Keywords that users send to request each type
TYPE_KEYWORDS: dict[str, ForecastType] = {
    "10d": ForecastType.DAY10_DAILY_2M,
    "5d": ForecastType.DAY5_DAILY_3M,
    "1d": ForecastType.DAY1_HOURLY_1M,
    "now": ForecastType.DAY1_HOURLY_1M,
    "today": ForecastType.DAY1_HOURLY_1M,
    "6h": ForecastType.DAY5_6H_1M,
    "12h": ForecastType.DAY5_12H_2M,
}


# ── Shared constants ──────────────────────────────────────────────────────────

WMO_CODES: list[int] = [
    0,
    1,
    2,
    3,
    45,
    48,
    51,
    53,
    55,
    56,
    57,
    61,
    63,
    65,
    66,
    67,
    71,
    73,
    75,
    77,
    80,
    81,
    82,
    85,
    86,
    95,
    96,
    99,
]
_WMO2IDX = {c: i for i, c in enumerate(WMO_CODES)}

CARDINALS: list[str] = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
CARDINAL_TO_IDX: dict[str, int] = {c: i for i, c in enumerate(CARDINALS)}


# ── Bit helpers ───────────────────────────────────────────────────────────────


def _put(b: bitarray, value: int, n: int) -> None:
    b.extend(int2ba(value, n))


def _take(b: bitarray, pos: int, n: int) -> tuple[int, int]:
    return ba2int(b[pos : pos + n]), pos + n


def _put_winds(b: bitarray, *pairs: tuple[int, int]) -> None:
    for spd, d in pairs:
        _put(b, min(spd // 5, 31), 5)
        _put(b, d % 8, 3)


def _take_winds(b: bitarray, pos: int) -> tuple[list[tuple[int, int]], int]:
    result = []
    for _ in range(3):
        spd, pos = _take(b, pos, 5)
        d, pos = _take(b, pos, 3)
        result.append((spd * 5, d))
    return result, pos


# ── Period classes ────────────────────────────────────────────────────────────


class PeriodFull(BaseModel):
    """50 bits — one forecast period for any type/model."""

    BITS: ClassVar[int] = 50
    weathercode:  int
    precip:       int
    freeze_ft:    int
    snow_in:      int
    cloud_mid:    int
    wind_500_mph: int
    wind_500_dir: int
    wind_600_mph: int
    wind_600_dir: int
    wind_700_mph: int
    wind_700_dir: int

    def to_bits(self) -> bitarray:
        b = bitarray()
        _put(b, _WMO2IDX.get(self.weathercode, 0), 5)
        _put(b, min(self.precip // 10, 10), 4)
        _put(b, min(self.freeze_ft // 100, 255), 8)
        _put(b, min(self.snow_in, 31), 5)
        _put(b, min(self.cloud_mid // 10, 10), 4)
        _put_winds(
            b,
            (self.wind_500_mph, self.wind_500_dir),
            (self.wind_600_mph, self.wind_600_dir),
            (self.wind_700_mph, self.wind_700_dir),
        )
        assert len(b) == self.BITS
        return b

    @classmethod
    def from_bits(cls, b: bitarray, pos: int) -> tuple["PeriodFull", int]:
        wc, pos = _take(b, pos, 5)
        pr, pos = _take(b, pos, 4)
        fz, pos = _take(b, pos, 8)
        sn, pos = _take(b, pos, 5)
        cl, pos = _take(b, pos, 4)
        w, pos = _take_winds(b, pos)
        return cls(
            weathercode=WMO_CODES[wc] if wc < len(WMO_CODES) else 0,
            precip=pr * 10,
            freeze_ft=fz * 100,
            snow_in=sn,
            cloud_mid=cl * 10,
            wind_500_mph=w[0][0],
            wind_500_dir=w[0][1],
            wind_600_mph=w[1][0],
            wind_600_dir=w[1][1],
            wind_700_mph=w[2][0],
            wind_700_dir=w[2][1],
        ), pos


PeriodSub = PeriodFull  # removed distinction; kept for any lingering imports


# ── ForecastMessage ───────────────────────────────────────────────────────────


@dataclass
class ForecastMessage:
    """
    Encodes any forecast type to 157 GSM chars.

    All models use PeriodFull (daily types) or PeriodSub (sub-daily types).
    Within each time slot, models are interleaved in TYPE_MODELS order.
    """

    type: int
    month: int
    day: int
    periods: list[list[Any]]  # periods[model_idx][period_idx]

    def to_bits(self) -> bitarray:
        b = bitarray()
        _put(b, self.type, 3)
        _put(b, self.month, 4)
        _put(b, self.day, 5)
        for i in range(len(self.periods[0])):
            for model_periods in self.periods:
                b.extend(model_periods[i].to_bits())
        return b

    def encode(self) -> str:
        return encode_gsm_safe(self.to_bits())

    @staticmethod
    def decode(s: str) -> "ForecastMessage":
        b = decode_gsm_safe(s)
        t, pos = _take(b, 0, 3)
        month, pos = _take(b, pos, 4)
        day, pos = _take(b, pos, 5)

        if t not in range(5):
            raise ValueError(f"Unknown forecast type: {t}")
        ft = ForecastType(t)

        n_periods = {
            ForecastType.DAY10_DAILY_2M: 10,
            ForecastType.DAY5_DAILY_3M:   5,
            ForecastType.DAY1_HOURLY_1M: 20,
            ForecastType.DAY5_6H_1M:     20,
            ForecastType.DAY5_12H_2M:    10,
        }[ft]

        n_models = len(TYPE_MODELS[ft])
        all_periods: list[list[Any]] = [[] for _ in range(n_models)]

        for _ in range(n_periods):
            for m in range(n_models):
                p, pos = PeriodFull.from_bits(b, pos)
                all_periods[m].append(p)

        return ForecastMessage(type=t, month=month, day=day, periods=all_periods)

    @property
    def forecast_type(self) -> ForecastType:
        return ForecastType(self.type)

    @property
    def start_date(self) -> datetime.date:
        year = datetime.date.today().year
        d = datetime.date(year, self.month, self.day)
        if (datetime.date.today() - d).days > 180:
            d = datetime.date(year + 1, self.month, self.day)
        return d


if __name__ == "__main__":
    from encoding import (
        _MSG_BITS,
        _MSG_CHARS,
        CARDINALS,
        TYPE_MODELS,
        ForecastMessage,
        ForecastType,
        PeriodFull,
    )

    sample = PeriodFull(
        weathercode=73,
        precip=100,
        freeze_ft=5500,
        snow_in=4,
        cloud_mid=80,
        wind_500_mph=30,
        wind_500_dir=4,
        wind_600_mph=25,
        wind_600_dir=4,
        wind_700_mph=10,
        wind_700_dir=4,
    )

    msg = ForecastMessage(
        type=int(ForecastType.DAY10_DAILY_2M),
        month=5,
        day=18,
        periods=[[sample] * 10, [sample] * 10],
    )
    encoded = msg.encode()
    decoded = ForecastMessage.decode(encoded)

    print(f"Type: {decoded.forecast_type.name}")
    print(f"Encoded ({len(encoded)} / 160 chars, {_MSG_BITS} bits): {encoded!r}")
    print(f"Start: {decoded.start_date}")
    for m_idx, m_name in enumerate(TYPE_MODELS[ForecastType.DAY10_DAILY_2M]):
        p = decoded.periods[m_idx][0]
        print(
            f"Day 1 {m_name}: wc={p.weathercode} precip={p.precip}% "
            f"freeze={p.freeze_ft}ft snow={p.snow_in}in cloud={p.cloud_mid}% "
            f"500={p.wind_500_mph}mph {CARDINALS[p.wind_500_dir]}"
        )
