interface EvidenceChipProps {
  label: string;
  description: string;
  pressed: boolean;
  onToggle: () => void;
}

/** P3 signature: a citation that highlights its evidence row (and chart point) when pressed. */
export function EvidenceChip({ label, description, pressed, onToggle }: EvidenceChipProps) {
  return (
    <button
      type="button"
      aria-pressed={pressed}
      aria-label={`Evidence ${label}: ${description}`}
      title={description}
      onClick={onToggle}
      className="inline-flex h-5 cursor-pointer items-center rounded-[3px] border border-border-strong bg-surface px-1.5 font-mono text-small font-medium text-text hover:border-accent hover:bg-highlight hover:text-accent aria-pressed:border-accent aria-pressed:bg-highlight aria-pressed:text-accent"
    >
      {label}
    </button>
  );
}
