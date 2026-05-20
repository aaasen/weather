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

The decoder app is a Progressive Web App (PWA) that can be installed on your phone for offline use. Open [weather.laneaasen.com](https://weather.laneaasen.com/) in your browser and tap the share button, then select "Add to Home Screen".

## Architecture

This is a pnpm monorepo with three packages:

- `packages/protocol` — shared TypeScript binary encoding/decoding used by both server and client
- `packages/server` — Hono/Node.js server; receives inbound email webhooks, fetches Open-Meteo forecasts, sends Garmin replies, and serves the decoder page
- `packages/client` — Vite PWA decoder; imports the protocol package to decode and render forecasts entirely in-browser

## Development

**Prerequisites:** Node.js 18+, pnpm (`npm install -g pnpm`)

Install dependencies:

```bash
pnpm install
```

### Build

Build all packages (protocol → client → server):

```bash
pnpm build
```

To build a single package:

```bash
pnpm --filter @weather/protocol build
pnpm --filter @weather/client build
pnpm --filter @weather/server build
```

### Run

Build and start the server:

```bash
pnpm start
```

The server starts at `http://localhost:8080`. Open it in a browser to use the decoder.

To use a different port:

```bash
PORT=3000 node packages/server/dist/index.js
```

### Tests

```bash
pnpm test
```

No automated tests exist yet. To manually verify the protocol, run a round-trip from the Node REPL:

```bash
node --input-type=module - << 'EOF'
import { messageToString, messageFromString } from './packages/protocol/dist/index.js';
const msg = { version: 1, location: 0, days: 3, resolution: 0, models_mask: 1, month: 5, day: 20, hour: 12,
  periods: [[0,0,0].map(() => ({ weathercode: 3, precip: 50, freeze_ft: 8000, snow_in: 2, cloud_mid: 75,
    wind_500_mph: 30, wind_500_dir: 2, wind_600_mph: 20, wind_600_dir: 2, wind_700_mph: 10, wind_700_dir: 2 }))] };
const s = messageToString(msg);
const d = messageFromString(s);
console.log(s, d.days === msg.days && d.periods[0][0].weathercode === 3 ? '✓' : '✗');
EOF
```

To test the inbound webhook without a real inReach message:

```bash
curl -X POST http://localhost:8080/inbound \
  -d 'from=you@example.com' \
  -d 'text=upper 10d daily ecmwf https://inreachlink.com/YOURTOKEN'
```

## Deploy

Requires [Google Cloud CLI](https://cloud.google.com/sdk/docs/install) with a project configured.

```bash
./deploy.sh
```

Or directly:

```bash
gcloud run deploy denali-wx --source . --region us-west1 --allow-unauthenticated --platform managed
```

The Dockerfile builds all packages from source and runs the server on `$PORT` (Cloud Run sets this automatically).
