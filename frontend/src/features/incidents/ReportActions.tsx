import { useT } from "@/shared/i18n/context";
import { Download } from "@carbon/icons-react";
import { useMutation } from "@tanstack/react-query";

import { api, ApiError, toApiError, unreachable } from "@/shared/api/client";
import type { paths } from "@/shared/api/schema";
import { Button } from "@/shared/ui/Button";
import { ApiErrorSummary, CorrelationId } from "@/shared/ui/QueryStates";

type Format = NonNullable<
  NonNullable<
    paths["/api/v1/reports/incidents/{incident_id}"]["get"]["parameters"]["query"]
  >["format"]
>;

async function report(incidentId: string, format: Format) {
  try {
    const { data, response, error } = await api.GET("/api/v1/reports/incidents/{incident_id}", {
      params: { path: { incident_id: incidentId }, query: { format } },
      parseAs: "blob",
    });
    if (data === undefined) throw toApiError(response, error);
    return data;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw unreachable();
  }
}

function save(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
  // Keep the URL alive while the browser starts the download, then release its file reference.
  setTimeout(() => {
    URL.revokeObjectURL(url);
  }, 60_000);
}

export function ReportActions({
  incidentId,
  reference,
}: {
  incidentId: string;
  reference: string;
}) {
  const t = useT();
  const download = useMutation({
    mutationFn: (format: Format) => report(incidentId, format),
    onSuccess: (blob, format) => {
      save(blob, `IPHI-${reference}-simulated.${format}`);
    },
  });
  const error = download.error;
  return (
    <div className="flex flex-col items-end gap-2 max-xl:items-start">
      <div
        role="group"
        aria-label={t("Incident report")}
        className="flex flex-wrap gap-2"
        aria-busy={download.isPending}
      >
        {(["pdf", "csv"] as const).map((format) => (
          <Button
            key={format}
            icon={<Download size={16} aria-hidden="true" />}
            disabled={download.isPending}
            onClick={() => {
              download.mutate(format);
            }}
          >
            {download.isPending && download.variables === format
              ? t("Generating…")
              : t("Export {format}", { format: format.toUpperCase() })}
          </Button>
        ))}
      </div>
      {download.isSuccess && (
        <p role="status" className="text-small text-text-muted">
          {t("Report ready. Your browser handles the download.")}
        </p>
      )}
      {error !== null && (
        <div role="alert" className="max-w-[60ch] border-l-[3px] border-border-strong px-3 py-2">
          <p className="font-medium">{t("Could not export the report.")}</p>
          <p className="text-text-muted">
            <ApiErrorSummary error={error} /> {t("Monitoring continues. Retry the export.")}
          </p>
          {error instanceof ApiError && error.correlationId !== null && (
            <CorrelationId value={error.correlationId} />
          )}
        </div>
      )}
    </div>
  );
}
