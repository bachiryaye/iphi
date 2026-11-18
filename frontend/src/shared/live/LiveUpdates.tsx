import { useQueryClient } from "@tanstack/react-query";
import { type ReactNode, useCallback, useEffect, useMemo, useState } from "react";

import type { components } from "@/shared/api/schema";
import { formatUtcTime } from "@/shared/format/time";
import { Button } from "@/shared/ui/Button";

import { LiveContext, useLiveState, type LiveState } from "./context";

type Notice = components["schemas"]["StreamEventOut"];
const EVENTS: Record<Notice["type"], true> = {
  "platform.health_changed": true,
  "component.health_changed": true,
  "incident.opened": true,
  "incident.updated": true,
  "incident.resolved": true,
  "scenario.changed": true,
  "monitor.status": true,
  heartbeat: true,
  sync: true,
};
const QUIET_LIMIT_MS = 35_000;
const WATCHDOG_MS = 5000;
const COALESCE_MS = 100;

function isNotice(value: unknown): value is Notice {
  return (
    typeof value === "object" &&
    value !== null &&
    "type" in value &&
    typeof value.type === "string" &&
    Object.hasOwn(EVENTS, value.type) &&
    "id" in value &&
    typeof value.id === "string" &&
    value.id.length <= 64 &&
    "platform_time" in value &&
    typeof value.platform_time === "string" &&
    Number.isFinite(Date.parse(value.platform_time)) &&
    "environment" in value &&
    value.environment === "simulation"
  );
}

export function LiveUpdatesProvider({ children }: { children: ReactNode }) {
  const client = useQueryClient();
  const [mode, setMode] = useState<LiveState["mode"]>(() =>
    typeof globalThis.EventSource === "undefined" ? "paused" : "connecting",
  );
  const [announcement, setAnnouncement] = useState("");
  const [attempt, setAttempt] = useState(0);
  const reconnect = useCallback(() => {
    setAttempt((value) => value + 1);
  }, []);

  useEffect(() => {
    if (typeof globalThis.EventSource === "undefined") {
      return;
    }
    const source = new EventSource("/api/v1/events/stream");
    let lastMessage = performance.now();
    let refresh: number | undefined;
    let stopped = false;
    let suspended = false;
    const receive = (event: Event) => {
      if (stopped || suspended) return;
      if (!(event instanceof MessageEvent) || typeof event.data !== "string") return;
      let value: unknown;
      try {
        value = JSON.parse(event.data);
      } catch {
        return;
      }
      if (!isNotice(value)) return;
      lastMessage = performance.now();
      setMode("live");
      if (value.type === "incident.opened") {
        setAnnouncement(
          `New incident detected at ${formatUtcTime(new Date(value.platform_time))} UTC. Updating the current view.`,
        );
      }
      if (refresh === undefined) {
        refresh = window.setTimeout(() => {
          refresh = undefined;
          void client.invalidateQueries({
            predicate: (query) => query.queryKey[0] !== "cited-evidence",
          });
        }, COALESCE_MS);
      }
    };
    for (const type of Object.keys(EVENTS)) source.addEventListener(type, receive);
    source.onerror = () => {
      if (!stopped) setMode("paused");
    };
    const offline = () => {
      suspended = true;
      source.close();
      setMode("paused");
    };
    window.addEventListener("offline", offline);
    window.addEventListener("online", reconnect);
    const watchdog = window.setInterval(() => {
      if (navigator.onLine && performance.now() - lastMessage > QUIET_LIMIT_MS) {
        setMode("paused");
        reconnect();
      }
    }, WATCHDOG_MS);
    return () => {
      stopped = true;
      source.close();
      window.removeEventListener("offline", offline);
      window.removeEventListener("online", reconnect);
      window.clearInterval(watchdog);
      window.clearTimeout(refresh);
    };
  }, [client, attempt, reconnect]);

  const value = useMemo(() => ({ mode, announcement, reconnect }), [mode, announcement, reconnect]);
  return <LiveContext value={value}>{children}</LiveContext>;
}

export function LiveUpdatesBanner() {
  const { mode, announcement, reconnect } = useLiveState();
  const supported = typeof globalThis.EventSource !== "undefined";
  return (
    <>
      <span className="sr-only" aria-live="polite" aria-atomic="true">
        {announcement}
      </span>
      {mode !== "live" && (
        <div className="flex flex-wrap items-center justify-between gap-2 border-l-[3px] border-border-strong bg-surface px-4 py-2 text-small text-text-muted">
          <p>
            {!supported
              ? "Live updates are unavailable in this browser."
              : mode === "connecting"
                ? "Connecting live updates…"
                : "Live updates paused. Reconnecting…"}{" "}
            This page refreshes every 30 s meanwhile.
          </p>
          {supported && (
            <Button variant="quiet" onClick={reconnect}>
              Retry live updates
            </Button>
          )}
        </div>
      )}
    </>
  );
}
