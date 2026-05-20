import { WMO_CODES, PERIOD_BITS } from "./constants.js";
import { putInt, takeInt, putWinds, takeWinds } from "./bits.js";

const WMO2IDX: Record<number, number> = Object.fromEntries(
  WMO_CODES.map((c, i) => [c, i]),
);

export interface Period {
  weathercode: number;
  precip: number;
  freeze_ft: number;
  snow_in: number;
  cloud_mid: number;
  wind_500_mph: number;
  wind_500_dir: number;
  wind_600_mph: number;
  wind_600_dir: number;
  wind_700_mph: number;
  wind_700_dir: number;
}

export function periodToBits(p: Period): number[] {
  const bits: number[] = [];
  putInt(bits, WMO2IDX[p.weathercode] ?? 0, 5);
  putInt(bits, Math.min(Math.round(p.precip / 12.5), 7), 3);
  putInt(bits, Math.min(Math.floor(p.freeze_ft / 1000), 15), 4);
  putInt(bits, Math.min(p.snow_in, 15), 4);
  putInt(bits, Math.min(Math.round(p.cloud_mid / 12.5), 7), 3);
  putWinds(
    bits,
    [p.wind_500_mph, p.wind_500_dir],
    [p.wind_600_mph, p.wind_600_dir],
    [p.wind_700_mph, p.wind_700_dir],
  );
  if (bits.length !== PERIOD_BITS)
    throw new Error(`Period bits: expected ${PERIOD_BITS}, got ${bits.length}`);
  return bits;
}

export function periodFromBits(bits: number[], pos: number): [Period, number] {
  let wc: number, pr: number, fz: number, sn: number, cl: number;
  [wc, pos] = takeInt(bits, pos, 5);
  [pr, pos] = takeInt(bits, pos, 3);
  [fz, pos] = takeInt(bits, pos, 4);
  [sn, pos] = takeInt(bits, pos, 4);
  [cl, pos] = takeInt(bits, pos, 3);
  const [w, nextPos] = takeWinds(bits, pos);
  return [
    {
      weathercode: WMO_CODES[wc] ?? 0,
      precip: Math.round(pr * 12.5),
      freeze_ft: fz * 1000,
      snow_in: sn,
      cloud_mid: Math.round(cl * 12.5),
      wind_500_mph: w[0][0],
      wind_500_dir: w[0][1],
      wind_600_mph: w[1][0],
      wind_600_dir: w[1][1],
      wind_700_mph: w[2][0],
      wind_700_dir: w[2][1],
    },
    nextPos,
  ];
}
