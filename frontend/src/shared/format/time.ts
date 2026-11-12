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

export const formatSeconds = (value: number): string => `${seconds.format(value)}\u00a0s`;
