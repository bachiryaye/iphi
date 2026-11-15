import { type ReactNode, useId, useState } from "react";

interface TooltipProps {
  content: ReactNode;
  children: ReactNode;
  /** Wraps a non-interactive element so keyboard users can reach the tooltip too. */
  focusable?: boolean;
  className?: string;
}

/** Hover and focus tooltip (design system §6.1); it enriches, never holds the only copy. */
export function Tooltip({ content, children, focusable = false, className = "" }: TooltipProps) {
  const id = useId();
  const [open, setOpen] = useState(false);
  const show = () => {
    setOpen(true);
  };
  const hide = () => {
    setOpen(false);
  };
  // WCAG 1.4.13: the tooltip must be reachable by keyboard, so its trigger takes focus.
  /* eslint-disable jsx-a11y/no-static-element-interactions, jsx-a11y/no-noninteractive-tabindex */
  return (
    <span
      className={`relative inline-flex ${className}`}
      tabIndex={focusable ? 0 : undefined}
      aria-describedby={open ? id : undefined}
      onMouseEnter={show}
      onMouseLeave={hide}
      onFocus={show}
      onBlur={hide}
      onKeyDown={(event) => {
        if (event.key === "Escape") hide();
      }}
    >
      {children}
      {open && (
        <span
          role="tooltip"
          id={id}
          className="absolute top-full left-0 z-20 mt-1.5 w-max max-w-80 rounded-control border border-border bg-surface px-3 py-2 text-left text-small font-normal text-text shadow-float"
        >
          {content}
        </span>
      )}
    </span>
  );
  /* eslint-enable jsx-a11y/no-static-element-interactions, jsx-a11y/no-noninteractive-tabindex */
}
