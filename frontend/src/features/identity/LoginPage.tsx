import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Navigate, useNavigate, useSearchParams } from "react-router";

import { SimulatedBanner } from "@/app/AppShell";
import { MonitorStatus } from "@/app/MonitorStatus";
import { api, call, setCsrfToken } from "@/shared/api/client";
import { Button } from "@/shared/ui/Button";
import { RefusedAlert } from "@/shared/ui/QueryStates";

import { safeReturnTo, useSession } from "@/shared/identity/session";

export function LoginPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [params] = useSearchParams();
  const target = safeReturnTo(params.get("next"));
  const navigate = useNavigate();
  const client = useQueryClient();
  const session = useSession();
  const login = useMutation({
    mutationFn: async () => {
      await client.cancelQueries({ queryKey: ["session"] });
      return call(api.POST("/api/v1/auth/login", { body: { username, password } }));
    },
    onSuccess: (data) => {
      setPassword("");
      setCsrfToken(data.csrf_token);
      client.removeQueries({ predicate: (query) => query.queryKey[0] !== "session" });
      client.setQueryData(["session"], data);
      void navigate(target, { replace: true });
    },
    onError: () => {
      setPassword("");
    },
  });
  if (session.data) return <Navigate to={target} replace />;
  return (
    <>
      <SimulatedBanner />
      <main
        id="main"
        className="mx-auto grid min-h-[calc(100vh-28px)] max-w-4xl content-center gap-10 p-6 md:grid-cols-2 md:gap-16"
      >
        <div className="flex flex-col gap-4">
          <p className="font-mono text-heading font-semibold" translate="no">
            IPHI
          </p>
          <h1 className="text-display font-semibold">Sign in to platform health</h1>
          <p className="max-w-[42ch] text-text-muted">
            Inspect simulated infrastructure, trace incidents to stored evidence and review platform
            health.
          </p>
          <p className="text-small text-text-muted">
            Synthetic data only. No real plant is connected.
          </p>
          <MonitorStatus />
        </div>
        <form
          method="post"
          action="/api/v1/auth/login"
          className="flex flex-col gap-4 border-l border-border pl-6 max-md:border-l-0 max-md:pl-0"
          onSubmit={(event) => {
            event.preventDefault();
            login.mutate();
          }}
        >
          <h2 className="text-heading font-semibold">Your account</h2>
          <label htmlFor="sign-in-username">Username</label>
          <input
            id="sign-in-username"
            name="username"
            autoComplete="username"
            autoCapitalize="none"
            autoCorrect="off"
            spellCheck={false}
            required
            maxLength={32}
            value={username}
            onChange={(event) => {
              setUsername(event.target.value);
            }}
            className="h-10 rounded-control border border-border-strong bg-surface px-3"
          />
          <label htmlFor="sign-in-password">Password</label>
          <input
            id="sign-in-password"
            name="password"
            type="password"
            autoComplete="current-password"
            required
            maxLength={128}
            value={password}
            onChange={(event) => {
              setPassword(event.target.value);
            }}
            className="h-10 rounded-control border border-border-strong bg-surface px-3"
          />
          <Button
            type="submit"
            variant="primary"
            disabled={login.isPending}
            className="mt-2 justify-center"
          >
            {login.isPending ? "Signing in…" : "Sign in"}
          </Button>
          <RefusedAlert action="Sign in" error={login.error} />
          <p className="text-small text-text-muted">
            Use the account supplied by the demo owner. Viewer access is read-only; engineer and
            admin actions are recorded.
          </p>
        </form>
      </main>
    </>
  );
}
