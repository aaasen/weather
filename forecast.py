import requests

FORECAST_LAT = 63.0692
FORECAST_LON = -151.0070
FORECAST_ELEV = 6190
FORECAST_TZ = "America/Anchorage"
FORECAST_DAYS = 5

_SURFACE_VARS = [
    "wind_speed_10m",
    "wind_direction_10m",
    "wind_gusts_10m",
    "precipitation_probability",
    "weathercode",
    "cloudcover_mid",
    "freezing_level_height",
]
_PRESSURE_LEVELS = [500, 450, 700]
_PRESSURE_VAR_NAMES = ["temperature", "wind_speed", "wind_direction"]
_CARDINALS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]


def _deg_to_cardinal(deg: float | None) -> str:
    if deg is None:
        return ""
    return _CARDINALS[round(deg / 45) % 8]


def _round5(v: float | None) -> int:
    return round((v or 0) / 5) * 5


def _round10(v: float | None) -> int:
    return round((v or 0) / 10) * 10


def fetch_noon_data() -> tuple[list[dict], list[str]]:
    """Return (noon_rows, times) where noon_rows has one entry per day."""
    pressure_vars = [
        f"{var}_{lvl}hPa"
        for var in _PRESSURE_VAR_NAMES
        for lvl in _PRESSURE_LEVELS
    ]
    params = {
        "latitude": FORECAST_LAT,
        "longitude": FORECAST_LON,
        "elevation": FORECAST_ELEV,
        "hourly": ",".join(_SURFACE_VARS + pressure_vars),
        "wind_speed_unit": "mph",
        "timezone": FORECAST_TZ,
        "forecast_days": FORECAST_DAYS,
        "models": "best_match",
    }
    resp = requests.get("https://api.open-meteo.com/v1/forecast", params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    h = data["hourly"]
    times = h["time"]

    rows = []
    for i, t in enumerate(times):
        if not t.endswith("T12:00"):
            continue
        fz_m = h["freezing_level_height"][i]
        rows.append({
            "day": len(rows) + 1,
            "time": t,
            "wind_speed": h["wind_speed_10m"][i],
            "wind_dir": h["wind_direction_10m"][i],
            "gust": h["wind_gusts_10m"][i],
            "precip": h["precipitation_probability"][i],
            "weathercode": h["weathercode"][i],
            "cloudcover_mid": h["cloudcover_mid"][i],
            "freezing_level_m": fz_m,
            "freezing_level_km": round(fz_m / 1000, 1) if fz_m else None,
            **{f"{var}_{lvl}hPa": h[f"{var}_{lvl}hPa"][i]
               for var in _PRESSURE_VAR_NAMES for lvl in _PRESSURE_LEVELS},
        })
        if len(rows) == FORECAST_DAYS:
            break
    return rows, times


def fetch_forecast() -> str:
    """Fetch 5-day Denali forecast and encode as a compact string ≤160 chars."""
    rows, _ = fetch_noon_data()
    parts = []
    for r in rows:
        ws = _round5(r["wind_speed"])
        gust = _round5(r["gust"])
        card = _deg_to_cardinal(r["wind_dir"])
        precip = _round10(r["precip"])
        wc = r["weathercode"] or 0
        fz_km = r["freezing_level_km"]

        entry = f"D{r['day']}:{ws}{card}"
        if gust and gust != ws:
            entry += f" G{gust}"
        if precip:
            entry += f" {precip}%"
        if wc:
            entry += f" wc{int(wc)}"
        if fz_km:
            entry += f" fz{fz_km}k"
        parts.append(entry)

    return " ".join(parts)


if __name__ == "__main__":
    rows, _ = fetch_noon_data()

    print("=== Raw Noon Values (noon Anchorage time) ===")
    for r in rows:
        print(f"\nDay {r['day']}  {r['time']}")
        print(f"  Wind:    {r['wind_speed']:.1f} mph  dir={r['wind_dir']}°  gust={r['gust']:.1f} mph")
        print(f"  Precip:  {r['precip']}%")
        print(f"  WxCode:  {int(r['weathercode'])}")
        print(f"  Cloud mid: {r['cloudcover_mid']}%")
        print(f"  Freeze:  {r['freezing_level_m']} m  ({r['freezing_level_km']} km)")
        for lvl in _PRESSURE_LEVELS:
            t = r.get(f"temperature_{lvl}hPa")
            ws = r.get(f"wind_speed_{lvl}hPa")
            wd = r.get(f"wind_direction_{lvl}hPa")
            print(f"  {lvl}hPa:   {t}°C  {ws} mph  {wd}°")

    encoded = fetch_forecast()
    print("\n=== Encoded Forecast ===")
    print(encoded)
    print(f"Length: {len(encoded)} / 160 chars")
