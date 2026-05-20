export function putInt(bits: number[], value: number, n: number): void {
  for (let i = n - 1; i >= 0; i--) {
    bits.push((value >> i) & 1);
  }
}

export function takeInt(bits: number[], pos: number, n: number): [number, number] {
  let v = 0;
  for (let i = 0; i < n; i++) v = (v << 1) | (bits[pos + i] ?? 0);
  return [v, pos + n];
}

export function putWinds(bits: number[], ...pairs: [number, number][]): void {
  for (const [spd, dir] of pairs) {
    putInt(bits, Math.min(Math.floor(spd / 5), 15), 4);
    putInt(bits, dir % 8, 3);
  }
}

export function takeWinds(
  bits: number[],
  pos: number,
): [[number, number][], number] {
  const result: [number, number][] = [];
  for (let i = 0; i < 3; i++) {
    const [spd, p1] = takeInt(bits, pos, 4);
    const [dir, p2] = takeInt(bits, p1, 3);
    result.push([spd * 5, dir]);
    pos = p2;
  }
  return [result, pos];
}
