import React from "react";
import { cn } from "../../lib/utils";

export interface Column<T> {
  key: string;
  header: string;
  render?: (item: T) => React.ReactNode;
  className?: string;
}

export interface TableProps<T> {
  columns: Column<T>[];
  data: T[];
  keyExtractor: (item: T) => string;
  loading?: boolean;
  emptyState?: React.ReactNode;
  className?: string;
}

export function Table<T>({
  columns,
  data,
  keyExtractor,
  loading = false,
  emptyState,
  className,
}: TableProps<T>): React.ReactElement {
  if (loading) {
    return (
      <div className="w-full space-y-2">
        <div className="h-10 bg-surface-muted rounded-control animate-pulse motion-reduce:animate-none" />
        <div className="h-14 bg-surface-muted/60 rounded-control animate-pulse motion-reduce:animate-none" />
        <div className="h-14 bg-surface-muted/60 rounded-control animate-pulse motion-reduce:animate-none" />
      </div>
    );
  }

  if (data.length === 0 && emptyState) {
    return <div className="py-6">{emptyState}</div>;
  }

  return (
    <div className={cn("w-full overflow-hidden", className)}>
      {/* Desktop / Tablet Semantic Table */}
      <div className="hidden sm:block overflow-x-auto rounded-control border border-border bg-surface">
        <table className="w-full text-left border-collapse text-sm">
          <thead>
            <tr className="border-b border-border bg-surface-raised text-text-secondary text-xs uppercase tracking-wider">
              {columns.map((col) => (
                <th key={col.key} scope="col" className={cn("px-4 py-3 font-semibold", col.className)}>
                  {col.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {data.map((item) => (
              <tr
                key={keyExtractor(item)}
                className="hover:bg-surface-raised/50 transition-colors motion-reduce:transition-none"
              >
                {columns.map((col) => (
                  <td key={col.key} className={cn("px-4 py-3.5 text-text-primary", col.className)}>
                    {col.render ? col.render(item) : (item as Record<string, unknown>)[col.key] as React.ReactNode}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Mobile Responsive Cards Fallback */}
      <div className="sm:hidden flex flex-col gap-3">
        {data.map((item) => (
          <div
            key={keyExtractor(item)}
            className="p-4 rounded-card border border-border bg-surface flex flex-col gap-2"
          >
            {columns.map((col) => (
              <div key={col.key} className="flex justify-between items-center text-xs">
                <span className="text-text-muted font-medium">{col.header}</span>
                <span className="text-text-primary text-right font-medium">
                  {col.render ? col.render(item) : (item as Record<string, unknown>)[col.key] as React.ReactNode}
                </span>
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
