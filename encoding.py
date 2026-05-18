"""
Binary forecast encoding using a printable-ASCII 6-bit alphabet.

Each character carries 6 bits, so 85 characters → 510 bits (≥ 509 needed).
A 10-day forecast uses 509 bits → 85 characters (1 bit of padding).

Alphabet: ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/
(standard Base64 characters — all printable, no control chars, safe to copy/paste)

Per-day bit layout (50 bits):
  5  weathercode  — index into WMO_CODES (28 used codes)
  4  precip       — precipitation probability, 0-10 (×10 = %)
  8  freeze_ft    — freezing level, 0-255 (×100 = feet)
  5  snow_in      — daily snow accumulation, 0-31 inches
  4  cloud_mid    — mid-level cloud cover, 0-10 (×10 = %)
  5  wind_700_mph — 700 hPa wind speed, 0-31 (×5 = mph)
  3  wind_700_dir — 700 hPa direction, 0-7 (index into CARDINALS)
  5  wind_500_mph
  3  wind_500_dir
  5  wind_450_mph
  3  wind_450_dir
 --
 50  total per day

Header (9 bits):
  4  month  — 1-12
  5  day    — 1-31

Full message: 9 + 10 × 50 = 509 bits → 85 chars
"""

import datetime
from typing import ClassVar

from bitarray import bitarray
from bitarray.util import ba2int, int2ba
from pydantic import BaseModel

# Printable-ASCII 6-bit alphabet — 64 unique characters, no control chars.
SAFE64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
_S2I = {c: i for i, c in enumerate(SAFE64)}


def encode_safe(bits: bitarray) -> str:
    """Pack bits into printable ASCII (6 bits each). Pads with zeros to multiple of 6."""
    pad = (6 - len(bits) % 6) % 6
    b = bits + bitarray(pad)
    return "".join(SAFE64[ba2int(b[i:i + 6])] for i in range(0, len(b), 6))


def decode_safe(s: str) -> bitarray:
    """Unpack printable ASCII back into a bitarray (skips unknown chars)."""
    b = bitarray()
    for c in s:
        if c in _S2I:
            b.extend(int2ba(_S2I[c], length=6))
    return b


# WMO weather codes used by Open-Meteo (28 values → 5 bits)
WMO_CODES: list[int] = [
    0, 1, 2, 3, 45, 48, 51, 53, 55, 56, 57,
    61, 63, 65, 66, 67, 71, 73, 75, 77,
    80, 81, 82, 85, 86, 95, 96, 99,
]
_WMO2IDX = {c: i for i, c in enumerate(WMO_CODES)}

# 8-point cardinal directions, index 0-7
CARDINALS: list[str] = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
CARDINAL_TO_IDX: dict[str, int] = {c: i for i, c in enumerate(CARDINALS)}


def _put(b: bitarray, value: int, n: int) -> None:
    b.extend(int2ba(value, n))


def _take(b: bitarray, pos: int, n: int) -> tuple[int, int]:
    return ba2int(b[pos:pos + n]), pos + n


class ForecastDay(BaseModel):
    """One day of forecast data — 50 bits."""
    BITS: ClassVar[int] = 50

    weathercode:  int  # raw WMO code
    precip:       int  # precipitation probability 0-100 (%)
    freeze_ft:    int  # freezing level in feet
    snow_in:      int  # daily snow in inches
    cloud_mid:    int  # mid-level cloud cover 0-100 (%)
    wind_700_mph: int  # 700 hPa (~10k ft) wind speed mph
    wind_700_dir: int  # 700 hPa direction index 0-7
    wind_500_mph: int  # 500 hPa (~18k ft) wind speed mph
    wind_500_dir: int
    wind_450_mph: int  # 450 hPa (~20k ft, summit) wind speed mph
    wind_450_dir: int

    def to_bits(self) -> bitarray:
        b = bitarray()
        _put(b, _WMO2IDX.get(self.weathercode, 0),  5)
        _put(b, min(self.precip    // 10, 10),       4)
        _put(b, min(self.freeze_ft // 100, 255),     8)
        _put(b, min(self.snow_in, 31),               5)
        _put(b, min(self.cloud_mid // 10, 10),       4)
        for spd, d in [
            (self.wind_700_mph, self.wind_700_dir),
            (self.wind_500_mph, self.wind_500_dir),
            (self.wind_450_mph, self.wind_450_dir),
        ]:
            _put(b, min(spd // 5, 31), 5)
            _put(b, d % 8,             3)
        assert len(b) == self.BITS
        return b

    @classmethod
    def from_bits(cls, b: bitarray) -> "ForecastDay":
        pos = 0
        wc_idx,     pos = _take(b, pos, 5)
        precip_raw, pos = _take(b, pos, 4)
        freeze_raw, pos = _take(b, pos, 8)
        snow,       pos = _take(b, pos, 5)
        cloud_raw,  pos = _take(b, pos, 4)
        spd700,     pos = _take(b, pos, 5)
        dir700,     pos = _take(b, pos, 3)
        spd500,     pos = _take(b, pos, 5)
        dir500,     pos = _take(b, pos, 3)
        spd450,     pos = _take(b, pos, 5)
        dir450,     pos = _take(b, pos, 3)
        return cls(
            weathercode=WMO_CODES[wc_idx] if wc_idx < len(WMO_CODES) else 0,
            precip=precip_raw * 10,
            freeze_ft=freeze_raw * 100,
            snow_in=snow,
            cloud_mid=cloud_raw * 10,
            wind_700_mph=spd700 * 5,
            wind_700_dir=dir700,
            wind_500_mph=spd500 * 5,
            wind_500_dir=dir500,
            wind_450_mph=spd450 * 5,
            wind_450_dir=dir450,
        )


class Forecast(BaseModel):
    """Full forecast message — 9-bit header + N × 50 bits per day."""
    month: int
    day:   int
    days:  list[ForecastDay]

    def to_bits(self) -> bitarray:
        b = bitarray()
        _put(b, self.month, 4)
        _put(b, self.day,   5)
        for d in self.days:
            b.extend(d.to_bits())
        return b

    @classmethod
    def from_bits(cls, b: bitarray) -> "Forecast":
        month, pos = _take(b, 0, 4)
        day,   pos = _take(b, pos, 5)
        days = []
        while pos + ForecastDay.BITS <= len(b):
            days.append(ForecastDay.from_bits(b[pos:pos + ForecastDay.BITS]))
            pos += ForecastDay.BITS
        return cls(month=month, day=day, days=days)

    def encode(self) -> str:
        return encode_safe(self.to_bits())

    @classmethod
    def decode(cls, s: str) -> "Forecast":
        return cls.from_bits(decode_safe(s))

    @property
    def start_date(self) -> datetime.date:
        year = datetime.date.today().year
        d = datetime.date(year, self.month, self.day)
        if (datetime.date.today() - d).days > 180:
            d = datetime.date(year + 1, self.month, self.day)
        return d


if __name__ == "__main__":
    sample = ForecastDay(
        weathercode=73, precip=100, freeze_ft=5500, snow_in=4, cloud_mid=80,
        wind_700_mph=10, wind_700_dir=4,
        wind_500_mph=30, wind_500_dir=4,
        wind_450_mph=25, wind_450_dir=4,
    )
    forecast = Forecast(month=5, day=18, days=[sample] * 10)
    encoded = forecast.encode()
    decoded = Forecast.decode(encoded)

    bits_used = 9 + len(forecast.days) * ForecastDay.BITS
    print(f"Bits: {bits_used}  →  GSM chars: {len(encoded)} / 160")
    print(f"Encoded: {encoded!r}")
    print(f"Round-trip match: {forecast == decoded}")
    d0 = decoded.days[0]
    print(f"Day 1: wc={d0.weathercode} precip={d0.precip}% freeze={d0.freeze_ft}ft "
          f"snow={d0.snow_in}in cloud={d0.cloud_mid}% "
          f"700={d0.wind_700_mph}mph {CARDINALS[d0.wind_700_dir]} "
          f"500={d0.wind_500_mph}mph {CARDINALS[d0.wind_500_dir]} "
          f"450={d0.wind_450_mph}mph {CARDINALS[d0.wind_450_dir]}")
