import { useSearchParams } from "react-router";

/** A filter whose value lives in the URL so every filtered view is shareable (§5). */
export function useSearchFilter<T extends string>(name: string, allowed: readonly T[]) {
  const [params, setParams] = useSearchParams();
  const raw = params.get(name);
  const value = allowed.find((v) => v === raw) ?? "";
  const set = (next: T | "") => {
    setParams(
      (current) => {
        const updated = new URLSearchParams(current);
        if (next === "") updated.delete(name);
        else updated.set(name, next);
        updated.delete("cursor");
        return updated;
      },
      { replace: true },
    );
  };
  return [value, set] as const;
}
