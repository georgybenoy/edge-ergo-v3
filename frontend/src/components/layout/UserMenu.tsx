import React, { useState, useRef, useEffect } from "react";
import { Link } from "react-router-dom";
import { User, LogOut, ChevronDown, Lock } from "lucide-react";
import { useAuth } from "../../features/auth/AuthContext";
import { useUserProfile } from "../../features/auth/UserProfileContext";
import { Badge } from "../ui/Badge";
import { cn } from "../../lib/utils";

export const UserMenu: React.FC = () => {
  const { user, signOut } = useAuth();
  const { profile } = useUserProfile();
  const [isOpen, setIsOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  // Close on outside click or Escape
  useEffect(() => {
    const handleOutsideClick = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        setIsOpen(false);
      }
    };

    document.addEventListener("mousedown", handleOutsideClick);
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("mousedown", handleOutsideClick);
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen]);

  const email = profile?.email || user?.email || "user@edgeergo.local";
  const initials = email.charAt(0).toUpperCase();
  const role = profile?.role || "reviewer";

  return (
    <div className="relative" ref={menuRef}>
      <button
        onClick={() => setIsOpen((prev) => !prev)}
        aria-expanded={isOpen}
        aria-haspopup="menu"
        aria-label="User account menu"
        className={cn(
          "flex items-center gap-2.5 p-1.5 rounded-control text-text-secondary hover:text-text-primary hover:bg-surface-raised",
          "min-h-[44px] min-w-[44px] transition-colors duration-150",
          "focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none",
          isOpen && "bg-surface-raised text-text-primary"
        )}
      >
        <div className="w-8 h-8 rounded-full bg-accent/20 border border-accent/40 text-accent font-semibold flex items-center justify-center text-xs select-none">
          {initials}
        </div>
        <div className="hidden md:flex flex-col text-left">
          <span className="text-xs font-medium text-text-primary max-w-[130px] truncate">
            {email}
          </span>
          <span className="text-[10px] text-text-muted capitalize">
            {role}
          </span>
        </div>
        <ChevronDown className={cn("w-3.5 h-3.5 text-text-muted transition-transform", isOpen && "rotate-180")} />
      </button>

      {isOpen && (
        <div
          role="menu"
          aria-label="Account options"
          className={cn(
            "absolute right-0 mt-2 w-64 rounded-card bg-surface-raised border border-border shadow-2xl p-2 z-50",
            "animate-in fade-in zoom-in-95 duration-100 motion-reduce:animate-none"
          )}
        >
          {/* Identity header */}
          <div className="px-3 py-2.5 border-b border-border/70 mb-1">
            <p className="text-xs text-text-muted">Signed in as</p>
            <p className="text-sm font-semibold text-text-primary truncate">{email}</p>
            <div className="mt-2 flex items-center gap-2">
              <Badge
                variant={role === "admin" ? "accent" : "neutral"}
                label={role === "admin" ? "Organization Admin" : "Reviewer"}
                className="text-[11px]"
              />
            </div>
          </div>

          <div className="py-1">
            <Link
              to="/settings"
              onClick={() => setIsOpen(false)}
              role="menuitem"
              className="flex items-center gap-2.5 px-3 py-2 text-xs font-medium text-text-secondary hover:text-text-primary hover:bg-surface rounded-control min-h-[44px]"
            >
              <User className="w-4 h-4 text-text-muted" />
              <span>Account Settings</span>
            </Link>

            <Link
              to="/settings#privacy"
              onClick={() => setIsOpen(false)}
              role="menuitem"
              className="flex items-center gap-2.5 px-3 py-2 text-xs font-medium text-text-secondary hover:text-text-primary hover:bg-surface rounded-control min-h-[44px]"
            >
              <Lock className="w-4 h-4 text-text-muted" />
              <span>Privacy & Data Transparency</span>
            </Link>
          </div>

          <div className="pt-1 border-t border-border/70 mt-1">
            <button
              onClick={() => {
                setIsOpen(false);
                signOut();
              }}
              role="menuitem"
              className="w-full flex items-center gap-2.5 px-3 py-2 text-xs font-medium text-danger hover:bg-danger/10 rounded-control min-h-[44px] transition-colors"
            >
              <LogOut className="w-4 h-4" />
              <span>Sign out</span>
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
