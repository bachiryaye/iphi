import { useMutation, useQueryClient } from "@tanstack/react-query";

import { api, toApiError } from "@/shared/api/client";
import { Button } from "@/shared/ui/Button";
import { RefusedAlert } from "@/shared/ui/QueryStates";

import { clearSession, useSession } from "@/shared/identity/session";

export function UserMenu() {
  const session = useSession();
  const client = useQueryClient();
  const logout = useMutation({
    mutationFn: async () => {
      const result = await api.POST("/api/v1/auth/logout", {
        headers: { "content-type": "application/json" },
      });
      if (!result.response.ok) throw toApiError(result.response, result.error);
    },
    onSuccess: () => clearSession(client),
  });
  if (!session.data) return null;
  const { user } = session.data;
  return (
    <details className="relative text-small">
      <summary className="cursor-pointer whitespace-nowrap rounded-control border border-border-strong px-2 py-1.5">
        {user.username} · {user.role}
      </summary>
      <div className="absolute right-0 z-20 mt-2 flex w-60 flex-col gap-3 rounded-card border border-border-strong bg-surface p-4 shadow-sm">
        <p>
          Signed in as {user.display_name}. Role: {user.role}.
        </p>
        <Button
          onClick={() => {
            logout.mutate();
          }}
          disabled={logout.isPending}
        >
          {logout.isPending ? "Signing out…" : "Sign out"}
        </Button>
        <RefusedAlert action="Sign out" error={logout.error} />
      </div>
    </details>
  );
}
