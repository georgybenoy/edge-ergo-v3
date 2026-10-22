import React from "react";
import { Calendar } from "lucide-react";
import { cn } from "../../lib/utils";

export type DateRangePreset = "today" | "7d" | "30d" | "90d";

export interface DateRangeControlProps {
  value: DateRangePreset;
  onChange: (preset: DateRangePreset) => void;
  className?: string;
}

export const DateRangeControl: React.FC<DateRangeControlProps> = ({
  value,
  onChange,
  className,
}) => {
  const options: { id: DateRangePreset; label: string }[] = [
    { id: "today", label: "Today" },
    { id: "7d", label: "7 Days" },
    { id: "30d", label: "30 Days" },
    { id: "90d", label: "90 Days" },
  ];

  return (
    <div
      role="group"
      aria-label="Filter date range"
      className={cn(
        "inline-flex items-center p-1 rounded-control bg-surface-muted border border-border select-none",
        className
      )}
    >
      <div className="px-2 text-text-muted hidden sm:flex items-center" aria-hidden="true">
        <Calendar className="w-4 h-4" />
      </div>
      <div className="flex gap-1">
        {options.map((opt) => {
          const isActive = value === opt.id;
          return (
            <button
              key={opt.id}
              onClick={() => onChange(opt.id)}
              aria-pressed={isActive}
              className={cn(
                "px-3 py-1.5 text-xs font-medium rounded min-h-[36px] min-w-[44px] transition-colors",
                "focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none",
                isActive
                  ? "bg-accent text-white shadow-xs"
                  : "text-text-secondary hover:text-text-primary hover:bg-surface-raised"
              )}
            >
              {opt.label}
            </button>
          );
        })}
      </div>
    </div>
  );
};
