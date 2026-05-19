import datetime

import requests

from encoding import (
    OPENMETEO_MODELS,
    TYPE_KEYWORDS,
    TYPE_MODELS,
    ForecastMessage,
    ForecastType,
    Period,
)

FORECAST_LAT = 63.0692
FORECAST_LON = -151.0070
FORECAST_TZ = "America/Anchorage"

_SURFACE_VARS = [
    "wind_speed_10m",
    "wind_direction_10m",
    "wind_gusts_10m",
    "precipitation_probability",
    "weather_code",
    "cloud_cover_mid",
    "freezing_level_height",
    "snowfall",
]
_PRESSURE_LEVELS = [500, 600, 700]
_PRESSURE_VAR_NAMES = ["temperature", "wind_speed", "wind_direction"]


def _deg_to_dir_idx(deg: float | None) -> int:
    if deg is None:
        return 0
    return round(deg / 45) % 8


def _round5(v: float | None) -> int:
    return round((v or 0) / 5) * 5


# ── API fetch helpers ─────────────────────────────────────────────────────────


def _fetch_hourly(model_key: str, n_days: int) -> tuple[dict, list[str]]:
    """Fetch raw hourly data for one model. Returns (hourly_vars, times)."""
    pressure_vars = [
        f"{v}_{l}hPa" for v in _PRESSURE_VAR_NAMES for l in _PRESSURE_LEVELS
    ]

    params = {
        "latitude": FORECAST_LAT,
        "longitude": FORECAST_LON,
        "hourly": ",".join(_SURFACE_VARS + pressure_vars),
        "wind_speed_unit": "mph",
        "timezone": FORECAST_TZ,
        "forecast_days": n_days,
        "models": OPENMETEO_MODELS[model_key],
    }
    resp = requests.get(
        "https://api.open-meteo.com/v1/forecast", params=params, timeout=15
    )
    resp.raise_for_status()
    h = resp.json()["hourly"]
    return h, h["time"]


def _build_row(h: dict, times: list[str], idx: int, snow_cm: float = 0.0) -> dict:
    row: dict = {
        "time": times[idx],
        "precip": h["precipitation_probability"][idx],
        "weathercode": h["weather_code"][idx],
        "cloudcover_mid": h["cloud_cover_mid"][idx],
        "freezing_level_m": h["freezing_level_height"][idx],
        "snow_cm": snow_cm,
    }
    for v in _PRESSURE_VAR_NAMES:
        for l in _PRESSURE_LEVELS:
            row[f"{v}_{l}hPa"] = h[f"{v}_{l}hPa"][idx]
    return row


def _noon_rows(model_key: str, n_days: int) -> list[dict]:
    """One row per day at noon local time, with cumulative daily snow."""
    h, times = _fetch_hourly(model_key, n_days)

    snow_arr = h.get("snowfall", [])
    daily_snow: dict[str, float] = {}
    for i, t in enumerate(times):
        date = t[:10]
        daily_snow[date] = daily_snow.get(date, 0.0) + (snow_arr[i] or 0.0)

    rows = []
    for i, t in enumerate(times):
        if t.endswith("T12:00") and len(rows) < n_days:
            rows.append(_build_row(h, times, i, round(daily_snow.get(t[:10], 0.0), 1)))
    return rows


def _hour_rows(model_key: str, n_days: int, target_hours: list[int]) -> list[dict]:
    """Rows at specific hours across n_days."""
    h, times = _fetch_hourly(model_key, n_days)
    snow_arr = h.get("snowfall", [])
    n_total = n_days * len(target_hours)
    rows = []
    for i, t in enumerate(times):
        hour = int(t[11:13])
        if hour in target_hours:
            rows.append(_build_row(h, times, i, snow_arr[i] or 0.0 if snow_arr else 0.0))
            if len(rows) == n_total:
                break
    return rows


# ── Row → period converters ───────────────────────────────────────────────────


def _to_full(r: dict, daily: bool = True) -> Period:
    fz_m = r.get("freezing_level_m") or 0
    snow_cm = r.get("snow_cm") or 0
    snow_in = round(snow_cm / 2.54) if daily else round(snow_cm / 0.254)
    return Period(
        weathercode=int(r.get("weathercode") or 0),
        precip=int(r.get("precip") or 0),
        freeze_ft=round(fz_m * 3.28084 / 1000) * 1000,
        snow_in=min(snow_in, 15),
        cloud_mid=int(r.get("cloudcover_mid") or 0),
        wind_700_mph=_round5(r.get("wind_speed_700hPa")),
        wind_700_dir=_deg_to_dir_idx(r.get("wind_direction_700hPa")),
        wind_500_mph=_round5(r.get("wind_speed_500hPa")),
        wind_500_dir=_deg_to_dir_idx(r.get("wind_direction_500hPa")),
        wind_600_mph=_round5(r.get("wind_speed_600hPa")),
        wind_600_dir=_deg_to_dir_idx(r.get("wind_direction_600hPa")),
    )


def _make_message(
    ft: ForecastType, rows_per_model: list[list[dict]], daily: bool
) -> str:
    start = datetime.date.fromisoformat(rows_per_model[0][0]["time"][:10])
    return ForecastMessage(
        type=int(ft),
        month=start.month,
        day=start.day,
        periods=[[_to_full(r, daily=daily) for r in rows] for rows in rows_per_model],
    ).encode()


# ── Per-type fetch functions ──────────────────────────────────────────────────


def fetch_type0() -> str:
    """10-day daily, 2 models (ECMWF + GFS)."""
    models = TYPE_MODELS[ForecastType.DAY10_DAILY_2M]
    return _make_message(
        ForecastType.DAY10_DAILY_2M,
        [_noon_rows(m, 10) for m in models],
        daily=True,
    )


def fetch_type1() -> str:
    """5-day daily, 4 models."""
    models = TYPE_MODELS[ForecastType.DAY5_DAILY_3M]
    return _make_message(
        ForecastType.DAY5_DAILY_3M,
        [_noon_rows(m, 5) for m in models],
        daily=True,
    )


def fetch_type2() -> str:
    """1-day hourly, 1 model (ECMWF)."""
    models = TYPE_MODELS[ForecastType.DAY1_HOURLY_1M]
    return _make_message(
        ForecastType.DAY1_HOURLY_1M,
        [_hour_rows(models[0], 1, list(range(20)))],
        daily=False,
    )


def fetch_type3() -> str:
    """5-day 6-hourly, 1 model (ECMWF)."""
    models = TYPE_MODELS[ForecastType.DAY5_6H_1M]
    return _make_message(
        ForecastType.DAY5_6H_1M,
        [_hour_rows(models[0], 5, [0, 6, 12, 18])],
        daily=False,
    )


def fetch_type4() -> str:
    """5-day 12-hourly, 2 models (ECMWF + GFS)."""
    models = TYPE_MODELS[ForecastType.DAY5_12H_2M]
    return _make_message(
        ForecastType.DAY5_12H_2M,
        [_hour_rows(m, 5, [0, 12]) for m in models],
        daily=False,
    )


_FETCH_FN = {
    ForecastType.DAY10_DAILY_2M: fetch_type0,
    ForecastType.DAY5_DAILY_3M: fetch_type1,
    ForecastType.DAY1_HOURLY_1M: fetch_type2,
    ForecastType.DAY5_6H_1M: fetch_type3,
    ForecastType.DAY5_12H_2M: fetch_type4,
}


def parse_keyword(body: str) -> str:
    """Return the first recognised type keyword from a message body."""
    for word in body.lower().split():
        if word in TYPE_KEYWORDS:
            return word
    return "10d"


def fetch_forecast(keyword: str = "10d") -> str:
    """Fetch and encode a forecast for the given type keyword."""
    ft = TYPE_KEYWORDS.get(keyword.lower().strip(), ForecastType.DAY10_DAILY_2M)
    return _FETCH_FN[ft]()


# ── __main__ ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from encoding import _MSG_CHARS, CARDINALS, TYPE_LABEL, ForecastMessage

    for keyword, ft in [
        ("10d", ForecastType.DAY10_DAILY_2M),
        ("5d", ForecastType.DAY5_DAILY_3M),
        ("1d", ForecastType.DAY1_HOURLY_1M),
        ("6h", ForecastType.DAY5_6H_1M),
        ("12h", ForecastType.DAY5_12H_2M),
    ]:
        print(f"\n{'=' * 60}")
        print(f"Type {int(ft)}: {TYPE_LABEL[ft]}  (keyword: {keyword!r})")
        encoded = fetch_forecast(keyword)
        decoded = ForecastMessage.decode(encoded)
        models = TYPE_MODELS[ft]
        print(f"Encoded ({len(encoded)}/{_MSG_CHARS} chars): {encoded}")
        print(f"Start date: {decoded.start_date}  periods: {len(decoded.periods[0])}")
        for m_idx, m_name in enumerate(models):
            p0 = decoded.periods[m_idx][0]
            if hasattr(p0, "snow_in"):
                print(
                    f"  {m_name} period 0: wc={p0.weathercode} precip={p0.precip}% "
                    f"freeze={p0.freeze_ft}ft snow={p0.snow_in}in cloud={p0.cloud_mid}% "
                    f"700={p0.wind_700_mph}mph {CARDINALS[p0.wind_700_dir]}"
                )
            elif hasattr(p0, "cloud_mid"):
                print(
                    f"  {m_name} period 0: wc={p0.weathercode} precip={p0.precip}% "
                    f"freeze={p0.freeze_ft}ft cloud={p0.cloud_mid}% "
                    f"700={p0.wind_700_mph}mph {CARDINALS[p0.wind_700_dir]}"
                )
            else:
                print(
                    f"  {m_name} period 0: wc={p0.weathercode} precip={p0.precip}% "
                    f"700={p0.wind_700_mph}mph {CARDINALS[p0.wind_700_dir]}"
                )
