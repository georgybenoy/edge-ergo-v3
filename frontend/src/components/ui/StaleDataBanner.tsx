import React from "react";
import { Clock, RefreshCw } from "lucide-react";
import { cn } from "../../lib/utils";

export interface StaleDataBannerProps {
  lastUpdated: Date | string | null;
  onRefresh?: () => void;
  className?: string;
}

export const StaleDataBanner: React.FC<StaleDataBannerProps> = ({
  lastUpdated,
  onRefresh,
  className,
}) => {
  const formattedTime =
    lastUpdated instanceof Date
      ? lastUpdated.toLocaleTimeString()
      : typeof lastUpdated === "string"
        ? new Date(lastUpdated).toLocaleTimeString()
        : "Unknown";

  return (
    <aside
      aria-label="Data freshness notice"
      className={cn(
        "flex flex-wrap items-center justify-between gap-3 px-4 py-2.5 rounded-control bg-[#221c10] border border-[#4d3a17] text-warning text-xs sm:text-sm select-none",
        className
      )}
    >
      <div className="flex items-center gap-2">
        <Clock className="w-4 h-4 shrink-0" aria-hidden="true" />
        <span>
          Data may be delayed. Last synchronized with telemetry service at <strong>{formattedTime}</strong>.
        </span>
      </div>
      {onRefresh && (
        <button
          onClick={onRefresh}
          className="inline-flex items-center gap-1 font-medium underline underline-offset-2 hover:opacity-80 focus-visible:ring-2 focus-visible:ring-warning focus-visible:outline-none rounded px-1 min-h-[32px]"
        >
          <RefreshCw className="w-3.5 h-3.5" aria-hidden="true" />
          Refresh now
        </button>
      )}
    </aside>
  );
};
