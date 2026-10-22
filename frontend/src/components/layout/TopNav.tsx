import React, { useState, useEffect, useRef } from "react";
import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  Activity,
  Laptop,
  FileSpreadsheet,
  Settings,
  Menu,
  X,
} from "lucide-react";
import { UserMenu } from "./UserMenu";
import { useUserProfile } from "../../features/auth/UserProfileContext";
import { cn } from "../../lib/utils";
import { DevFixtureToggle } from "../../lib/devFixtures";

export const TopNav: React.FC = () => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const drawerRef = useRef<HTMLDivElement>(null);
  const { profile } = useUserProfile();

  const allNavItems = [
    { to: "/", label: "Overview", icon: <LayoutDashboard className="w-4 h-4" /> },
    { to: "/assessments", label: "Assessments", icon: <Activity className="w-4 h-4" /> },
    { to: "/devices", label: "Devices", icon: <Laptop className="w-4 h-4" />, adminOnly: true },
    { to: "/reports", label: "Reports", icon: <FileSpreadsheet className="w-4 h-4" /> },
    { to: "/settings", label: "Settings", icon: <Settings className="w-4 h-4" /> },
  ];

  const navItems = allNavItems.filter((item) => !item.adminOnly || profile?.role === "admin");

  // Mobile drawer focus trap & Escape key
  useEffect(() => {
    if (!mobileMenuOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setMobileMenuOpen(false);
      } else if (e.key === "Tab" && drawerRef.current) {
        const focusables = drawerRef.current.querySelectorAll<HTMLElement>(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        );
        if (focusables.length === 0) return;
        const first = focusables[0];
        const last = focusables[focusables.length - 1];

        if (first && last) {
          if (e.shiftKey && document.activeElement === first) {
            e.preventDefault();
            last.focus();
          } else if (!e.shiftKey && document.activeElement === last) {
            e.preventDefault();
            first.focus();
          }
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [mobileMenuOpen]);

  return (
    <header className="sticky top-0 z-40 w-full border-b border-border bg-bg/95 backdrop-blur-md">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between gap-4">
        {/* Brand Logo */}
        <div className="flex items-center gap-3">
          <button
            onClick={() => setMobileMenuOpen((open) => !open)}
            aria-expanded={mobileMenuOpen}
            aria-label={mobileMenuOpen ? "Close navigation menu" : "Open navigation menu"}
            className="md:hidden text-text-secondary hover:text-text-primary p-2 min-h-[44px] min-w-[44px] flex items-center justify-center rounded-control focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none"
          >
            {mobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
          </button>

          <NavLink
            to="/"
            className="flex items-center gap-2.5 focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none rounded-control p-1"
          >
            <div className="w-8 h-8 rounded-control bg-accent flex items-center justify-center text-white shadow-md">
              <span className="font-bold text-sm tracking-wider">E</span>
            </div>
            <span className="text-base font-bold text-text-primary tracking-tight">
              Edge<span className="text-accent">Ergo</span>
            </span>
          </NavLink>
        </div>

        {/* Desktop / Tablet Horizontal Navigation */}
        <nav
          aria-label="Primary navigation"
          className="hidden md:flex items-center gap-1 lg:gap-2"
        >
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-2 px-3.5 py-2 text-sm font-medium rounded-control min-h-[44px] transition-colors duration-150",
                  "focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none",
                  isActive
                    ? "bg-surface-raised text-accent font-semibold border border-border"
                    : "text-text-secondary hover:text-text-primary hover:bg-surface"
                )
              }
            >
              <span aria-hidden="true">{item.icon}</span>
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>

        {/* Right side affordances */}
        <div className="flex items-center gap-3">
          <DevFixtureToggle />
          <UserMenu />
        </div>
      </div>

      {/* Mobile Navigation Drawer */}
      {mobileMenuOpen && (
        <div
          className="md:hidden fixed inset-0 top-16 z-50 bg-black/80 backdrop-blur-xs flex flex-col"
          role="dialog"
          aria-modal="true"
          aria-label="Mobile navigation"
          ref={drawerRef}
        >
          <div className="bg-surface border-b border-border p-4 flex flex-col gap-2">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === "/"}
                onClick={() => setMobileMenuOpen(false)}
                className={({ isActive }) =>
                  cn(
                    "flex items-center gap-3 px-4 py-3 rounded-control text-sm font-medium min-h-[44px]",
                    "focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none",
                    isActive
                      ? "bg-surface-raised text-accent font-semibold border border-border"
                      : "text-text-secondary hover:text-text-primary hover:bg-surface-muted"
                  )
                }
              >
                <span aria-hidden="true">{item.icon}</span>
                <span>{item.label}</span>
              </NavLink>
            ))}
          </div>
          <div
            className="flex-1"
            onClick={() => setMobileMenuOpen(false)}
            aria-hidden="true"
          />
        </div>
      )}
    </header>
  );
};
