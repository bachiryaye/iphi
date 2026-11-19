import { useT } from "@/shared/i18n/context";
import { Branch } from "@carbon/icons-react";
import { Link } from "react-router";

import type { ComponentRef } from "@/shared/api/types";

/** An annotation, never a state (§4): the component is downstream of a failing one. */
export function ImpactNote({ by }: { by: readonly ComponentRef[] }) {
  const t = useT();
  if (by.length === 0) return null;
  return (
    <span className="inline-flex items-center gap-1 text-small whitespace-nowrap text-text-muted">
      <Branch size={16} aria-hidden="true" /> {t("Impacted by")}{" "}
      {by.map((ref, index) => (
        <span key={ref.id}>
          {index > 0 && ", "}
          <Link
            to={`/components/${ref.id}`}
            className="text-text-muted underline underline-offset-2"
          >
            {ref.key}
          </Link>
        </span>
      ))}
    </span>
  );
}
