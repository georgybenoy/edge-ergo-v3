import React from "react";
import { TopNav } from "./TopNav";
import { DevFixtureBanner } from "../../lib/devFixtures";
import { cn } from "../../lib/utils";

export interface AppShellProps {
  children: React.ReactNode;
  banner?: React.ReactNode;
  className?: string;
}

export const AppShell: React.FC<AppShellProps> = ({ children, banner, className }) => {
  return (
    <div className="min-h-screen bg-bg text-text-primary flex flex-col selection:bg-accent/30 selection:text-white">
      {/* Accessible skip link */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50 focus:p-3 focus:bg-accent focus:text-white focus:rounded-control focus:outline-none focus:ring-2 focus:ring-white"
      >
        Skip to main content
      </a>

      {/* Persistent dev fixture banner (DEV only) */}
      <DevFixtureBanner />

      {/* Navigation Bar */}
      <TopNav />

      {/* System alert / banner slot */}
      {banner && <div className="max-w-7xl mx-auto w-full px-4 sm:px-6 lg:px-8 pt-4">{banner}</div>}

      {/* Main Content Area */}
      <main
        id="main-content"
        tabIndex={-1}
        className={cn("flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-8 outline-none", className)}
      >
        {children}
      </main>

      {/* Footer */}
      <footer className="border-t border-border/60 py-6 px-4 sm:px-6 lg:px-8 bg-surface/50 text-xs text-text-muted">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-3 text-center sm:text-left">
          <p>
            EdgeErgo V3 &bull; Privacy-Preserving Ergonomic Assessment Platform.
          </p>
          <p className="max-w-md">
            Screening indicator and practical guide only; not a medical diagnostic tool or employee evaluation system.
          </p>
        </div>
      </footer>
    </div>
  );
};
