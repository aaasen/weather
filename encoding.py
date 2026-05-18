"""
Binary forecast encoding using the GSM 03.38 printable alphabet.

Uses the 125 printable GSM 03.38 characters (all 128 minus LF, CR, ESC)
as a base-125 alphabet. 509 bits encodes in exactly 74 characters — just 1
more than the full 128-char GSM encoding (73 chars), with no control characters.

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

Full message: 9 + 10 × 50 = 509 bits → 74 GSM chars
"""

import math
import datetime
from typing import ClassVar

from bitarray import bitarray
from bitarray.util import ba2int, int2ba
from pydantic import BaseModel

# GSM 03.38 default alphabet minus LF (10), CR (13), ESC (27) — 125 printable chars.
SAFE_GSM = (
    "@£$¥èéùìòÇ"                              # GSM  0- 9
    "Øø"                                       # GSM 11-12
    "ÅåΔ_ΦΓΛΩΠΨΣΘΞ"                           # GSM 14-26
    "ÆæßÉ "                                    # GSM 28-32
    "!\"#¤%&'()*+,-./"                         # GSM 33-47
    "0123456789:;<=>?"                         # GSM 48-63
    "¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§"        # GSM 64-95
    "¿abcdefghijklmnopqrstuvwxyzäöñüà"        # GSM 96-127
)
assert len(SAFE_GSM) == 125
assert len(set(SAFE_GSM)) == 125
_SG2I = {c: i for i, c in enumerate(SAFE_GSM)}

_MSG_BITS  = 509  # 9 header + 10 × 50 day bits
_MSG_CHARS = math.ceil(_MSG_BITS * math.log(2) / math.log(125))  # = 74


def encode_gsm_safe(bits: bitarray) -> str:
    """Encode a bitarray as printable GSM chars using base-125 arithmetic."""
    value = ba2int(bits)
    chars = []
    for _ in range(_MSG_CHARS):
        chars.append(SAFE_GSM[value % 125])
        value //= 125
    return "".join(reversed(chars))


def decode_gsm_safe(s: str) -> bitarray:
    """Decode base-125 printable GSM chars back to a bitarray."""
    value = 0
    count = 0
    for c in s:
        if c in _SG2I:
            value = value * 125 + _SG2I[c]
            count += 1
            if count == _MSG_CHARS:
                break
    return int2ba(value, length=_MSG_BITS)


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
        return encode_gsm_safe(self.to_bits())

    @classmethod
    def decode(cls, s: str) -> "Forecast":
        return cls.from_bits(decode_gsm_safe(s))

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
