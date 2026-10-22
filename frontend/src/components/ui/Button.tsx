import React, { forwardRef } from "react";
import { Loader2 } from "lucide-react";
import { cn } from "../../lib/utils";

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "outline" | "danger" | "ghost";
  size?: "sm" | "md" | "lg";
  loading?: boolean;
  icon?: React.ReactNode;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      className,
      variant = "primary",
      size = "md",
      loading = false,
      disabled,
      icon,
      children,
      ...props
    },
    ref
  ) => {
    const baseStyles =
      "inline-flex items-center justify-center font-medium rounded-control transition-colors duration-150 " +
      "min-h-[44px] min-w-[44px] px-4 py-2 text-sm select-none " +
      "focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none focus-visible:ring-offset-2 focus-visible:ring-offset-bg " +
      "disabled:opacity-50 disabled:cursor-not-allowed motion-reduce:transition-none";

    const variantStyles = {
      primary:
        "bg-accent text-white hover:bg-accent-strong active:bg-accent-strong shadow-sm",
      secondary:
        "bg-surface-raised text-text-primary hover:bg-surface-muted active:bg-surface-muted border border-border",
      outline:
        "bg-transparent text-text-primary hover:bg-surface-raised active:bg-surface-muted border border-border",
      danger:
        "bg-danger text-white hover:opacity-90 active:opacity-80 shadow-sm",
      ghost:
        "bg-transparent text-text-secondary hover:text-text-primary hover:bg-surface-raised active:bg-surface-muted",
    };

    const sizeStyles = {
      sm: "min-h-[38px] px-3 py-1.5 text-xs",
      md: "min-h-[44px] px-4 py-2 text-sm",
      lg: "min-h-[48px] px-6 py-2.5 text-base",
    };

    return (
      <button
        ref={ref}
        disabled={disabled || loading}
        className={cn(baseStyles, variantStyles[variant], sizeStyles[size], className)}
        {...props}
      >
        {loading ? (
          <Loader2 className="w-4 h-4 mr-2 animate-spin motion-reduce:animate-none" aria-hidden="true" />
        ) : icon ? (
          <span className="mr-2 inline-flex items-center" aria-hidden="true">
            {icon}
          </span>
        ) : null}
        {children}
      </button>
    );
  }
);

Button.displayName = "Button";
