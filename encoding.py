"""
Binary forecast encoding — 157 printable GSM chars for all forecast types.

Uses 125 printable GSM 03.38 chars (all 128 minus LF, CR, ESC) as a base-125
alphabet. All messages encode to exactly 157 chars (covers 1092 bits, the
maximum needed by any type).

Common header (12 bits):
  3  type   — forecast type 0-4
  4  month  — 1-12
  5  day    — 1-31

Period types:
  Full    (50 bits) — daily, primary model
    5 wc  4 precip  8 freeze  5 snow  4 cloud  8 w700  8 w500  8 w450
  Sub     (45 bits) — sub-daily, primary model (no snow)
    5 wc  4 precip  8 freeze  4 cloud  8 w700  8 w500  8 w450
  Compact (33 bits) — additional models
    5 wc  4 precip  8 w700  8 w500  8 w450

Type layout (header + interleaved slots):
  0 (10d-daily-2m):  12 + 10×(Full+Compact)         =  842 bits
  1 (5d-daily-3m):   12 +  5×(Full+2×Compact)        =  592 bits
  2 (1d-hourly-1m):  12 + 24×Sub                     = 1092 bits  ← max
  3 (5d-6h-1m):      12 + 20×Sub                     =  912 bits
  4 (5d-12h-2m):     12 + 10×(Sub+Compact)           =  792 bits

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
    "ECMWF": "ecmwf_ifs04",
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
    """50 bits — daily primary model."""

    BITS: ClassVar[int] = 50
    weathercode: int
    precip: int  # 0-100 %
    freeze_ft: int
    snow_in: int
    cloud_mid: int  # 0-100 %
    wind_700_mph: int
    wind_700_dir: int
    wind_500_mph: int
    wind_500_dir: int
    wind_450_mph: int
    wind_450_dir: int

    def to_bits(self) -> bitarray:
        b = bitarray()
        _put(b, _WMO2IDX.get(self.weathercode, 0), 5)
        _put(b, min(self.precip // 10, 10), 4)
        _put(b, min(self.freeze_ft // 100, 255), 8)
        _put(b, min(self.snow_in, 31), 5)
        _put(b, min(self.cloud_mid // 10, 10), 4)
        _put_winds(
            b,
            (self.wind_700_mph, self.wind_700_dir),
            (self.wind_500_mph, self.wind_500_dir),
            (self.wind_450_mph, self.wind_450_dir),
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
            wind_700_mph=w[0][0],
            wind_700_dir=w[0][1],
            wind_500_mph=w[1][0],
            wind_500_dir=w[1][1],
            wind_450_mph=w[2][0],
            wind_450_dir=w[2][1],
        ), pos


class PeriodSub(BaseModel):
    """45 bits — sub-daily primary model (no snow)."""

    BITS: ClassVar[int] = 45
    weathercode: int
    precip: int
    freeze_ft: int
    cloud_mid: int
    wind_700_mph: int
    wind_700_dir: int
    wind_500_mph: int
    wind_500_dir: int
    wind_450_mph: int
    wind_450_dir: int

    def to_bits(self) -> bitarray:
        b = bitarray()
        _put(b, _WMO2IDX.get(self.weathercode, 0), 5)
        _put(b, min(self.precip // 10, 10), 4)
        _put(b, min(self.freeze_ft // 100, 255), 8)
        _put(b, min(self.cloud_mid // 10, 10), 4)
        _put_winds(
            b,
            (self.wind_700_mph, self.wind_700_dir),
            (self.wind_500_mph, self.wind_500_dir),
            (self.wind_450_mph, self.wind_450_dir),
        )
        assert len(b) == self.BITS
        return b

    @classmethod
    def from_bits(cls, b: bitarray, pos: int) -> tuple["PeriodSub", int]:
        wc, pos = _take(b, pos, 5)
        pr, pos = _take(b, pos, 4)
        fz, pos = _take(b, pos, 8)
        cl, pos = _take(b, pos, 4)
        w, pos = _take_winds(b, pos)
        return cls(
            weathercode=WMO_CODES[wc] if wc < len(WMO_CODES) else 0,
            precip=pr * 10,
            freeze_ft=fz * 100,
            cloud_mid=cl * 10,
            wind_700_mph=w[0][0],
            wind_700_dir=w[0][1],
            wind_500_mph=w[1][0],
            wind_500_dir=w[1][1],
            wind_450_mph=w[2][0],
            wind_450_dir=w[2][1],
        ), pos


class PeriodCompact(BaseModel):
    """33 bits — additional models (no freeze/snow/cloud)."""

    BITS: ClassVar[int] = 33
    weathercode: int
    precip: int
    wind_700_mph: int
    wind_700_dir: int
    wind_500_mph: int
    wind_500_dir: int
    wind_450_mph: int
    wind_450_dir: int

    def to_bits(self) -> bitarray:
        b = bitarray()
        _put(b, _WMO2IDX.get(self.weathercode, 0), 5)
        _put(b, min(self.precip // 10, 10), 4)
        _put_winds(
            b,
            (self.wind_700_mph, self.wind_700_dir),
            (self.wind_500_mph, self.wind_500_dir),
            (self.wind_450_mph, self.wind_450_dir),
        )
        assert len(b) == self.BITS
        return b

    @classmethod
    def from_bits(cls, b: bitarray, pos: int) -> tuple["PeriodCompact", int]:
        wc, pos = _take(b, pos, 5)
        pr, pos = _take(b, pos, 4)
        w, pos = _take_winds(b, pos)
        return cls(
            weathercode=WMO_CODES[wc] if wc < len(WMO_CODES) else 0,
            precip=pr * 10,
            wind_700_mph=w[0][0],
            wind_700_dir=w[0][1],
            wind_500_mph=w[1][0],
            wind_500_dir=w[1][1],
            wind_450_mph=w[2][0],
            wind_450_dir=w[2][1],
        ), pos


# Backward-compat alias
ForecastDay = PeriodFull


# ── ForecastMessage ───────────────────────────────────────────────────────────


@dataclass
class ForecastMessage:
    """
    Encodes any forecast type to 157 GSM chars.

    periods[0]  = primary model list (PeriodFull or PeriodSub)
    periods[1:] = additional model lists (PeriodCompact)

    Within each time slot, primary comes first then compacts, so the
    decoder can interleave models correctly.
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

        if ft in (ForecastType.DAY10_DAILY_2M, ForecastType.DAY5_DAILY_3M):
            PrimaryClass = PeriodFull
            n_periods = 10 if ft == ForecastType.DAY10_DAILY_2M else 5
        else:
            PrimaryClass = PeriodSub
            n_periods = {
                ForecastType.DAY1_HOURLY_1M: 24,
                ForecastType.DAY5_6H_1M: 20,
                ForecastType.DAY5_12H_2M: 10,
            }[ft]

        n_extra = len(TYPE_MODELS[ft]) - 1
        primary: list[Any] = []
        extras: list[list[Any]] = [[] for _ in range(n_extra)]

        for _ in range(n_periods):
            p, pos = PrimaryClass.from_bits(b, pos)
            primary.append(p)
            for m in range(n_extra):
                c, pos = PeriodCompact.from_bits(b, pos)
                extras[m].append(c)

        return ForecastMessage(type=t, month=month, day=day, periods=[primary] + extras)

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
        PeriodCompact,
        PeriodFull,
        PeriodSub,
    )

    sample_full = PeriodFull(
        weathercode=73,
        precip=100,
        freeze_ft=5500,
        snow_in=4,
        cloud_mid=80,
        wind_700_mph=10,
        wind_700_dir=4,
        wind_500_mph=30,
        wind_500_dir=4,
        wind_450_mph=25,
        wind_450_dir=4,
    )
    sample_compact = PeriodCompact(
        weathercode=73,
        precip=80,
        wind_700_mph=15,
        wind_700_dir=4,
        wind_500_mph=35,
        wind_500_dir=4,
        wind_450_mph=30,
        wind_450_dir=4,
    )

    msg = ForecastMessage(
        type=int(ForecastType.DAY10_DAILY_2M),
        month=5,
        day=18,
        periods=[[sample_full] * 10, [sample_compact] * 10],
    )
    encoded = msg.encode()
    decoded = ForecastMessage.decode(encoded)

    print(f"Type: {decoded.forecast_type.name}")
    print(f"Encoded ({len(encoded)} / 160 chars, {_MSG_BITS} bits): {encoded!r}")
    print(f"Start: {decoded.start_date}")
    p = decoded.periods[0][0]
    print(
        f"Day 1 ECMWF: wc={p.weathercode} precip={p.precip}% freeze={p.freeze_ft}ft "
        f"snow={p.snow_in}in cloud={p.cloud_mid}% "
        f"700={p.wind_700_mph}mph {CARDINALS[p.wind_700_dir]}"
    )
    c = decoded.periods[1][0]
    print(
        f"Day 1 GFS:   wc={c.weathercode} precip={c.precip}% "
        f"700={c.wind_700_mph}mph {CARDINALS[c.wind_700_dir]}"
    )
