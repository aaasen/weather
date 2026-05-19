# Satellite Weather

Weather forecasts via Garmin inReach satellite messenger.

The goal of this project is to provide better weather forecasts than the default inReach system. Forecasts are sourced from [Open-Meteo](https://open-meteo.com/). They are encoded with a custom binary encoding to maximize information density. Using this encoding, it is possible to get 10-day daily forecasts in a single message.

## Usage

Send a message to `wx@email.laneaasen.com` from your inReach device. Include a forecast type keyword in the body (default: `10d`):

| Keyword | Forecast |
|---------|----------|
| `10d` | 10-day daily · ECMWF + GFS |
| `5d` | 5-day daily · ECMWF + GFS + ICON |
| `1d` / `today` / `now` | Today hourly · ECMWF |
| `6h` | 5-day 6-hourly · ECMWF |
| `12h` | 5-day 12-hourly · ECMWF + GFS |

Copy the response into the decoder app at [weather.laneaasen.com](https://weather.laneaasen.com/). 

## Offline Usage

The decoder app is a Progressive Web App (PWA) that can be installed on your phone for offline use.

Open [weather.laneaasen.com](https://weather.laneaasen.com/) in your browser and tap the share button. Select "Add to Home Screen" to install the app on your phone.


## Architecture

- `server.py` — Flask app; serves the decoder page, receives inbound email webhooks, sends Garmin replies
- `forecast.py` — fetches Open-Meteo data and encodes it
- `encoding.py` — binary encoding (base-125 GSM alphabet, 157 chars)
- `decoder/index.html` — static offline decoder page (PWA), served at `/`

## Running locally

```bash
pip install -r requirements.txt
flask --app server run --port 8080
```

The server starts at `http://localhost:8080`. Open it in a browser to use the decoder.

To test the inbound webhook without a real inReach message, POST to `/inbound` with form fields matching what SendGrid delivers:

```bash
curl -X POST http://localhost:8080/inbound \
  -d 'from=you@example.com' \
  -d 'text=10d https://inreachlink.com/YOURTOKEN'
```

## Deploy

### Backend (Cloud Run)

Requires [Google Cloud CLI](https://cloud.google.com/sdk/docs/install) with a project configured.

```bash
gcloud run deploy denali-wx --source . --region us-west1 --allow-unauthenticated --platform managed
```

Or use the helper script:

```bash
./deploy.sh
```

The service listens on `POST /inbound` for SendGrid inbound parse webhooks and `GET /health`.

### Decoder page

The `decoder/` directory is a standalone PWA — no build step required. Deploy it to any static host, or open `decoder/index.html` directly in a browser.

To host on Firebase Hosting (or any static host), deploy the `decoder/` directory as the public root.
