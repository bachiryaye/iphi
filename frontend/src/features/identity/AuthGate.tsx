import { useT } from "@/shared/i18n/context";
import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { Navigate, Outlet, useLocation } from "react-router";

import { MonitorStatus } from "@/app/MonitorStatus";
import { SimulatedBanner } from "@/app/AppShell";
import { LoadError } from "@/shared/ui/QueryStates";

import { clearSession, useSession } from "@/shared/identity/session";

export function AuthGate() {
  const t = useT();
  const session = useSession();
  const location = useLocation();
  const client = useQueryClient();
  useEffect(() => {
    const expired = () => {
      void clearSession(client);
    };
    window.addEventListener("iphi:session-expired", expired);
    return () => {
      window.removeEventListener("iphi:session-expired", expired);
    };
  }, [client]);

  if (session.data === null) {
    return (
      <Navigate
        to={`/login?next=${encodeURIComponent(location.pathname + location.search)}`}
        replace
      />
    );
  }
  if (session.data !== undefined) return <Outlet />;
  return (
    <>
      <SimulatedBanner />
      <main id="main" className="mx-auto flex max-w-xl flex-col gap-6 p-6">
        <MonitorStatus />
        {session.isError ? (
          <LoadError what={t("your session")} query={session} />
        ) : (
          <p role="status">{t("Checking session…")}</p>
        )}
      </main>
    </>
  );
}
