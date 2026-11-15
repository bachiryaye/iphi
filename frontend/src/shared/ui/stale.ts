/** Stale content stays readable but muted on a light hatch (§8, stale view). */
export function staleClass(stale: boolean): string {
  return stale ? "stale-view text-text-muted" : "";
}
