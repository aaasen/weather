"""
Binary forecast encoding using 94 printable ASCII characters 33–126 (! through ~) as a base-94 alphabet.

Header (32 bits):
  7  version    — protocol version; decoder rejects mismatches
  1  location   — 0=upper mountain, 1=airstrip
  4  days       — 0–9 stored → 1–10 forecast days
  3  resolution — 0=daily, 1=12h, 2=6h, 3=3h, 4=1h
  3  models     — bitmask: bit0=ECMWF, bit1=GFS, bit2=ICON
  4  month      — 1–12
  5  day        — 1–31
  5  hour       — 0–23, start hour of first period

Period (40 bits):
  5  wc      WMO weather code; index into 28-value WMO_CODES table
  3  precip  precipitation probability 0–100 %, stored in 12.5 % steps (0–7)
  4  freeze  freezing level 0–15,000 ft, stored in 1,000 ft steps (0–15)
  4  snow    snowfall 0–15; unit: 1"/step daily, 0.1"/step sub-daily
  3  cloud   mid-level cloud cover 0–100 %, stored in 12.5 % steps (0–7)
  7  w500    500 hPa (~18k ft) wind: 4 bits speed (0–75 mph, 5 mph steps) + 3 bits direction (8 cardinals)
  7  w600    600 hPa (~14k ft) wind: same encoding
  7  w700    700 hPa (~10k ft) wind: same encoding

Total bits = 32 + n_periods × n_models × 40
  where n_periods = days × (24 / resolution_hours)  [1 for daily]
  and   n_models  = popcount(models bitmask)
"""

import datetime
import math
from dataclasses import dataclass
from typing import Any, ClassVar

from bitarray import bitarray
from bitarray.util import ba2int, int2ba
from pydantic import BaseModel

# ── Alphabet ──────────────────────────────────────────────────────────────────

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


# ── Protocol constants ────────────────────────────────────────────────────────

VERSION = 1
HEADER_BITS = 32
PERIOD_BITS = 40

LOCATIONS: list[str] = ["upper", "airstrip"]

# resolution index → hours between periods
RESOLUTION_HOURS: dict[int, int] = {0: 24, 1: 12, 2: 6, 3: 3, 4: 1}
RESOLUTION_LABEL: dict[int, str] = {0: "daily", 1: "12h", 2: "6h", 3: "3h", 4: "1h"}

# model name → bit position in the 3-bit bitmask
MODEL_BIT: dict[str, int] = {"ECMWF": 0, "GFS": 1, "ICON": 2}
MODEL_NAMES: list[str] = ["ECMWF", "GFS", "ICON"]  # index = bit position


def models_from_mask(mask: int) -> list[str]:
    return [name for name in MODEL_NAMES if mask & (1 << MODEL_BIT[name])]


def mask_from_models(models: list[str]) -> int:
    return sum(1 << MODEL_BIT[m.upper()] for m in models if m.upper() in MODEL_BIT)


# ── Shared constants ──────────────────────────────────────────────────────────

WMO_CODES: list[int] = [
    0, 1, 2, 3, 45, 48, 51, 53, 55, 56, 57,
    61, 63, 65, 66, 67, 71, 73, 75, 77, 80,
    81, 82, 85, 86, 95, 96, 99,
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
    """40 bits — one forecast period."""

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


# ── Char → bit count ──────────────────────────────────────────────────────────


def _bits_from_chars(n_chars: int) -> int | None:
    """Return the unique valid n_bits for a given encoded char count, or None.

    Valid n_bits = HEADER_BITS + k × PERIOD_BITS for k ≥ 0.
    Since PERIOD_BITS (40) > log2(94) (~6.55), the char→bit mapping is injective.
    """
    for k in range(1000):
        n_bits = HEADER_BITS + k * PERIOD_BITS
        nc = _n_chars(n_bits)
        if nc == n_chars:
            return n_bits
        if nc > n_chars:
            break
    return None


# ── ForecastMessage ───────────────────────────────────────────────────────────


@dataclass
class ForecastMessage:
    """Encodes a configurable forecast to a variable-length base-94 ASCII string."""

    version: int
    location: int      # index into LOCATIONS
    days: int          # 1–10
    resolution: int    # index into RESOLUTION_HOURS
    models_mask: int   # 3-bit bitmask: bit0=ECMWF, bit1=GFS, bit2=ICON
    month: int         # 1–12
    day: int           # 1–31
    hour: int          # 0–23, start hour of first period
    periods: list[list[Any]]  # [model_idx][period_idx]

    def to_bits(self) -> bitarray:
        b = bitarray()
        _put(b, self.version, 7)
        _put(b, self.location, 1)
        _put(b, self.days - 1, 4)   # store 0-indexed (0–9 → days 1–10)
        _put(b, self.resolution, 3)
        _put(b, self.models_mask, 3)
        _put(b, self.month, 4)
        _put(b, self.day, 5)
        _put(b, self.hour, 5)
        for i in range(len(self.periods[0])):
            for model_periods in self.periods:
                b.extend(model_periods[i].to_bits())
        return b

    def encode(self) -> str:
        return encode(self.to_bits())

    @staticmethod
    def decode(s: str) -> "ForecastMessage":
        n_bits = _bits_from_chars(len(s))
        if n_bits is None:
            raise ValueError(f"Unexpected message length: {len(s)} chars")
        b = decode(s, n_bits)
        pos = 0

        version, pos = _take(b, pos, 7)
        location, pos = _take(b, pos, 1)
        days_raw, pos = _take(b, pos, 4)
        days = days_raw + 1
        resolution, pos = _take(b, pos, 3)
        models_mask, pos = _take(b, pos, 3)
        month, pos = _take(b, pos, 4)
        day, pos = _take(b, pos, 5)
        hour, pos = _take(b, pos, 5)

        if version != VERSION:
            raise ValueError(f"Version mismatch: encoded v{version}, expected v{VERSION}")

        res_hours = RESOLUTION_HOURS.get(resolution, 24)
        periods_per_day = 1 if res_hours >= 24 else 24 // res_hours
        n_periods = days * periods_per_day
        n_models = bin(models_mask).count("1")

        all_periods: list[list[Any]] = [[] for _ in range(n_models)]
        for _ in range(n_periods):
            for m in range(n_models):
                p, pos = Period.from_bits(b, pos)
                all_periods[m].append(p)

        return ForecastMessage(
            version=version,
            location=location,
            days=days,
            resolution=resolution,
            models_mask=models_mask,
            month=month,
            day=day,
            hour=hour,
            periods=all_periods,
        )

    @property
    def start_datetime(self) -> datetime.datetime:
        year = datetime.date.today().year
        d = datetime.datetime(year, self.month, self.day, self.hour)
        if (datetime.datetime.now() - d) > datetime.timedelta(days=180):
            d = d.replace(year=year + 1)
        return d


if __name__ == "__main__":
    sample = Period(
        weathercode=73,
        precip=75,
        freeze_ft=6000,
        snow_in=4,
        cloud_mid=75,
        wind_500_mph=30,
        wind_500_dir=4,
        wind_600_mph=25,
        wind_600_dir=4,
        wind_700_mph=15,
        wind_700_dir=4,
    )
    msg = ForecastMessage(
        version=VERSION,
        location=0,
        days=10,
        resolution=0,
        models_mask=0b011,  # ECMWF + GFS
        month=5,
        day=20,
        hour=12,
        periods=[[sample] * 10, [sample] * 10],
    )
    encoded = msg.encode()
    decoded = ForecastMessage.decode(encoded)
    print(f"Version: {decoded.version}")
    print(f"Location: {LOCATIONS[decoded.location]}")
    print(f"Days: {decoded.days}, Resolution: {RESOLUTION_LABEL[decoded.resolution]}")
    print(f"Models: {models_from_mask(decoded.models_mask)}")
    print(f"Encoded ({len(encoded)} chars): {encoded}")
    p0 = decoded.periods[0][0]
    print(
        f"Period 0 ECMWF: wc={p0.weathercode} precip={p0.precip}% "
        f"freeze={p0.freeze_ft}ft snow={p0.snow_in}in 700={p0.wind_700_mph}mph {CARDINALS[p0.wind_700_dir]}"
    )
