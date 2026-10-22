import React from "react";
import { CheckCircle2, AlertTriangle, XCircle, Info, ShieldCheck } from "lucide-react";
import { cn } from "../../lib/utils";

export type BadgeVariant = "success" | "warning" | "danger" | "neutral" | "accent";

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
  icon?: React.ReactNode;
  label: string;
}

export const Badge: React.FC<BadgeProps> = ({
  variant = "neutral",
  icon,
  label,
  className,
  ...props
}) => {
  const defaultIcons: Record<BadgeVariant, React.ReactNode> = {
    success: <CheckCircle2 className="w-3.5 h-3.5" aria-hidden="true" />,
    warning: <AlertTriangle className="w-3.5 h-3.5" aria-hidden="true" />,
    danger: <XCircle className="w-3.5 h-3.5" aria-hidden="true" />,
    neutral: <Info className="w-3.5 h-3.5" aria-hidden="true" />,
    accent: <ShieldCheck className="w-3.5 h-3.5" aria-hidden="true" />,
  };

  const variantStyles: Record<BadgeVariant, string> = {
    success: "bg-[#182613] text-success border border-[#2d471b]",
    warning: "bg-[#2b1f0c] text-warning border border-[#4d3714]",
    danger: "bg-[#2d1210] text-danger border border-[#52201d]",
    neutral: "bg-surface-muted text-text-secondary border border-border",
    accent: "bg-[#1f1738] text-accent border border-[#3b2b6b]",
  };

  const chosenIcon = icon !== undefined ? icon : defaultIcons[variant];

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium select-none",
        variantStyles[variant],
        className
      )}
      {...props}
    >
      {chosenIcon && <span className="inline-flex shrink-0">{chosenIcon}</span>}
      <span>{label}</span>
    </span>
  );
};

export const StatusPill = Badge;
