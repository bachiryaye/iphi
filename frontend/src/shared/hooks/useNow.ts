import { useCallback, useSyncExternalStore } from "react";

// One shared ticker: every relative age on screen moves together, on a single interval.
const listeners = new Set<() => void>();
let now = Date.now();
let timer: number | undefined;

function subscribe(listener: () => void) {
  listeners.add(listener);
  if (timer === undefined) {
    timer = window.setInterval(() => {
      now = Date.now();
      for (const l of listeners) l();
    }, 1000);
  }
  return () => {
    listeners.delete(listener);
    if (listeners.size === 0 && timer !== undefined) {
      window.clearInterval(timer);
      timer = undefined;
    }
  };
}

const snapshot = () => now;

/** Current wall time, refreshed every second by a ticker shared across components. */
export function useNow(): Date {
  return new Date(useSyncExternalStore(subscribe, snapshot));
}

/** Wall time rounded down to `periodMs`, for consumers that should change less often. */
export function useNowEvery(periodMs: number): Date {
  // Rounded inside the snapshot: React skips the re-render until the period changes.
  const rounded = useCallback(() => Math.floor(now / periodMs) * periodMs, [periodMs]);
  return new Date(useSyncExternalStore(subscribe, rounded));
}
