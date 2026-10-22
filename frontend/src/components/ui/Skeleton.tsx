import React from "react";
import { cn } from "../../lib/utils";

export interface SkeletonProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "rect" | "circle" | "text";
}

export const Skeleton: React.FC<SkeletonProps> = ({
  className,
  variant = "rect",
  ...props
}) => {
  const variantStyles = {
    rect: "rounded-control",
    circle: "rounded-full",
    text: "rounded h-4 w-full",
  };

  return (
    <div
      className={cn(
        "bg-surface-muted animate-pulse motion-reduce:animate-none",
        variantStyles[variant],
        className
      )}
      aria-hidden="true"
      {...props}
    />
  );
};
