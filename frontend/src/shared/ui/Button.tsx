import type { ButtonHTMLAttributes, ReactNode } from "react";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "default" | "primary" | "quiet";
  icon?: ReactNode;
}

const VARIANT = {
  default: "border-border-strong bg-surface text-text hover:bg-surface-sunken",
  primary: "border-accent bg-accent text-surface hover:brightness-95",
  quiet:
    "border-transparent bg-transparent text-text-muted hover:bg-surface-sunken hover:text-text",
} as const;

export function Button({
  variant = "default",
  icon,
  children,
  className = "",
  type = "button",
  ...rest
}: ButtonProps) {
  return (
    <button
      type={type}
      className={`inline-flex h-8 cursor-pointer items-center gap-1.5 rounded-control border px-3 font-medium whitespace-nowrap disabled:cursor-not-allowed disabled:border-border disabled:bg-surface disabled:text-text-muted ${VARIANT[variant]} ${className}`}
      {...rest}
    >
      {icon}
      {children}
    </button>
  );
}
