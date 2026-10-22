/* eslint-disable react-refresh/only-export-components */
import React, { createContext, useContext, useState, useEffect } from "react";
export * from "./devFixtureData";

interface DevFixtureContextType {
  isDevFixtureActive: boolean;
  toggleDevFixture: () => void;
  setDevFixtureActive: (active: boolean) => void;
}

const DevFixtureContext = createContext<DevFixtureContextType>({
  isDevFixtureActive: false,
  toggleDevFixture: () => {},
  setDevFixtureActive: () => {},
});

const DEV_STORAGE_KEY = "edge_ergo_dev_fixture_active";

export const DevFixtureProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  // If compiled for production, Dev Fixtures are completely disabled
  if (!import.meta.env.DEV) {
    return <>{children}</>;
  }

  // eslint-disable-next-line react-hooks/rules-of-hooks
  const [active, setActive] = useState<boolean>(() => {
    return localStorage.getItem(DEV_STORAGE_KEY) === "true";
  });

  // eslint-disable-next-line react-hooks/rules-of-hooks
  useEffect(() => {
    localStorage.setItem(DEV_STORAGE_KEY, String(active));
  }, [active]);

  const toggleDevFixture = () => setActive((prev) => !prev);

  return (
    <DevFixtureContext.Provider
      value={{
        isDevFixtureActive: active,
        toggleDevFixture,
        setDevFixtureActive: setActive,
      }}
    >
      {children}
    </DevFixtureContext.Provider>
  );
};

export function useDevFixture(): DevFixtureContextType {
  return useContext(DevFixtureContext);
}

/**
 * Persistent banner displayed whenever development fixture data is active.
 * Only rendered in DEV mode.
 */
export const DevFixtureBanner: React.FC = () => {
  if (!import.meta.env.DEV) {
    return null;
  }

  // eslint-disable-next-line react-hooks/rules-of-hooks
  const { isDevFixtureActive, toggleDevFixture } = useDevFixture();

  if (!isDevFixtureActive) {
    return null;
  }

  return (
    <div
      role="status"
      className="bg-amber-950/90 border-b border-amber-500/50 text-amber-200 px-4 py-2 text-xs flex flex-wrap items-center justify-between gap-3 shadow-sm"
    >
      <div className="flex items-center gap-2 font-mono font-bold tracking-wide">
        <span className="text-amber-400">⚠️</span>
        <span>DEVELOPMENT FIXTURE DATA</span>
        <span className="hidden sm:inline font-normal text-amber-300/80 lowercase">
          (simulated local contract fixtures enabled)
        </span>
      </div>
      <button
        onClick={toggleDevFixture}
        className="px-2.5 py-1 text-xs font-medium rounded border border-amber-500/60 bg-amber-900/50 hover:bg-amber-800 text-amber-100 transition-colors focus:outline-none focus:ring-1 focus:ring-amber-400"
      >
        Switch to Live API
      </button>
    </div>
  );
};

/**
 * Developer toggle button for switching between Live API and Development Fixtures.
 * Tree-shaken out in production.
 */
export const DevFixtureToggle: React.FC = () => {
  if (!import.meta.env.DEV) {
    return null;
  }

  // eslint-disable-next-line react-hooks/rules-of-hooks
  const { isDevFixtureActive, toggleDevFixture } = useDevFixture();

  return (
    <button
      type="button"
      onClick={toggleDevFixture}
      className={`text-xs px-2.5 py-1 rounded font-mono border transition-all ${
        isDevFixtureActive
          ? "bg-amber-500/20 text-amber-300 border-amber-500/50 hover:bg-amber-500/30"
          : "bg-surface-elevated text-text-muted border-border hover:text-text-primary"
      }`}
      title="Toggle development fixture data mode (Local only)"
      aria-pressed={isDevFixtureActive}
    >
      {isDevFixtureActive ? "Fixtures: ON" : "Fixtures: OFF"}
    </button>
  );
};
