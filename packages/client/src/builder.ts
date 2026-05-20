import { HEADER_BITS, PERIOD_BITS } from "@weather/protocol";

const MAX_CHARS = 160;
const LOG94 = Math.log(94);

export function builderChars(days: number, resHours: number, nModels: number): number {
  const periodsPerDay = resHours >= 24 ? 1 : 24 / resHours;
  const nBits = HEADER_BITS + days * periodsPerDay * nModels * PERIOD_BITS;
  return Math.ceil((nBits * Math.log(2)) / LOG94);
}

export function builderMsg(location: string, days: number, resHours: number, models: string[]): string {
  const res = resHours >= 24 ? "daily" : `${resHours}h`;
  return `${location} ${days}d ${res} ${models.join(",")}`;
}

export function updateBuilder(): void {
  const location =
    (document.querySelector('input[name="location"]:checked') as HTMLInputElement | null)?.value ??
    "upper";
  const days = parseInt(
    (document.getElementById("days-slider") as HTMLInputElement).value,
  );
  const resHours = parseInt(
    (document.querySelector('input[name="resolution"]:checked') as HTMLInputElement | null)
      ?.value ?? "24",
  );
  const models = [
    ...(document.querySelectorAll('input[name="model"]:checked') as NodeListOf<HTMLInputElement>),
  ].map((el) => el.value);

  (document.getElementById("days-display") as HTMLElement).textContent =
    `${days} day${days > 1 ? "s" : ""}`;

  const nChars = models.length > 0 ? builderChars(days, resHours, models.length) : 0;
  const bar = document.getElementById("len-bar") as HTMLElement;
  const txt = document.getElementById("len-text") as HTMLElement;
  const pct = Math.min((nChars / MAX_CHARS) * 100, 100);
  const over = nChars > MAX_CHARS;

  bar.style.width = pct + "%";
  bar.style.background = over ? "#cc2222" : "#2a8f5a";
  txt.className = "len-text " + (over ? "len-over" : "len-ok");
  txt.textContent =
    models.length === 0
      ? "Select at least one model"
      : over
        ? `${nChars} chars — exceeds ${MAX_CHARS}, reduce days or resolution`
        : `${nChars} / ${MAX_CHARS} chars`;

  const msg = models.length > 0 ? builderMsg(location, days, resHours, models) : "";
  (document.getElementById("builder-msg") as HTMLElement).textContent = msg;
  (document.getElementById("builder-copy") as HTMLButtonElement).disabled =
    over || models.length === 0;
}
