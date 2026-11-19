import { useT } from "@/shared/i18n/context";
import { Copy } from "@carbon/icons-react";
import { useState } from "react";

const COPIED_FEEDBACK_MS = 2000;

/** Icon button copying an identifier, with a polite "Copied" confirmation. */
export function CopyButton({ value, label }: { value: string; label: string }) {
  const t = useT();
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    await navigator.clipboard.writeText(value);
    setCopied(true);
    window.setTimeout(() => {
      setCopied(false);
    }, COPIED_FEEDBACK_MS);
  };
  return (
    <>
      <button
        type="button"
        aria-label={label}
        onClick={() => void copy()}
        className="inline-grid size-6 cursor-pointer place-items-center rounded-control text-text-muted hover:bg-surface-sunken hover:text-text"
      >
        <Copy size={16} aria-hidden="true" />
      </button>
      <span aria-live="polite" className="text-small text-text-muted">
        {copied ? t("Copied") : ""}
      </span>
    </>
  );
}
