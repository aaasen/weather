import { VERSION, HEADER_BITS, PERIOD_BITS, RESOLUTION_HOURS } from "./constants.js";
import { putInt, takeInt } from "./bits.js";
import { encode, decode, bitsFromChars } from "./codec.js";
import { type Period, periodToBits, periodFromBits } from "./period.js";

export interface ForecastMessage {
  version: number;
  location: number;
  days: number;
  resolution: number;
  models_mask: number;
  month: number;
  day: number;
  hour: number;
  periods: Period[][];
}

export function messageToString(msg: ForecastMessage): string {
  const bits: number[] = [];
  putInt(bits, msg.version, 7);
  putInt(bits, msg.location, 1);
  putInt(bits, msg.days - 1, 4);
  putInt(bits, msg.resolution, 3);
  putInt(bits, msg.models_mask, 3);
  putInt(bits, msg.month, 4);
  putInt(bits, msg.day, 5);
  putInt(bits, msg.hour, 5);
  const nPeriods = msg.periods[0].length;
  for (let i = 0; i < nPeriods; i++) {
    for (const modelPeriods of msg.periods) {
      bits.push(...periodToBits(modelPeriods[i]));
    }
  }
  return encode(bits);
}

export function messageFromString(s: string): ForecastMessage {
  const nBits = bitsFromChars(s.length);
  if (nBits === null) throw new Error(`Unexpected message length: ${s.length} chars`);
  const bits = decode(s, nBits);
  let pos = 0;

  let version: number,
    location: number,
    daysRaw: number,
    resolution: number,
    models_mask: number,
    month: number,
    day: number,
    hour: number;
  [version, pos] = takeInt(bits, pos, 7);
  [location, pos] = takeInt(bits, pos, 1);
  [daysRaw, pos] = takeInt(bits, pos, 4);
  [resolution, pos] = takeInt(bits, pos, 3);
  [models_mask, pos] = takeInt(bits, pos, 3);
  [month, pos] = takeInt(bits, pos, 4);
  [day, pos] = takeInt(bits, pos, 5);
  [hour, pos] = takeInt(bits, pos, 5);

  if (version !== VERSION)
    throw new Error(`Version mismatch: encoded v${version}, expected v${VERSION}`);

  const resHours = RESOLUTION_HOURS[resolution] ?? 24;
  const periodsPerDay = resHours >= 24 ? 1 : 24 / resHours;
  const nPeriods = (daysRaw + 1) * periodsPerDay;
  const nModels = popcount(models_mask);

  const allPeriods: Period[][] = Array.from({ length: nModels }, () => []);
  for (let i = 0; i < nPeriods; i++) {
    for (let m = 0; m < nModels; m++) {
      const [p, nextPos] = periodFromBits(bits, pos);
      pos = nextPos;
      allPeriods[m].push(p);
    }
  }

  return { version, location, days: daysRaw + 1, resolution, models_mask, month, day, hour, periods: allPeriods };
}

export function startDatetime(msg: ForecastMessage): Date {
  const now = new Date();
  const d = new Date(now.getFullYear(), msg.month - 1, msg.day, msg.hour);
  if (now.getTime() - d.getTime() > 180 * 86400000) d.setFullYear(d.getFullYear() + 1);
  return d;
}

function popcount(n: number): number {
  let c = 0;
  while (n) { c += n & 1; n >>>= 1; }
  return c;
}
