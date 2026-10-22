import React from "react";
import { HelpCircle } from "lucide-react";
import { Card } from "./Card";
import { cn } from "../../lib/utils";

export interface KpiCardProps {
  label: string;
  value: string | number | null;
  unit?: string;
  definition: string;
  sampleCount?: number | null;
  insufficientReason?: string | null;
  className?: string;
  icon?: React.ReactNode;
}

export const KpiCard: React.FC<KpiCardProps> = ({
  label,
  value,
  unit,
  definition,
  sampleCount,
  insufficientReason,
  className,
  icon,
}) => {
  const hasValue = value !== null && value !== undefined;

  return (
    <Card className={cn("flex flex-col justify-between relative overflow-hidden", className)}>
      <div className="flex items-center justify-between gap-2 mb-2">
        <span className="text-xs sm:text-sm font-medium text-text-secondary truncate">{label}</span>
        {icon && <span className="text-text-muted shrink-0" aria-hidden="true">{icon}</span>}
      </div>

      <div className="my-2">
        {hasValue ? (
          <div className="flex items-baseline gap-1.5">
            <span className="text-2xl sm:text-3xl md:text-4xl font-semibold tracking-tight text-text-primary tabular-nums">
              {value}
            </span>
            {unit && <span className="text-xs sm:text-sm text-text-muted font-medium">{unit}</span>}
          </div>
        ) : (
          <div className="py-1">
            <span className="text-lg sm:text-xl font-medium text-text-muted italic">
              Not enough data
            </span>
            {insufficientReason && (
              <p className="text-xs text-text-muted mt-0.5">{insufficientReason}</p>
            )}
          </div>
        )}
      </div>

      <div className="mt-2 pt-2 border-t border-border/50 flex flex-col gap-1">
        <div className="flex items-start gap-1 text-xs text-text-muted">
          <HelpCircle className="w-3.5 h-3.5 mt-0.5 shrink-0" aria-hidden="true" />
          <span>{definition}</span>
        </div>
        {sampleCount !== undefined && sampleCount !== null && (
          <span className="text-[11px] text-text-muted pl-4">
            Sample size: {sampleCount.toLocaleString()} observations
          </span>
        )}
      </div>
    </Card>
  );
};
