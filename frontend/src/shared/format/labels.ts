import { english, type Translator } from "@/shared/i18n/translate";

/** `telemetry_loss` → `telemetry loss`: API enum values as an operator reads them. */
export const humanize = (value: string, t: Translator = english): string =>
  t.label(value.replaceAll("_", " "));
