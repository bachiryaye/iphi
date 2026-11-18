import { useId, useState } from "react";

import { useComment, useIncidentEvents, useMutationGuard } from "@/shared/api/queries";
import type { IncidentDetail } from "@/shared/api/types";
import { Button } from "@/shared/ui/Button";
import { LoadError, RefusedAlert } from "@/shared/ui/QueryStates";

import { IncidentTimeline } from "./IncidentTimeline";

function TimelinePage({ id, cursor }: { id: string; cursor: string }) {
  const page = useIncidentEvents(id, cursor, true);
  const [expanded, setExpanded] = useState(false);
  return (
    <>
      {page.isPending && (
        <p className="p-4" role="status">
          Loading more events…
        </p>
      )}
      {page.isError && <LoadError what="more timeline events" query={page} />}
      {page.data !== undefined && (
        <>
          <IncidentTimeline events={page.data.items} />
          {page.data.next_cursor !== null &&
            (expanded ? (
              <TimelinePage id={id} cursor={page.data.next_cursor} />
            ) : (
              <Button
                className="m-4"
                onClick={() => {
                  setExpanded(true);
                }}
              >
                Load more events
              </Button>
            ))}
        </>
      )}
    </>
  );
}

export function InvestigationTimeline({ incident }: { incident: IncidentDetail }) {
  const [expanded, setExpanded] = useState(false);
  const [text, setText] = useState("");
  const [saved, setSaved] = useState(false);
  const fieldId = useId();
  const helpId = useId();
  const guard = useMutationGuard();
  const comment = useComment(incident.id);
  return (
    <>
      <IncidentTimeline events={incident.events} />
      {incident.events_next_cursor !== null && (
        <>
          <p className="border-t border-border px-4 py-2.5 text-small text-text-muted">
            Showing the first {incident.events.length} of {incident.event_count} events.
          </p>
          {expanded ? (
            <TimelinePage id={incident.id} cursor={incident.events_next_cursor} />
          ) : (
            <Button
              className="mx-4 mb-3"
              onClick={() => {
                setExpanded(true);
              }}
            >
              Load more events
            </Button>
          )}
        </>
      )}
      <form
        className="flex flex-col gap-2 border-t border-border p-4"
        onSubmit={(event) => {
          event.preventDefault();
          comment.mutate(text.trim(), {
            onSuccess: () => {
              setText("");
              setSaved(true);
            },
          });
        }}
      >
        <label htmlFor={fieldId} className="font-medium">
          Investigation comment
        </label>
        <textarea
          id={fieldId}
          name="investigation-comment"
          rows={3}
          maxLength={4000}
          required
          autoComplete="off"
          disabled={!guard.allowed || comment.isPending}
          value={text}
          aria-describedby={helpId}
          onChange={(event) => {
            setText(event.target.value);
            setSaved(false);
          }}
          className="rounded-control border border-border-strong bg-surface px-2 py-1.5 text-text disabled:opacity-60"
        />
        <p id={helpId} className="text-small text-text-muted">
          {guard.allowed
            ? "Saved with actor and platform UTC in this timeline. Up to 4,000 characters."
            : guard.reason}
        </p>
        <Button type="submit" disabled={!guard.allowed || text.trim() === "" || comment.isPending}>
          {comment.isPending ? "Saving comment…" : "Add comment"}
        </Button>
        {saved && (
          <p role="status" className="text-small">
            Comment saved in the timeline.
          </p>
        )}
        {comment.error !== null && <RefusedAlert action="Add comment" error={comment.error} />}
      </form>
    </>
  );
}
