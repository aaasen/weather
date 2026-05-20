import { ALPHABET, HEADER_BITS, PERIOD_BITS } from "./constants.js";

const A2I: Record<string, number> = Object.fromEntries(
  [...ALPHABET].map((c, i) => [c, i]),
);

export function nCharsForBits(nBits: number): number {
  return Math.ceil((nBits * Math.log(2)) / Math.log(94));
}

export function encode(bits: number[]): string {
  const nChars = nCharsForBits(bits.length);
  let value = 0n;
  for (const b of bits) value = (value << 1n) | BigInt(b);
  const chars: string[] = [];
  for (let i = 0; i < nChars; i++) {
    chars.push(ALPHABET[Number(value % 94n)]);
    value /= 94n;
  }
  return chars.reverse().join("");
}

export function decode(s: string, nBits: number): number[] {
  let value = 0n;
  for (const c of s) {
    const idx = A2I[c];
    if (idx !== undefined) value = value * 94n + BigInt(idx);
  }
  const bits: number[] = new Array(nBits).fill(0);
  for (let i = nBits - 1; i >= 0; i--) {
    bits[i] = Number(value & 1n);
    value >>= 1n;
  }
  return bits;
}

export function bitsFromChars(nChars: number): number | null {
  for (let k = 0; k < 1000; k++) {
    const nBits = HEADER_BITS + k * PERIOD_BITS;
    const nc = nCharsForBits(nBits);
    if (nc === nChars) return nBits;
    if (nc > nChars) break;
  }
  return null;
}
