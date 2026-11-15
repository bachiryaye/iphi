import { ChevronDown } from "@carbon/icons-react";
import { type ReactNode, useId, useState } from "react";

import type { Citation, Claim, Diagnostic, IncidentEvidence } from "@/shared/api/types";
import { EvidenceChip } from "@/shared/status/EvidenceChip";
import { Timestamp } from "@/shared/status/Timestamp";

import { evidenceSummary, evidenceTime } from "./evidenceText";

export interface EvidenceFocus {
  active: number | null;
  toggle: (evidenceId: number) => void;
  byId: Map<number, IncidentEvidence>;
}

function Chips({ citations, focus }: { citations: readonly Citation[]; focus: EvidenceFocus }) {
  return (
    <span className="inline-flex flex-wrap gap-1">
      {citations.map((c) => {
        const item = focus.byId.get(c.evidence_id);
        return (
          <EvidenceChip
            key={c.evidence_id}
            label={c.label}
            description={
              item === undefined ? "not in the first evidence page" : evidenceSummary(item)
            }
            pressed={focus.active === c.evidence_id}
            onToggle={() => {
              focus.toggle(c.evidence_id);
            }}
          />
        );
      })}
    </span>
  );
}

interface ClaimRowProps {
  text: ReactNode;
  citations: readonly Citation[];
  focus: EvidenceFocus;
}

/** A claim, its chips, and a separate toggle revealing the cited evidence in place (§6.4). */
function ClaimRow({ text, citations, focus }: ClaimRowProps) {
  const [open, setOpen] = useState(false);
  const id = useId();
  return (
    <div className="py-1">
      <div className="grid grid-cols-[minmax(0,1fr)_auto_24px] items-start gap-3">
        <div className="pt-0.5">{text}</div>
        <Chips citations={citations} focus={focus} />
        {citations.length > 0 ? (
          <button
            type="button"
            aria-expanded={open}
            aria-controls={id}
            aria-label={open ? "Hide cited evidence" : "Show cited evidence"}
            onClick={() => {
              setOpen((v) => !v);
            }}
            className="inline-grid size-6 cursor-pointer place-items-center rounded-control text-text-muted hover:bg-surface-sunken hover:text-text"
          >
            <ChevronDown
              size={16}
              aria-hidden="true"
              className={`transition-transform duration-150 ${open ? "rotate-180" : ""}`}
            />
          </button>
        ) : (
          <span />
        )}
      </div>
      {open && (
        <ul id={id} className="my-1 ml-0 border-l-2 border-border py-1 pl-3">
          {citations.map((c) => {
            const item = focus.byId.get(c.evidence_id);
            return (
              <li
                key={c.evidence_id}
                className="grid grid-cols-[32px_minmax(0,1fr)_auto] gap-2 text-data"
              >
                <span className="data font-medium">{c.label}</span>
                <span>
                  {item === undefined ? "Not in the first evidence page." : evidenceSummary(item)}
                </span>
                {item !== undefined && (
                  <span className="text-text-muted">
                    {item.component?.key ?? ""}{" "}
                    <Timestamp iso={evidenceTime(item)} suffix={false} />
                  </span>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="grid grid-cols-[112px_minmax(0,1fr)] gap-4 border-t border-border px-4 py-3 first:border-t-0 max-md:grid-cols-1">
      <h3 className="pt-1 text-data font-semibold">{title}</h3>
      <div>{children}</div>
    </section>
  );
}

function claims(list: readonly Claim[], focus: EvidenceFocus) {
  return list.map((claim, index) => (
    <ClaimRow key={index} text={claim.text} citations={claim.evidence} focus={focus} />
  ));
}

/** Facts, hypotheses, checks and limits, each styled apart (§6.4). */
export function DiagnosisBody({
  diagnostic,
  focus,
}: {
  diagnostic: Diagnostic;
  focus: EvidenceFocus;
}) {
  return (
    <div>
      <Section title="Facts">{claims(diagnostic.observed_facts, focus)}</Section>
      <Section title="Hypotheses">
        {diagnostic.hypotheses.map((h, index) => (
          <ClaimRow
            key={index}
            focus={focus}
            citations={h.evidence}
            text={
              <>
                <em>{h.text}</em>
                <span className="ml-1.5 inline-block rounded-[3px] border border-border px-1.5 text-small text-text-muted not-italic">
                  Uncertainty: {h.uncertainty}
                </span>
              </>
            }
          />
        ))}
      </Section>
      <Section title="Checks">
        <ol className="list-none">
          {diagnostic.recommended_checks.map((check, index) => (
            <li key={index} className="grid grid-cols-[20px_minmax(0,1fr)] gap-2">
              <span className="data pt-1.5 text-right text-text-muted">{index + 1}</span>
              <ClaimRow text={check.text} citations={check.evidence} focus={focus} />
            </li>
          ))}
        </ol>
      </Section>
      <Section title="Limitations">
        <ul className="border-l-2 border-border-strong bg-surface-sunken/50 px-3 py-2 text-text-muted">
          {diagnostic.limitations.map((limit, index) => (
            <li key={index}>{limit}</li>
          ))}
        </ul>
      </Section>
      {diagnostic.validation.removed.length > 0 && (
        <Section title="Removed">
          <p className="text-small text-text-muted">Unsupported by evidence:</p>
          <ul className="list-disc pl-5 text-text-muted">
            {diagnostic.validation.removed.map((text, index) => (
              <li key={index}>{text}</li>
            ))}
          </ul>
        </Section>
      )}
    </div>
  );
}
