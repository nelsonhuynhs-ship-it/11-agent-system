"use client";

import { useState } from "react";
import Sidebar from "@/components/layout/Sidebar";
import Topbar from "@/components/layout/Topbar";
import DataFreshnessBanner from "@/components/layout/DataFreshnessBanner";
import BottomNav from "@/components/layout/BottomNav";
import ErrorBoundary from "@/components/ui/ErrorBoundary";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="min-h-screen bg-background transition-colors">
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <Topbar onMenuClick={() => setSidebarOpen(true)} />
      <div className="lg:ml-[220px] pt-14 transition-[margin] duration-200">
        <DataFreshnessBanner />
        <main>
          <div className="p-4 sm:p-6 max-w-[1400px] pb-20 lg:pb-6">
            <ErrorBoundary>{children}</ErrorBoundary>
          </div>
        </main>
      </div>
      <BottomNav />
    </div>
  );
}
