import { useClock } from "@/shared/api/queries";

import { useNow, useNowEvery } from "./useNow";

function estimate(
  clock: { mode: string; speed: number; platform_time: string } | undefined,
  fetchedAt: number,
  wall: Date,
): Date | null {
  if (clock === undefined) return null;
  const base = new Date(clock.platform_time).getTime();
  if (clock.mode === "manual") return new Date(base);
  const speed = clock.mode === "accelerated" ? clock.speed : 1;
  return new Date(base + Math.max(0, wall.getTime() - fetchedAt) * speed);
}

/**
 * Platform time estimated between clock polls, updated every `periodMs`: history windows and
 * stored timestamps are in platform time, which runs faster than the wall clock in accelerated
 * mode and stands still in manual mode.
 */
export function usePlatformNow(periodMs: number): Date | null {
  const clock = useClock();
  const wall = useNowEvery(periodMs);
  return estimate(clock.data, clock.dataUpdatedAt, wall);
}

/** Platform time each second, falling back to wall time until the clock is known. */
export function usePlatformClock(): Date {
  const clock = useClock();
  const wall = useNow();
  return estimate(clock.data, clock.dataUpdatedAt, wall) ?? wall;
}
