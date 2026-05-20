import { WMO, ARROWS, BEAUFORT, MODEL_COLORS } from "./ui-constants.js";

export interface WindCell {
  ws: number;
  dir: string;
}

export interface DecodedPeriod {
  date: Date;
  wc: number;
  precip: number;
  fz_ft: number;
  snow: number;
  cloud: number;
  p500: WindCell;
  p600: WindCell;
  p700: WindCell;
}

export interface ForecastView {
  label: string;
  models: string[];
  hasSnow: boolean;
  timeStep: number;
  snowUnit: number;
  periods: DecodedPeriod[][];
}

function beaufort(mph: number): { bg: string; fg: string } {
  const i = BEAUFORT.findIndex(([t]) => mph < t);
  return { bg: BEAUFORT[i][2], fg: BEAUFORT[i][3] };
}

function wmoIcon(c: number): string {
  return (WMO[c] ?? ["", "", "❓"])[2];
}

function wmoShort(c: number): string {
  return (WMO[c] ?? ["", `wc${c}`, ""])[1];
}

function precipColor(pct: number): string {
  if (pct >= 60) return "#c04040";
  if (pct >= 30) return "#c08020";
  return "#4080c8";
}

type CellValue = string | { style: string; html: string };

function windCellHtml(ws: number | null, dir: string | null, colored: boolean): CellValue {
  if (ws == null) return '<span class="nil">—</span>';
  const arrow = dir ? (ARROWS[dir] ?? "") : "";
  const inner = `<div class="wind-cell"><span class="bft-mph">${ws} mph</span>${dir ? ` <span style="font-size:.75rem"> ${dir} ${arrow}</span>` : ""}</div>`;
  if (!colored || !ws) return inner;
  const b = beaufort(ws);
  return { style: `background:${b.bg};color:${b.fg}`, html: inner };
}

function periodLabel(date: Date, timeStep: number): string {
  const days = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  if (timeStep >= 24) {
    return `${days[date.getDay()]}<br><span style="font-weight:400;opacity:.7">${date.getMonth() + 1}/${date.getDate()}</span>`;
  } else if (timeStep === 1) {
    return `${String(date.getHours()).padStart(2, "0")}:00`;
  } else {
    return `${days[date.getDay()]}<br><span style="font-weight:400;opacity:.7">${date.getHours()}h</span>`;
  }
}

function row(lbl: string, cells: CellValue[], cls = ""): string {
  const tds = cells
    .map((c) => {
      if (c && typeof c === "object" && "html" in c)
        return `<td style="${c.style || ""}">${c.html}</td>`;
      return `<td>${c}</td>`;
    })
    .join("");
  return `<tr class="${cls}"><td class="lbl">${lbl}</td>${tds}</tr>`;
}

function sectionRow(lbl: string, n: number): string {
  return `<tr class="section-head"><td class="lbl">${lbl}</td>${Array(n).fill("<td></td>").join("")}</tr>`;
}

function sepRow(n: number): string {
  return `<tr class="model-sep">${Array(n + 1)
    .fill("<td></td>")
    .join("")}</tr>`;
}

function modelRow(name: string, n: number): string {
  const color = MODEL_COLORS[name] ?? "#666";
  return `<tr class="model-head"><td colspan="${n + 1}" style="background:${color}">${name}</td></tr>`;
}

function iconCells(ps: DecodedPeriod[]): string[] {
  return ps.map(
    (p) =>
      `<span class="wx-icon">${wmoIcon(p.wc)}</span><div class="wx-short">${wmoShort(p.wc)}</div>`,
  );
}

function precipCells(ps: DecodedPeriod[]): string[] {
  return ps.map((p) => {
    const c = precipColor(p.precip);
    return (
      `<div class="precip-pct" style="color:${c}">${p.precip}%</div>` +
      `<div class="precip-bar"><div class="precip-fill" style="width:${p.precip}%;background:${c}"></div></div>`
    );
  });
}

function cloudCells(ps: DecodedPeriod[]): string[] {
  return ps.map((p) =>
    p.cloud != null
      ? `<div class="precip-pct" style="color:#777">${p.cloud}%</div>` +
        `<div class="precip-bar"><div class="precip-fill" style="width:${p.cloud}%;background:#aaa"></div></div>`
      : '<span class="nil">—</span>',
  );
}

function snowCells(ps: DecodedPeriod[], snowUnit: number): string[] {
  return ps.map((p) => {
    const val = p.snow * snowUnit;
    return val
      ? `<span class="snow-val">${val.toFixed(snowUnit < 1 ? 1 : 0)}</span> <span class="snow-unit">in</span>`
      : '<span class="nil">—</span>';
  });
}

function freezeCells(ps: DecodedPeriod[]): string[] {
  return ps.map((p) =>
    p.fz_ft != null
      ? `<span class="fz-val">${p.fz_ft.toLocaleString()}</span> <span class="snow-unit">ft</span>`
      : '<span class="nil">—</span>',
  );
}

function altRows(ps: DecodedPeriod[], n: number): string {
  const w700 = ps.map((p) =>
    p.p700 ? windCellHtml(p.p700.ws, p.p700.dir, true) : '<span class="nil">—</span>',
  );
  const w600 = ps.map((p) =>
    p.p600 ? windCellHtml(p.p600.ws, p.p600.dir, true) : '<span class="nil">—</span>',
  );
  const w500 = ps.map((p) =>
    p.p500 ? windCellHtml(p.p500.ws, p.p500.dir, true) : '<span class="nil">—</span>',
  );
  return `
    ${sectionRow("Alt", n)}
    ${row('500<br><span style="font-weight:400;letter-spacing:0;opacity:.65">~18k ft</span>', w500)}
    ${row('600<br><span style="font-weight:400;letter-spacing:0;opacity:.65">~14k ft</span>', w600)}
    ${row('700<br><span style="font-weight:400;letter-spacing:0;opacity:.65">~10k ft</span>', w700)}`;
}

export function render(fc: ForecastView): string {
  const { label, models, hasSnow, timeStep, snowUnit, periods } = fc;
  const primary = periods[0];
  const extras = periods.slice(1);
  const n = primary.length;

  const th = `<th class="lbl"></th>${primary.map((p) => `<th class="day-h">${periodLabel(p.date, timeStep)}</th>`).join("")}`;

  let body = "";

  if (models.length > 1) body += modelRow(models[0], n);
  body += row("", iconCells(primary));
  body += sectionRow("Surface", n);
  body += row("Cloud mid", cloudCells(primary));
  body += row("Precip", precipCells(primary));
  if (hasSnow) body += row("Snow", snowCells(primary, snowUnit));
  body += row("Freeze", freezeCells(primary));
  body += altRows(primary, n);
  if (models.length > 1) body += sepRow(n);

  extras.forEach((ps, mi) => {
    body += modelRow(models[mi + 1], n);
    body += row("", iconCells(ps));
    body += sectionRow("Surface", n);
    body += row("Cloud mid", cloudCells(ps));
    body += row("Precip", precipCells(ps));
    if (hasSnow) body += row("Snow", snowCells(ps, snowUnit));
    body += row("Freeze", freezeCells(ps));
    body += altRows(ps, n);
    body += sepRow(n);
  });

  return `<div class="type-badge">${label}</div>
    <div class="table-wrap"><table>
      <thead><tr>${th}</tr></thead>
      <tbody>${body}</tbody>
    </table></div>`;
}
