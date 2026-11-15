interface SegmentedProps<T extends string> {
  label: string;
  options: readonly { value: T; label: string }[];
  value: T;
  onChange: (value: T) => void;
}

/** Exclusive choice among few options (time window, metric), as toggle buttons. */
export function Segmented<T extends string>({
  label,
  options,
  value,
  onChange,
}: SegmentedProps<T>) {
  return (
    <div
      role="group"
      aria-label={label}
      className="inline-flex overflow-hidden rounded-control border border-border-strong"
    >
      {options.map((option, index) => (
        <button
          key={option.value}
          type="button"
          aria-pressed={option.value === value}
          onClick={() => {
            onChange(option.value);
          }}
          className={`h-6 cursor-pointer px-2 font-mono text-small font-medium text-text-muted aria-pressed:bg-surface-sunken aria-pressed:text-text ${
            index > 0 ? "border-l border-border" : ""
          }`}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}
