"""
Binary forecast encoding using 94 printable ASCII characters 33–126 (! through ~) as a base-94 alphabet.

Common header (12 bits):
  3  type   — forecast type 0-4
  4  month  — 1-12
  5  day    — 1-31

Period (40 bits) — all types and models:
  5  wc      WMO weather code; index into 28-value WMO_CODES table
  3  precip  precipitation probability 0–100 %, stored in 12.5 % steps (0–7)
  4  freeze  freezing level 0–15,000 ft, stored in 1,000 ft steps (0–15)
  4  snow    snowfall 0–15; unit depends on type: 1"/step daily, 0.1"/step sub-daily
  3  cloud   mid-level cloud cover 0–100 %, stored in 12.5 % steps (0–7)
  7  w500    500 hPa (~18k ft) wind: 4 bits speed (0–75 mph, 5 mph steps) + 3 bits direction (8 cardinals)
  7  w600    600 hPa (~14k ft) wind: same encoding
  7  w700    700 hPa (~10k ft) wind: same encoding

Type layout (header + interleaved slots):
  0 (10d-daily-2m):  12 + 10×2×40 =  812 bits
  1 (5d-daily-3m):   12 +  5×3×40 =  612 bits
  2 (1d-hourly-1m):  12 + 20×1×40 =  812 bits
  3 (5d-6h-1m):      12 + 20×1×40 =  812 bits
  4 (5d-12h-2m):     12 + 10×2×40 =  812 bits

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

# Printable ASCII 33–126 (! through ~) — 94 chars.
ALPHABET = "!\"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~"
assert len(ALPHABET) == 94
assert len(set(ALPHABET)) == 94
_A2I = {c: i for i, c in enumerate(ALPHABET)}

def _n_chars(n_bits: int) -> int:
    return math.ceil(n_bits * math.log(2) / math.log(94))


def encode(bits: bitarray) -> str:
    """Encode a bitarray to the minimum number of base-94 ASCII chars."""
    n_bits = len(bits)
    n_chars = _n_chars(n_bits)
    value = ba2int(bits)
    chars = []
    for _ in range(n_chars):
        chars.append(ALPHABET[value % 94])
        value //= 94
    return "".join(reversed(chars))


def decode(s: str, n_bits: int) -> bitarray:
    """Decode a base-94 ASCII string back to exactly n_bits bits."""
    value = 0
    for c in s:
        if c in _A2I:
            value = value * 94 + _A2I[c]
    return int2ba(value, length=n_bits)


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
        _put(b, min(spd // 5, 15), 4)
        _put(b, d % 8, 3)


def _take_winds(b: bitarray, pos: int) -> tuple[list[tuple[int, int]], int]:
    result = []
    for _ in range(3):
        spd, pos = _take(b, pos, 4)
        d, pos = _take(b, pos, 3)
        result.append((spd * 5, d))
    return result, pos


# ── Period ────────────────────────────────────────────────────────────────────


class Period(BaseModel):
    """40 bits — one forecast period for any type/model."""

    BITS: ClassVar[int] = 40
    weathercode: int
    precip: int
    freeze_ft: int
    snow_in: int
    cloud_mid: int
    wind_500_mph: int
    wind_500_dir: int
    wind_600_mph: int
    wind_600_dir: int
    wind_700_mph: int
    wind_700_dir: int

    def to_bits(self) -> bitarray:
        b = bitarray()
        _put(b, _WMO2IDX.get(self.weathercode, 0), 5)
        _put(b, min(round(self.precip / 12.5), 7), 3)
        _put(b, min(self.freeze_ft // 1000, 15), 4)
        _put(b, min(self.snow_in, 15), 4)
        _put(b, min(round(self.cloud_mid / 12.5), 7), 3)
        _put_winds(
            b,
            (self.wind_500_mph, self.wind_500_dir),
            (self.wind_600_mph, self.wind_600_dir),
            (self.wind_700_mph, self.wind_700_dir),
        )
        assert len(b) == self.BITS
        return b

    @classmethod
    def from_bits(cls, b: bitarray, pos: int) -> tuple["Period", int]:
        wc, pos = _take(b, pos, 5)
        pr, pos = _take(b, pos, 3)
        fz, pos = _take(b, pos, 4)
        sn, pos = _take(b, pos, 4)
        cl, pos = _take(b, pos, 3)
        w, pos = _take_winds(b, pos)
        return cls(
            weathercode=WMO_CODES[wc] if wc < len(WMO_CODES) else 0,
            precip=round(pr * 12.5),
            freeze_ft=fz * 1000,
            snow_in=sn,
            cloud_mid=round(cl * 12.5),
            wind_500_mph=w[0][0],
            wind_500_dir=w[0][1],
            wind_600_mph=w[1][0],
            wind_600_dir=w[1][1],
            wind_700_mph=w[2][0],
            wind_700_dir=w[2][1],
        ), pos


# Maps encoded message length (chars) → exact bit count, one entry per distinct layout.
_CHARS_TO_BITS: dict[int, int] = {
    _n_chars(12 + n_periods * n_models * Period.BITS): 12 + n_periods * n_models * Period.BITS
    for n_periods, n_models in [(10, 2), (5, 3), (20, 1)]
}
# {94: 612, 124: 812}


# ── ForecastMessage ───────────────────────────────────────────────────────────


@dataclass
class ForecastMessage:
    """
    Encodes any forecast type to a variable-length base-94 ASCII string.

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
        return encode(self.to_bits())

    @staticmethod
    def decode(s: str) -> "ForecastMessage":
        n_bits = _CHARS_TO_BITS.get(len(s))
        if n_bits is None:
            raise ValueError(f"Unexpected message length: {len(s)} chars")
        b = decode(s, n_bits)
        t, pos = _take(b, 0, 3)
        month, pos = _take(b, pos, 4)
        day, pos = _take(b, pos, 5)

        if t not in range(5):
            raise ValueError(f"Unknown forecast type: {t}")
        ft = ForecastType(t)

        n_periods = {
            ForecastType.DAY10_DAILY_2M: 10,
            ForecastType.DAY5_DAILY_3M: 5,
            ForecastType.DAY1_HOURLY_1M: 20,
            ForecastType.DAY5_6H_1M: 20,
            ForecastType.DAY5_12H_2M: 10,
        }[ft]

        n_models = len(TYPE_MODELS[ft])
        all_periods: list[list[Any]] = [[] for _ in range(n_models)]

        for _ in range(n_periods):
            for m in range(n_models):
                p, pos = Period.from_bits(b, pos)
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
    sample = Period(
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
        day=19,
        periods=[[sample] * 10, [sample] * 10],
    )
    encoded = msg.encode()
    decoded = ForecastMessage.decode(encoded)

    print(f"Type: {decoded.forecast_type.name}")
    print(f"Encoded ({len(encoded)} chars): {encoded}")
    print(f"Start: {decoded.start_date}")
    for m_idx, m_name in enumerate(TYPE_MODELS[ForecastType.DAY10_DAILY_2M]):
        p = decoded.periods[m_idx][0]
        print(
            f"Day 1 {m_name}: wc={p.weathercode} precip={p.precip}% "
            f"freeze={p.freeze_ft}ft snow={p.snow_in}in cloud={p.cloud_mid}% "
            f"500={p.wind_500_mph}mph {CARDINALS[p.wind_500_dir]}"
        )
