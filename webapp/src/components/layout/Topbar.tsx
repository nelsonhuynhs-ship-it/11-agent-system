"use client";

import { useState, useEffect, useRef } from "react";

interface TopbarProps {
  onMenuClick?: () => void;
}

export default function Topbar({ onMenuClick }: TopbarProps) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [loggingOut, setLoggingOut] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  // Close menu on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  // Multi-tab logout: listen for storage event
  useEffect(() => {
    function handleStorage(e: StorageEvent) {
      if (e.key === "logout-event") {
        window.location.href = "/login";
      }
    }
    window.addEventListener("storage", handleStorage);
    return () => window.removeEventListener("storage", handleStorage);
  }, []);

  async function handleLogout() {
    setLoggingOut(true);
    try {
      await fetch("/api/auth/logout", { method: "POST" });
      // Signal other tabs to logout
      localStorage.setItem("logout-event", Date.now().toString());
      localStorage.removeItem("logout-event");
      window.location.href = "/login";
    } catch {
      // Force redirect even if API fails
      window.location.href = "/login";
    }
  }

  return (
    <header className="fixed top-0 left-0 lg:left-[220px] right-0 z-30 h-14 bg-surface/80 backdrop-blur-md border-b border-border flex items-center justify-between px-4 sm:px-6">
      <div className="flex items-center gap-3">
        {/* Hamburger Menu (mobile only) */}
        <button onClick={onMenuClick} className="lg:hidden p-1.5 rounded-lg hover:bg-surface-hover cursor-pointer">
          <svg className="w-5 h-5 text-text-secondary" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
            <path d="M4 6h16M4 12h16M4 18h16" strokeLinecap="round" />
          </svg>
        </button>

        {/* Search (hidden on mobile) */}
        <div className="relative w-72 hidden sm:block">
          <SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
          <input
            type="text"
            placeholder="Search rates, customers, shipments..."
            className="input pl-10 !py-1.5 !text-[13px] !bg-background"
          />
        </div>
      </div>

      {/* Right side */}
      <div className="flex items-center gap-3">
        <button className="btn-primary !text-xs !py-1.5 !px-3">
          + New Quote
        </button>

        {/* Notifications */}
        <button className="relative p-2 rounded-lg hover:bg-surface-hover transition-colors cursor-pointer">
          <BellIcon className="w-[18px] h-[18px] text-text-secondary" />
          <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-danger" />
        </button>

        {/* Divider */}
        <div className="w-px h-6 bg-border" />

        {/* User Menu */}
        <div className="relative" ref={menuRef}>
          <button
            onClick={() => setMenuOpen(!menuOpen)}
            className="flex items-center gap-2 cursor-pointer rounded-lg px-2 py-1.5 hover:bg-surface-hover transition-colors"
          >
            <div className="w-8 h-8 rounded-full bg-accent/10 flex items-center justify-center">
              <span className="text-xs font-bold text-accent">SN</span>
            </div>
            <div className="hidden sm:block text-left">
              <p className="text-xs font-semibold text-text leading-none">Nelson</p>
              <p className="text-[10px] text-text-muted">Admin</p>
            </div>
            <ChevronIcon className={`w-3.5 h-3.5 text-text-muted transition-transform ${menuOpen ? "rotate-180" : ""}`} />
          </button>

          {/* Dropdown Menu */}
          {menuOpen && (
            <div className="absolute right-0 top-full mt-1.5 w-48 py-1.5 bg-surface rounded-xl border border-border shadow-lg shadow-black/8 z-50">
              <div className="px-3.5 py-2.5 border-b border-border">
                <p className="text-xs font-semibold text-text">Nelson</p>
                <p className="text-[10px] text-text-muted mt-0.5">Admin · nelson</p>
              </div>
              <div className="py-1">
                <button
                  onClick={handleLogout}
                  disabled={loggingOut}
                  className="w-full text-left px-3.5 py-2 text-xs text-danger hover:bg-danger/5 transition-colors flex items-center gap-2 cursor-pointer disabled:opacity-50"
                >
                  <LogoutIcon className="w-3.5 h-3.5" />
                  {loggingOut ? "Signing out..." : "Sign out"}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}

function SearchIcon({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="1.75" strokeLinecap="round"
      strokeLinejoin="round" className={className}>
      <circle cx="11" cy="11" r="8" /><path d="m21 21-4.3-4.3" />
    </svg>
  );
}

function BellIcon({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="1.75" strokeLinecap="round"
      strokeLinejoin="round" className={className}>
      <path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" />
      <path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" />
    </svg>
  );
}

function ChevronIcon({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2" strokeLinecap="round"
      strokeLinejoin="round" className={className}>
      <path d="m6 9 6 6 6-6" />
    </svg>
  );
}

function LogoutIcon({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="1.75" strokeLinecap="round"
      strokeLinejoin="round" className={className}>
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
      <polyline points="16 17 21 12 16 7" />
      <line x1="21" y1="12" x2="9" y2="12" />
    </svg>
  );
}
