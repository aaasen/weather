# Denali

Denali weather forecasts via Garmin inReach satellite messenger.

Send a message to `wx@email.laneaasen.com` from your inReach device. Include a forecast type keyword in the body (default: `10d`):

| Keyword | Forecast |
|---------|----------|
| `10d` | 10-day daily · ECMWF + GFS |
| `5d` | 5-day daily · ECMWF + GFS + ICON |
| `1d` / `today` / `now` | Today hourly · ECMWF |
| `6h` | 5-day 6-hourly · ECMWF |
| `12h` | 5-day 12-hourly · ECMWF + GFS |

The reply is 157 printable GSM characters. Decode it at the decoder page (`decoder/index.html`).

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
