import { english, type Translator } from "@/shared/i18n/translate";

const utcTime = new Intl.DateTimeFormat("en-GB", {
  timeZone: "UTC",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hourCycle: "h23",
});

const localTime = new Intl.DateTimeFormat("en-GB", {
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hourCycle: "h23",
});

const utcDate = new Intl.DateTimeFormat("en-CA", {
  timeZone: "UTC",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
});

const seconds = new Intl.NumberFormat("en-GB", { maximumFractionDigits: 1 });

/** `10:42:07` in UTC. */
export const formatUtcTime = (date: Date): string => utcTime.format(date);

/** `11:42:07` in the browser's time zone. */
export const formatLocalTime = (date: Date): string => localTime.format(date);

/** `2026-11-12 10:42:07 UTC` (design system §10). */
export const formatUtcDateTime = (date: Date): string =>
  `${utcDate.format(date)} ${utcTime.format(date)} UTC`;

export const formatSeconds = (value: number, t: Translator = english): string =>
  `${t.language === "fr" ? value.toLocaleString("fr-FR", { maximumFractionDigits: 1 }) : seconds.format(value)}\u00a0s`;

/** `2 min 15 s`, `14 min`, `3 h 05 min`: the largest two units, never a bare number. */
export function formatDuration(totalSeconds: number): string {
  const s = Math.max(0, Math.round(totalSeconds));
  if (s < 60) return `${String(s)}\u00a0s`;
  const minutes = Math.floor(s / 60);
  if (minutes < 60) {
    const rest = s % 60;
    return rest === 0 || minutes >= 10
      ? `${String(minutes)}\u00a0min`
      : `${String(minutes)}\u00a0min ${String(rest)}\u00a0s`;
  }
  const hours = Math.floor(minutes / 60);
  if (hours < 48)
    return `${String(hours)}\u00a0h ${String(minutes % 60).padStart(2, "0")}\u00a0min`;
  return `${String(Math.floor(hours / 24))}\u00a0d`;
}

/** `4 min ago`; always shown next to, or with a title holding, the absolute time (P6). */
export const formatAge = (from: Date, now: Date, t: Translator = english): string =>
  t("{duration} ago", { duration: formatDuration((now.getTime() - from.getTime()) / 1000) });

/** `2026-11-12 10:42:07 UTC (11:42:07 local)` for titles. */
export const formatFullTimestamp = (date: Date, t: Translator = english): string =>
  `${formatUtcDateTime(date)} (${formatLocalTime(date)} ${t("local")})`;
