import React from "react";
import { cn } from "../../lib/utils";

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "default" | "raised" | "muted" | "accent";
}

export const Card: React.FC<CardProps> = ({
  className,
  variant = "default",
  children,
  ...props
}) => {
  const variantStyles = {
    default: "bg-surface border-border",
    raised: "bg-surface-raised border-border",
    muted: "bg-surface-muted border-border",
    accent: "bg-[#13111c] border-[#342759]",
  };

  return (
    <div
      className={cn(
        "rounded-card border p-4 sm:p-5 md:p-6 transition-colors shadow-sm",
        variantStyles[variant],
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
};
