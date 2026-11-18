import { createContext, useContext } from "react";

export const FALLBACK_MS = 30_000;
export const MONITOR_REFRESH_MS = 5_000;

export interface LiveState {
  mode: "connecting" | "live" | "paused";
  announcement: string;
  reconnect: () => void;
}

export const LiveContext = createContext<LiveState>({
  mode: "paused",
  announcement: "",
  reconnect: () => undefined,
});

export function useLiveState() {
  return useContext(LiveContext);
}

export function usePolling(): { refetchInterval: number | false; staleTime: number } {
  const { mode } = useLiveState();
  return { refetchInterval: mode === "live" ? false : FALLBACK_MS, staleTime: 5000 };
}
