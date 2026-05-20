import datetime

import requests

from encoding import (
    VERSION,
    RESOLUTION_HOURS,
    MODEL_BIT,
    ForecastMessage,
    Period,
)

OPENMETEO_MODELS: dict[str, str] = {
    "ECMWF": "ecmwf_ifs025",
    "GFS": "gfs_seamless",
    "ICON": "icon_seamless",
}

LOCATION_COORDS: dict[str, tuple[float, float, str]] = {
    "upper": (63.0692, -151.0070, "America/Anchorage"),
    "airstrip": (62.900, -151.093, "America/Anchorage"),
}

# resolution index → hours to request from API (None = use noon daily rows)
RESOLUTION_TARGET_HOURS: dict[int, list[int] | None] = {
    0: None,
    1: [0, 12],
    2: [0, 6, 12, 18],
    3: [0, 3, 6, 9, 12, 15, 18, 21],
    4: list(range(24)),
}

_RESOLUTION_LABEL_TO_IDX: dict[str, int] = {
    "daily": 0, "24h": 0,
    "12h": 1,
    "6h": 2,
    "3h": 3,
    "1h": 4,
}

_MODEL_NAME_TO_BIT: dict[str, int] = {
    "ecmwf": MODEL_BIT["ECMWF"], "euro": MODEL_BIT["ECMWF"],
    "gfs": MODEL_BIT["GFS"],
    "icon": MODEL_BIT["ICON"],
}

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


def _fetch_hourly(
    model_key: str, n_days: int, lat: float, lon: float, tz: str
) -> tuple[dict, list[str]]:
    pressure_vars = [
        f"{v}_{l}hPa" for v in _PRESSURE_VAR_NAMES for l in _PRESSURE_LEVELS
    ]
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": ",".join(_SURFACE_VARS + pressure_vars),
        "wind_speed_unit": "mph",
        "timezone": tz,
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


def _noon_rows(
    model_key: str, n_days: int, lat: float, lon: float, tz: str
) -> list[dict]:
    """One row per day at noon local time, with cumulative daily snow."""
    h, times = _fetch_hourly(model_key, n_days, lat, lon, tz)
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


def _hour_rows(
    model_key: str,
    n_days: int,
    target_hours: list[int],
    lat: float,
    lon: float,
    tz: str,
) -> list[dict]:
    """Rows at specific hours across n_days."""
    h, times = _fetch_hourly(model_key, n_days, lat, lon, tz)
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


# ── Row → Period ──────────────────────────────────────────────────────────────


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


# ── Request parser ────────────────────────────────────────────────────────────


def parse_request(body: str) -> dict:
    """Parse 'upper 10d daily ecmwf,gfs' into fetch_forecast kwargs."""
    words = body.lower().strip().split()

    location_idx = 0
    days = 10
    resolution_idx = 0
    models_mask = 1  # ECMWF default

    for word in words:
        if word == "upper":
            location_idx = 0
        elif word == "airstrip":
            location_idx = 1
        elif word.endswith("d") and word[:-1].isdigit():
            days = max(1, min(10, int(word[:-1])))
        elif word in _RESOLUTION_LABEL_TO_IDX:
            resolution_idx = _RESOLUTION_LABEL_TO_IDX[word]
        else:
            model_parts = word.split(",")
            if any(m in _MODEL_NAME_TO_BIT for m in model_parts):
                mask = 0
                for m in model_parts:
                    if m in _MODEL_NAME_TO_BIT:
                        mask |= 1 << _MODEL_NAME_TO_BIT[m]
                if mask:
                    models_mask = mask

    return {
        "location_idx": location_idx,
        "days": days,
        "resolution_idx": resolution_idx,
        "models_mask": models_mask,
    }


# ── Forecast fetch ────────────────────────────────────────────────────────────


def fetch_forecast(
    location_idx: int = 0,
    days: int = 10,
    resolution_idx: int = 0,
    models_mask: int = 1,
) -> str:
    location_name = list(LOCATION_COORDS.keys())[location_idx]
    lat, lon, tz = LOCATION_COORDS[location_name]

    model_keys = [
        key
        for key, bit in [("ECMWF", 0), ("GFS", 1), ("ICON", 2)]
        if models_mask & (1 << bit)
    ] or ["ECMWF"]

    target_hours = RESOLUTION_TARGET_HOURS[resolution_idx]
    daily = resolution_idx == 0

    if daily:
        rows_per_model = [_noon_rows(m, days, lat, lon, tz) for m in model_keys]
    else:
        rows_per_model = [_hour_rows(m, days, target_hours, lat, lon, tz) for m in model_keys]

    first_time = rows_per_model[0][0]["time"]
    start_date = datetime.date.fromisoformat(first_time[:10])
    start_hour = int(first_time[11:13])

    return ForecastMessage(
        version=VERSION,
        location=location_idx,
        days=days,
        resolution=resolution_idx,
        models_mask=models_mask,
        month=start_date.month,
        day=start_date.day,
        hour=start_hour,
        periods=[[_to_full(r, daily=daily) for r in rows] for rows in rows_per_model],
    ).encode()


# ── __main__ ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from encoding import CARDINALS, LOCATIONS, RESOLUTION_LABEL, models_from_mask

    test_requests = [
        "upper 10d daily ecmwf",
        "upper 5d 6h ecmwf,gfs",
        "airstrip 3d 12h ecmwf,gfs",
    ]
    for req_str in test_requests:
        print(f"\n{'=' * 60}")
        print(f"Request: {req_str!r}")
        params = parse_request(req_str)
        encoded = fetch_forecast(**params)
        decoded = ForecastMessage.decode(encoded)
        loc = LOCATIONS[decoded.location]
        res = RESOLUTION_LABEL[decoded.resolution]
        mods = models_from_mask(decoded.models_mask)
        print(f"Encoded ({len(encoded)} chars): {encoded}")
        print(f"Location: {loc}, Days: {decoded.days}, Res: {res}, Models: {mods}")
        print(f"Start: {decoded.start_datetime}")
        for m_idx, m_name in enumerate(mods):
            p = decoded.periods[m_idx][0]
            print(
                f"  {m_name} period 0: wc={p.weathercode} precip={p.precip}% "
                f"freeze={p.freeze_ft}ft snow={p.snow_in}in cloud={p.cloud_mid}% "
                f"700={p.wind_700_mph}mph {CARDINALS[p.wind_700_dir]}"
            )
