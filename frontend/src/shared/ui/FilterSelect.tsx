import { useId } from "react";
import { humanize } from "@/shared/format/labels";

interface FilterSelectProps<T extends string> {
  label: string;
  value: T | "";
  options: readonly T[];
  onChange: (value: T | "") => void;
  format?: (value: T) => string;
}

/** Native select: keyboard and screen-reader behaviour for free, value kept in the URL. */
export function FilterSelect<T extends string>({
  label,
  value,
  options,
  onChange,
  format = humanize,
}: FilterSelectProps<T>) {
  const id = useId();
  return (
    <span className="inline-flex items-center gap-2">
      <label htmlFor={id} className="text-small text-text-muted">
        {label}
      </label>
      <select
        id={id}
        name={label.toLowerCase().replaceAll(" ", "-")}
        value={value}
        onChange={(event) => {
          onChange(options.find((option) => option === event.target.value) ?? "");
        }}
        className="h-8 rounded-control border border-border-strong bg-surface px-2 text-text"
      >
        <option value="">All</option>
        {options.map((option) => (
          <option key={option} value={option}>
            {format(option)}
          </option>
        ))}
      </select>
    </span>
  );
}
