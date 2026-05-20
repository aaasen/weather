import { describe, it, expect } from "vitest";
import {
  messageToString,
  messageFromString,
  type ForecastMessage,
  type Period,
  CARDINALS,
} from "../src/index.js";

const PERIOD: Period = {
  weathercode: 73,
  precip: 75,
  freeze_ft: 6000,
  snow_in: 4,
  cloud_mid: 75,
  wind_500_mph: 30,
  wind_500_dir: 4,
  wind_600_mph: 25,
  wind_600_dir: 3,
  wind_700_mph: 15,
  wind_700_dir: 2,
};

function msg(overrides: Partial<ForecastMessage> = {}): ForecastMessage {
  return {
    version: 1,
    location: 0,
    days: 3,
    resolution: 0,
    models_mask: 0b001,
    month: 5,
    day: 20,
    hour: 12,
    periods: [[PERIOD, PERIOD, PERIOD]],
    ...overrides,
  };
}

function roundTrip(m: ForecastMessage): ForecastMessage {
  return messageFromString(messageToString(m));
}

describe("round-trip encoding", () => {
  it("preserves header fields", () => {
    const original = msg({ location: 1, days: 7, resolution: 2, models_mask: 0b011, month: 1, day: 31, hour: 0 });
    const decoded = roundTrip(original);
    expect(decoded.version).toBe(original.version);
    expect(decoded.location).toBe(original.location);
    expect(decoded.days).toBe(original.days);
    expect(decoded.resolution).toBe(original.resolution);
    expect(decoded.models_mask).toBe(original.models_mask);
    expect(decoded.month).toBe(original.month);
    expect(decoded.day).toBe(original.day);
    expect(decoded.hour).toBe(original.hour);
  });

  it("preserves period fields", () => {
    const decoded = roundTrip(msg());
    const p = decoded.periods[0][0];
    expect(p.weathercode).toBe(PERIOD.weathercode);
    expect(p.precip).toBe(PERIOD.precip);
    expect(p.freeze_ft).toBe(PERIOD.freeze_ft);
    expect(p.snow_in).toBe(PERIOD.snow_in);
    expect(p.cloud_mid).toBe(PERIOD.cloud_mid);
    expect(p.wind_500_mph).toBe(PERIOD.wind_500_mph);
    expect(p.wind_500_dir).toBe(PERIOD.wind_500_dir);
    expect(p.wind_600_mph).toBe(PERIOD.wind_600_mph);
    expect(p.wind_600_dir).toBe(PERIOD.wind_600_dir);
    expect(p.wind_700_mph).toBe(PERIOD.wind_700_mph);
    expect(p.wind_700_dir).toBe(PERIOD.wind_700_dir);
  });

  it("handles all 8 wind directions", () => {
    for (let dir = 0; dir < 8; dir++) {
      const period = { ...PERIOD, wind_700_dir: dir };
      const decoded = roundTrip(msg({ periods: [[period]] }));
      expect(decoded.periods[0][0].wind_700_dir).toBe(dir);
      expect(CARDINALS[decoded.periods[0][0].wind_700_dir]).toBe(CARDINALS[dir]);
    }
  });

  it("handles all resolutions", () => {
    // resolution 0 = daily (1 period/day), 1 = 12h (2/day), 2 = 6h (4/day), 3 = 3h (8/day), 4 = 1h (24/day)
    const periodsPerDay = [1, 2, 4, 8, 24];
    for (let resolution = 0; resolution <= 4; resolution++) {
      const nPeriods = 2 * periodsPerDay[resolution];
      const periods = Array(nPeriods).fill(PERIOD);
      const decoded = roundTrip(msg({ resolution, days: 2, periods: [periods] }));
      expect(decoded.resolution).toBe(resolution);
      expect(decoded.periods[0]).toHaveLength(nPeriods);
    }
  });

  it("handles multiple models", () => {
    const periods = [[PERIOD, PERIOD, PERIOD], [PERIOD, PERIOD, PERIOD]];
    const decoded = roundTrip(msg({ models_mask: 0b011, periods }));
    expect(decoded.models_mask).toBe(0b011);
    expect(decoded.periods).toHaveLength(2);
    expect(decoded.periods[0]).toHaveLength(3);
    expect(decoded.periods[1]).toHaveLength(3);
  });

  it("handles all three models", () => {
    const row = Array(10).fill(PERIOD);
    const decoded = roundTrip(msg({ models_mask: 0b111, days: 10, periods: [row, row, row] }));
    expect(decoded.models_mask).toBe(0b111);
    expect(decoded.periods).toHaveLength(3);
  });

  it("clamps wind speed to 5 mph steps", () => {
    // 27 mph → stored as floor(27/5)=5 → decoded as 25 mph
    const period = { ...PERIOD, wind_700_mph: 27 };
    const decoded = roundTrip(msg({ periods: [[period]] }));
    expect(decoded.periods[0][0].wind_700_mph).toBe(25);
  });

  it("clamps snow to 15 max", () => {
    const period = { ...PERIOD, snow_in: 20 };
    const decoded = roundTrip(msg({ periods: [[period]] }));
    expect(decoded.periods[0][0].snow_in).toBe(15);
  });

  it("clamps freeze level to 15,000 ft max", () => {
    const period = { ...PERIOD, freeze_ft: 20000 };
    const decoded = roundTrip(msg({ periods: [[period]] }));
    expect(decoded.periods[0][0].freeze_ft).toBe(15000);
  });

  it("encodes zero-value period", () => {
    const period: Period = {
      weathercode: 0, precip: 0, freeze_ft: 0, snow_in: 0, cloud_mid: 0,
      wind_500_mph: 0, wind_500_dir: 0,
      wind_600_mph: 0, wind_600_dir: 0,
      wind_700_mph: 0, wind_700_dir: 0,
    };
    const decoded = roundTrip(msg({ periods: [[period]] }));
    const p = decoded.periods[0][0];
    expect(p.weathercode).toBe(0);
    expect(p.precip).toBe(0);
    expect(p.freeze_ft).toBe(0);
    expect(p.snow_in).toBe(0);
    expect(p.wind_700_mph).toBe(0);
  });

  it("throws on invalid encoded string length", () => {
    expect(() => messageFromString("abc")).toThrow("Unexpected message length");
  });

  it("throws on version mismatch", () => {
    const encoded = messageToString(msg({ version: 99 }));
    expect(() => messageFromString(encoded)).toThrow("Version mismatch");
  });
});
